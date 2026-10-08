import re
from datetime import date, datetime, time

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.auth.decorators import roles_required
from app.models.event import Event
from app.models.user import User
from app.models.venue import Venue, VenueBooking
from app.venues.services import availability, booking, booking_requests, catalogue, search, suitability
from app.venues.services.booking_requests import BookingRequestError

venues_bp = Blueprint("venues", __name__)


def _current_user():
    return User.query.get(int(get_jwt_identity()))


# ---------------------------------------------------------------------
# Venue Catalogue
# ---------------------------------------------------------------------

@venues_bp.post("")
@roles_required("venue_staff")
def create_venue():
    user = _current_user()
    try:
        venue = catalogue.create_venue(user.id, request.get_json() or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(venue.to_dict()), 201


@venues_bp.get("")
@jwt_required()
def list_venues():
    return jsonify([v.to_dict() for v in catalogue.list_venues()]), 200


@venues_bp.get("/<int:venue_id>")
@jwt_required()
def get_venue(venue_id):
    venue = catalogue.get_venue(venue_id)
    if not venue:
        return jsonify({"error": "Venue not found"}), 404
    return jsonify(venue.to_dict()), 200


@venues_bp.put("/<int:venue_id>")
@roles_required("venue_staff")
def update_venue(venue_id):
    venue = catalogue.get_venue(venue_id)
    if not venue:
        return jsonify({"error": "Venue not found"}), 404
    venue, flags = catalogue.update_venue(venue, request.get_json() or {})
    return jsonify({
        "venue": venue.to_dict(),
        "flagsRaised": [f.to_dict() for f in flags],
    }), 200


@venues_bp.delete("/<int:venue_id>")
@roles_required("venue_staff")
def deactivate_venue(venue_id):
    venue = catalogue.get_venue(venue_id)
    if not venue:
        return jsonify({"error": "Venue not found"}), 404
    try:
        catalogue.deactivate_venue(venue)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return "", 204


# ---------------------------------------------------------------------
# Venue Availability Calendar
# ---------------------------------------------------------------------

@venues_bp.get("/<int:venue_id>/calendar")
@jwt_required()
def get_calendar(venue_id):
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "start and end query params (ISO datetimes) are required"}), 400
    calendar = availability.get_calendar(venue_id, datetime.fromisoformat(start), datetime.fromisoformat(end))
    return jsonify(calendar), 200


@venues_bp.get("/calendar")
@jwt_required()
def get_combined_calendar():
    """Combined (all-venues) view -- the other half of the per-venue vs.
    combined toggle, paired with GET /<venue_id>/calendar above."""
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "start and end query params (ISO datetimes) are required"}), 400
    calendar = availability.get_combined_calendar(datetime.fromisoformat(start), datetime.fromisoformat(end))
    return jsonify(calendar), 200


@venues_bp.post("/<int:venue_id>/unavailability")
@roles_required("venue_staff")
def add_unavailability(venue_id):
    venue = catalogue.get_venue(venue_id)
    if not venue:
        return jsonify({"error": "Venue not found"}), 404
    user = _current_user()
    data = request.get_json() or {}
    try:
        block, flags = availability.add_unavailability(
            venue,
            user.id,
            datetime.fromisoformat(data.get("start")),
            datetime.fromisoformat(data.get("end")),
            data.get("reason"),
        )
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({
        "unavailability": block.to_dict(),
        "flagsRaised": [f.to_dict() for f in flags],
    }), 201


@venues_bp.get("/flags/mine")
@roles_required("event_coordinator")
def my_availability_flags():
    """Coordinator views unresolved availability-change flags for events
    assigned to them."""
    user = _current_user()
    flags = availability.list_unresolved_flags_for_coordinator(user.id)
    return jsonify([f.to_dict() for f in flags]), 200


