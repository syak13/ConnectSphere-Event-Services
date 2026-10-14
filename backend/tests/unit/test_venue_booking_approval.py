"""AC tests for Venue Staff reviewing pending booking requests and approving them."""
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


# STORY 1: Venue Staff review pending booking requests

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


def test_ac2_does_not_show_other_staff_venues(client, context):
    mine = add_booking(context, days=20)
    theirs = add_booking(context, venue_id=context.other_venue_id, days=21)

    mine_response = get_queue(client, context.staff_headers)
    other_response = get_queue(client, context.other_headers)

    assert mine_response.status_code == 200
    assert other_response.status_code == 200
    assert [b["id"] for b in mine_response.get_json()] == [mine]
    assert [b["id"] for b in other_response.get_json()] == [theirs]


def test_ac3_excludes_approved_rejected_and_withdrawn(client, context):
    pending_id = add_booking(context, status="pending", days=25)
    for status in ("approved", "rejected", "withdrawn"):
        add_booking(context, status=status, days=26)

    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert [b["id"] for b in response.get_json()] == [pending_id]


def test_ac4_returns_empty_list_when_no_pending_requests(client, context):
    add_booking(context, status="approved")
    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert response.get_json() == []


def test_ac5_orders_soonest_event_first(client, context):
    latest = add_booking(context, days=60)
    earliest = add_booking(context, days=10)
    middle = add_booking(context, days=30)

    response = get_queue(client, context.staff_headers)
    assert response.status_code == 200
    assert [b["id"] for b in response.get_json()] == [earliest, middle, latest]


def test_access_denied_to_event_coordinator(client, context):
    add_booking(context)
    response = get_queue(client, context.coordinator_headers)
    assert response.status_code == 403


def test_access_denied_without_login(client, context):
    response = client.get(URL)
    assert response.status_code in (401, 422)


# STORY 2: Venue Staff approve a booking request

def at(days, hour=10, minute=0):
    return datetime.combine(utcnow().date() + timedelta(days=days), time(hour, minute))


@pytest.fixture()
def approve_context(client, organiser, make_user, make_event, auth_header):
    staff = make_user('approve-staff@test.com', ['venue_staff'])
    other_staff = make_user('approve-other@test.com', ['venue_staff'])
    coordinator = make_user('approve-coordinator@test.com', ['event_coordinator'])
    other_coordinator = make_user('approve-coordinator2@test.com', ['event_coordinator'])
    event = make_event(organiser, coordinator_id=coordinator)
    other_event = make_event(organiser, coordinator_id=other_coordinator)
    venue = Venue(name='Approval Hall', location='Campus', capacity=200, created_by=staff)
    other_venue = Venue(name='Other Hall', location='Elsewhere', capacity=200, created_by=other_staff)
    db.session.add_all([venue, other_venue])
    db.session.commit()
    return SimpleNamespace(
        staff=staff, other_staff=other_staff, coordinator=coordinator,
        event=event, other_event=other_event, venue=venue.id, other_venue=other_venue.id,
        staff_headers=auth_header('approve-staff@test.com'),
        other_staff_headers=auth_header('approve-other@test.com'),
        coordinator_headers=auth_header('approve-coordinator@test.com'),
        other_coordinator_headers=auth_header('approve-coordinator2@test.com'),
    )


def add_approval_booking(ctx, *, start=None, end=None, status='pending', event=None, venue=None):
    start = start or at(30)
    end = end or start + timedelta(hours=2)
    booking = VenueBooking(
        event_id=event or ctx.event, venue_id=venue or ctx.venue,
        requested_by=ctx.coordinator, status=status,
        start_datetime=start, end_datetime=end,
    )
    db.session.add(booking)
    db.session.commit()
    return booking.id


def approve_request(client, ctx, booking_id, headers=None):
    return client.post(f'/api/venues/bookings/{booking_id}/approve',
                       headers=headers or ctx.staff_headers)


def get_approval_calendar(client, ctx, start, end):
    return client.get(f'/api/venues/{ctx.venue}/calendar',
                      query_string={'start': start.isoformat(), 'end': end.isoformat()},
                      headers=ctx.staff_headers)


