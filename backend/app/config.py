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
    
    # Broker Configuration & Upstox Market Data Settings
    active_broker_provider: str = "UPSTOX" # UPSTOX, FYERS, DHAN, MOCK
    allow_mock_fallback: bool = True
    
    # Upstox Analytics Token Integration
    upstox_enabled: bool = True
    upstox_analytics_token: Optional[str] = None
    upstox_base_url: str = "https://api.upstox.com"
    upstox_ws_enabled: bool = True
    upstox_provider_priority: str = "upstox"
    
    # Legacy Upstox fields (maintained for backward compatibility)
    upstox_api_key: Optional[str] = None
    upstox_api_secret: Optional[str] = None
    upstox_access_token: Optional[str] = None
    
    # Dhan Broker Configuration
    dhan_client_id: Optional[str] = None
    dhan_access_token: Optional[str] = None

    # Safety Flags
    real_trading_enabled: bool = False
    default_paper_capital: float = 1000000.0

    @property
    def get_upstox_token(self) -> Optional[str]:
        return self.upstox_analytics_token or self.upstox_access_token

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
