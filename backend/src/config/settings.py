import os
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Pre-load .env into os.environ so Pydantic always sees the variables,
# regardless of whether model_config env_file is honoured.
load_dotenv("/opt/teledock/backend/.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/opt/teledock/backend/.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    bot_token: str = Field(alias="BOT_TOKEN")
    bot_webhook_secret: str = Field(alias="BOT_WEBHOOK_SECRET")
    bot_admin_ids: List[int] = Field(default_factory=list, alias="BOT_ADMIN_IDS")
    admin_chat_id: int = Field(alias="ADMIN_CHAT_ID")

    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(alias="DB_NAME")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_pool_min_size: int = Field(default=5, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=20, alias="DB_POOL_MAX_SIZE")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_url: str = Field(alias="API_BASE_URL")
    frontend_url: str = Field(alias="FRONTEND_URL")

    payme_merchant_id: str = Field(alias="PAYME_MERCHANT_ID")
    payme_secret_key: str = Field(alias="PAYME_SECRET_KEY")
    payme_endpoint: str = Field(alias="PAYME_ENDPOINT")

    click_service_id: str = Field(alias="CLICK_SERVICE_ID")
    click_merchant_id: str = Field(alias="CLICK_MERCHANT_ID")
    click_secret_key: str = Field(alias="CLICK_SECRET_KEY")
    click_endpoint: str = Field(alias="CLICK_ENDPOINT")

    p2p_card_number: str = Field(alias="P2P_CARD_NUMBER")
    p2p_card_holder: str = Field(alias="P2P_CARD_HOLDER")
    p2p_webhook_secret: str = Field(alias="P2P_WEBHOOK_SECRET")
    merchant_card_number: str = Field(alias="MERCHANT_CARD_NUMBER")
    merchant_card_name: str = Field(alias="MERCHANT_CARD_NAME")
    sms_gateway_token: str = Field(alias="SMS_GATEWAY_TOKEN")
    telegram_api_id: int = Field(alias="TELEGRAM_API_ID")
    telegram_api_hash: str = Field(alias="TELEGRAM_API_HASH")
    telegram_session_name: str = Field(default="teledock_userbot", alias="TELEGRAM_SESSION_NAME")

    # Fulfillment Worker session (Pyrogram or Telethon string session)
    pyrogram_session_string: str = Field(default="", alias="PYROGRAM_SESSION_STRING")
    telethon_session_string: str = Field(default="", alias="TELETHON_SESSION_STRING")

    # Fragment.com Procurement Worker credentials
    fragment_wallet_seed: str = Field(default="", alias="FRAGMENT_WALLET_SEED")
    fragment_cookie_stel_ssid: str = Field(default="", alias="FRAGMENT_COOKIE_STEL_SSID")
    fragment_cookie_stel_dt: str = Field(default="", alias="FRAGMENT_COOKIE_STEL_DT")
    fragment_cookie_stel_token: str = Field(default="", alias="FRAGMENT_COOKIE_STEL_TOKEN")
    fragment_cookie_stel_ton_token: str = Field(default="", alias="FRAGMENT_COOKIE_STEL_TON_TOKEN")
    procurement_daily_budget_usd: float = Field(default=500.0, alias="PROCUREMENT_DAILY_BUDGET_USD")

    # Bot username for Fragment purchases to self
    bot_username: str = Field(default="Teledock_bot", alias="BOT_USERNAME")

    # Admin Telegram ID for alerts
    admin_telegram_id: int = Field(default=0, alias="ADMIN_TELEGRAM_ID")

    # ─── HUMOcardbot listener ─────────────────────────────────────
    humo_listener_chat_id: Optional[str] = Field(default=None, alias="HUMO_LISTENER_CHAT_ID")
    """Telegram chat ID (group / channel) where @HUMOcardbot posts.
    Numeric ID (e.g. -1001234567890) or username (e.g. @mygroup)."""

    humo_listener_enabled: bool = Field(default=True, alias="HUMO_LISTENER_ENABLED")

    humo_listener_session_string: str = Field(default="", alias="HUMO_LISTENER_SESSION_STRING")
    """Telethon StringSession for the account that receives @HUMOcardbot notifications.
    If set, the listener uses this session instead of TELETHON_SESSION_STRING."""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def database_dsn(self) -> str:
        return (
            f"postgres://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def is_prod(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