# AC1: Approval changes status, records decision, and appears on calendar.
def test_approve_ac1_approve_pending_and_update_calendar(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = approve_request(client, approve_context, booking_id)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'approved'
    db.session.expire_all()
    saved = db.session.get(VenueBooking, booking_id)
    assert saved.status == 'approved'
    assert saved.decided_by == approve_context.staff
    assert saved.decided_at is not None
    result = get_approval_calendar(client, approve_context, at(29), at(31))
    assert result.status_code == 200
    assert booking_id in [b['id'] for b in result.get_json()['confirmedBookings']]


# AC2: Only the event's coordinator receives the in-app confirmation.
def test_approve_ac2_coordinator_receives_confirmation_notice(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    assert approve_request(client, approve_context, booking_id).status_code == 200
    response = client.get('/api/venues/bookings/confirmation-notices',
                          headers=approve_context.coordinator_headers)
    assert response.status_code == 200
    notices = response.get_json()
    notice = next(n for n in notices if n['bookingId'] == booking_id)
    assert notice['eventId'] == approve_context.event
    assert 'Approval Hall' in notice['message']
    assert notice['confirmedAt'] is not None
    other = client.get('/api/venues/bookings/confirmation-notices',
                       headers=approve_context.other_coordinator_headers)
    assert other.status_code == 200
    assert booking_id not in [n['bookingId'] for n in other.get_json()]


# AC3: Calendar includes correct event and original datetimes, including overnight.
def test_approve_ac3_calendar_displays_overnight_booking(client, approve_context):
    start = at(30, 22)
    end = start + timedelta(hours=4)  # next day, 02:00
    booking_id = add_approval_booking(approve_context, start=start, end=end)
    assert approve_request(client, approve_context, booking_id).status_code == 200
    response = get_approval_calendar(client, approve_context, at(31, 0), at(31, 12))
    assert response.status_code == 200
    item = next(b for b in response.get_json()['confirmedBookings'] if b['id'] == booking_id)
    assert item['eventId'] == approve_context.event
    assert item['eventName']
    assert item['startDatetime'] == start.isoformat()
    assert item['endDatetime'] == end.isoformat()
    assert end.date() > start.date()


# AC4: An approved booking overlapping the requested window blocks approval.
def test_approve_ac4_overlapping_approved_booking_is_identified(client, approve_context):
    existing_id = add_approval_booking(approve_context, start=at(30, 10), end=at(30, 12), status='approved', event=approve_context.other_event)
    candidate_id = add_approval_booking(approve_context, start=at(30, 11), end=at(30, 13))
    response = approve_request(client, approve_context, candidate_id)
    assert response.status_code == 409
    assert str(existing_id) in response.get_json()['error']
    assert 'conflict' in response.get_json()['error'].lower()
    db.session.expire_all()
    assert db.session.get(VenueBooking, candidate_id).status == 'pending'


# AC4: Adjacent bookings are allowed when there is no setup/turnaround padding.
def test_approve_ac4_back_to_back_bookings_do_not_overlap(client, approve_context):
    add_approval_booking(approve_context, start=at(30, 10), end=at(30, 12), status='approved', event=approve_context.other_event)
    candidate_id = add_approval_booking(approve_context, start=at(30, 12), end=at(30, 14))
    response = approve_request(client, approve_context, candidate_id)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'approved'


# AC5: A second approval after another decision cannot overwrite it.
@pytest.mark.parametrize('decided_status', ['approved', 'rejected'])
def test_approve_ac5_already_decided_request_cannot_be_approved(client, approve_context, decided_status):
    booking_id = add_approval_booking(approve_context, status=decided_status)
    response = approve_request(client, approve_context, booking_id)
    assert response.status_code == 409
    assert 'already been decided' in response.get_json()['error'].lower()
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == decided_status


# Security: staff cannot approve venues owned by another staff member.
def test_approve_staff_cannot_approve_another_staff_venue(client, approve_context):
    booking_id = add_approval_booking(approve_context, venue=approve_context.other_venue)
    response = approve_request(client, approve_context, booking_id)
    assert response.status_code == 403
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == 'pending'


# Security: coordinator cannot use staff approval endpoint.
def test_approve_coordinator_cannot_approve(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = approve_request(client, approve_context, booking_id, headers=approve_context.coordinator_headers)
    assert response.status_code == 403


def test_approve_unauthenticated_cannot_approve(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = client.post(f'/api/venues/bookings/{booking_id}/approve')
    assert response.status_code in (401, 422)


def test_approve_missing_booking_returns_404(client, approve_context):
    response = approve_request(client, approve_context, 99999999)
    assert response.status_code == 404

# STORY 3: Venue Staff reject a booking request (optional reason/suggestion)

def reject_request(client, ctx, booking_id, payload=None, headers=None):
    return client.post(
        f'/api/venues/bookings/{booking_id}/reject',
        json={} if payload is None else payload,
        headers=headers if headers is not None else ctx.staff_headers,
    )


def rejection_notices(client, ctx, headers=None):
    return client.get(
        '/api/venues/bookings/rejection-notices',
        headers=headers if headers is not None else ctx.coordinator_headers,
    )


# AC1: Both optional fields can be omitted, and coordinator is notified.
def test_reject_ac1_without_reason_or_alternative(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id)
    assert response.status_code == 200
    assert response.get_json()['status'] == 'rejected'
    db.session.expire_all()
    saved = db.session.get(VenueBooking, booking_id)
    assert saved.status == 'rejected'
    assert saved.decided_by == approve_context.staff
    assert saved.decided_at is not None
    assert saved.decision_reason is None
    assert saved.alternative_suggestion is None
    notice_response = rejection_notices(client, approve_context)
    assert notice_response.status_code == 200
    notice = next(n for n in notice_response.get_json() if n['bookingId'] == booking_id)
    assert notice['reason'] is None
    assert notice['alternativeSuggestion'] is None
    assert notice['rejectedAt'] is not None


# AC1: Explicitly blank strings are accepted too.
def test_reject_ac1_blank_fields_are_accepted(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id,
                              {'reason': '', 'alternativeSuggestion': '   '})
    assert response.status_code == 200
    db.session.expire_all()
    saved = db.session.get(VenueBooking, booking_id)
    assert saved.decision_reason is None
    assert saved.alternative_suggestion is None


# AC2: Reason is saved and visible in both request details and notification.
def test_reject_ac2_reason_visible_to_coordinator(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    reason = 'Venue is undergoing maintenance.'
    response = reject_request(client, approve_context, booking_id, {'reason': reason})
    assert response.status_code == 200
    assert response.get_json()['decisionReason'] == reason
    requests_response = client.get('/api/venues/bookings/my',
                                   headers=approve_context.coordinator_headers)
    assert requests_response.status_code == 200
    item = next(b for b in requests_response.get_json() if b['id'] == booking_id)
    assert item['status'] == 'rejected'
    assert item['decisionReason'] == reason
    notice = next(n for n in rejection_notices(client, approve_context).get_json()
                  if n['bookingId'] == booking_id)
    assert notice['reason'] == reason


# AC3: Alternative suggestion is saved and visible with the rejection.
def test_reject_ac3_alternative_visible_to_coordinator(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    suggestion = 'Try the other hall on Friday.'
    response = reject_request(client, approve_context, booking_id,
                              {'alternativeSuggestion': suggestion})
    assert response.status_code == 200
    assert response.get_json()['alternativeSuggestion'] == suggestion
    requests_response = client.get('/api/venues/bookings/my',
                                   headers=approve_context.coordinator_headers)
    item = next(b for b in requests_response.get_json() if b['id'] == booking_id)
    assert item['status'] == 'rejected'
    assert item['alternativeSuggestion'] == suggestion
    notice = next(n for n in rejection_notices(client, approve_context).get_json()
                  if n['bookingId'] == booking_id)
    assert notice['alternativeSuggestion'] == suggestion


# AC3: Both reason and alternative can be submitted together.
def test_reject_ac3_reason_and_alternative_together(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    payload = {'reason': 'Not available.', 'alternativeSuggestion': 'Try next Tuesday.'}
    response = reject_request(client, approve_context, booking_id, payload)
    assert response.status_code == 200
    assert response.get_json()['decisionReason'] == payload['reason']
    assert response.get_json()['alternativeSuggestion'] == payload['alternativeSuggestion']
    notice = next(n for n in rejection_notices(client, approve_context).get_json()
                  if n['bookingId'] == booking_id)
    assert notice['reason'] == payload['reason']
    assert notice['alternativeSuggestion'] == payload['alternativeSuggestion']


# AC4: Rejected booking is excluded from confirmed calendar.
def test_reject_ac4_not_shown_in_confirmed_calendar(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    approved_id = add_approval_booking(approve_context, start=at(31), end=at(31, 12), status='approved')
    assert reject_request(client, approve_context, booking_id).status_code == 200
    response = get_approval_calendar(client, approve_context, at(29), at(33))
    assert response.status_code == 200
    ids = [b['id'] for b in response.get_json()['confirmedBookings']]
    assert booking_id not in ids
    assert approved_id in ids


# AC5: Each text field has a maximum of 500 characters.
@pytest.mark.parametrize('field', ['reason', 'alternativeSuggestion'])
def test_reject_ac5_more_than_500_characters_blocked(client, approve_context, field):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id, {field: 'x' * 501})
    assert response.status_code == 400
    assert '500' in response.get_json()['error']
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == 'pending'


@pytest.mark.parametrize('field', ['reason', 'alternativeSuggestion'])
def test_reject_ac5_exactly_500_characters_accepted(client, approve_context, field):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id, {field: 'x' * 500})
    assert response.status_code == 200
    assert response.get_json()['status'] == 'rejected'


# Security and error handling.
def test_reject_staff_cannot_reject_another_staff_venue(client, approve_context):
    booking_id = add_approval_booking(approve_context, venue=approve_context.other_venue)
    response = reject_request(client, approve_context, booking_id)
    assert response.status_code == 403
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == 'pending'


@pytest.mark.parametrize('status', ['approved', 'rejected', 'withdrawn'])
def test_reject_already_decided_request_returns_conflict(client, approve_context, status):
    booking_id = add_approval_booking(approve_context, status=status)
    response = reject_request(client, approve_context, booking_id)
    assert response.status_code == 409
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == status


def test_reject_second_decision_cannot_overwrite_first(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    assert reject_request(client, approve_context, booking_id,
                          {'reason': 'First decision'}).status_code == 200
    response = reject_request(client, approve_context, booking_id,
                              {'reason': 'Second decision'})
    assert response.status_code == 409
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).decision_reason == 'First decision'


def test_reject_coordinator_cannot_reject(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id,
                              headers=approve_context.coordinator_headers)
    assert response.status_code == 403


def test_reject_unauthenticated_cannot_reject(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    response = client.post(f'/api/venues/bookings/{booking_id}/reject', json={})
    assert response.status_code in (401, 422)


def test_reject_missing_booking_returns_404(client, approve_context):
    response = reject_request(client, approve_context, 99999999)
    assert response.status_code == 404


@pytest.mark.parametrize('field', ['reason', 'alternativeSuggestion'])
def test_reject_non_text_field_returns_400(client, approve_context, field):
    booking_id = add_approval_booking(approve_context)
    response = reject_request(client, approve_context, booking_id, {field: 123})
    assert response.status_code == 400
    db.session.expire_all()
    assert db.session.get(VenueBooking, booking_id).status == 'pending'


def test_reject_notices_are_private_to_requesting_coordinator(client, approve_context):
    booking_id = add_approval_booking(approve_context)
    assert reject_request(client, approve_context, booking_id).status_code == 200
    other_response = rejection_notices(client, approve_context,
                                       headers=approve_context.other_coordinator_headers)
    assert other_response.status_code == 200
    assert booking_id not in [n['bookingId'] for n in other_response.get_json()]
