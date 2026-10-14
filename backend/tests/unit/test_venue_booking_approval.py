"""
AC tests for Venue Staff reviewing pending booking requests.

"""
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app.common.time import utcnow
from app.extensions import db
from app.models.venue import Venue, VenueBooking

URL = "/api/venues/bookings/pending"


def when(days, hour=10):
    return datetime.combine(utcnow().date() + timedelta(days=days), time(hour, 0))


@pytest.fixture()
def context(client, organiser, make_user, make_event, auth_header):
    staff_id = make_user("approval-staff@test.com", ["venue_staff"])
    other_staff_id = make_user("approval-other@test.com", ["venue_staff"])
    coordinator_id = make_user("approval-coord@test.com", ["event_coordinator"])
    event_id = make_event(organiser, coordinator_id=coordinator_id)

    my_venue = Venue(name="Approval Test Hall", location="North Campus", capacity=300,
                     created_by=staff_id)
    other_venue = Venue(name="Other Staff Hall", location="South Campus", capacity=200,
                        created_by=other_staff_id)
    db.session.add_all([my_venue, other_venue])
    db.session.commit()

    return SimpleNamespace(
        staff_id=staff_id, other_staff_id=other_staff_id,
        coordinator_id=coordinator_id, event_id=event_id,
        my_venue_id=my_venue.id, other_venue_id=other_venue.id,
        staff_headers=auth_header("approval-staff@test.com"),
        other_headers=auth_header("approval-other@test.com"),
        coordinator_headers=auth_header("approval-coord@test.com"),
    )


def add_booking(ctx, *, venue_id=None, status="pending", days=30, hour=10):
    record = VenueBooking(
        event_id=ctx.event_id,
        venue_id=venue_id if venue_id is not None else ctx.my_venue_id,
        requested_by=ctx.coordinator_id,
        status=status,
        start_datetime=when(days, hour),
        end_datetime=when(days, hour) + timedelta(hours=2),
    )
    db.session.add(record)
    db.session.commit()
    return record.id


def get_queue(client, headers):
    return client.get(URL, headers=headers)


# AC1: Pending requests for venues managed by the logged-in staff member,
# including details needed to identify the event and venue.
def test_ac1_shows_my_pending_requests_with_event_details(client, context):
    booking_id = add_booking(context)
    response = get_queue(client, context.staff_headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 1
    item = payload[0]
    assert item["id"] == booking_id
    assert item["status"] == "pending"
    assert item["eventId"] == context.event_id
    assert item["venueId"] == context.my_venue_id
    assert item["venueName"] == "Approval Test Hall"
    assert item["venueLocation"] == "North Campus"
    assert item["eventName"]
    assert "eventDescription" in item
    assert "expectedAttendance" in item
    assert item["startDatetime"] == when(30).isoformat()
    assert item["endDatetime"] == (when(30) + timedelta(hours=2)).isoformat()


# AC2: Venue ownership isolation works in both directions.
def test_ac2_does_not_show_other_staff_venues(client, context):
    mine = add_booking(context, days=20)
    theirs = add_booking(context, venue_id=context.other_venue_id, days=21)

    mine_response = get_queue(client, context.staff_headers)
    other_response = get_queue(client, context.other_headers)

    assert mine_response.status_code == 200
    assert other_response.status_code == 200
    assert [b["id"] for b in mine_response.get_json()] == [mine]
    assert [b["id"] for b in other_response.get_json()] == [theirs]


# AC3: Exclude every non-pending status.
def test_ac3_excludes_approved_rejected_and_withdrawn(client, context):
    pending_id = add_booking(context, status="pending", days=25)
    for status in ("approved", "rejected", "withdrawn"):
        add_booking(context, status=status, days=26)

    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert [b["id"] for b in response.get_json()] == [pending_id]


# AC4: Empty list enables the frontend's explicit empty-state message.
def test_ac4_returns_empty_list_when_no_pending_requests(client, context):
    add_booking(context, status="approved")
    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert response.get_json() == []


# AC5: Sort by event start date/time, not insertion or submission order.
def test_ac5_orders_soonest_event_first(client, context):
    latest = add_booking(context, days=60)
    earliest = add_booking(context, days=10)
    middle = add_booking(context, days=30)

    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert [b["id"] for b in response.get_json()] == [earliest, middle, latest]


# Additional authorization tests for staff-only API.
def test_access_denied_to_event_coordinator(client, context):
    add_booking(context)
    response = get_queue(client, context.coordinator_headers)
    assert response.status_code == 403


def test_access_denied_without_login(client, context):
    response = client.get(URL)
    assert response.status_code in (401, 422)
