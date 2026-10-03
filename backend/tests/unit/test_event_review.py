import pytest
from datetime import datetime, timezone, date, time
from werkzeug.security import generate_password_hash
from app.models.event import Event, EventReview, EventClarificationResponse
from app.events.routes import _build_display_fields, _require_confirmation  # both pure/stateless, safe to import directly
from app.models.user import Role, User
from app.events.services.review import (
    request_clarification,
    approve_event,
    reject_event,
    get_clarification_thread,
    respond_to_clarification,
    delete_clarification_request,
)
from app.events.services.status import InvalidTransitionError, change_status
from app.events.services.assignment import assign_coordinator, reassign_coordinator
from app.extensions import db
from app.common.text_validation import validate_descriptive_text

@pytest.fixture(scope="function")
def test_db(app):
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()

@pytest.fixture
def event():
    return Event(
        id=1,
        organiser_id=100,
        coordinator_id=200,
        status="under_review",
        name="Annual Tech Conference",
        purpose="Discuss latest tech trends",
        description="A conference for tech enthusiasts",
        proposed_date="2023-12-01",
        proposed_time="10:00",
        expected_attendance=500,
        required_layout="Theater",
        accessibility_needs="Wheelchair access",
        required_facilities="Projector, Microphones",
        registration_required=True,
        review_timestamp=datetime.now(timezone.utc),  # Use timezone-aware datetime
    )

@pytest.fixture
def coordinator():
    return {"id": 200, "role": "event_coordinator"}

@pytest.fixture
def non_coordinator():
    return {"id": 300, "role": "attendee"}

@pytest.fixture
def organiser():
    return {"id": 100, "role": "event_organiser"}


@pytest.fixture
def second_coordinator():
    return {"id": 201, "role": "event_coordinator"}


@pytest.fixture
def two_real_coordinators(app):
    """assign_coordinator/reassign_coordinator query real User/Role rows,
    so unlike the other fixtures here, this one needs actual persisted
    users rather than a plain dict."""
    with app.app_context():
        role = Role.query.filter_by(name="event_coordinator").first()
        user_a = User(
            name="Real Coordinator A",
            email="realcoord.a@test.com",
            password_hash=generate_password_hash("password"),
        )
        user_a.roles = [role]
        user_b = User(
            name="Real Coordinator B",
            email="realcoord.b@test.com",
            password_hash=generate_password_hash("password"),
        )
        user_b.roles = [role]
        db.session.add_all([user_a, user_b])
        db.session.commit()
        return user_a.id, user_b.id

def test_request_clarification(app, event, coordinator):
    with app.app_context():
        clarification_comment = "Please provide more details about the venue requirements."
        updated_event = request_clarification(event, coordinator["id"], clarification_comment)
        assert updated_event.clarification_flag is True
        assert updated_event.clarification_comments == clarification_comment

def test_clarification_requires_valid_comment(app, event, coordinator):
    with app.app_context():
        with pytest.raises(ValueError, match="Clarification comment must contain descriptive text"):
            request_clarification(event, coordinator["id"], "!!!")

def test_reject_event(app, event, coordinator):
    with app.app_context():
        reason = "The event does not meet the required criteria."
        updated_event = reject_event(event, coordinator["id"], reason)
        assert updated_event.status == "rejected"
        assert updated_event.review_outcome == "rejected"
        assert updated_event.review_reason == reason

def test_invalid_status_for_review(app, event, coordinator):
    with app.app_context():
        event.status = "draft"
        with pytest.raises(ValueError, match="Only a request under review can be approved"):
            approve_event(event, coordinator["id"], comments="Looks good")
        with pytest.raises(ValueError, match="Only a request under review can be rejected"):
            reject_event(event, coordinator["id"], reason="Invalid reason")
        with pytest.raises(ValueError, match="Clarification can only be requested while a request is under review"):
            request_clarification(event, coordinator["id"], "Need more details")


# =======================================================================
# Clarification requests: comment validation and editable-fields grant
# =======================================================================

@pytest.mark.parametrize("invalid_comment", ["!!!", "12345", "@@@###", "-----", "123-456-7890"])
def test_request_clarification_symbols_or_digits_only_is_rejected(app, event, coordinator, invalid_comment):
    with app.app_context():
        with pytest.raises(ValueError, match="Clarification comment must contain descriptive text"):
            request_clarification(event, coordinator["id"], invalid_comment)


