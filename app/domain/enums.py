"""Domain enums — mirror PostgreSQL enum types."""

from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    procurement = "procurement"
    warehouse = "warehouse"
    staff = "staff"


class POStatus(str, Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"
    confirmed = "confirmed"
    in_transit = "in_transit"
    received = "received"
    closed = "closed"
    cancelled = "cancelled"


class WFState(str, Enum):
    draft = "draft"
    pending_l1 = "pending_l1"
    pending_l2 = "pending_l2"
    approved = "approved"
    rejected = "rejected"
    in_progress = "in_progress"
    completed = "completed"


class RFQStatus(str, Enum):
    draft = "draft"
    sent = "sent"
    receiving = "receiving"
    comparing = "comparing"
    selected = "selected"
    closed = "closed"
