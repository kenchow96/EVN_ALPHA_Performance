#!/usr/bin/env python3
"""
local_commit_bot.py
-------------------
Persistent, asynchronous Telegram bot that monitors a LOCAL Git repository
directory for new commits and broadcasts commit metadata to a configured
Telegram chat or channel.

Design notes:
- Reads commit metadata natively from the on-disk .git folder (no GitHub / no
  webhooks). This makes it work with bare repos, offline repos, and local-only
  WIP workflows.
- Uses python-telegram-bot v20+ async Application + JobQueue.
- 10 second polling interval (configurable via POLL_INTERVAL_SECONDS).
- On startup, the current HEAD is recorded as the baseline so historical
  commits are NOT broadcast as "new".
- All user-generated commit strings (author, message, file list) are wrapped in
  fenced code blocks, which neutralises MarkdownV2 parse failures caused by
  special characters in commit messages.
- Secrets (Telegram bot token, chat id) are read from environment variables
  only — no hardcoded credentials, no .env loading.

Environment variables (all required unless noted):
  TELEGRAM_BOT_TOKEN       Bot token issued by @BotFather.
  TELEGRAM_CHAT_ID         Target chat or channel id (numeric, or @channelname).
  LOCAL_REPO_PATH          Path to the local git repo to monitor. Default: "."
  POLL_INTERVAL_SECONDS    Optional polling interval, default 10.

Run:
  Windows (PowerShell):
    $env:TELEGRAM_BOT_TOKEN="..."
    $env:TELEGRAM_CHAT_ID="..."
    $env:LOCAL_REPO_PATH="C:\\path\\to\\repo"
    python tools/local_commit_bot.py

  Linux / macOS:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... LOCAL_REPO_PATH=... \
        python local_commit_bot.py
"""

from __future__ import annotations

import os
import sys
import logging
import traceback
from typing import Optional, List

from git import Repo, InvalidGitRepositoryError, NoSuchPathError, BadName
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHAT_ID: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")
REPO_PATH: str = os.getenv("LOCAL_REPO_PATH", ".")

try:
    POLL_INTERVAL_SECONDS: float = float(os.getenv("POLL_INTERVAL_SECONDS", "10"))
except ValueError:
    POLL_INTERVAL_SECONDS = 10.0


# Runtime state: the most recent commit hash we have observed (or None until
# the first poll synchronises the baseline).
last_reported_commit: Optional[str] = None


# Telegram caps single text messages at 4096 chars. We trim the body well
# below that to leave headroom for Markdown parsing and header lines.
TELEGRAM_MAX_MESSAGE_CHARS = 3900


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("local_commit_bot")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _escape_for_code_block(text: str) -> str:
    """Neutralise stray triple-backticks inside text wrapped in a code fence.

    Telegram's parser will close the outer code fence if it encounters an
    unmatched ``` inside the content. We replace internal triple-backticks
    with a visually similar but parser-safe sequence.
    """
    return text.replace("```", "ʼʼʼ")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _format_files_block(changed_files: List[str]) -> str:
    if not changed_files:
        return ""
    head = changed_files[:5]
    body = "\n".join(f"  • {f}" for f in head)
    if len(changed_files) > 5:
        body += f"\n  • ... and {len(changed_files) - 5} more files."
    return _escape_for_code_block(body)


def _build_notification(repo_name: str, short_hash: str, author: str,
                        message: str, changed_files: List[str]) -> str:
    safe_author = _escape_for_code_block(author)
    safe_message = _escape_for_code_block(_truncate(message, 1500))
    files_block = _format_files_block(changed_files)

    parts: List[str] = [
        "🚀 *LOCAL COMMIT BROADCAST*",
        "",
        f"📁 *Repo:* `{_escape_for_code_block(repo_name)}`",
        f"🆔 *Commit:* `{_escape_for_code_block(short_hash)}`",
        f"👤 *Author:* `{safe_author}`",
        "",
        f"📝 *Message:*\n```text\n{safe_message}\n```",
    ]
    if files_block:
        parts.append(f"🛠️ *Modified Files:*\n```text\n{files_block}\n```")
    text = "\n".join(parts)
    return _truncate(text, TELEGRAM_MAX_MESSAGE_CHARS)


# --------------------------------------------------------------------------- #
# Job
# --------------------------------------------------------------------------- #

