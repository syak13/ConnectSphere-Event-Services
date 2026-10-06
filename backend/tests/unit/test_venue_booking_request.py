from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from app.common.time import utcnow
from app.extensions import db
from app.models.venue import Venue, VenueBooking


BASE = "/api/venues"
TODAY = utcnow().date()


def day(offset):
    return TODAY + timedelta(days=offset)


def at(d, hour):
    return datetime.combine(d, time(hour, 0))


# --------------------------------------------------------------------------
# Fixtures and helpers
# --------------------------------------------------------------------------

@pytest.fixture()
def make_venue(app):
    def _make(name):
        venue = Venue(
            name=name,
            location="Test Location",
            capacity=100,
        )
        db.session.add(venue)
        db.session.commit()
        return venue.id

    return _make


@pytest.fixture()
def ctx(client, organiser, make_user, make_event, make_venue, auth_header):
    coord_id = make_user(
        "coord@test.com",
        ["event_coordinator"],
    )

    make_user(
        "staff@test.com",
        ["venue_staff"],
    )

    return SimpleNamespace(
        coord_id=coord_id,
        coord=auth_header("coord@test.com"),
        staff=auth_header("staff@test.com"),
        event_id=make_event(
            organiser,
            coordinator_id=coord_id,
        ),
        hall_a=make_venue("Hall A"),
        hall_b=make_venue("Hall B"),
    )


def entry(venue_id, **overrides):
    """One venue's booking request JSON."""

    data = {
        "venueId": venue_id,
        "date": day(30).isoformat(),
        "startTime": "10:00",
        "endTime": "12:00",
    }

    data.update(overrides)
    return data


def submit(client, ctx, venues):
    return client.post(
        f"{BASE}/bookings",
        json={
            "eventId": ctx.event_id,
            "venues": venues,
        },
        headers=ctx.coord,
    )


def all_bookings():
    # Read what the API committed.
    db.session.rollback()

    return VenueBooking.query.order_by(
        VenueBooking.id
    ).all()


def add_booking(ctx, venue_id, status):
    db.session.add(
        VenueBooking(
            event_id=ctx.event_id,
            venue_id=venue_id,
            status=status,
            requested_by=ctx.coord_id,
            start_datetime=at(day(30), 10),
            end_datetime=at(day(30), 12),
        )
    )

    db.session.commit()


def error_pairs(res):
    return {
        (e["venue"], e["field"])
        for e in res.get_json()["errors"]
    }


# --------------------------------------------------------------------------
# AC1:
# One request can contain several venues.
# Each venue has its own timing and creates its own pending booking.
# --------------------------------------------------------------------------

def test_ac1_request_with_several_venues_creates_a_linked_pending_booking_per_venue(
    client,
    ctx,
):
    d1 = day(30)
    d2 = day(31)

    res = submit(
        client,
        ctx,
        [
            entry(
                ctx.hall_a,
                date=d1.isoformat(),
                startTime="09:00",
                endTime="17:00",
            ),
            entry(
                ctx.hall_b,
                date=d2.isoformat(),
                startTime="13:00",
                endTime="15:00",
            ),
        ],
    )

    assert res.status_code == 201

    by_venue = {
        booking["venueId"]: booking
        for booking in res.get_json()
    }

    assert set(by_venue) == {
        ctx.hall_a,
        ctx.hall_b,
    }

    assert all(
        booking["eventId"] == ctx.event_id
        and booking["status"] == "pending"
        for booking in by_venue.values()
    )

    assert (
        by_venue[ctx.hall_a]["startDatetime"]
        == at(d1, 9).isoformat()
    )

    assert (
        by_venue[ctx.hall_a]["endDatetime"]
        == at(d1, 17).isoformat()
    )

    assert (
        by_venue[ctx.hall_b]["startDatetime"]
        == at(d2, 13).isoformat()
    )

    assert (
        by_venue[ctx.hall_b]["endDatetime"]
        == at(d2, 15).isoformat()
    )

    # Each venue should be a separate pending booking
    # that Venue Staff can review.
    pending = client.get(
        f"{BASE}/bookings/pending",
        headers=ctx.staff,
    ).get_json()

    assert sorted(
        booking["venueId"]
        for booking in pending
    ) == sorted(
        [
            ctx.hall_a,
            ctx.hall_b,
        ]
    )


# --------------------------------------------------------------------------
# AC2:
# At least one venue is required.
# Every venue requires date, start time and end time.
# --------------------------------------------------------------------------

