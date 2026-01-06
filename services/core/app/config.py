from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Storage
    sqlite_path: str = "data/market.db"

    # Data providers
    provider: str = "binance"  # binance | polygon | oanda

    # Symbols by asset class (you can use any subset)
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


def get_settings() -> Settings:
    return Settings()
