import time
import pandas as pd
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

    # --- CORRECTED FUNCTION START ---
    def _open_trade(self, symbol: str):
        self.logger.info("Opening trade for %s", symbol)
        try:
            self.client.cancel_open_orders(symbol)
            
            # --- ATTEMPT THE TRADE ---
            order = self.client.market_buy(symbol, MIN_TRADE_USD)
            
            # --- PROCESS SUCCESSFUL ORDER ---
            fills = order.get("fills", [])
            if not fills:
                self.logger.error("Market buy for %s created no fills. Aborting trade.", symbol)
                return

            total_qty = sum(float(f["qty"]) for f in fills)
            total_spent = sum(float(f["qty"]) * float(f["price"]) for f in fills)
            entry_price = total_spent / total_qty if total_qty else 0

            # If we can't determine an entry price, something is wrong.
            if not entry_price:
                self.logger.error("Could not determine entry price from fills. Aborting trade.")
                return

            # --- SET STATE ONLY AFTER SUCCESS ---
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

            self.logger.info("Successfully opened trade for %s at %s", symbol, entry_price)
            self.notifier.notify_new_trade(
                symbol, entry_price, total_qty, sl_price, tp_price
            )

        except Exception as e:
            self.logger.exception("Failed to execute open trade for %s. Error: %s", symbol, e)
            # self.in_trade remains False. The bot will try again on the next cycle.
            return
    # --- CORRECTED FUNCTION END ---

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

    # --- CORRECTED FUNCTION START ---
    def _close_trade(self, reason: str, trigger_price: float):
        symbol = self.active_symbol
        self.logger.info("Attempting to close %s (%s) at %s", symbol, reason, trigger_price)
        
        try:
            self.client.cancel_open_orders(symbol)

            # --- ATTEMPT TO SELL ---
            sell_order = self.client.market_sell(symbol, self.trade["qty"])

            # --- PROCESS SUCCESSFUL SALE ---
            fills = sell_order.get("fills", [])
            if not fills:
                self.logger.error("Market sell for %s created no fills. State not reset.", symbol)
                # We don't reset state, so the bot will try again.
                return
            
            total_qty = sum(float(f["qty"]) for f in fills)
            total_return = sum(float(f["qty"]) * float(f["price"]) for f in fills)
            exit_price = total_return / total_qty if total_qty else trigger_price

            pnl_percent = (exit_price / self.trade["entry_price"] - 1) * 100
            balance = self.client.get_balance(BASE_CURRENCY)

            # --- NOTIFY AND RESET STATE ONLY AFTER SUCCESS ---
            if reason == "TP":
                self.notifier.notify_tp_hit(symbol, exit_price, pnl_percent, balance)
            elif reason == "SL":
                self.notifier.notify_sl_hit(symbol, exit_price, pnl_percent, balance)
            else:
                self.notifier.notify_auto_close(symbol, exit_price, pnl_percent, balance)

            # Reset state
            self.reference_prices[symbol] = exit_price
            self.in_trade = False
            self.active_symbol = None
            self.trade = {}
            self.logger.info("Trade closed successfully. Resuming scan.")

        except Exception as e:
            self.logger.exception("Failed to execute close trade for %s. Will retry. Error: %s", symbol, e)
            # We DO NOT reset state here, forcing a retry on the next cycle.
            return
    # --- CORRECTED FUNCTION END ---


if __name__ == "__main__":
    trader = Trader()
    trader.start()

