# bot/notifier.py

import time
import requests
import logging
from typing import Optional

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, BASE_CURRENCY
from utils.logger import get_logger

logger = get_logger("Notifier")

class TelegramNotifier:
    _API_URL = "https://api.telegram.org/bot{token}/sendMessage"
    _MAX_RETRIES = 3
    _RETRY_DELAY = 1

    def __init__(self):
        self.chat_id = TELEGRAM_CHAT_ID
        self.url = self._API_URL.format(token=TELEGRAM_BOT_TOKEN)

    def _send(self, text: str) -> None:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        for attempt in range(1, self._MAX_RETRIES + 1):
            try:
                resp = requests.post(self.url, json=payload, timeout=10)
                resp.raise_for_status()
                return
            except Exception as e:
                logger.warning("Telegram fail %d/%d: %s", attempt, self._MAX_RETRIES, e)
                time.sleep(self._RETRY_DELAY)
        logger.error("Failed to send Telegram message.")

    def notify_new_trade(self, symbol: str, entry_price: float, quantity: float, sl_price: float, tp_price: float) -> None:
        text = (
            f"*New Trade Opened*\n"
            f"Pair: `{symbol}`\n"
            f"Side: BUY\n"
            f"Entry: `{entry_price}`\n"
            f"Quantity: `{quantity}`\n"
            f"SL: `{sl_price}`\n"
            f"TP: `{tp_price}`"
        )
        self._send(text)

    def notify_tp_hit(self, symbol: str, exit_price: float, pnl_percent: float, balance: float) -> None:
        text = (
            f"*Take Profit Hit ({symbol})*\n"
            f"Exit Price: `{exit_price}`\n"
            f"P&L: `{pnl_percent:.2f}%`\n"
            f"Balance: `{balance:.2f} {BASE_CURRENCY}`"
        )
        self._send(text)

    def notify_sl_hit(self, symbol: str, exit_price: float, pnl_percent: float, balance: float) -> None:
        text = (
            f"*Stop Loss Hit ({symbol})*\n"
            f"Exit Price: `{exit_price}`\n"
            f"P&L: `{pnl_percent:.2f}%`\n"
            f"Balance: `{balance:.2f} {BASE_CURRENCY}`"
        )
        self._send(text)

    def notify_auto_close(self, symbol: str, exit_price: float, pnl_percent: float, balance: float) -> None:
        text = (
            f"*Auto-Close Triggered ({symbol})*\n"
            f"P&L: `{pnl_percent:.2f}%`\n"
            f"Exit Price: `{exit_price}`\n"
            f"Balance: `{balance:.2f} {BASE_CURRENCY}`"
        )
        self._send(text)