import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Get the directory where this config.py file is located
_config_dir = Path(__file__).parent
_env_file = _config_dir.parent / ".env"  # services/core/.env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_env_file),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Storage
    sqlite_path: str = "data/market.db"

    # Data providers (multi-provider support)
    providers: str = "binance"  # comma-separated: "binance,oanda" or empty to use legacy 'provider'
    provider: str = "binance"  # legacy single-provider (used if 'providers' is empty)

    # Provider-specific symbols/instruments
    binance_symbols: str = "btcusdt,ethusdt"  # lowercase for Binance
    binance_transport: str = "auto"  # "ws" | "rest" | "auto" - auto tries WS first, falls back to REST
    binance_rest_poll_seconds: float = 2.0  # polling interval for REST mode
    
    oanda_instruments: str = "EUR_USD,GBP_USD,US30_USD"  # OANDA format with underscores

    # Legacy symbol lists (kept for backward compatibility)
    crypto_symbols: str = "btcusdt,ethusdt"
    fx_symbols: str = "EUR_USD,GBP_USD"
    index_symbols: str = "NAS100_USD,SPX500_USD"

    # Provider keys (only needed for polygon/oanda)
    polygon_api_key: str | None = None
    oanda_api_key: str | None = None
    oanda_account_id: str | None = None
    oanda_environment: str = "practice"  # practice | live

    # Bar aggregation
    bar_intervals: str = "1m,5m,15m,1h,4h,1d,1w"

    # Forecast horizons
    horizons: str = "minutes,hours,days,weeks"
    
    def get_enabled_providers(self) -> list[str]:
        """Return list of enabled providers with backward compatibility."""
        if self.providers.strip():
            return [p.strip().lower() for p in self.providers.split(",") if p.strip()]
        # Backward compatibility: use legacy 'provider' field
        if self.provider.strip():
            return [self.provider.strip().lower()]
        return []
    
    def get_binance_symbols(self) -> list[str]:
        """Get Binance symbols (lowercase)."""
        if self.binance_symbols.strip():
            return [s.strip().lower() for s in self.binance_symbols.split(",") if s.strip()]
        # Fallback to crypto_symbols
        if self.crypto_symbols.strip():
            return [s.strip().lower() for s in self.crypto_symbols.split(",") if s.strip()]
        return []
    
    def get_oanda_instruments(self) -> list[str]:
        """Get OANDA instruments (uppercase with underscores)."""
        if self.oanda_instruments.strip():
            return [s.strip().upper() for s in self.oanda_instruments.split(",") if s.strip()]
        # Fallback: combine fx_symbols and index_symbols
        instruments = []
        if self.fx_symbols.strip():
            instruments.extend([s.strip().upper() for s in self.fx_symbols.split(",") if s.strip()])
        if self.index_symbols.strip():
            instruments.extend([s.strip().upper() for s in self.index_symbols.split(",") if s.strip()])
        return instruments
    
    def get_bar_intervals(self) -> list[str]:
        """Parse bar intervals."""
        return [i.strip() for i in self.bar_intervals.split(",") if i.strip()]


def get_settings() -> Settings:
    return Settings()
