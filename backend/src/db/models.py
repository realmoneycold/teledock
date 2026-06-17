from enum import Enum
from typing import Optional


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class TransactionProvider(str, Enum):
    PAYME = "payme"
    CLICK = "click"
    P2P = "p2p"
    INTERNAL_PURCHASE = "internal_purchase"


class ProductType(str, Enum):
    STARS = "stars"
    PREMIUM = "premium"
    ACCOUNT_BUY = "account_buy"
    ACCOUNT_RENT = "account_rent"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FULFILLED = "fulfilled"
    REFUNDED = "refunded"
    FAILED = "failed"
    EXPIRED = "expired"


class User:
    def __init__(
        self,
        id: int,
        username: Optional[str],
        first_name: str,
        wallet_balance: int = 0,
        created_at=None,
    ):
        self.id = id
        self.username = username
        self.first_name = first_name
        self.wallet_balance = wallet_balance
        self.created_at = created_at


class WalletTransaction:
    def __init__(
        self,
        id: str,
        user_id: int,
        amount: int,
        status: TransactionStatus,
        provider: TransactionProvider,
        provider_tx_id: Optional[str] = None,
        created_at=None,
    ):
        self.id = id
        self.user_id = user_id
        self.amount = amount
        self.status = status
        self.provider = provider
        self.provider_tx_id = provider_tx_id
        self.created_at = created_at


class Order:
    def __init__(
        self,
        id: str,
        user_id: int,
        product_type: ProductType,
        package_details: dict,
        cost: int,
        status: OrderStatus = OrderStatus.PENDING,
        created_at=None,
    ):
        self.id = id
        self.user_id = user_id
        self.product_type = product_type
        self.package_details = package_details
        self.cost = cost
        self.status = status
        self.created_at = created_at
