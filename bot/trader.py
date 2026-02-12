# bot/trader.py

import time
from apscheduler.schedulers.blocking import BlockingScheduler

from config.settings import MIN_TRADE_USD, POLL_INTERVAL_SECONDS, BASE_CURRENCY, SYMBOLS
from utils.binance_client import BinanceClient
from utils.calculations import (
    calculate_dip_price,
    calculate_sl_price,
    calculate_tp_price,
    calculate_auto_close_price,
)
from bot.notifier import TelegramNotifier
from utils.logger import get_logger


class Trader:
    """
    Multi-currency Dip Trader.
    One active trade at a time.
    """

    def __init__(self):
        self.logger = get_logger("Trader")
        self.client = BinanceClient()
        self.notifier = TelegramNotifier()

        # Trading state
        self.in_trade = False
        self.active_symbol = None  # Which symbol are we currently trading?
        self.trade = {}

        # Track reference prices for ALL symbols
        # { 'BTCUSDT': 80000.0, 'ETHUSDT': 3000.0 }
        self.reference_prices = {}

        self.scheduler = BlockingScheduler()

    def start(self):
        self.logger.info("Trader initializing for symbols: %s", SYMBOLS)
        # Initialize reference prices
        for s in SYMBOLS:
            price = self.client.get_current_price(s)
            self.reference_prices[s] = price
            self.logger.info("Ref price for %s: %s", s, price)

        self.scheduler.add_job(self._trade_cycle, "interval", seconds=POLL_INTERVAL_SECONDS)
        self.logger.info("Scheduler started.")
        self.scheduler.start()

    def _trade_cycle(self):
        try:
            if self.in_trade:
                # Only monitor the active symbol
                self._monitor_active_trade()
            else:
                # Scan all symbols for a dip
                self._scan_for_opportunities()

        except Exception as e:
            self.logger.exception("Error during trade cycle: %s", e)

    def _scan_for_opportunities(self):
        """Check all symbols to see if any hit the dip trigger."""
        for symbol in SYMBOLS:
            current_price = self.client.get_current_price(symbol)
            ref_price = self.reference_prices.get(symbol, current_price)

            dip_trigger = calculate_dip_price(ref_price)

            # Simple logic: If current > ref, update ref (trailing up)
            if current_price > ref_price:
                self.reference_prices[symbol] = current_price
                # self.logger.debug("Updated Ref for %s to %s", symbol, current_price)

            # Check dip
            elif current_price <= dip_trigger:
                self.logger.info("Dip found on %s! Price: %s, Trigger: %s", symbol, current_price, dip_trigger)
                self._open_trade(symbol)
                return  # Stop scanning, we found a trade

    def _open_trade(self, symbol: str):
        self.logger.info("Opening trade for %s", symbol)
        self.client.cancel_open_orders(symbol)

        order = self.client.market_buy(symbol, MIN_TRADE_USD)
        if not order:
            return

        fills = order.get("fills", [])
        total_qty = sum(float(f["qty"]) for f in fills)
        total_spent = sum(float(f["qty"]) * float(f["price"]) for f in fills)
        entry_price = total_spent / total_qty if total_qty else 0

        sl_price = calculate_sl_price(entry_price)
        tp_price = calculate_tp_price(entry_price)
        auto_close_price = calculate_auto_close_price(entry_price)

        self.trade = {
            "qty": total_qty,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "auto_close_price": auto_close_price,
        }
        self.in_trade = True
        self.active_symbol = symbol

        self.notifier.notify_new_trade(
            symbol, entry_price, total_qty, sl_price, tp_price
        )

    def _monitor_active_trade(self):
        symbol = self.active_symbol
        current_price = self.client.get_current_price(symbol)
        t = self.trade

        self.logger.debug(
            "Monitoring %s: Cur=%s, Entry=%s, SL=%s, TP=%s",
            symbol, current_price, t["entry_price"], t["sl_price"], t["tp_price"]
        )

        if current_price <= t["sl_price"]:
            self._close_trade("SL", current_price)
        elif current_price >= t["tp_price"]:
            self._close_trade("TP", current_price)
        elif current_price >= t["auto_close_price"]:
            self._close_trade("Auto-Close", current_price)

    def _close_trade(self, reason: str, trigger_price: float):
        symbol = self.active_symbol
        self.logger.info("Closing %s (%s) at %s", symbol, reason, trigger_price)

        self.client.cancel_open_orders(symbol)
        sell_order = self.client.market_sell(symbol, self.trade["qty"])

        if not sell_order:
            self.logger.error("Failed to sell %s. Manual intervention needed.", symbol)
            return

        fills = sell_order.get("fills", [])
        total_qty = sum(float(f["qty"]) for f in fills)
        total_return = sum(float(f["qty"]) * float(f["price"]) for f in fills)
        exit_price = total_return / total_qty if total_qty else trigger_price

        pnl_percent = (exit_price / self.trade["entry_price"] - 1) * 100
        balance = self.client.get_balance(BASE_CURRENCY)

        if reason == "TP":
            self.notifier.notify_tp_hit(symbol, exit_price, pnl_percent, balance)
        elif reason == "SL":
            self.notifier.notify_sl_hit(symbol, exit_price, pnl_percent, balance)
        else:
            self.notifier.notify_auto_close(symbol, exit_price, pnl_percent, balance)

        # Reset state
        # The exit price becomes the new reference for this symbol
        self.reference_prices[symbol] = exit_price

        self.in_trade = False
        self.active_symbol = None
        self.trade = {}
        self.logger.info("Trade closed. Resuming scan.")


if __name__ == "__main__":
    trader = Trader()
    trader.start()