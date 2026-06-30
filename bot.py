"""
=========================================================
 Telegram Video Encoder Bot
 - Superfast re-encode (NVENC/x264 ultrafast preset)
 - Vibrant color grading
 - Metadata wipe/change
 - Realtime % progress
 Developer Credit: RH.RATUL
=========================================================
"""

import os
import re
import time
import shutil
import asyncio
import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

# ---------------------------------------------------------
# CONFIG  (Railway -> Variables tab e ei value gula set korben)
# ---------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

DEV_CREDIT = "RH.RATUL"
WORK_DIR = "downloads"
os.makedirs(WORK_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("videobot")

app = Client(
    "video_encoder_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ---------------------------------------------------------
# Helper: human readable size / time
# ---------------------------------------------------------
def human_size(num: float) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num < 1024:
            return f"{num:.2f}{unit}"
        num /= 1024
    return f"{num:.2f}TB"


def human_time(seconds: int) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def progress_bar(percent: float, length: int = 20) -> str:
    filled = int(length * percent / 100)
    return "█" * filled + "░" * (length - filled)


# ---------------------------------------------------------
# Pyrogram download/upload progress callback
# ---------------------------------------------------------
last_edit_time = {}

async def tg_progress(current, total, message: Message, label: str):
    chat_key = message.chat.id
    now = time.time()
    # throttle edits to ~ every 2 seconds to avoid flood limits
    if chat_key in last_edit_time and now - last_edit_time[chat_key] < 2:
        return
    last_edit_time[chat_key] = now

    percent = current * 100 / total if total else 0
    text = (
        f"**{label}**\n"
        f"`{progress_bar(percent)}` {percent:.1f}%\n"
        f"{human_size(current)} / {human_size(total)}\n\n"
        f"⚙️ Dev: {DEV_CREDIT}"
    )
    try:
        await message.edit_text(text)
    except Exception:
        pass


# ---------------------------------------------------------
# FFmpeg encode with realtime progress parsing
# ---------------------------------------------------------
async def ffmpeg_encode(input_path: str, output_path: str, duration: float, status_msg: Message):
    """
    - ultrafast preset for speed
    - vibrant color grading via eq + vibrance-like saturation boost
    - metadata stripped & replaced with custom tag
    """
    vf_filter = (
        "eq=contrast=1.08:brightness=0.02:saturation=1.35:gamma=1.02,"
        "unsharp=3:3:0.5"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-map_metadata", "-1",          # strip all original metadata
        "-metadata", f"title=Encoded by {DEV_CREDIT}",
        "-metadata", f"comment=Processed via {DEV_CREDIT} VideoBot",
        "-metadata", f"encoder={DEV_CREDIT}",
        "-progress", "pipe:1",
        "-nostats",
        output_path,
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    last_edit = 0
    time_pattern = re.compile(r"out_time_ms=(\d+)")
    start = time.time()

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        line = line.decode("utf-8", errors="ignore").strip()

        match = time_pattern.search(line)
        if match and duration > 0:
            out_time_sec = int(match.group(1)) / 1_000_000
            percent = min(out_time_sec / duration * 100, 100)

            now = time.time()
            if now - last_edit >= 2:
                last_edit = now
                elapsed = now - start
                eta = (elapsed / percent * (100 - percent)) if percent > 1 else 0
                text = (
                    f"🎬 **Encoding Video...**\n"
                    f"`{progress_bar(percent)}` {percent:.1f}%\n"
                    f"⏱ Elapsed: {human_time(elapsed)} | ETA: {human_time(eta)}\n"
                    f"🎨 Vibrant Color Grading: ON\n"
                    f"🧹 Metadata: Cleaned & Re-tagged\n\n"
                    f"⚙️ Dev: {DEV_CREDIT}"
                )
                try:
                    await status_msg.edit_text(text)
                except Exception:
                    pass

    await process.wait()
    return process.returncode == 0


# ---------------------------------------------------------
# Get video duration via ffprobe
# ---------------------------------------------------------
async def get_duration(path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ]
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await process.communicate()
    try:
        return float(out.decode().strip())
    except Exception:
        return 0.0


# ---------------------------------------------------------
# /start command
# ---------------------------------------------------------
@app.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    await message.reply_text(
        f"👋 **স্বাগতম!**\n\n"
        f"আমাকে যেকোনো ভিডিও **পাঠান বা ফরওয়ার্ড করুন** (200-300MB ঠিক আছে)।\n"
        f"আমি সেটা:\n"
        f"🚀 সুপারফাস্ট রি-এনকোড করবো\n"
        f"🎨 ভাইব্রেন্ট কালার গ্রেডিং দিবো\n"
        f"🧹 মেটাডেটা ক্লিন করে নতুন ট্যাগ লাগাবো\n"
        f"📊 রিয়েলটাইম % প্রগ্রেস দেখাবো\n\n"
        f"⚙️ **Developer Credit: {DEV_CREDIT}**"
    )


# ---------------------------------------------------------
# Main video handler
# ---------------------------------------------------------
@app.on_message(filters.video | filters.document)
async def video_handler(client: Client, message: Message):
    media = message.video or message.document
    if media is None:
        return

    # if it's a document, make sure it's a video mime type
    if message.document and not (message.document.mime_type or "").startswith("video"):
        return

    user_dir = os.path.join(WORK_DIR, str(message.chat.id))
    os.makedirs(user_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = os.path.join(user_dir, f"in_{timestamp}.mp4")
    output_path = os.path.join(user_dir, f"out_{timestamp}.mp4")

    status_msg = await message.reply_text(
        f"📥 **Downloading...**\n`{progress_bar(0)}` 0.0%\n\n⚙️ Dev: {DEV_CREDIT}"
    )

    try:
        # ---------- DOWNLOAD ----------
        await client.download_media(
            message,
            file_name=input_path,
            progress=tg_progress,
            progress_args=(status_msg, "📥 Downloading"),
        )

        await status_msg.edit_text(f"🔍 Analyzing video...\n\n⚙️ Dev: {DEV_CREDIT}")
        duration = await get_duration(input_path)

        # ---------- ENCODE ----------
        ok = await ffmpeg_encode(input_path, output_path, duration, status_msg)

        if not ok or not os.path.exists(output_path):
            await status_msg.edit_text(f"❌ Encoding failed.\n\n⚙️ Dev: {DEV_CREDIT}")
            return

        await status_msg.edit_text(f"📤 **Uploading...**\n`{progress_bar(0)}` 0.0%\n\n⚙️ Dev: {DEV_CREDIT}")

        out_size = os.path.getsize(output_path)

        # ---------- UPLOAD ----------
        await client.send_video(
            chat_id=message.chat.id,
            video=output_path,
            caption=(
                f"✅ **Done!**\n"
                f"📦 Size: {human_size(out_size)}\n"
                f"🎨 Color Grade: Vibrant\n"
                f"🧹 Metadata: Cleaned\n\n"
                f"⚙️ **Developer Credit: {DEV_CREDIT}**"
            ),
            progress=tg_progress,
            progress_args=(status_msg, "📤 Uploading"),
        )

        await status_msg.delete()

    except Exception as e:
        log.exception("Error processing video")
        await status_msg.edit_text(f"❌ Error: `{e}`\n\n⚙️ Dev: {DEV_CREDIT}")

    finally:
        # cleanup
        for p in (input_path, output_path):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass


if __name__ == "__main__":
    log.info(f"Bot starting... Developer Credit: {DEV_CREDIT}")
    app.run()
