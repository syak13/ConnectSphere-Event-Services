"""
Venue Suitability Check
------------------------
Story 1 - Flag capacity mismatch as unsuitable
Story 2 - Flag accessibility or layout mismatch as unsuitable
Story 3 - Coordinator overrides a suitability flag

Suitability is never stored: it is recalculated from the current event and
venue data on every read, so any edit to expected attendance or requirements
is reflected the next time the check runs (Story 1 AC4). Only overrides are
persisted, together with a snapshot ("basis") of the mismatch they were
granted for, so a changed mismatch automatically clears them (Story 3 AC6).

Human judgement stays in charge: a flag never stops a Coordinator outright.
An unsuitable flag must be consciously overridden, with a recorded reason,
before that venue can go into a booking request (see booking_requests.py).

This is separate from suitability.check_suitability(), which the Venue
Catalogue uses to re-check approved bookings when Venue Staff edit a venue.
That function is left unchanged.
"""
from app.common.text_validation import validate_descriptive_text
from app.common.time import utcnow
from app.extensions import db
from app.models.venue import Venue, VenueSuitabilityOverride
from app.venues.services.requirements import (
    accessibility_label,
    layout_label,
    normalise_layout,
    venue_accessibility_codes,
    venue_layout_codes,
)

CAPACITY = "capacity"
ACCESSIBILITY = "accessibility"
LAYOUT = "layout"
FLAG_TYPES = (CAPACITY, ACCESSIBILITY, LAYOUT)
FLAG_TITLES = {CAPACITY: "Capacity", ACCESSIBILITY: "Accessibility", LAYOUT: "Layout"}

# check statuses
PASS = "pass"
UNSUITABLE = "unsuitable"
OVERRIDDEN = "overridden"
NOT_VERIFIED = "not_verified"

MIN_OVERRIDE_REASON_LENGTH = 10

# Events in these statuses are finished (or not yet visible to staff), so
# their flags can no longer be overridden.
NON_OVERRIDABLE_STATUSES = ("draft", "completed", "cancelled", "rejected")

DASH = "–"  # en dash, as in "Unsuitable – Capacity"


class SuitabilityError(ValueError):
    """Business-rule violation; routes map this to HTTP 400."""


# ---------------------------------------------------------------------
# Individual checks (pure functions — no DB access)
# ---------------------------------------------------------------------

def _check(flag_type, status, reasons=None, basis=None):
    return {"type": flag_type, "status": status, "reasons": reasons or [], "basis": basis}


def check_capacity(event, venue):
    """Story 1. Rule is strictly "capacity < expected attendance": an exact
    match is suitable (AC3)."""
    attendance = event.expected_attendance
    capacity = venue.capacity

    missing = []
    if attendance is None or attendance <= 0:
        missing.append("Expected attendance is not recorded for this event.")
    if capacity is None or capacity <= 0:
        missing.append("Capacity is not recorded for this venue.")
    if missing:
        return _check(CAPACITY, NOT_VERIFIED, missing)

    if capacity < attendance:
        return _check(
            CAPACITY,
            UNSUITABLE,
            [f"Capacity {capacity} is less than expected attendance {attendance}."],
            {"expectedAttendance": attendance, "venueCapacity": capacity},
        )
    return _check(CAPACITY, PASS)


def check_accessibility(event, venue):
    """Story 2. Every unmet requirement is listed individually (AC3); no
    requirements recorded means no flag (AC5)."""
    required = list(event.accessibility_requirements or [])
    if not required:
        return _check(ACCESSIBILITY, PASS)

    available = set(venue_accessibility_codes(venue))
    unmet = [code for code in required if code not in available]
    if not unmet:
        return _check(ACCESSIBILITY, PASS)

    reasons = [f"{accessibility_label(code)} required but not available." for code in unmet]
    return _check(ACCESSIBILITY, UNSUITABLE, reasons, {"unmet": sorted(unmet)})


