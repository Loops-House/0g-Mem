#!/usr/bin/env python3
"""Convenience script to run the 0g Mem Telegram bot.

Usage:
    python scripts/run_telegram.py

Requires TELEGRAM_BOT_TOKEN and AGENT_KEY env vars to be set.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.telegram_bot import main

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run 0g Mem Telegram Bot")
    parser.add_argument(
        "--token", dest="token", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)"
    )
    args = parser.parse_args()

    if args.token:
        os.environ["TELEGRAM_BOT_TOKEN"] = args.token

    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("ERROR: TELEGRAM_BOT_TOKEN is not set.")
        print("  Set it via env var or pass --token")
        sys.exit(1)

    main()
