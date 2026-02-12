# config/settings.py

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

# Load .env file from project root
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

def _get_env(var_name: str, cast_type, required: bool = True):
    raw = os.getenv(var_name)
    if required and raw is None:
        raise ConfigError(f"Environment variable '{var_name}' is required but not set.")
    if raw is None:
        return None
    try:
        return cast_type(raw)
    except (ValueError, TypeError):
        raise ConfigError(f"Environment variable '{var_name}' must be of type {cast_type.__name__}.")

# Binance environment selection
BINANCE_ENVIRONMENT = _get_env("BINANCE_ENVIRONMENT", str)
MAINNET_API_URL     = _get_env("MAINNET_API_URL", str)
TESTNET_API_URL     = _get_env("TESTNET_API_URL", str)

if BINANCE_ENVIRONMENT.lower() == "mainnet":
    BINANCE_BASE_URL = MAINNET_API_URL
elif BINANCE_ENVIRONMENT.lower() == "testnet":
    BINANCE_BASE_URL = TESTNET_API_URL
else:
    raise ConfigError("Invalid BINANCE_ENVIRONMENT. Choose 'mainnet' or 'testnet'.")

# Credentials
BINANCE_API_KEY    = _get_env("BINANCE_API_KEY", str)
BINANCE_API_SECRET = _get_env("BINANCE_API_SECRET", str)
TELEGRAM_BOT_TOKEN = _get_env("TELEGRAM_BOT_TOKEN", str)
TELEGRAM_CHAT_ID   = _get_env("TELEGRAM_CHAT_ID", str)

# Trading pairs - Parse comma-separated list
_symbols_str = _get_env("SYMBOLS", str)
SYMBOLS = [s.strip() for s in _symbols_str.split(",") if s.strip()]

BASE_CURRENCY = _get_env("BASE_CURRENCY", str)

# Trade parameters
MIN_TRADE_USD       = _get_env("MIN_TRADE_USD", float)
SL_PERCENT          = _get_env("SL_PERCENT", float)
TP_PERCENT          = _get_env("TP_PERCENT", float)
AUTO_CLOSE_PERCENT  = _get_env("AUTO_CLOSE_PERCENT", float)
DIP_TRIGGER_PERCENT = _get_env("DIP_TRIGGER_PERCENT", float)

# Precision and polling
PRICE_PRECISION       = _get_env("PRICE_PRECISION", int)
QTY_PRECISION         = _get_env("QTY_PRECISION", int)
POLL_INTERVAL_SECONDS = _get_env("POLL_INTERVAL_SECONDS", int)

# Logging
LOG_LEVEL = _get_env("LOG_LEVEL", str)

# Validate numeric thresholds
_num_settings = {
    "MIN_TRADE_USD": MIN_TRADE_USD,
    "SL_PERCENT": SL_PERCENT,
    "TP_PERCENT": TP_PERCENT,
    "AUTO_CLOSE_PERCENT": AUTO_CLOSE_PERCENT,
    "DIP_TRIGGER_PERCENT": DIP_TRIGGER_PERCENT,
    "POLL_INTERVAL_SECONDS": POLL_INTERVAL_SECONDS,
}

for name, value in _num_settings.items():
    if isinstance(value, (int, float)) and value < 0:
        raise ConfigError(f"'{name}' must be non-negative. Got {value}.")

if LOG_LEVEL.upper() not in logging._nameToLevel:
    raise ConfigError(f"Invalid LOG_LEVEL '{LOG_LEVEL}'")

logging.basicConfig(
    level=logging._nameToLevel[LOG_LEVEL.upper()],
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger("bot.settings")
logger.debug("Config loaded. Symbols: %s", SYMBOLS)