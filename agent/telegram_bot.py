"""0g Mem Telegram Bot — Desktop + Telegram, same agent, same memory.

Connects to the Agent Runtime via WebSocket and streams responses back to Telegram.

Auth: user signs a nonce with their wallet (MetaMask) to prove ownership.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ChatAction

from agent.agent_loop import AgentLoop, AgentConfig
from agent.tools import ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-user session state (in-memory; keyed by telegram_user_id)
# ---------------------------------------------------------------------------

class UserSession:
    """Tracks active session state per Telegram user."""

    def __init__(self, user_id: int, wallet_address: str):
        self.user_id = user_id
        self.wallet_address: str = wallet_address
        self.session_id: str = ""
        self.mode: str = "assistant"
        self.is_authenticated: bool = False
        self.last_message_at: float = 0.0


# In-memory session store — keyed by telegram_user_id
_user_sessions: dict[int, UserSession] = {}

# In-memory agent loops — one per authenticated user
# (lazily created after wallet auth)
_agent_loops: dict[int, AgentLoop] = {}

# Global config
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


# ---------------------------------------------------------------------------
# Wallet Authentication Middleware
# ---------------------------------------------------------------------------

async def _verify_wallet_signature(
    user_id: int,
    wallet_address: str,
    signature: str,
    nonce: str,
) -> bool:
    """
    Verify that the user controls the claimed wallet address.
    Signs the nonce challenge with the wallet's private key.
    """
    try:
        from web3 import Web3
        msg = f"0g Mem Telegram auth: {nonce}"
        recovered = Web3().eth.account.recover_message(
            message=msg,
            signature=signature,
        )
        return recovered.lower() == wallet_address.lower()
    except Exception as exc:
        logger.warning("Signature verification failed: %s", exc)
        return False


async def _handle_auth_start(update: Update, text: str) -> None:
    """Handle /auth <wallet_address> — starts the auth flow."""
    parts = text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text(
            "To authenticate, send your wallet address:\n"
            "/auth 0xYourWalletAddress\n\n"
            "Then sign the challenge message that appears."
        )
        return

    wallet_address = parts[1].strip()
    user_id = update.effective_user.id

    # Generate a nonce challenge
    nonce = str(int(time.time()))
    msg = f"0g Mem Telegram auth: {nonce}"

    # Store pending auth state
    pending_auth[user_id] = {
        "wallet_address": wallet_address,
        "nonce": nonce,
        "msg": msg,
    }

    await update.message.reply_text(
        f"SIGN THIS MESSAGE with your wallet to prove ownership:\n\n"
        f"```\n{msg}\n```\n\n"
        f"Then send:\n/auth confirm <your_signature>\n\n"
        f"Wallet: `{wallet_address}`",
        parse_mode="Markdown",
    )


async def _handle_auth_confirm(update: Update, text: str, user_id: int) -> None:
    """Handle /auth confirm <signature> — complete the auth flow."""
    pending = pending_auth.pop(user_id, None)
    if not pending:
        await update.message.reply_text(
            "No pending auth. Run /auth <wallet_address> first."
        )
        return

    signature = text.strip()
    is_valid = await _verify_wallet_signature(
        user_id,
        pending["wallet_address"],
        signature,
        pending["nonce"],
    )

    if not is_valid:
        await update.message.reply_text(
            "Signature verification failed. Please try again:\n"
            "/auth <wallet_address>"
        )
        return

    # Create user session
    session = UserSession(
        user_id=user_id,
        wallet_address=pending["wallet_address"],
    )
    session.is_authenticated = True
    session.session_id = _make_session_id(pending["wallet_address"])
    _user_sessions[user_id] = session

    # Create agent loop for this user
    from ogmem.config import NETWORKS
    net = NETWORKS["0g-testnet"]
    agent_loop = AgentLoop(
        private_key=os.environ.get("AGENT_KEY", ""),
        config=AgentConfig(
            memory_ws_url=os.environ.get("MEMORY_WS_URL", "ws://localhost:8000"),
            max_tool_calls=5,
            max_reasoning_turns=3,
        ),
        tool_registry=ToolRegistry(),
    )
    _agent_loops[user_id] = agent_loop

    await update.message.reply_text(
        f"Authenticated as `{session.wallet_address}`\n\n"
        f"Session: `{session.session_id}`\n\n"
        f"Mode: {session.mode}\n\n"
        f"Send me a message to talk to your agent!",
        parse_mode="Markdown",
    )


# Pending auth state: user_id → {wallet_address, nonce, msg}
pending_auth: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Telegram Message Handler
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main message handler — routes to auth flow or agent."""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Handle commands
    if text.startswith("/auth"):
        if "confirm" in text:
            await _handle_auth_confirm(update, text.replace("/auth confirm", "").strip(), user_id)
        else:
            await _handle_auth_start(update, text)
        return

    if text.startswith("/mode"):
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("Usage: /mode assistant | coding | research")
            return
        new_mode = parts[1].strip()
        if new_mode not in ("assistant", "coding", "research"):
            await update.message.reply_text("Mode must be: assistant, coding, or research")
            return
        session = _user_sessions.get(user_id)
        if not session:
            await update.message.reply_text("Not authenticated. Run /auth <wallet_address> first.")
            return
        session.mode = new_mode
        await update.message.reply_text(f"Mode set to: {new_mode}")
        return

    if text.startswith("/reset"):
        session = _user_sessions.get(user_id)
        if session:
            loop = _agent_loops.get(user_id)
            if loop:
                await loop.end_session(session.wallet_address, session.session_id)
            session.session_id = _make_session_id(session.wallet_address)
            _agent_loops.pop(user_id, None)
        await update.message.reply_text("Session reset. Start fresh!")
        return

    if text.startswith("/know"):
        session = _user_sessions.get(user_id)
        if not session:
            await update.message.reply_text("Not authenticated. Run /auth <wallet_address> first.")
            return
        # Quick lookup — show what the agent knows about the user
        # TODO: wire to memory dashboard API to get memory summary
        await update.message.reply_text(
            "Check your memory dashboard at the desktop app to see what I know about you.\n\n"
            "Usage:\n"
            "/auth — authenticate\n"
            "/mode <assistant|coding|research> — switch mode\n"
            "/reset — reset session\n"
            "/know — see memory summary"
        )
        return

    # Normal message — must be authenticated
    session = _user_sessions.get(user_id)
    if not session or not session.is_authenticated:
        await update.message.reply_text(
            "Not authenticated. Run:\n"
            "/auth <wallet_address>\n\n"
            "Example: /auth 0x1234abcd..."
        )
        return

    loop = _agent_loops.get(user_id)
    if not loop:
        await update.message.reply_text("Session error. Run /reset and try again.")
        return

    # Indicate typing while processing
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        turn = await loop.handle_message(
            user_id=session.wallet_address,
            session_id=session.session_id,
            text=text,
            channel="telegram",
            mode=session.mode,
        )

        if turn.error:
            await update.message.reply_text(
                f"Something went wrong: {turn.error}",
                parse_mode="Markdown",
            )
            return

        # Build response text
        lines = [turn.response_text]

        # Add tool call results summary if any
        if turn.tool_results:
            tool_summaries = []
            for tr in turn.tool_results:
                if tr.success:
                    preview = tr.output[:200] + ("..." if len(tr.output) > 200 else "")
                    tool_summaries.append(f"[{tr.tool}] {preview}")
                else:
                    tool_summaries.append(f"[{tr.tool}] Error: {tr.error}")
            if tool_summaries:
                lines.append("\n---\nTool results:")
                lines.extend(tool_summaries)

        # Add memory indicator
        if turn.memories_retrieved > 0:
            lines.append(f"\n_(Used {turn.memories_retrieved} memory/ies)_")

        response_text = "\n".join(lines)
        await update.message.reply_text(response_text[:4096])  # Telegram message limit

    except Exception as exc:
        logger.exception("Telegram handler error")
        await update.message.reply_text(f"Error: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_id(wallet_address: str) -> str:
    """Create an hourly session ID: f'{wallet}_{hour_timestamp}'."""
    hour = int(time.time() // 3600)
    return f"{wallet_address}_{hour}"


# ---------------------------------------------------------------------------
# App Builder
# ---------------------------------------------------------------------------

def build_app() -> telegram.Application:
    """Build and return the Telegram bot application."""
    import telegram

    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Get a bot token from @BotFather on Telegram."
        )

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the Telegram bot."""
    import telegram

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = build_app()
    logger.info("0g Mem Telegram bot starting...")
    app.run_polling()
