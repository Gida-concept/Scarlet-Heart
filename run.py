import signal
import sys
from config.settings import logger
from bot.trader import Trader

def _handle_exit(signum, frame):
    """
    Graceful shutdown on SIGINT/SIGTERM.
    """
    logger.info("Received exit signal (%s). Shutting down.", signum)
    sys.exit(0)

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)

    logger.info("Initialization complete. Launching Trader...")
    trader = Trader()
    trader.start()

if __name__ == "__main__":
    main()