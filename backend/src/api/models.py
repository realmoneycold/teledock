"""Pydantic models for Payme and Click payment integrations."""

import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------
# Payme JSON-RPC 2.0 Models
# ---------------------------------------------------------

class PaymeMethod(str, Enum):
    CHECK_PERFORM_TRANSACTION = "CheckPerformTransaction"
    CREATE_TRANSACTION = "CreateTransaction"
    PERFORM_TRANSACTION = "PerformTransaction"
    CANCEL_TRANSACTION = "CancelTransaction"
    CHECK_TRANSACTION = "CheckTransaction"
    GET_STATEMENT = "GetStatement"
    CHANGE_PASSWORD = "ChangePassword"


class PaymeState(int, Enum):
    PENDING = 1
    DONE = 2
    CANCELLED = -1
    CANCELLED_AFTER_DONE = -2


class PaymeReason(int, Enum):
    RECEIVER_NOT_FOUND = 1
    DEBIT_OPERATION_ERROR = 2
    TRANSACTION_ERROR = 3
    TRANSACTION_TIMEOUT = 4
    REFUND_FAILED = 5
    UNKNOWN_ERROR = 10


class PaymeAccount(BaseModel):
    user_id: str = Field(alias="user_id")


class PaymeParams(BaseModel):
    id: str
    time: Optional[int] = None
    amount: int
    account: PaymeAccount
    reason: Optional[int] = None
    from_: Optional[int] = Field(default=None, alias="from")
    to: Optional[int] = None


class PaymeRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: PaymeMethod
    params: Optional[PaymeParams] = None


class PaymeResponseResult(BaseModel):
    allow: Optional[bool] = None
    perform_time: Optional[int] = None
    cancel_time: Optional[int] = None
    transaction: Optional[str] = None
    state: Optional[int] = None
    reason: Optional[int] = None
    receivers: Optional[list] = None

    class Config:
        populate_by_name = True


class PaymeResponseError(BaseModel):
    code: int
    message: str
    data: Optional[str] = None


class PaymeResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    result: Optional[PaymeResponseResult] = None
    error: Optional[PaymeResponseError] = None


# ---------------------------------------------------------
# Click Models
# ---------------------------------------------------------

class ClickPrepareRequest(BaseModel):
    click_trans_id: str
    service_id: str
    merchant_trans_id: str
    amount: float
    action: int
    sign_time: str
    sign_string: str
    error: int = 0
    error_note: str = ""

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return float(v)


class ClickCompleteRequest(BaseModel):
    click_trans_id: str
    service_id: str
    merchant_trans_id: str
    amount: float
    action: int
    sign_time: str
    sign_string: str
    error: int = 0
    error_note: str = ""
    merchant_prepare_id: Optional[int] = None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return float(v)


class ClickPrepareResponse(BaseModel):
    click_trans_id: str
    merchant_trans_id: str
    merchant_prepare_id: int
    error: int
    error_note: str


class ClickCompleteResponse(BaseModel):
    click_trans_id: str
    merchant_trans_id: str
    merchant_confirm_id: int
    error: int
    error_note: str


# ---------------------------------------------------------
# P2P Card-to-Card Webhook Model
# ---------------------------------------------------------

class P2PWebhookPayload(BaseModel):
    amount: float
    currency: str = "UZS"
    card_last4: Optional[str] = None
    sender: Optional[str] = None
    raw_message: Optional[str] = None
    timestamp: Optional[str] = None

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return float(v)


# ---------------------------------------------------------
# Phase 2: Product & Order Models
# ---------------------------------------------------------

class ProductType(str, Enum):
    STARS = "stars"
    PREMIUM = "premium"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    COMPLETED = "completed"
    FAILED = "failed"


class ProductRead(BaseModel):
    id: uuid.UUID
    name: str
    type: ProductType
    price_uzs: int
    description: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    name: str
    type: ProductType
    price_uzs: int
    description: Optional[str] = None
    is_active: bool = True


class OrderCreateRequest(BaseModel):
    product_id: uuid.UUID


class OrderRead(BaseModel):
    id: uuid.UUID
    user_id: int
    product_id: Optional[uuid.UUID] = None
    amount_uzs: Optional[int] = None
    exact_amount: Optional[float] = None
    payment_code: Optional[str] = None
    status: OrderStatus
    created_at: Optional[str] = None
    card_number: Optional[str] = None
    card_holder: Optional[str] = None

    class Config:
        from_attributes = True