def check_layout(event, venue):
    """Story 2. Compares the event's required layout with the layouts the
    venue supports, using the fixed LAYOUT_TYPES vocabulary."""
    raw = (event.required_layout or "").strip()
    if not raw:
        return _check(LAYOUT, PASS)

    required = normalise_layout(raw)
    if required is None:
        return _check(
            LAYOUT,
            NOT_VERIFIED,
            [f"Required layout '{raw}' is not a recognised layout type, so it cannot be checked automatically."],
        )

    supported = venue_layout_codes(venue)
    if not supported:
        return _check(LAYOUT, NOT_VERIFIED, ["No supported layouts are recorded for this venue."])

    if required in supported:
        return _check(LAYOUT, PASS)

    supported_labels = ", ".join(layout_label(c) for c in supported)
    return _check(
        LAYOUT,
        UNSUITABLE,
        [f"{layout_label(required)} layout required but this venue only supports: {supported_labels}."],
        {"requiredLayout": required, "venueLayouts": sorted(supported)},
    )


CHECKS = (check_capacity, check_accessibility, check_layout)


def run_checks(event, venue):
    """Raw check results keyed by flag type (basis included)."""
    return {r["type"]: r for r in (fn(event, venue) for fn in CHECKS)}


def _status_label(flag_type, status):
    title = FLAG_TITLES[flag_type]
    return {
        PASS: "Meets requirement",
        UNSUITABLE: f"Unsuitable {DASH} {title}",
        OVERRIDDEN: f"Overridden {DASH} {title}",
        NOT_VERIFIED: f"{title} not verified",
    }[status]


def evaluate(event, venue, active_overrides=None):
    """Runs all checks for one event/venue pair and applies any active
    overrides whose basis still matches the current mismatch. Pure: does not
    touch the database. `active_overrides` is {flag_type: override}."""
    active_overrides = active_overrides or {}
    checks = []
    for result in run_checks(event, venue).values():
        override = active_overrides.get(result["type"])
        if result["status"] == UNSUITABLE and override is not None and override.basis == result["basis"]:
            result["status"] = OVERRIDDEN
            result["override"] = override.to_dict()
        else:
            result["override"] = None
        result["title"] = FLAG_TITLES[result["type"]]
        result["statusLabel"] = _status_label(result["type"], result["status"])
        result["canOverride"] = result["status"] == UNSUITABLE
        checks.append(result)

    statuses = {c["status"] for c in checks}
    if UNSUITABLE in statuses:
        overall, overall_label = UNSUITABLE, "Unsuitable"
    elif NOT_VERIFIED in statuses:
        overall, overall_label = NOT_VERIFIED, "Not verified"
    elif OVERRIDDEN in statuses:
        overall, overall_label = OVERRIDDEN, "Suitable (overridden)"
    else:
        overall, overall_label = PASS, "Suitable"

    for c in checks:
        c.pop("basis", None)  # internal only

    return {
        "venue": venue.to_dict(),
        "overallStatus": overall,
        "overallLabel": overall_label,
        "checks": checks,
        "flags": [c for c in checks if c["status"] != PASS],
        "isBlocked": overall == UNSUITABLE,
    }


# ---------------------------------------------------------------------
# Persistence-aware helpers
# ---------------------------------------------------------------------

def _active_overrides(event_id, venue_id):
    return VenueSuitabilityOverride.query.filter_by(event_id=event_id, venue_id=venue_id, cleared_at=None).all()


def sync_overrides(event, venue):
    """Clears any active override whose flag has disappeared or whose
    mismatch has changed since it was granted (Story 3 AC6). Returns the
    still-valid overrides keyed by flag type."""
    current = run_checks(event, venue)
    still_valid, changed = {}, False
    for override in _active_overrides(event.id, venue.id):
        check = current[override.flag_type]
        if check["status"] != UNSUITABLE:
            override.cleared_at = utcnow()
            override.cleared_reason = "Mismatch no longer applies after event or venue details changed"
            changed = True
        elif check["basis"] != override.basis:
            override.cleared_at = utcnow()
            override.cleared_reason = "Event or venue details changed, creating a different mismatch"
            changed = True
        else:
            still_valid[override.flag_type] = override
    if changed:
        db.session.commit()
    return still_valid