def test_ac2_request_without_a_venue_is_rejected(
    client,
    ctx,
):
    res = submit(
        client,
        ctx,
        [],
    )

    assert res.status_code == 400

    assert [
        error["field"]
        for error in res.get_json()["errors"]
    ] == ["venues"]

    assert all_bookings() == []


def test_ac2_missing_date_or_times_names_the_venue_and_fields(
    client,
    ctx,
):
    res = submit(
        client,
        ctx,
        [
            entry(ctx.hall_a),
            entry(
                ctx.hall_b,
                date=None,
                startTime=None,
                endTime=None,
            ),
        ],
    )

    assert res.status_code == 400

    assert error_pairs(res) == {
        ("Hall B", "date"),
        ("Hall B", "start_time"),
        ("Hall B", "end_time"),
    }

    # Hall A must not be saved either.
    # The whole request is all-or-nothing.
    assert all_bookings() == []


# --------------------------------------------------------------------------
# AC3:
# End time must be after start time.
# Booking date cannot be in the past.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "end",
    [
        "10:00",
        "09:30",
    ],
)
def test_ac3_end_same_as_or_before_start_is_rejected(
    client,
    ctx,
    end,
):
    res = submit(
        client,
        ctx,
        [
            entry(ctx.hall_a),
            entry(
                ctx.hall_b,
                endTime=end,
            ),
        ],
    )

    assert res.status_code == 400

    assert error_pairs(res) == {
        ("Hall B", "end_time"),
    }

    assert (
        "after the start time"
        in res.get_json()["errors"][0]["message"]
    )

    assert all_bookings() == []


def test_ac3_date_in_the_past_is_rejected(
    client,
    ctx,
):
    res = submit(
        client,
        ctx,
        [
            entry(
                ctx.hall_a,
                date=day(-1).isoformat(),
            )
        ],
    )

    assert res.status_code == 400

    assert error_pairs(res) == {
        ("Hall A", "date"),
    }

    assert (
        "in the past"
        in res.get_json()["errors"][0]["message"]
    )

    assert all_bookings() == []


# --------------------------------------------------------------------------
# AC4:
# A booking may end on the following day.
# --------------------------------------------------------------------------

def test_ac4_end_time_on_the_next_day_is_accepted_with_the_correct_end(
    client,
    ctx,
):
    d = day(30)
    next_day = d + timedelta(days=1)

    res = submit(
        client,
        ctx,
        [
            entry(
                ctx.hall_a,
                startTime="22:00",
                endTime="02:00",
                endDate=next_day.isoformat(),
            )
        ],
    )

    assert res.status_code == 201

    pending = client.get(
        f"{BASE}/bookings/pending",
        headers=ctx.staff,
    ).get_json()[0]

    assert (
        pending["startDatetime"]
        == at(d, 22).isoformat()
    )

    assert (
        pending["endDatetime"]
        == at(next_day, 2).isoformat()
    )

# --------------------------------------------------------------------------
# AC5:
# One active (pending/approved) request
# per venue per event.
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "existing_status",
    [
        "pending",
        "approved",
    ],
)
def test_ac6_venue_with_an_active_booking_is_blocked_and_named(
    client,
    ctx,
    existing_status,
):
    add_booking(
        ctx,
        ctx.hall_a,
        existing_status,
    )

    res = submit(
        client,
        ctx,
        [
            entry(ctx.hall_a),
            entry(ctx.hall_b),
        ],
    )

    assert res.status_code == 400

    assert error_pairs(res) == {
        ("Hall A", "venue_id"),
    }

    assert (
        "already has an active booking"
        in res.get_json()["errors"][0]["message"]
    )

    # Only the booking created before the request should exist.
    # Nothing from the failed request should be saved.
    assert len(all_bookings()) == 1


@pytest.mark.parametrize(
    "old_status",
    [
        "rejected",
        "withdrawn",
    ],
)
def test_ac6_venue_can_be_included_again_after_reject_or_withdraw(
    client,
    ctx,
    old_status,
):
    add_booking(
        ctx,
        ctx.hall_a,
        old_status,
    )

    res = submit(
        client,
        ctx,
        [
            entry(ctx.hall_a),
        ],
    )

    assert res.status_code == 201

    assert [
        booking.status
        for booking in all_bookings()
    ] == [
        old_status,
        "pending",
    ]