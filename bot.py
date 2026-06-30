"""
=========================================================
  RH.RATUL VIDEO PROCESSOR BOT
  Developer Credit: RH.RATUL
=========================================================
"""

import os
import re
import asyncio
import logging
import subprocess
import tempfile
import time
import uuid

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
LOCAL_API_URL = os.environ.get("LOCAL_API_URL", "").rstrip("/")
DEVELOPER_CREDIT = "RH.RATUL"

MAX_VIDEO_MB = 1900 if LOCAL_API_URL else 19

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("rh-ratul-bot")


def build_filter_chain(width_expr="iw", height_expr="ih"):
    return (
        "eq=contrast=1.07:saturation=1.15:brightness=0.02,"
        "colorbalance=rs=0.08:gs=0.02:bs=-0.06:"
        "rm=0.06:gm=0.0:bm=-0.04:"
        "rh=0.03:gh=0.0:bh=-0.02,"
        "vignette=PI/5,"
        f"drawtext=text='{DEVELOPER_CREDIT}':"
        "fontcolor=white@0.55:fontsize=h*0.025:"
        "x=w-tw-12:y=h-th-12:"
        "box=1:boxcolor=black@0.25:boxborderw=6"
    )


TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+\.\d+)")


def _to_seconds(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


async def probe_duration(input_path: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        input_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except Exception:
        return 0.0


async def run_ffmpeg_with_progress(cmd, total_duration, on_progress):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    last_reported = -1
    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        text = line.decode(errors="ignore")
        match = TIME_RE.search(text)
        if match and total_duration > 0:
            current = _to_seconds(*match.groups())
            percent = min(99, int((current / total_duration) * 100))
            if percent != last_reported:
                last_reported = percent
                await on_progress(percent)

    await proc.wait()
    return proc.returncode


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 স্বাগতম! আমাকে যেকোনো ভিডিও পাঠান বা ফরওয়ার্ড করুন।\n\n"
        f"আমি করব:\n"
        f"⚡ সুপারফাস্ট রি-এনকোড\n"
        f"🎨 সিনেমাটিক/উষ্ণ কালার গ্রেডিং\n"
        f"🏷 মেটাডেটা পরিবর্তন\n"
        f"📊 রিয়েলটাইম প্রগ্রেস %\n\n"
        f"🔰 Developer Credit: {DEVELOPER_CREDIT}",
        parse_mode=ParseMode.HTML,
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    video = message.video or message.document
    if video is None:
        return

    if getattr(video, "file_size", None) and video.file_size > MAX_VIDEO_MB * 1024 * 1024:
        if LOCAL_API_URL:
            await message.reply_text(f"⚠️ ভিডিওটি {MAX_VIDEO_MB}MB এর চেয়ে বড়, প্রসেস করা যাচ্ছে না।")
        else:
            await message.reply_text(
                "⚠️ ভিডিওটি অনেক বড় (Cloud Bot API লিমিট ~20MB)।\n"
                "২GB পর্যন্ত ভিডিও প্রসেস করতে Local Bot API Server সেটআপ করতে হবে।"
            )
        return

    status_msg = await message.reply_text("📥 ভিডিও ডাউনলোড হচ্ছে... 0%")

    job_id = uuid.uuid4().hex[:8]
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, f"in_{job_id}.mp4")
        output_path = os.path.join(tmpdir, f"out_{job_id}.mp4")

        tg_file = await video.get_file()
        await tg_file.download_to_drive(input_path)
        await status_msg.edit_text("✅ ডাউনলোড সম্পন্ন।\n🔍 ভিডিও বিশ্লেষণ হচ্ছে...")

        duration = await probe_duration(input_path)

        filter_chain = build_filter_chain()
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", filter_chain,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "21",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            "-metadata", f"title=Processed by {DEVELOPER_CREDIT}",
            "-metadata", "artist=RH.RATUL",
            "-metadata", "comment=Edited & Color Graded by RH.RATUL Bot",
            "-metadata", "encoder=RH.RATUL-Engine",
            output_path,
        ]

        last_edit_time = [0.0]

        async def on_progress(percent):
            now = time.time()
            if now - last_edit_time[0] < 1.5 and percent < 99:
                return
            last_edit_time[0] = now
            bar_filled = percent // 5
            bar = "▰" * bar_filled + "▱" * (20 - bar_filled)
            try:
                await status_msg.edit_text(
                    f"⚙️ প্রসেসিং চলছে...\n"
                    f"{bar}  {percent}%\n\n"
                    f"🎨 কালার গ্রেডিং: সিনেমাটিক/উষ্ণ\n"
                    f"🔰 {DEVELOPER_CREDIT}"
                )
            except Exception:
                pass

        await status_msg.edit_text("⚙️ এনকোডিং শুরু হচ্ছে... 0%")
        try:
            returncode = await run_ffmpeg_with_progress(cmd, duration, on_progress)
        except FileNotFoundError:
            await status_msg.edit_text("❌ সার্ভারে ffmpeg ইনস্টল নেই। হোস্টিং বিল্ড কনফিগ চেক করুন।")
            return

        if returncode != 0 or not os.path.exists(output_path):
            await status_msg.edit_text("❌ প্রসেসিং ব্যর্থ হয়েছে, আবার চেষ্টা করুন।")
            return

        await status_msg.edit_text("📤 প্রসেসড ভিডিও আপলোড হচ্ছে... 100%")

        with open(output_path, "rb") as f:
            await message.reply_video(
                video=f,
                caption=(
                    f"✅ প্রসেসিং সম্পন্ন!\n"
                    f"🎨 কালার গ্রেড: সিনেমাটিক/উষ্ণ\n"
                    f"🏷 মেটাডেটা: পরিবর্তিত\n\n"
                    f"🔰 Developer Credit: {DEVELOPER_CREDIT}"
                ),
                supports_streaming=True,
            )

        await status_msg.delete()


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)


def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN পরিবেশ ভ্যারিয়েবল সেট করা নেই।")

    builder = Application.builder().token(BOT_TOKEN)
    if LOCAL_API_URL:
        builder = builder.base_url(f"{LOCAL_API_URL}/bot").base_file_url(f"{LOCAL_API_URL}/file/bot")
        logger.info(f"Local Bot API Server ব্যবহার হচ্ছে: {LOCAL_API_URL}")
    else:
        logger.warning("LOCAL_API_URL সেট নেই — Cloud Bot API লিমিট প্রযোজ্য হবে")

    app = builder.build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_error_handler(error_handler)

    logger.info(f"Bot starting... Developer Credit: {DEVELOPER_CREDIT}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