@venues_bp.post("/flags/<int:flag_id>/resolve")
@roles_required("event_coordinator")
def resolve_availability_flag(flag_id):
    from app.models.venue import VenueAvailabilityFlag

    flag = VenueAvailabilityFlag.query.get(flag_id)
    if not flag:
        return jsonify({"error": "Flag not found"}), 404
    flag = availability.resolve_flag(flag)
    return jsonify(flag.to_dict()), 200


# ---------------------------------------------------------------------
# Venue Search and Filtering / Venue Suitability Checking
# ---------------------------------------------------------------------

@venues_bp.get("/search")
@roles_required("event_coordinator")
def search_venues():
    args = request.args
    errors = {}

    date_text = args.get("date", "").strip()
    start_text = args.get("start_time", "").strip()
    end_text = args.get("end_time", "").strip()
    attendance_text = args.get("attendance", "").strip()

    event_date = None
    if not date_text:
        errors["date"] = "Date is required."
    else:
        try:
            event_date = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            errors["date"] = "Enter a valid date."

    parsed_times = {}
    for field, value in (("start_time", start_text), ("end_time", end_text)):
        if not value:
            errors[field] = f"{field.replace('_', ' ').capitalize()} is required."
            continue
        try:
            parsed_times[field] = datetime.strptime(value, "%H:%M").time()
        except ValueError:
            errors[field] = "Enter a valid time."

    attendance = None
    if not attendance_text:
        errors["attendance"] = "Expected attendance is required."
    elif not re.fullmatch(r"[0-9]+", attendance_text):
        errors["attendance"] = "Enter a positive whole number."
    else:
        try:
            attendance = int(attendance_text)
        except ValueError:
            errors["attendance"] = "Enter a positive whole number."
        else:
            if attendance < 1:
                errors["attendance"] = "Enter a positive whole number."

    if (
        "start_time" not in errors
        and "end_time" not in errors
        and parsed_times["end_time"] <= parsed_times["start_time"]
    ):
        errors["end_time"] = "End time must be after start time."

    if errors:
        return jsonify({"errors": errors}), 400

    results = search.search_venues(
        date=event_date,
        start_time=parsed_times["start_time"],
        end_time=parsed_times["end_time"],
        expected_attendance=attendance,
        # location=args.get("location"),
        # accessibility_needs=args.getlist("accessibility"),
        # required_facilities=args.getlist("facilities"),
        # required_layout=args.get("layout"),
    )
    return jsonify([v.to_dict() for v in results]), 200


@venues_bp.get("/<int:venue_id>/suitability/<int:event_id>")
@roles_required("event_coordinator")
def check_suitability(venue_id, event_id):
    venue = catalogue.get_venue(venue_id)
    event = Event.query.get(event_id)
    if not venue or not event:
        return jsonify({"error": "Venue or event not found"}), 404
    flags = suitability.check_suitability(event, venue)
    return jsonify({"suitable": len(flags) == 0, "flags": flags}), 200


# ---------------------------------------------------------------------
# Venue Booking Request / Venue Booking Approval / Booking Conflict Detection
# ---------------------------------------------------------------------

_DATE_TIME_FIELDS = (
    # (json key, parsed key, parser, human label)
    ("date", "date", date.fromisoformat, "event date"),
    ("endDate", "end_date", date.fromisoformat, "end date"),
    ("startTime", "start_time", time.fromisoformat, "start time"),
    ("endTime", "end_time", time.fromisoformat, "end time"),
)
 
 
def _parse_venue_request(raw, index):
    """Turn one venue's JSON into the dict the service expects.
    Returns (parsed, errors); errors are for values that are present but
    not valid ISO dates/times (missing values are reported by the service)."""
    if not isinstance(raw, dict):
        return {}, [{
            "venue_id": None,
            "venue": f"Venue {index}",
            "field": "venue",
            "message": f"Venue {index}: invalid venue entry",
        }]
 
    parsed = {
    "venue_id": raw.get("venueId"),
    }
    
    errors = []
    for json_key, field, parser, label in _DATE_TIME_FIELDS:
        value = raw.get(json_key)
        if value in (None, ""):
            parsed[field] = None
            continue
        try:
            parsed[field] = parser(value)
        except (ValueError, TypeError):
            parsed[field] = None
            errors.append({
                "venue_id": raw.get("venueId"),
                "venue": f"Venue {index}",
                "field": field,
                "message": f"Venue {index}: {label} is not a valid value",
            })
    return parsed, errors

