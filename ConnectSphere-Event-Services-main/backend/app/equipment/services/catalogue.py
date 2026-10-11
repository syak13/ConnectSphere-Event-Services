"""Backs Equipment Availability Checking: Technical Support Staff's real
inventory, separate from what an Organiser requests on an event."""
from app.extensions import db
from app.models.equipment import EquipmentItem


def create_item(data: dict) -> EquipmentItem:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Equipment name is required")
    total_quantity = data.get("totalQuantity")
    if total_quantity is None or int(total_quantity) < 0:
        raise ValueError("totalQuantity must be zero or greater")

    item = EquipmentItem(name=name, category=data.get("category"), total_quantity=int(total_quantity))
    db.session.add(item)
    db.session.commit()
    return item


def update_item(item: EquipmentItem, data: dict) -> EquipmentItem:
    if "name" in data:
        item.name = data["name"]
    if "category" in data:
        item.category = data["category"]
    if "totalQuantity" in data:
        item.total_quantity = int(data["totalQuantity"])
    db.session.commit()
    return item


def mark_unavailable(item: EquipmentItem) -> EquipmentItem:
    """Marks an item as under maintenance/damaged, excluding it from
    availability checks (Equipment Availability Checking epic)."""
    item.status = "maintenance"
    db.session.commit()
    return item


def mark_active(item: EquipmentItem) -> EquipmentItem:
    item.status = "active"
    db.session.commit()
    return item


def list_items():
    return EquipmentItem.query.order_by(EquipmentItem.name.asc()).all()


def get_item(item_id: int):
    return EquipmentItem.query.get(item_id)


def get_item_by_name(name: str):
    return EquipmentItem.query.filter_by(name=name).first()
