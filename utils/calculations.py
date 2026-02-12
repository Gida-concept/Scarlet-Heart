# utils/calculations.py

from config.settings import (
    SL_PERCENT,
    TP_PERCENT,
    AUTO_CLOSE_PERCENT,
    DIP_TRIGGER_PERCENT,
    PRICE_PRECISION,
    QTY_PRECISION,
)


def calculate_sl_price(entry_price: float) -> float:
    """
    Calculate the stop-loss price given an entry price.
    """
    sl = entry_price * (1 - SL_PERCENT / 100)
    return round_price(sl)


def calculate_tp_price(entry_price: float) -> float:
    """
    Calculate the take-profit price given an entry price.
    """
    tp = entry_price * (1 + TP_PERCENT / 100)
    return round_price(tp)


def calculate_auto_close_price(entry_price: float) -> float:
    """
    Calculate the auto-close price at a smaller profit threshold.
    """
    ac = entry_price * (1 + AUTO_CLOSE_PERCENT / 100)
    return round_price(ac)


def calculate_dip_price(current_price: float) -> float:
    """
    Calculate the price at which to place a dip-triggered buy order.
    """
    dip = current_price * (1 - DIP_TRIGGER_PERCENT / 100)
    return round_price(dip)


def round_price(price: float) -> float:
    """
    Round a price to the configured precision.
    """
    return float(round(price, PRICE_PRECISION))


def round_quantity(quantity: float) -> float:
    """
    Round an order quantity to the configured precision.
    """
    return float(round(quantity, QTY_PRECISION))


def calculate_order_quantity(usdt_amount: float, price: float) -> float:
    """
    Calculate how much base asset to buy/sell given a USDT amount and price.
    """
    raw_qty = usdt_amount / price
    return round_quantity(raw_qty)