async def check_local_commits_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Periodic worker: detect new commits in the local repo and notify."""
    global last_reported_commit

    try:
        repo = Repo(REPO_PATH)
    except (InvalidGitRepositoryError, NoSuchPathError) as exc:
        log.error("Path '%s' is not a valid git repository: %s", REPO_PATH, exc)
        return
    except Exception as exc:  # pragma: no cover - defensive
        log.error("Failed to open repository at '%s': %s\n%s",
                  REPO_PATH, exc, traceback.format_exc())
        return

    try:
        if not repo.head.is_valid():
            return  # Empty or unborn HEAD — nothing to broadcast.

        latest_commit = repo.head.commit
        current_hash = latest_commit.hexsha
    except (BadName, Exception) as exc:
        # BadName happens on a corrupt HEAD reference; any other exception we
        # log and skip this cycle so the watcher keeps running.
        log.error("Could not read HEAD: %s", exc)
        return

    # Initial baseline sync: do not flood the chat with history on startup.
    if last_reported_commit is None:
        last_reported_commit = current_hash
        log.info("[INIT] Baseline sync to local commit %s", current_hash[:7])
        return

    if current_hash == last_reported_commit:
        return  # No change.

    # New commit detected — update state BEFORE attempting to send so that
    # a transient Telegram outage does not cause duplicate notifications on
    # the next cycle.
    last_reported_commit = current_hash

    try:
        author = latest_commit.author.name or "(unknown author)"
        message = (latest_commit.message or "").strip()
        short_hash = current_hash[:7]
        repo_name = os.path.basename(os.path.abspath(REPO_PATH))

        changed_files: List[str] = []
        try:
            if latest_commit.parents:
                diffs = latest_commit.diff(latest_commit.parents[0])
                changed_files = [d.a_path for d in diffs if d.a_path]
        except Exception as exc:
            log.warning("Could not compute diff for %s: %s", short_hash, exc)

        text = _build_notification(repo_name, short_hash, author,
                                   message, changed_files)

        await context.bot.send_message(
            chat_id=TARGET_CHAT_ID,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
        log.info("[BROADCAST] Sent notification for commit %s", short_hash)

    except Exception as exc:
        # If Telegram is unreachable we keep the new commit marked as
        # reported (state already advanced above) so we don't replay it
        # forever; the operator will see the failure in stderr.
        log.error("Broadcast failed for commit %s: %s",
                  current_hash[:7], exc)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledge the bot is alive and report the watched repo."""
    if update.message is None:
        return
    await update.message.reply_text(
        "🤖 Commit Watcher Active.\n"
        f"Monitoring local repo: `{_escape_for_code_block(os.path.abspath(REPO_PATH))}`\n"
        f"Polling every {POLL_INTERVAL_SECONDS:g}s.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report the last broadcast commit (for sanity-checking the watcher)."""
    if update.message is None:
        return
    if last_reported_commit:
        await update.message.reply_text(
            f"📡 Last observed commit: `{_escape_for_code_block(last_reported_commit[:12])}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text("📡 No commit observed yet (baseline not yet synced).")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> int:
    if not TOKEN:
        print("[CRITICAL] TELEGRAM_BOT_TOKEN is not set.", file=sys.stderr)
        return 1
    if not TARGET_CHAT_ID:
        print("[CRITICAL] TELEGRAM_CHAT_ID is not set.", file=sys.stderr)
        return 1

    abs_repo = os.path.abspath(REPO_PATH)
    if not os.path.isdir(abs_repo):
        print(f"[CRITICAL] LOCAL_REPO_PATH does not exist: {abs_repo}",
              file=sys.stderr)
        return 1
    if not os.path.isdir(os.path.join(abs_repo, ".git")) and \
       not os.path.isfile(os.path.join(abs_repo, "HEAD")):
        # Plain "gitdir: ..." file or .git directory both qualify.
        print(f"[CRITICAL] LOCAL_REPO_PATH is not a git repo: {abs_repo}",
              file=sys.stderr)
        return 1

    log.info("🤖 Bot loop engaged. Targeting local path: %s", abs_repo)
    log.info("   Polling interval: %.1fs", POLL_INTERVAL_SECONDS)

    app = ApplicationBuilder().token(TOKEN).build()

    # JobQueue: first=1 starts the first scan one second after startup
    # (gives the event loop a beat to settle). Subsequent runs every N seconds.
    app.job_queue.run_repeating(
        check_local_commits_job,
        interval=POLL_INTERVAL_SECONDS,
        first=1,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status_cmd))

    app.run_polling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
