from datetime import time
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, read from environment variables (or the .env file).

    Each field maps to an env var of the same name, case-insensitive:
    `database_url` <- DATABASE_URL. Pydantic validates types at startup, so a
    missing or malformed setting crashes immediately instead of failing later.
    """

    # Look for .env in the project root (when run from backend/) or the current dir
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str  # no default -> required
    app_timezone: str = "Asia/Kolkata"
    environment: str = "development"

    # Public URL of the site; also the only Origin allowed to make state-changing requests
    public_base_url: str = "http://localhost:3000"
    allowed_origins: str = ""  # extra comma-separated origins, if any

    session_days: int = 30
    storage_dir: str = "../storage"
    max_upload_mb: int = 10
    max_video_mb: int = 100

    # WhatsApp service (internal)
    whatsapp_url: str = "http://localhost:3001"
    whatsapp_token: str = "dev-whatsapp-token"
    wa_min_delay_seconds: int = 8
    wa_max_delay_seconds: int = 20
    wa_daily_limit: int = 250

    # Schedules (IST)
    reminder_days: str = "5-8"  # day-of-month range for tenant reminders
    reminder_time: str = "17:00"
    reminder_cutoff_time: str = "21:00"  # unsent reminders expire after this
    owner_report_day: int = 9
    owner_report_time: str = "10:00"

    # Email (for WhatsApp-disconnect alerts)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def origin_list(self) -> list[str]:
        extra = [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]
        return [self.public_base_url.rstrip("/"), *extra]

    @property
    def reminder_day_range(self) -> range:
        start, _, end = self.reminder_days.partition("-")
        return range(int(start), int(end or start) + 1)

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = value.split(":")
        return time(int(hour), int(minute))

    @property
    def reminder_at(self) -> time:
        return self._parse_time(self.reminder_time)

    @property
    def reminder_cutoff(self) -> time:
        return self._parse_time(self.reminder_cutoff_time)

    @property
    def owner_report_at(self) -> time:
        return self._parse_time(self.owner_report_time)


settings = Settings()
