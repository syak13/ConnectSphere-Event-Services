"""Equipment Availability Checking epic."""
from app.models.equipment import EquipmentItem, EquipmentReservation

ACTIVE = "active"
RESERVED = "reserved"


def check_availability(equipment_item: EquipmentItem, quantity_needed: int, start, end) -> dict:
    """Returns whether enough units are free for [start, end], excluding
    equipment already committed to another overlapping event and equipment
    currently under maintenance."""
    if equipment_item.status != ACTIVE:
        return {"available": False, "reason": "Equipment is not active (under maintenance or retired)"}

    overlapping = EquipmentReservation.query.filter(
        EquipmentReservation.equipment_item_id == equipment_item.id,
        EquipmentReservation.status == RESERVED,
        EquipmentReservation.start_datetime < end,
        EquipmentReservation.end_datetime > start,
    ).all()
    committed = sum(r.quantity for r in overlapping)
    free = equipment_item.total_quantity - committed

    return {
        "available": free >= quantity_needed,
        "freeQuantity": free,
        "totalQuantity": equipment_item.total_quantity,
    }
