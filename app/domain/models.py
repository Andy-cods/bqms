"""Pydantic v2 domain models — request/response schemas."""

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr, ConfigDict

from .enums import UserRole, POStatus, RFQStatus


# ── Auth ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


# ── Users ───────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)
    role: UserRole = UserRole.staff
    department: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    department: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Products ────────────────────────────────────────────

class ProductCreate(BaseModel):
    bqms_code: Optional[str] = None
    product_name: str = Field(min_length=1)
    spec: Optional[str] = None
    maker: Optional[str] = None
    category: Optional[str] = None
    unit: str = "EA"
    type: Optional[str] = Field(None, pattern="^(gc|tm)$")
    min_stock: float = 0
    current_stock: float = 0


class ProductUpdate(BaseModel):
    product_name: Optional[str] = None
    spec: Optional[str] = None
    maker: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    type: Optional[str] = Field(None, pattern="^(gc|tm)$")
    min_stock: Optional[float] = None
    current_stock: Optional[float] = None


class ProductOut(BaseModel):
    id: int
    bqms_code: Optional[str] = None
    product_name: str
    spec: Optional[str] = None
    maker: Optional[str] = None
    category: Optional[str] = None
    unit: str = "EA"
    type: Optional[str] = None
    min_stock: float = 0
    current_stock: float = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Suppliers ───────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str = Field(min_length=1)
    code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    country: str = "VN"
    payment_terms: Optional[str] = None


class SupplierOut(BaseModel):
    id: int
    name: str
    code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    country: str = "VN"
    payment_terms: Optional[str] = None
    rating: float = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


# ── Purchase Orders ─────────────────────────────────────

class POCreate(BaseModel):
    po_number: str = Field(min_length=1)
    supplier_id: Optional[int] = None
    total_amount: Optional[float] = None
    currency: str = "VND"
    eta_date: Optional[date] = None
    notes: Optional[str] = None


class POLineItemCreate(BaseModel):
    product_id: Optional[int] = None
    bqms_code: Optional[str] = None
    spec: Optional[str] = None
    quantity: float
    unit_price: Optional[float] = None


class POOut(BaseModel):
    id: int
    po_number: str
    supplier_id: Optional[int] = None
    total_amount: Optional[float] = None
    currency: str = "VND"
    status: POStatus = POStatus.draft
    eta_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── RFQ ─────────────────────────────────────────────────

class RFQCreate(BaseModel):
    rfq_no: str = Field(min_length=1)
    deadline: Optional[datetime] = None
    person_in_charge: Optional[str] = None


class RFQItemCreate(BaseModel):
    bqms_code: Optional[str] = None
    spec: Optional[str] = None
    maker: Optional[str] = None
    quantity: Optional[float] = None
    unit: str = "EA"


class RFQOut(BaseModel):
    id: int
    rfq_no: str
    status: RFQStatus = RFQStatus.draft
    deadline: Optional[datetime] = None
    person_in_charge: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Transactions ────────────────────────────────────────

class TransactionOut(BaseModel):
    id: int
    transaction_date: Optional[date] = None
    rfq_no: Optional[str] = None
    bqms_code: Optional[str] = None
    spec: Optional[str] = None
    maker: Optional[str] = None
    quantity: Optional[float] = None
    price_rmb: Optional[float] = None
    price_vnd: Optional[float] = None
    price_quoted: Optional[float] = None
    result: Optional[str] = None
    person_in_charge: Optional[str] = None
    source_file: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ── Deliveries ──────────────────────────────────────────

class DeliveryCreate(BaseModel):
    po_number: Optional[str] = None
    po_id: Optional[int] = None
    delivery_date: Optional[date] = None
    quantity_expected: Optional[float] = None
    quantity_received: Optional[float] = None
    receiver: Optional[str] = None
    notes: Optional[str] = None


class DeliveryOut(BaseModel):
    id: int
    po_id: Optional[int] = None
    po_number: Optional[str] = None
    delivery_date: Optional[date] = None
    quantity_expected: Optional[float] = None
    quantity_received: Optional[float] = None
    status: str = "waiting"
    receiver: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Market Prices ───────────────────────────────────────

class MarketPriceCreate(BaseModel):
    bqms_code: Optional[str] = None
    product_name: str
    spec: Optional[str] = None
    maker: Optional[str] = None
    platform: Optional[str] = None
    supplier_name: Optional[str] = None
    supplier_url: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    price_usd: Optional[float] = None
    moq: Optional[int] = None
    match_confidence: Optional[float] = None


class MarketPriceOut(BaseModel):
    id: int
    bqms_code: Optional[str] = None
    product_name: str
    platform: Optional[str] = None
    supplier_name: Optional[str] = None
    price_usd: Optional[float] = None
    moq: Optional[int] = None
    confirmed: bool = False
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ── Generic ─────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    data: list
    total: int
    page: int
    pages: int


class StatsResponse(BaseModel):
    transactions: int = 0
    products: int = 0
    purchase_orders: int = 0
    rfq_count: int = 0
    deliveries: int = 0
    market_prices: int = 0
    users: int = 0
