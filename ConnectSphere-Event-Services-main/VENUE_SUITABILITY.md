# Venue Suitability Check

Checks every active venue against an event request and flags it as
unsuitable when it is too small, lacks required accessibility features, or
doesn't support the required layout. The assigned Coordinator can override an
individual flag with a recorded reason. A venue with an un-overridden
unsuitable flag cannot go into a **Venue Booking Request**.

## Where it appears

| Page | What you see |
|---|---|
| **Event detail** (`/events/<id>`) | "Venue Suitability" panel: every venue's flags, **Override** buttons, override history, and **Request this venue** (opens the booking page pre-filled) |
| **Venue Booking** (`/venue-booking-request`) | A suitability box under each selected venue; **Submit** is disabled while a selected venue has an un-overridden unsuitable flag |
| **New Request** (`/events/new`) | Accessibility requirements checklist + layout suggestions |

## Setup

| Situation | Command |
|---|---|
| Fresh database | import `database/schema.sql` (already includes the new column and table) |
| Database built from this branch's schema before the feature | import `database/migrations/001_venue_suitability.sql` |
| Sample venues | `cd backend && python scripts/seed_venues.py` |

## Rules

| Check | Unsuitable when | Not verified when |
|---|---|---|
| Capacity | `venue.capacity < event.expected_attendance` (exact match is suitable) | expected attendance is missing (venue capacity is always required by the catalogue) |
| Accessibility | any code in `event.accessibility_requirements` is missing from the venue's features — each listed separately | — |
| Layout | required layout not among the venue's layouts | layout text not a recognised type, or the venue has no layouts recorded |

* Fixed vocabularies: `backend/app/venues/services/requirements.py`.
* **Venue data comes from the Venue Catalogue.** Layouts and accessibility
  features are whatever Venue Staff record on the Venue Catalogue page (free
  text). They are matched onto the fixed lists case-insensitively, including
  common wordings: "Ramp", "Lift" or "Wheelchair access" count as *Step-free
  access*, "Induction loop" as *Hearing loop*, "Disabled parking" as
  *Accessible parking*, and so on. A name that matches nothing (e.g. "Good
  acoustics") is not counted. For reliable results, Venue Staff should use the
  standard names: Step-free access, Hearing loop, Accessible toilet,
  Wheelchair seating, Accessible parking.
* Suitability is **calculated on every read**, never stored.
* An override covers **one flag on one event + venue**, stores a snapshot of the mismatch, and is cleared (kept in history) if the mismatch changes or disappears.
* "Not verified" and overridden flags never block a booking request.
* The Venue Catalogue's own `suitability.check_suitability()` (used to flag
  approved bookings when Venue Staff edit a venue, and by
  `GET /api/venues/<id>/suitability/<event_id>`) is a separate, advisory check
  and is unchanged.

## API

| Method | Path | Who |
|---|---|---|
| GET | `/api/venues/suitability-options` | any signed-in user |
| GET | `/api/events/<id>/venue-suitability` | Coordinator, Venue Staff, Tech Support |
| GET | `/api/events/<id>/venue-suitability/<venueId>` | same |
| GET | `/api/events/<id>/venue-suitability/overrides` | same |
| POST | `/api/events/<id>/venue-suitability/<venueId>/overrides` `{flagType, reason}` | assigned Coordinator |
| POST | `/api/venues/bookings` (existing) | now returns `field: "suitability"` errors for blocked venues |

## Code map

| File | Contents |
|---|---|
| `backend/app/venues/services/suitability_check.py` | the three checks, overrides, `blocking_flags` |
| `backend/app/venues/services/requirements.py` | fixed vocabularies + matching of catalogue names |
| `backend/app/venues/suitability_routes.py` | the API above |
| `backend/app/venues/services/booking_requests.py` | `_suitability_errors` — the booking gate |
| `backend/app/models/venue.py` | `VenueSuitabilityOverride` (layouts and accessibility features are the Venue Catalogue's) |
| `frontend/src/components/VenueSuitabilityPanel.vue` | event-page panel |
| `frontend/src/views/VenueBookingRequestView.vue` | suitability box + submit gate |

## Acceptance criteria → tests

`backend/tests/unit/test_venue_suitability.py`, one test per AC:

| Story | AC | Test |
|---|---|---|
| 1 Capacity | 1–6 | `TestStory1Capacity::test_ac1_…` … `test_ac6_…` |
| 2 Accessibility/layout | 1–6 | `TestStory2AccessibilityLayout::test_ac1_…` … `test_ac6_…` |
| 3 Override | 1–6 | `TestStory3Override::test_ac1_…` … `test_ac6_…` |

Supporting rules: `tests/unit/test_venue_suitability_rules.py`. HTTP + booking flow:
`tests/integration/test_venue_suitability_api.py`. These feature files are at 100%
line and branch coverage:

```
coverage run --branch --source=app -m pytest
coverage report -m --include="app/venues/services/suitability_check.py,app/venues/services/requirements.py,app/venues/suitability_routes.py,app/venues/services/booking_requests.py"
```

## Out of scope (by design)
Flagging oversized rooms, suggesting alternatives, per-layout capacity, approval
workflows or bulk overrides, notifications. Recording venue layouts and
accessibility features is the Venue Catalogue's job.