@venues_bp.post("/bookings")
@roles_required("event_coordinator")
def submit_booking():
    """One request, one or more venues, each with its own timing/requirements.
 
    Body:
    {
      "eventId": 5,
      "venues": [
        {"venueId": 10, "date": "2026-11-01", "startTime": "20:00",
         "endTime": "02:00", "endDate": "2026-11-02",
         "label": "Main hall", "equipment": "Projector",
         "catering": null, "otherRequirements": null}
      ]
    }
    """
    user = _current_user()
    data = request.get_json() or {}
    event = Event.query.get(data.get("eventId"))
    if not event:
        return jsonify({"error": "Event not found"}), 404
    if event.coordinator_id != user.id:
        return jsonify({"error": "Only the assigned Coordinator can request a venue for this event"}), 403
 
    raw_venues = data.get("venues")
    if not isinstance(raw_venues, list):
        raw_venues = []
 
    venue_requests, parse_errors = [], []
    for index, raw in enumerate(raw_venues, start=1):
        parsed, errors = _parse_venue_request(raw, index)
        venue_requests.append(parsed)
        parse_errors.extend(errors)
    if parse_errors:
        return jsonify({"error": "Booking request could not be submitted", "errors": parse_errors}), 400
 
    try:
        results = booking_requests.submit_booking_requests(event, venue_requests, user.id)
    except BookingRequestError as e:
        return jsonify({"error": "Booking request could not be submitted", "errors": e.errors}), 400
    return jsonify([b.to_dict() for b in results]), 201


@venues_bp.get("/events/<int:event_id>/bookings")
@jwt_required()
def list_event_bookings(event_id):
    """Week 7 change #3: an event can have several venue bookings (e.g. a
    main auditorium plus breakout rooms) -- this lists all of them,
    independent of their individual statuses, so the UI can show the full
    multi-venue picture for one event."""
    event = Event.query.get(event_id)
    if not event:
        return jsonify({"error": "Event not found"}), 404
    bookings = VenueBooking.query.filter_by(event_id=event_id).order_by(VenueBooking.created_at.asc()).all()
    return jsonify([b.to_dict() for b in bookings]), 200


@venues_bp.post("/bookings/<int:booking_id>/withdraw")
@roles_required("event_coordinator")
def withdraw_booking(booking_id):
    user = _current_user()
    record = VenueBooking.query.get(booking_id)
    if not record:
        return jsonify({"error": "Booking not found"}), 404
    try:
        result = booking.withdraw_booking_request(record, user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result.to_dict()), 200


@venues_bp.get("/bookings/pending")
@roles_required("venue_staff")
def list_pending_bookings():
    pending = VenueBooking.query.filter_by(status="pending").order_by(VenueBooking.created_at.asc()).all()
    return jsonify([b.to_dict() for b in pending]), 200


@venues_bp.post("/bookings/<int:booking_id>/approve")
@roles_required("venue_staff")
def approve_booking(booking_id):
    user = _current_user()
    record = VenueBooking.query.get(booking_id)
    if not record:
        return jsonify({"error": "Booking not found"}), 404
    try:
        result = booking.approve_booking(record, user.id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result.to_dict()), 200


@venues_bp.post("/bookings/<int:booking_id>/reject")
@roles_required("venue_staff")
def reject_booking(booking_id):
    user = _current_user()
    record = VenueBooking.query.get(booking_id)
    if not record:
        return jsonify({"error": "Booking not found"}), 404
    data = request.get_json() or {}
    try:
        result = booking.reject_booking(record, user.id, data.get("reason"))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(result.to_dict()), 200
