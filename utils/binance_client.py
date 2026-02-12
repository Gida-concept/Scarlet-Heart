# utils/binance_client.py

import time
from decimal import Decimal, ROUND_DOWN

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException

from config.settings import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    SYMBOLS,  # Imported for logging or init, but methods will be dynamic
    BINANCE_ENVIRONMENT
)
from utils.logger import get_logger
from utils.calculations import calculate_order_quantity

_MAX_RETRIES = 3
_RETRY_DELAY = 1

logger = get_logger("BinanceClient")


def _retry(fn):
    def wrapped(*args, **kwargs):
        last_exc = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except (BinanceAPIException, BinanceRequestException) as e:
                last_exc = e
                logger.warning("API call %s failed: %s", fn.__name__, e)
                time.sleep(_RETRY_DELAY)
        logger.error("All retries failed for %s", fn.__name__)
        raise last_exc

    return wrapped


class BinanceClient:
    def __init__(self):
        testnet = BINANCE_ENVIRONMENT.lower() == "testnet"
        self._client = Client(
            api_key=BINANCE_API_KEY,
            api_secret=BINANCE_API_SECRET,
            testnet=testnet
        )
        env = "testnet" if testnet else "mainnet"
        logger.info("Initialized Binance client on %s", env)

        # Dictionary to store filter info per symbol: { 'BTCUSDT': {min, max, step} }
        self._filters = {}
        # Pre-load filters for all configured symbols
        for s in SYMBOLS:
            self._load_symbol_filters(s)

    def _load_symbol_filters(self, symbol: str):
        """Fetch symbol_info and parse LOT_SIZE constraints."""
        try:
            info = self._client.get_symbol_info(symbol)
            min_qty = Decimal("0")
            max_qty = Decimal("0")
            step_size = Decimal("1")

            if info:
                for f in info.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        min_qty = Decimal(f["minQty"])
                        max_qty = Decimal(f["maxQty"])
                        step_size = Decimal(f["stepSize"])
                        break

            self._filters[symbol] = {
                "min": min_qty,
                "max": max_qty,
                "step": step_size
            }
            logger.debug("Filters for %s: %s", symbol, self._filters[symbol])
        except Exception as e:
            logger.error("Failed to load filters for %s: %s", symbol, e)
            # Defaults
            self._filters[symbol] = {
                "min": Decimal("0"), "max": Decimal("0"), "step": Decimal("1")
            }

    def _apply_lot_size(self, symbol: str, qty: float) -> Decimal:
        filters = self._filters.get(symbol)
        if not filters:
            self._load_symbol_filters(symbol)
            filters = self._filters[symbol]

        dec_qty = Decimal(str(qty))
        step_size = filters["step"]
        min_qty = filters["min"]
        max_qty = filters["max"]

        rounded = (dec_qty // step_size) * step_size
        if rounded < min_qty:
            raise ValueError(f"Quantity {rounded} is below minimum {min_qty} for {symbol}")
        if max_qty and max_qty > 0 and rounded > max_qty:
            rounded = max_qty

        return rounded.quantize(step_size, rounding=ROUND_DOWN)

    @_retry
    def get_current_price(self, symbol: str) -> float:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        price = float(ticker["price"])
        return price

    @_retry
    def get_balance(self, asset: str) -> float:
        balance = self._client.get_asset_balance(asset=asset)
        return float(balance.get("free", 0.0))

    @_retry
    def cancel_open_orders(self, symbol: str):
        try:
            result = self._client.cancel_all_open_orders(symbol=symbol)
            logger.info("Canceled open orders for %s", symbol)
            return result
        except BinanceAPIException as e:
            if getattr(e, "code", None) == -2011:
                return []
            raise

    @_retry
    def market_buy(self, symbol: str, usdt_amount: float):
        price = self.get_current_price(symbol)
        raw_qty = calculate_order_quantity(usdt_amount, price)
        try:
            qty = self._apply_lot_size(symbol, raw_qty)
        except ValueError as e:
            logger.warning("Cannot place BUY for %s: %s", symbol, e)
            return None

        order = self._client.order_market_buy(symbol=symbol, quantity=float(qty))
        logger.info("Market BUY: %s %s ~%s USDT", qty, symbol, usdt_amount)
        return order

    @_retry
    def market_sell(self, symbol: str, quantity: float):
        try:
            qty = self._apply_lot_size(symbol, quantity)
        except ValueError as e:
            logger.warning("Cannot place SELL for %s: %s", symbol, e)
            return None

        order = self._client.order_market_sell(symbol=symbol, quantity=float(qty))
        logger.info("Market SELL: %s %s", qty, symbol)
        return order