def test_request_clarification_word_comment_is_accepted(app, event, coordinator):
    with app.app_context():
        updated = request_clarification(event, coordinator["id"], "Please confirm A/V setup.")
        assert updated.clarification_comments == "Please confirm A/V setup."


def test_request_clarification_only_assigned_coordinator_can_request(app, event, second_coordinator):
    with app.app_context():
        with pytest.raises(PermissionError, match="Only the assigned Coordinator can request clarification"):
            request_clarification(event, second_coordinator["id"], "Trying to clarify someone else's event.")


def test_request_clarification_records_editable_fields(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(
            event, coordinator["id"], "Please confirm the venue capacity.", editable_fields=["capacity_needed"]
        )

        latest_review = event.reviews[-1]
        assert latest_review.action == "clarification_requested"
        assert latest_review.editable_fields == ["capacity_needed"]
        assert event.clarification_flag is True


def test_request_clarification_rejects_unknown_editable_field(app, event, coordinator):
    with app.app_context():
        with pytest.raises(ValueError, match="Unknown field.*not_a_real_field"):
            request_clarification(
                event, coordinator["id"], "Testing an invalid field grant.", editable_fields=["not_a_real_field"]
            )


def test_multiple_clarifications_are_all_recorded_in_order(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "First question.")
        request_clarification(event, coordinator["id"], "Second question.")
        request_clarification(event, coordinator["id"], "Third question.")

        clarification_entries = [r for r in event.reviews if r.action == "clarification_requested"]
        assert [r.comments for r in clarification_entries] == [
            "First question.",
            "Second question.",
            "Third question.",
        ]
        assert event.clarification_comments == "Third question."


# =======================================================================
# Approve / Reject: status and ownership rules not covered by the
# existing test_invalid_status_for_review / test_reject_event
# =======================================================================

def test_approve_event_requires_assigned_coordinator(app, event, second_coordinator):
    with app.app_context():
        with pytest.raises(PermissionError, match="Only the assigned Coordinator can approve this request"):
            approve_event(event, second_coordinator["id"])


def test_reject_event_requires_assigned_coordinator(app, event, second_coordinator):
    with app.app_context():
        with pytest.raises(PermissionError, match="Only the assigned Coordinator can reject this request"):
            reject_event(event, second_coordinator["id"], "Not my call")


def test_reject_event_requires_a_reason(app, event, coordinator):
    with app.app_context():
        with pytest.raises(ValueError, match="At least one rejection reason is required"):
            reject_event(event, coordinator["id"], "")


def test_cannot_approve_an_already_approved_event(app, event, coordinator):
    with app.app_context():
        approve_event(event, coordinator["id"])
        with pytest.raises(ValueError, match="Only a request under review can be approved"):
            approve_event(event, coordinator["id"])


def test_cannot_reject_an_already_rejected_event(app, event, coordinator):
    with app.app_context():
        reject_event(event, coordinator["id"], "First rejection")
        with pytest.raises(ValueError, match="Only a request under review can be rejected"):
            reject_event(event, coordinator["id"], "Second attempt")


# =======================================================================
# Organiser's response to clarification: editable-fields whitelist,
# one-response-per-request, and answering by reviewId
# =======================================================================

def test_respond_to_clarification_applies_only_granted_fields(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(
            event, coordinator["id"], "Please update the description only.", editable_fields=["description"]
        )
        review_id = event.reviews[-1].id

        respond_to_clarification(
            event,
            organiser["id"],
            review_id,
            {
                "comments": "Updated as requested.",
                "description": "A much more detailed description.",
                "name": "Attempted Rename",  # not granted - must be ignored
            },
        )

        assert event.description == "A much more detailed description."
        assert event.name == "Annual Tech Conference"  # unchanged
        assert event.clarification_flag is False

        response = EventClarificationResponse.query.filter_by(review_id=review_id).first()
        assert response.updated_fields == {"description": "A much more detailed description."}



@pytest.mark.parametrize("invalid_comment", ["", "   ", "!!!", "12345"])
def test_respond_to_clarification_requires_valid_comment(app, event, coordinator, organiser, invalid_comment):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        with pytest.raises(ValueError):
            respond_to_clarification(event, organiser["id"], review_id, {"comments": invalid_comment})


def test_respond_to_clarification_cannot_be_submitted_twice_for_same_review(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        respond_to_clarification(event, organiser["id"], review_id, {"comments": "Confirmed at 120."})

        with pytest.raises(ValueError, match="already been responded to"):
            respond_to_clarification(event, organiser["id"], review_id, {"comments": "Trying again."})


def test_respond_to_clarification_fails_for_unknown_review_id(app, event, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        with pytest.raises(ValueError, match="No such clarification request"):
            respond_to_clarification(event, organiser["id"], 999999, {"comments": "Answering nothing."})


def test_respond_to_clarification_fails_for_non_owning_organiser(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        with pytest.raises(PermissionError, match="Only the requesting Organiser can respond"):
            respond_to_clarification(event, 999, review_id, {"comments": "Not my event."})


def test_earlier_clarification_remains_answerable_after_a_newer_one_is_opened(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "First question.")
        request_clarification(event, coordinator["id"], "Second question.")
        first_review_id, second_review_id = [r.id for r in event.reviews if r.action == "clarification_requested"]

        respond_to_clarification(event, organiser["id"], second_review_id, {"comments": "Answering the second."})
        assert event.clarification_flag is True

        respond_to_clarification(event, organiser["id"], first_review_id, {"comments": "Answering the first."})
        assert event.clarification_flag is False

        responses = {r.review_id: r.comments for r in EventClarificationResponse.query.filter_by(event_id=event.id)}
        assert responses[first_review_id] == "Answering the first."
        assert responses[second_review_id] == "Answering the second."


def test_get_clarification_thread_pairs_requests_with_responses(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Still waiting on this one.")
        thread = get_clarification_thread(event)
        assert len(thread) == 1
        assert thread[0]["response"] is None

        review_id = thread[0]["reviewId"]
        respond_to_clarification(event, organiser["id"], review_id, {"comments": "Here is the answer."})

        thread = get_clarification_thread(event)
        assert thread[0]["response"]["comments"] == "Here is the answer."


# =======================================================================
# Review-detail display fields (pure/stateless — no persistence needed)
# =======================================================================

def test_display_fields_show_nil_for_missing_optional_values(app):
    with app.app_context():
        minimal_event = Event(
            organiser_id=100,
            status="under_review",
            name="Minimal Event",
            purpose="Testing",
            description="Only the required fields are set.",
            proposed_date=date(2026, 12, 1),
            expected_attendance=50,
        )
        fields = {f["title"]: f["value"] for f in _build_display_fields(minimal_event)}

        assert fields["Proposed date and time"] == "2026-12-01"
        assert fields["Venue requirements"] == "NIL"
        assert fields["Accessibility requirements"] == "NIL"
        assert fields["Equipment requirements"] == "NIL"
        assert fields["Registration requirements"] == "NIL"


def test_display_fields_show_populated_values_with_exact_titles(app):
    with app.app_context():
        full_event = Event(
            organiser_id=100,
            status="under_review",
            name="Full Event",
            purpose="Testing",
            description="Every optional field is set.",
            proposed_date=date(2026, 12, 1),
            proposed_time=time(9, 30),
            expected_attendance=100,
            capacity_needed=80,
            required_layout="theatre",
            accessibility_needs="Wheelchair access required",
            registration_required=True,
            intended_capacity=80,
        )
        fields = {f["title"]: f["value"] for f in _build_display_fields(full_event)}

        assert fields["Proposed date and time"] == "2026-12-01 09:30:00"
        assert fields["Venue requirements"] == {
            "capacityNeeded": 80,
            "requiredLayout": "theatre",
            "requiredFacilities": "NIL",
        }
        assert fields["Accessibility requirements"] == "Wheelchair access required"
        assert fields["Registration requirements"] == {"registrationRequired": True, "intendedCapacity": 80}


# =======================================================================
# Coordinator assignment / reassignment (needs real User/Role rows)
# =======================================================================

def test_assign_coordinator_picks_an_active_coordinator(app, two_real_coordinators):
    with app.app_context():
        coordinator_a_id, coordinator_b_id = two_real_coordinators
        new_event = Event(
            organiser_id=100,
            status="submitted",
            name="Board Meeting",
            purpose="Quarterly review",
            description="Standard quarterly board meeting.",
            proposed_date=date(2026, 6, 1),
            expected_attendance=20,
        )
        db.session.add(new_event)
        db.session.commit()

        assign_coordinator(new_event)
        assert new_event.coordinator_id in (coordinator_a_id, coordinator_b_id)


def test_reassign_coordinator_updates_assignment_and_history(app, two_real_coordinators):
    with app.app_context():
        coordinator_a_id, coordinator_b_id = two_real_coordinators
        new_event = Event(
            organiser_id=100,
            status="submitted",
            name="Board Meeting",
            purpose="Quarterly review",
            description="Standard quarterly board meeting.",
            proposed_date=date(2026, 6, 1),
            expected_attendance=20,
        )
        db.session.add(new_event)
        db.session.commit()

        assign_coordinator(new_event, coordinator=User.query.get(coordinator_a_id))
        reassign_coordinator(new_event, User.query.get(coordinator_b_id))

        assert new_event.coordinator_id == coordinator_b_id
        history_ids = [h.coordinator_id for h in new_event.coordinator_history]
        assert coordinator_a_id in history_ids
        assert coordinator_b_id in history_ids

# =======================================================================
# Shared reason validation: rejection & cancellation follow the same
# rules as clarification comments (validate_descriptive_text)
# =======================================================================

@pytest.mark.parametrize("invalid_reason", ["!!!", "12345", "@@@###", "-----", "123-456-7890"])
def test_reject_event_rejects_symbols_or_digits_only_reason(app, event, coordinator, invalid_reason):
    with app.app_context():
        with pytest.raises(ValueError, match="must contain descriptive text"):
            reject_event(event, coordinator["id"], invalid_reason)


def test_reject_event_rejects_blank_reason_with_shared_validation_message(app, event, coordinator):
    with app.app_context():
        with pytest.raises(ValueError, match="At least one rejection reason is required"):
            reject_event(event, coordinator["id"], "")


def test_reject_event_accepts_reason_with_real_words(app, event, coordinator):
    with app.app_context():
        updated = reject_event(event, coordinator["id"], "Insufficient lead time for setup.")
        assert updated.status == "rejected"
        assert updated.review_reason == "Insufficient lead time for setup."


@pytest.mark.parametrize("invalid_reason", ["!!!", "12345", "", "   "])
def test_validate_descriptive_text_rejects_invalid_cancellation_reason(invalid_reason):
    # Cancellation reuses this exact shared helper (see cancel_event_route
    # in routes.py) — testing it directly here proves cancellation follows
    # the same rule as clarification comments and rejection reasons.
    with pytest.raises(ValueError):
        validate_descriptive_text(invalid_reason, "cancellation reason")


def test_validate_descriptive_text_accepts_a_real_cancellation_reason():
    validate_descriptive_text("Venue became unavailable due to flooding.", "cancellation reason")


def test_change_status_allows_cancelling_directly_from_under_review(app, event):
    with app.app_context():
        updated = change_status(event, "cancelled", changed_by_id=event.coordinator_id, reason="Testing")
        assert updated.status == "cancelled"


def test_change_status_allows_cancelling_directly_from_submitted(app, event):
    with app.app_context():
        event.status = "submitted"
        updated = change_status(event, "cancelled", changed_by_id=event.coordinator_id, reason="Testing")
        assert updated.status == "cancelled"


# =======================================================================
# Coordinator deletes (withdraws) a clarification request
# =======================================================================

def test_delete_clarification_request_by_assigned_coordinator(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        updated = delete_clarification_request(event, coordinator["id"], review_id)

        deleted_review = next(r for r in updated.reviews if r.id == review_id)
        assert deleted_review.withdrawn_at is not None
        assert updated.clarification_flag is False  # no other open requests


def test_delete_clarification_request_requires_assigned_coordinator(app, event, coordinator, second_coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        with pytest.raises(PermissionError, match="Only the assigned Coordinator can delete a clarification request"):
            delete_clarification_request(event, second_coordinator["id"], review_id)


def test_delete_clarification_request_fails_for_unknown_review_id(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        with pytest.raises(ValueError, match="No such clarification request"):
            delete_clarification_request(event, coordinator["id"], 999999)


def test_cannot_delete_an_already_withdrawn_clarification_request(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id
        delete_clarification_request(event, coordinator["id"], review_id)

        with pytest.raises(ValueError, match="already been deleted"):
            delete_clarification_request(event, coordinator["id"], review_id)


def test_cannot_delete_a_clarification_request_that_has_already_been_answered(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id
        respond_to_clarification(event, organiser["id"], review_id, {"comments": "Confirmed at 120."})

        with pytest.raises(ValueError, match="already been responded to"):
            delete_clarification_request(event, coordinator["id"], review_id)


def test_deleting_one_clarification_leaves_another_open_request_intact(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "First question.")
        request_clarification(event, coordinator["id"], "Second question.")
        first_id, second_id = [r.id for r in event.reviews if r.action == "clarification_requested"]

        updated = delete_clarification_request(event, coordinator["id"], first_id)

        # the second, still-open request keeps the flag set
        assert updated.clarification_flag is True

        thread = get_clarification_thread(updated)
        first_entry = next(t for t in thread if t["reviewId"] == first_id)
        second_entry = next(t for t in thread if t["reviewId"] == second_id)
        assert first_entry["withdrawn"] is True
        assert second_entry["withdrawn"] is False


def test_get_clarification_thread_marks_withdrawn_requests(app, event, coordinator):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id
        delete_clarification_request(event, coordinator["id"], review_id)

        thread = get_clarification_thread(event)
        assert thread[0]["withdrawn"] is True
        assert thread[0]["response"] is None


# =======================================================================
# Organiser cannot respond to a clarification once the event has reached
# a terminal outcome (approved / rejected / cancelled)
# =======================================================================

@pytest.mark.parametrize("terminal_status", ["approved", "rejected", "cancelled"])
def test_cannot_respond_to_clarification_once_event_is_in_a_terminal_status(
    app, event, coordinator, organiser, terminal_status
):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        event.status = terminal_status  # simulate the event having since been decided
        db.session.commit()

        with pytest.raises(ValueError, match=f"once the request has been {terminal_status}"):
            respond_to_clarification(event, organiser["id"], review_id, {"comments": "Too late now."})


def test_can_still_respond_while_status_is_submitted_or_under_review(app, event, coordinator, organiser):
    with app.app_context():
        event.proposed_date = date(2023, 12, 1)
        event.proposed_time = time(10, 0)
        db.session.add(event)
        db.session.commit()

        request_clarification(event, coordinator["id"], "Please confirm the headcount.")
        review_id = event.reviews[-1].id

        updated = respond_to_clarification(event, organiser["id"], review_id, {"comments": "Confirmed at 120."})
        assert updated.clarification_flag is False


# =======================================================================
# Confirmation gate for approve / reject / cancel
# (app.events.routes._require_confirmation is the actual decision logic
# behind the HTTP 409 "please confirm" response; tested directly since
# it needs no request/JWT context of its own — just an app context for
# jsonify)
# =======================================================================

def test_require_confirmation_prompts_when_not_yet_confirmed(app, event):
    with app.app_context():
        event.clarification_flag = False
        result = _require_confirmation(event, {}, "approve")
        assert result is not None
        response, status_code = result
        assert status_code == 409
        body = response.get_json()
        assert body["requiresConfirmation"] is True
        assert body["hasUnresolvedClarification"] is False
        assert "approve" in body["message"]


@pytest.mark.parametrize("action_label", ["approve", "reject", "cancel"])
def test_require_confirmation_warns_about_unresolved_clarification(app, event, action_label):
    with app.app_context():
        event.clarification_flag = True
        result = _require_confirmation(event, {}, action_label)
        assert result is not None
        response, status_code = result
        body = response.get_json()
        assert status_code == 409
        assert body["hasUnresolvedClarification"] is True
        assert "unresolved clarification" in body["message"].lower()
        assert action_label in body["message"]


def test_require_confirmation_returns_none_once_confirmed(app, event):
    with app.app_context():
        event.clarification_flag = True  # even with an unresolved clarification...
        result = _require_confirmation(event, {"confirmed": True}, "reject")
        assert result is None  # ...explicit confirmation always lets the action through


def test_require_confirmation_is_required_even_without_any_unresolved_clarification(app, event):
    with app.app_context():
        event.clarification_flag = False
        result = _require_confirmation(event, {}, "cancel")
        assert result is not None  # confirmation is unconditional, not just a warning-triggered thing