# bot/monitor.py

import time

from config.settings import BASE_CURRENCY, POLL_INTERVAL_SECONDS
from utils.logger import get_logger
from utils.binance_client import BinanceClient
from bot.notifier import TelegramNotifier


class Monitor:
    """
    Monitors an active trade for SL, TP, and Auto-Close levels.
    When a trigger hits, it closes the trade and sends a notification.
    """

    def __init__(self):
        self.logger = get_logger("Monitor")
        self.client = BinanceClient()
        self.notifier = TelegramNotifier()

    def run(self, trade: dict):
        """
        Block until one of the exit conditions is met:
        - Stop-Loss
        - Take-Profit
        - Auto-Close
        Then execute the market sell and notify.
        """
        entry = trade["entry_price"]
        sl_price = trade["sl_price"]
        tp_price = trade["tp_price"]
        ac_price = trade["auto_close_price"]
        qty = trade["qty"]

        self.logger.info(
            "Starting monitor: entry=%s, SL=%s, TP=%s, Auto-Close=%s",
            entry, sl_price, tp_price, ac_price
        )

        while True:
            try:
                price = self.client.get_current_price()
                self.logger.debug("Current price: %s", price)

                if price <= sl_price:
                    self.logger.info("SL trigger hit at %s", price)
                    self._close_trade(qty, entry, price, "SL")
                    break

                if price >= tp_price:
                    self.logger.info("TP trigger hit at %s", price)
                    self._close_trade(qty, entry, price, "TP")
                    break

                if price >= ac_price:
                    self.logger.info("Auto-Close trigger hit at %s", price)
                    self._close_trade(qty, entry, price, "Auto-Close")
                    break

            except Exception as e:
                self.logger.exception("Error in monitor loop: %s", e)

            time.sleep(POLL_INTERVAL_SECONDS)

    def _close_trade(self, qty: float, entry_price: float, exit_price: float, reason: str):
        """
        Executes market sell for the given quantity and notifies based on reason.
        """
        # Cancel any stray orders
        self.client.cancel_open_orders()

        # Market sell
        sell = self.client.market_sell(qty)
        fills = sell.get("fills", [])
        total_qty = sum(float(f["qty"]) for f in fills)
        total_return = sum(float(f["qty"]) * float(f["price"]) for f in fills)
        real_exit = total_return / total_qty
        pnl_pct = (real_exit / entry_price - 1) * 100

        # Fetch updated balance
        balance = self.client.get_balance(BASE_CURRENCY)

        # Notify accordingly
        if reason == "TP":
            self.notifier.notify_tp_hit(real_exit, pnl_pct, balance)
        elif reason == "SL":
            self.notifier.notify_sl_hit(real_exit, pnl_pct, balance)
        else:
            self.notifier.notify_auto_close(real_exit, pnl_pct, balance)