"""Equipment Reservation epic."""
from app.extensions import db
from app.equipment.services.availability import check_availability
from app.models.equipment import EquipmentItem, EquipmentReservation
from app.models.event import Event, EventEquipmentRequirement

RESERVED = "reserved"
RELEASED = "released"


def reserve(
    event: Event,
    requirement: EventEquipmentRequirement,
    equipment_item: EquipmentItem,
    start,
    end,
    user_id: int,
) -> EquipmentReservation:
    result = check_availability(equipment_item, requirement.quantity, start, end)
    if not result["available"]:
        raise ValueError(f"Not enough {equipment_item.name} available for the requested period")

    reservation = EquipmentReservation(
        event_id=event.id,
        equipment_requirement_id=requirement.id,
        equipment_item_id=equipment_item.id,
        quantity=requirement.quantity,
        start_datetime=start,
        end_datetime=end,
        status=RESERVED,
        created_by=user_id,
    )
    db.session.add(reservation)
    requirement.status = "confirmed"
    db.session.commit()
    return reservation


def release(reservation: EquipmentReservation) -> EquipmentReservation:
    """Releases equipment back to availability when an event is cancelled
    or the requirement is removed."""
    if reservation.status != RESERVED:
        raise ValueError("Only a currently reserved item can be released")
    reservation.status = RELEASED
    db.session.commit()
    return reservation