def evaluate_venue(event, venue):
    return evaluate(event, venue, sync_overrides(event, venue))


def list_suitability(event):
    """Every ACTIVE venue checked against the event, best options first."""
    venues = Venue.query.filter(Venue.is_active.is_(True)).order_by(Venue.name.asc()).all()
    results = [evaluate_venue(event, v) for v in venues]
    rank = {PASS: 0, OVERRIDDEN: 1, NOT_VERIFIED: 2, UNSUITABLE: 3}
    results.sort(key=lambda r: (rank[r["overallStatus"]], r["venue"]["name"].lower()))
    return results


def blocking_flags(event, venue):
    """Unsuitable flags that have NOT been overridden — the ones that stop
    this venue going into a booking request (Story 1 AC6, Story 3 AC5)."""
    return [f for f in evaluate_venue(event, venue)["flags"] if f["status"] == UNSUITABLE]


def override_history(event):
    rows = (
        VenueSuitabilityOverride.query.filter_by(event_id=event.id)
        .order_by(VenueSuitabilityOverride.created_at.desc(), VenueSuitabilityOverride.id.desc())
        .all()
    )
    return [r.to_dict() for r in rows]


def event_requirements(event):
    """The requirements the checks run against, for display above the list."""
    layout_code = normalise_layout(event.required_layout)
    return {
        "expectedAttendance": event.expected_attendance,
        "requiredLayout": event.required_layout,
        "requiredLayoutCode": layout_code,
        "requiredLayoutLabel": layout_label(layout_code) if layout_code else None,
        "accessibilityRequirements": [
            {"code": c, "label": accessibility_label(c)} for c in (event.accessibility_requirements or [])
        ],
        "accessibilityNotes": event.accessibility_needs,
    }


# ---------------------------------------------------------------------
# Story 3 - override a single flag
# ---------------------------------------------------------------------

def _require_assigned_coordinator(event, user):
    if not user or not user.has_role("event_coordinator"):
        raise PermissionError("Only an Event Coordinator can do this")
    if event.coordinator_id != user.id:
        raise PermissionError("Only the assigned Coordinator can do this for this event")


def validate_override_reason(reason):
    text = (reason or "").strip()
    if len(text) < MIN_OVERRIDE_REASON_LENGTH:
        raise SuitabilityError(
            f"An override reason of at least {MIN_OVERRIDE_REASON_LENGTH} characters is required"
        )
    validate_descriptive_text(text, "override reason")
    return text


def override_flag(event, venue, user, flag_type, reason):
    _require_assigned_coordinator(event, user)
    if event.status in NON_OVERRIDABLE_STATUSES:
        raise SuitabilityError(f"Flags cannot be overridden while the event is {event.status}")
    if flag_type not in FLAG_TYPES:
        raise SuitabilityError(f"flagType must be one of: {', '.join(FLAG_TYPES)}")

    text = validate_override_reason(reason)

    active = sync_overrides(event, venue)
    if flag_type in active:
        raise SuitabilityError(f"The {FLAG_TITLES[flag_type].lower()} flag is already overridden for this venue")

    check = run_checks(event, venue)[flag_type]
    if check["status"] != UNSUITABLE:
        raise SuitabilityError(
            f"There is no active {FLAG_TITLES[flag_type].lower()} flag on this venue to override"
        )

    override = VenueSuitabilityOverride(
        event_id=event.id,
        venue_id=venue.id,
        flag_type=flag_type,
        reason=text,
        basis=check["basis"],
        overridden_by=user.id,
    )
    db.session.add(override)
    db.session.commit()
    return override
