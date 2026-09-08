import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "APEX Quant Lab Backend"
    environment: str = "development"
    port: int = 8000
    log_level: str = "INFO"
    
    # API Keys
    gemini_api_key: Optional[str] = None
    
    # Environment & Deployment Configuration
    apex_env: Optional[str] = None
    
    # Paper Trading & Live Safety Flags
    paper_trading: bool = True
    live_trading: bool = False
    real_trading_enabled: bool = False
    default_paper_capital: float = 1000000.0

    # Broker & Upstox Market Data Settings
    active_broker_provider: str = "UPSTOX" # UPSTOX, FYERS, DHAN, MOCK
    allow_mock_fallback: bool = True
    upstox_enabled: bool = True
    upstox_analytics_token: Optional[str] = None
    upstox_base_url: str = "https://api.upstox.com"
    upstox_ws_enabled: bool = True
    upstox_provider_priority: str = "upstox"
    
    # Standard Upstox Credentials
    upstox_client_id: Optional[str] = None
    upstox_client_secret: Optional[str] = None
    upstox_access_token: Optional[str] = None
    upstox_api_key: Optional[str] = None
    upstox_api_secret: Optional[str] = None
    
    # Dhan Broker Configuration
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None

    # Database Configuration
    database_url: Optional[str] = None

    # Security & Access Control
    api_auth_token: Optional[str] = None
    cors_allowed_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,https://apex-trading-lab.vercel.app"

    @property
    def is_production(self) -> bool:
        env_val = (self.apex_env or self.environment or os.environ.get("APEX_ENV") or os.environ.get("ENVIRONMENT") or "").lower()
        return env_val in ("production", "prod")

    @property
    def get_upstox_token(self) -> Optional[str]:
        return (
            self.upstox_analytics_token
            or self.upstox_access_token
            or os.environ.get("UPSTOX_ACCESS_TOKEN")
            or os.environ.get("UPSTOX_ANALYTICS_TOKEN")
        )

    def validate_production_invariants(self) -> None:
        """Enforces fail-closed safety and database requirements in production mode."""
        if self.is_production:
            # 1. Live orders strictly forbidden
            if self.live_trading or self.real_trading_enabled:
                raise RuntimeError(
                    "PRODUCTION SECURITY VIOLATION: LIVE_TRADING or real_trading_enabled is True. "
                    "Live money trading is strictly prohibited."
                )
            
            # 2. Database URL mandatory
            db_url = self.database_url or os.environ.get("DATABASE_URL")
            if not db_url or not db_url.strip():
                raise RuntimeError(
                    "PRODUCTION FAIL-CLOSED: DATABASE_URL is missing. "
                    "Production worker state requires an external PostgreSQL database. "
                    "Silent SQLite fallback is strictly prohibited in production."
                )
            
            db_lower = db_url.strip().lower()
            if "sqlite" in db_lower or "/tmp/" in db_lower:
                raise RuntimeError(
                    "PRODUCTION FAIL-CLOSED: SQLite / local database detected in production. "
                    "Production worker state requires an external PostgreSQL database (DATABASE_URL)."
                )
            
            if not any(db_lower.startswith(prefix) for prefix in ("postgres://", "postgresql://", "postgresql+")):
                raise RuntimeError(
                    f"PRODUCTION FAIL-CLOSED: DATABASE_URL schema '{db_url.split('://')[0]}' is invalid. "
                    "Must be an external PostgreSQL connection URL."
                )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

