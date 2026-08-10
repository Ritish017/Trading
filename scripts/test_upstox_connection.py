import asyncio
import os
import sys
import logging

# Ensure root directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.config import settings
from backend.app.broker_providers.upstox import UpstoxProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_upstox")

async def main():
    token = settings.get_upstox_token
    if not token:
        logger.error("❌ UPSTOX_ANALYTICS_TOKEN is missing or empty in backend/.env!")
        logger.info("Please set UPSTOX_ANALYTICS_TOKEN in .env to test real Upstox market data connection.")
        sys.exit(1)

    # Redacted verification logging
    masked_token = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
    logger.info(f"Loaded Upstox Analytics Token: {masked_token}")

    provider = UpstoxProvider(token=token, base_url=settings.upstox_base_url)
    connected = await provider.connect()

    if not connected:
        logger.error("❌ Upstox authentication failed. Check token validity or network connection.")
        sys.exit(1)

    logger.info("✅ Connected successfully to Upstox API!")

    # Fetch normalized quote for NIFTY 50 benchmark
    symbol = "NIFTY 50"
    logger.info(f"Fetching live normalized quote for {symbol}...")
    try:
        quote = await provider.get_quote(symbol)
        logger.info("Normalized Quote Result:")
        logger.info(f"  Symbol: {quote.get('symbol')}")
        logger.info(f"  LTP: ₹{quote.get('ltp')}")
        logger.info(f"  Change: {quote.get('change')} ({quote.get('change_percent')}%)")
        logger.info(f"  Open: ₹{quote.get('open')} | High: ₹{quote.get('high')} | Low: ₹{quote.get('low')}")
        logger.info(f"  Source: {quote.get('source')} (is_live: {quote.get('is_live')})")
    except Exception as e:
        logger.error(f"❌ Failed to fetch quote: {str(e)}")

    await provider.disconnect()
    logger.info("Disconnected gracefully.")

if __name__ == "__main__":
    asyncio.run(main())
