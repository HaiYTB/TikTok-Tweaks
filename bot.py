import os
import sys
import re
import logging
import tempfile
import asyncio
import uuid
import urllib.parse
from typing import Dict, Any, Optional

# Đảm bảo console Windows hỗ trợ Emoji và tiếng Việt UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    ChatMemberUpdated,
    constants
)
from telegram.request import HTTPXRequest
from telegram.error import Conflict
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ContextTypes,
    filters
)

import config
import database
from tiktok_api import (
    fetch_tiktok_video,
    fetch_instagram_media,
    fetch_author_recent_12_videos,
    get_download_url_by_quality,
    download_file_to_path,
    download_thumbnail_to_path
)
from multi_platform_api import (
    classify_media_url,
    fetch_youtube_media,
    download_youtube_to_path,
    fetch_twitter_media,
    download_twitter_to_path,
    fetch_pinterest_media,
    download_pinterest_to_path,
    fetch_spotify_track,
    download_mp3_320kbps
)
from shazam_service import (
    identify_song_from_path,
    build_shazam_card,
    SHAZAM_CACHE
)
from stats_formatter import (
    build_video_stats_message,
    build_profile_analytics_message,
    build_similar_videos_message,
    build_user_info_message,
    build_instagram_stats_message,
    build_youtube_stats_message,
    build_twitter_stats_message,
    build_pinterest_stats_message,
    build_spotify_stats_message,
    build_user_profile_stats_message
)

# Cấu hình logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cache tạm thời dữ liệu media tránh gọi API lặp lại
MEDIA_CACHE: Dict[str, Dict[str, Any]] = {}

def get_caption_text(title: str, author_name: str, platform_name: str, user_settings: Dict[str, Any]) -> str:
    """Tạo chú thích đính kèm file tải theo cài đặt cá nhân (Caption Mode & No Signature)."""
    caption_mode = user_settings.get("caption_mode", "full")
    no_sig = user_settings.get("no_signature", 0)

    if caption_mode == "none":
        return ""

    title_clean = (title or "Media File")[:120]
    author_clean = author_name or "Creator"

    if caption_mode == "minimal":
        caption = f"🎬 <b>{title_clean}</b>"
    else:
        caption = (
            f"🎬 <b>{title_clean}</b>\n"
            f"👤 <code>{author_clean}</code> | 🌐 {platform_name}"
        )

    if not no_sig:
        caption += "\n\n🤖 <i>Tải bởi @TikTok_Tweaks_Bot</i>"

    return caption

# ==============================================================
# Telegram Command Handlers
# ==============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /start: Chào mừng và menu điều hướng (hỗ trợ cả nhóm chat & tin nhắn riêng)."""
    if not update.effective_chat or not update.message:
        return

    is_group = update.effective_chat.type in (constants.ChatType.GROUP, constants.ChatType.SUPERGROUP)
    user = update.effective_user
    user_id = user.id if user else 0
    username = user.username or ""
    full_name = user.full_name or "Bạn"

    # Ghi nhận người dùng vào DB
    database.get_or_create_user(user_id, username, full_name)

    if is_group:
        group_text = (
            "👑 <b>TikTok Tweaks Bot</b> • <i>Group Assistant</i>\n"
            "Tải video TikTok 120fps, YouTube 4K, IG, X, Pinterest & Spotify 320k.\n"
            "👉 <i>Gửi link trực tiếp vào nhóm để tải tự động!</i>"
        )
        keyboard = [
            [
                InlineKeyboardButton("📱 Profile", callback_data=f"user_profile:{user_id}"),
                InlineKeyboardButton("⚙️ Cài đặt nhóm", callback_data="group_settings_menu")
            ]
        ]
        await update.message.reply_text(group_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # Giao diện /start trong tin nhắn riêng
    welcome_text = (
        "👑 <b>TikTok Tweaks Bot</b>\n"
        "Tải video gốc TikTok (120fps, HEVC), YouTube 4K, IG, X, Pinterest & Spotify 320k.\n\n"
        "💡 <i>Gửi link trực tiếp để tải, hoặc dùng <code>/check &lt;link&gt;</code> để kiểm tra.</i>"
    )
    keyboard = [
        [
            InlineKeyboardButton("🔍 Check", callback_data="check_help"),
            InlineKeyboardButton("🔀 Chế độ", callback_data="mode_menu"),
            InlineKeyboardButton("📱 Profile", callback_data=f"user_profile:{user_id}")
        ],
        [
            InlineKeyboardButton("⚙️ Cài đặt", callback_data="settings_menu"),
            InlineKeyboardButton("🎧 Shazam", callback_data="shazam_info"),
            InlineKeyboardButton("📖 Hướng dẫn", callback_data="help_menu")
        ]
    ]
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=constants.ParseMode.HTML
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /help: Hướng dẫn sử dụng chi tiết tất cả nền tảng."""
    help_text = (
        "📖 <b>Command & Feature Guide</b>\n\n"
        "<b>Commands</b>\n"
        "• <code>/check &lt;url or @user&gt;</code> — Inspect video stream specs, VQScore, or creator analytics\n"
        "• <code>/mode</code> — Switch between Hybrid (interactive menu), Downloader (instant), and Checker\n"
        "• <code>/profile</code> — View real usage statistics and open Telegram Mini App\n"
        "• <code>/settings</code> — Configure Document mode, caption formats, and language\n"
        "• <code>/shazam</code> — Audio recognition instructions\n"
        "• <code>/group_settings</code> — Manage auto-download and silent mode in group chats\n\n"
        "<b>Downloader & Inspector</b>\n"
        "• <b>TikTok:</b> Original H.265/AVC stream, 120 FPS, audio track, VQScore rating\n"
        "• <b>YouTube:</b> 4K Ultra HD, 1080p FHD, 720p, or standalone MP3 320 kbps\n"
        "• <b>Instagram:</b> Clean Reels, Posts, and Stories without watermark\n"
        "• <b>Twitter/X & Pinterest:</b> Highest resolution video and HD images\n"
        "• <b>Spotify:</b> Studio-quality MP3 320 kbps with metadata & cover art\n\n"
        "<b>Music Recognition (Shazam)</b>\n"
        "Forward or send any voice message, circular video note, or video clip directly to the chat."
    )
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")]]
    if update.message:
        await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /mode: Chọn giữa 3 chế độ (Hybrid, Downloader, Checker)."""
    user_id = update.effective_user.id if update.effective_user else 0
    user_data = database.get_or_create_user(user_id)
    current_mode = user_data.get("mode", config.DEFAULT_MODE)

    mode_text = (
        f"🔀 <b>Chế độ hoạt động:</b> <b>{current_mode.upper()}</b>\n\n"
        "• <b>Hybrid:</b> Bảng điều khiển tải & kiểm tra thông số.\n"
        "• <b>Downloader:</b> Tải ngay chất lượng gốc không cần bấm nút.\n"
        "• <b>Checker:</b> Phân tích chuyên sâu codec, bitrate, VQScore."
    )
    keyboard = [
        [
            InlineKeyboardButton(f"{'✅ ' if current_mode == 'hybrid' else ''}🔄 Hybrid", callback_data="set_mode:hybrid"),
            InlineKeyboardButton(f"{'✅ ' if current_mode == 'downloader' else ''}⚡ Tải ngay", callback_data="set_mode:downloader"),
            InlineKeyboardButton(f"{'✅ ' if current_mode == 'checker' else ''}🔍 Checker", callback_data="set_mode:checker")
        ],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data="back_to_start")]
    ]
    if update.message:
        await update.message.reply_text(mode_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /settings: Tùy chỉnh cài đặt cá nhân."""
    user_id = update.effective_user.id if update.effective_user else 0
    user_data = database.get_or_create_user(user_id)
    quality = user_data.get("quality", "original").upper()
    doc_mode = "BẬT" if user_data.get("doc_mode") else "TẮT"
    no_sig = "BẬT" if user_data.get("no_signature") else "TẮT"
    reply_mode = (user_data.get("reply_mode") or "direct").capitalize()
    caption_mode = (user_data.get("caption_mode") or "full").capitalize()

    settings_text = (
        f"⚙️ <b>Cài đặt cá nhân</b>\n"
        f"• File gốc: <b>{doc_mode}</b> • Không chữ ký: <b>{no_sig}</b>\n"
        f"• Phản hồi: <b>{reply_mode}</b> • Caption: <b>{caption_mode}</b>"
    )
    keyboard = [
        [
            InlineKeyboardButton(f"📁 Doc: {doc_mode}", callback_data="toggle_opt:doc_mode"),
            InlineKeyboardButton(f"🛡️ No-Sig: {no_sig}", callback_data="toggle_opt:no_signature"),
            InlineKeyboardButton(f"💬 Gửi: {reply_mode}", callback_data="cycle_opt:reply_mode")
        ],
        [
            InlineKeyboardButton(f"📝 Chữ: {caption_mode}", callback_data="cycle_opt:caption_mode"),
            InlineKeyboardButton("🔀 Chế độ", callback_data="mode_menu"),
            InlineKeyboardButton("📱 Profile", callback_data=f"user_profile:{user_id}")
        ]
    ]
    if update.message:
        await update.message.reply_text(settings_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /profile & /webapp: Xem hồ sơ số liệu thực tế và mở Mini App."""
    user = update.effective_user
    if not user:
        return
    user_id = user.id
    user_data = database.get_or_create_user(user_id, user.username or "", user.full_name or "")
    profile_msg = build_user_profile_stats_message(user_data)

    buttons = []
    # Nếu có WEBAPP_URL, tích hợp WebAppInfo
    if config.WEBAPP_URL and config.WEBAPP_URL.startswith("https://"):
        webapp_link = (
            f"{config.WEBAPP_URL}?user_id={user_id}"
            f"&name={urllib.parse.quote(user.full_name or 'User')}"
            f"&username={urllib.parse.quote(user.username or '')}"
            f"&dl={user_data.get('total_downloads', 0)}"
            f"&ck={user_data.get('total_checks', 0)}"
            f"&sh={user_data.get('total_shazams', 0)}"
            f"&tt={user_data.get('dl_tiktok', 0)}"
            f"&ig={user_data.get('dl_instagram', 0)}"
            f"&yt={user_data.get('dl_youtube', 0)}"
            f"&tw={user_data.get('dl_twitter', 0)}"
            f"&pin={user_data.get('dl_pinterest', 0)}"
            f"&sp={user_data.get('dl_spotify', 0)}"
            f"&lang={user_data.get('language', 'vi')}"
            f"&reply={user_data.get('reply_mode', 'direct')}"
            f"&caption={user_data.get('caption_mode', 'full')}"
            f"&doc={user_data.get('doc_mode', 0)}"
            f"&nosig={user_data.get('no_signature', 0)}"
        )
        buttons.append([InlineKeyboardButton("📱 Mở Mini App (Full Screen)", web_app=WebAppInfo(url=webapp_link))])

    # Nút chuyển đổi tương tác trực tiếp trong Telegram (2 hàng gọn gàng)
    buttons.append([
        InlineKeyboardButton(f"📁 Doc: {'BẬT' if user_data.get('doc_mode') else 'TẮT'}", callback_data="toggle_opt:doc_mode"),
        InlineKeyboardButton(f"🛡️ No-Sig: {'BẬT' if user_data.get('no_signature') else 'TẮT'}", callback_data="toggle_opt:no_signature"),
        InlineKeyboardButton(f"💬 Gửi: {(user_data.get('reply_mode') or 'direct').capitalize()}", callback_data="cycle_opt:reply_mode")
    ])
    buttons.append([
        InlineKeyboardButton(f"📝 Chữ: {(user_data.get('caption_mode') or 'full').capitalize()}", callback_data="cycle_opt:caption_mode"),
        InlineKeyboardButton("🔄 Làm mới", callback_data=f"user_profile:{user_id}"),
        InlineKeyboardButton("❌ Đóng", callback_data="close_box")
    ])

    if update.message:
        await update.message.reply_text(profile_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)

async def group_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /group_settings: Dành cho quản trị viên cấu hình nhóm."""
    chat = update.effective_chat
    if not chat or chat.type not in (constants.ChatType.GROUP, constants.ChatType.SUPERGROUP):
        if update.message:
            await update.message.reply_text("💡 Lệnh này chỉ sử dụng được trong Nhóm Chat (Groups).")
        return

    group_data = database.get_group_settings(chat.id, chat.title or "")
    auto_dl = "✅ BẬT" if group_data.get("auto_download") else "❌ TẮT"
    silent = "✅ BẬT" if group_data.get("silent_mode") else "❌ TẮT"

    msg = (
        f"👥 <b>Cài đặt nhóm: {chat.title}</b>\n"
        f"• Tự động tải: <b>{auto_dl}</b> • Gửi im lặng: <b>{silent}</b>"
    )
    keyboard = [
        [
            InlineKeyboardButton(f"⚡ Tự động tải: {auto_dl}", callback_data=f"toggle_grp:auto_download:{chat.id}"),
            InlineKeyboardButton(f"🔕 Gửi im lặng: {silent}", callback_data=f"toggle_grp:silent_mode:{chat.id}")
        ],
        [InlineKeyboardButton("❌ Đóng", callback_data="close_box")]
    ]
    if update.message:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)

async def shazam_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /shazam: Hướng dẫn nhận diện nhạc."""
    text = (
        "🎧 <b>Shazam Music Recognition</b>\n\n"
        "Identify music from any audio or video source:\n\n"
        "1. 🎤 <b>Voice Message:</b> Record audio or hum a melody and send it.\n"
        "2. 📹 <b>Video Note / Video Clip:</b> Forward or upload any video containing music.\n"
        "3. 🎵 <b>Audio File:</b> Send an MP3, AAC, or voice clip.\n"
        "4. 🎬 <b>Interactive Button:</b> Click '🎧 Shazam' on any video inspector card.\n\n"
        "<i>Includes direct links to Spotify, Apple Music, YouTube Music, and 320 kbps MP3 download!</i>"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode=constants.ParseMode.HTML)

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lệnh /check [url/@username]: Phân tích chuyên sâu thông số video, codec, bitrate, VQScore, tài khoản."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0

    target_text = ""
    if context.args:
        target_text = " ".join(context.args).strip()
    elif update.message.reply_to_message:
        reply_msg = update.message.reply_to_message
        target_text = (reply_msg.text or reply_msg.caption or "").strip()

    if not target_text:
        help_msg = (
            "🔍 <b>Video & Creator Inspector</b>\n\n"
            "Analyze video streams, MP4 headers, real codecs, bitrates, and creator metrics.\n\n"
            "<b>Usage:</b>\n"
            "• <code>/check &lt;TikTok/YouTube/IG Link&gt;</code>\n"
            "• <code>/check @username</code> (Analyze creator's last 12 videos)\n"
            "• Reply to any message containing a link with <code>/check</code>\n\n"
            "<b>Supported Platforms:</b>\n"
            "• <b>TikTok:</b> Full VQScore, 120 FPS, H.265/H.264 streams, exact counts\n"
            "• <b>TikTok Accounts:</b> 12-video performance analytics & engagement rate\n"
            "• <b>YouTube:</b> 4K check, stream formats, duration, views\n"
            "• <b>Instagram:</b> Reels resolution, audio, interaction stats"
        )
        await update.message.reply_text(help_msg, parse_mode=constants.ParseMode.HTML)
        return

    # 1. Kiểm tra nếu là TikTok username (ví dụ: @mihchiet01 hoặc mihchiet01 hoặc link profile tiktok.com/@username)
    username_match = re.search(r'(?:https?://(?:www\.)?tiktok\.com/)?@([a-zA-Z0-9_.-]{3,30})', target_text)
    is_pure_user = target_text.startswith("@") or ("/video/" not in target_text and "/t/" not in target_text and "/@" in target_text)

    # Phân loại link media
    media_url, platform = classify_media_url(target_text)

    # Nếu không phải link video nhưng là username hoặc link profile
    if not media_url and (is_pure_user or (username_match and not target_text.startswith("http"))):
        uname = (username_match.group(1) if username_match else target_text.lstrip("@")).strip()
        status_msg = await update.message.reply_text(
            f"⏳ <b>Đang phân tích kênh @{uname} và 12 video gần nhất...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        videos = await fetch_author_recent_12_videos(uname)
        if not videos:
            await status_msg.edit_text(f"❌ Không thể phân tích tài khoản @{uname} (Kênh có thể ở chế độ riêng tư hoặc bị giới hạn).")
            return
        database.record_check(user_id)
        profile_msg = build_profile_analytics_message(uname, f"@{uname}", videos)
        await status_msg.edit_text(profile_msg, parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True)
        return

    if not media_url or not platform:
        await update.message.reply_text(
            "❌ <b>Link không hợp lệ.</b>\nVui lòng cung cấp link video TikTok, YouTube, Instagram hoặc username TikTok (@user).",
            parse_mode=constants.ParseMode.HTML
        )
        return

    # 2. Check TikTok Video
    if platform in ("tiktok_video", "tiktok_music"):
        status_msg = await update.message.reply_text(
            "⏳ <b>Inspecting TikTok stream, decoding MP4 header & VQScore...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        success, data, err_msg = await fetch_tiktok_video(media_url)
        if not success or not data:
            await status_msg.edit_text(f"❌ {err_msg or 'Failed to inspect TikTok video.'}")
            return

        video_id = str(data.get("id") or uuid.uuid4().hex[:8])
        data["_source_url"] = media_url
        MEDIA_CACHE[video_id] = {"data": data, "time": asyncio.get_event_loop().time(), "type": "tiktok"}
        database.record_check(user_id)

        meta = data.get("_meta") or {}
        app_size_mb = meta.get("app_size_mb", 0)
        browser_size_mb = meta.get("browser_size_mb", 0)

        tt_msg = build_video_stats_message(data)
        buttons = [
            [
                InlineKeyboardButton(f"📥 Gốc ({app_size_mb:.1f}M)", callback_data=f"dl_tt:original:{video_id}"),
                InlineKeyboardButton(f"⚡ Web ({browser_size_mb:.1f}M)", callback_data=f"dl_tt:standard:{video_id}"),
                InlineKeyboardButton("🎵 Nhạc", callback_data=f"dl_tt_audio:{video_id}")
            ],
            [
                InlineKeyboardButton("📁 Doc", callback_data=f"dl_tt_doc:{video_id}"),
                InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{video_id}"),
                InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_tt:{video_id}"),
                InlineKeyboardButton("📊 Kênh", callback_data=f"profile:{data.get('author', {}).get('unique_id', '')}")
            ]
        ]
        await status_msg.edit_text(tt_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # 3. Check YouTube
    if platform == "youtube":
        status_msg = await update.message.reply_text("⏳ <b>Inspecting YouTube stream specs...</b>", parse_mode=constants.ParseMode.HTML)
        ok, yt_data, err = await fetch_youtube_media(media_url)
        if not ok or not yt_data:
            await status_msg.edit_text(f"❌ {err or 'Failed to inspect YouTube media.'}")
            return
        yt_id = uuid.uuid4().hex[:8]
        MEDIA_CACHE[yt_id] = {"data": yt_data, "time": asyncio.get_event_loop().time(), "type": "youtube"}
        database.record_check(user_id)

        yt_msg = build_youtube_stats_message(yt_data)
        buttons = []
        fmt_row = []
        for f in yt_data.get("formats", [])[:3]:
            fmt_row.append(InlineKeyboardButton(f"{f['res']}", callback_data=f"dl_yt:{yt_id}:{f['format_id']}:{f['res']}"))
        fmt_row.append(InlineKeyboardButton("🎵 MP3", callback_data=f"dl_yt_audio:{yt_id}"))
        buttons.append(fmt_row)
        buttons.append([
            InlineKeyboardButton("📁 Doc", callback_data=f"dl_yt_doc:{yt_id}"),
            InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{yt_id}"),
            InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_yt:{yt_id}")
        ])
        await status_msg.edit_text(yt_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # 4. Check Instagram
    if platform == "instagram":
        status_msg = await update.message.reply_text("⏳ <b>Inspecting Instagram media...</b>", parse_mode=constants.ParseMode.HTML)
        ok, ig_data, err = await fetch_instagram_media(media_url)
        if not ok or not ig_data:
            await status_msg.edit_text(f"❌ {err or 'Failed to inspect Instagram media.'}")
            return
        ig_id = uuid.uuid4().hex[:8]
        MEDIA_CACHE[ig_id] = {"data": ig_data, "time": asyncio.get_event_loop().time(), "type": "instagram"}
        database.record_check(user_id)

        ig_msg = build_instagram_stats_message(ig_data)
        buttons = [
            [
                InlineKeyboardButton("📥 Tải Video", callback_data=f"dl_ig:{ig_id}"),
                InlineKeyboardButton("📁 Doc", callback_data=f"dl_ig_doc:{ig_id}"),
                InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{ig_id}"),
                InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_ig:{ig_id}")
            ]
        ]
        await status_msg.edit_text(ig_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # Default fallback
    await handle_message(update, context)

# ==============================================================
# Group Chat Join Event Handler
# ==============================================================

async def chat_member_updated_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Chào mừng nhóm khi bot được thêm vào nhóm chat."""
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    old_status = result.old_chat_member.status

    # Kiểm tra xem bot có vừa mới được thêm vào nhóm không
    if old_status in ("left", "kicked") and new_status in ("member", "administrator"):
        chat = update.effective_chat
        if not chat:
            return

        # Lưu thông tin nhóm vào database
        database.get_group_settings(chat.id, chat.title or "")

        welcome_text = (
            f"👋 Xin chào <b>{chat.title}</b>!\n"
            "Tôi là <b>TikTok Tweaks Bot</b> — hỗ trợ tải video TikTok (120fps), YouTube 4K, IG, X, Pinterest & Spotify.\n"
            "👉 <i>Gửi link vào nhóm để tải tự động!</i>"
        )
        keyboard = [
            [InlineKeyboardButton("⚙️ Cài đặt nhóm", callback_data="group_settings_menu")]
        ]
        await context.bot.send_message(
            chat_id=chat.id,
            text=welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=constants.ParseMode.HTML
        )

# ==============================================================
# Shazam Audio / Voice / Video Media Handler
# ==============================================================

async def handle_media_shazam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn thoại, video message, audio hoặc clip để nhận diện nhạc Shazam."""
    if not update.message:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    msg = update.message

    # Xác định đối tượng file media
    media_obj = msg.voice or msg.video_note or msg.audio or msg.video
    if not media_obj:
        return

    status_msg = await msg.reply_text(
        "🎧 <b>Đang lắng nghe và nhận diện bài hát qua Shazam...</b>",
        parse_mode=constants.ParseMode.HTML
    )

    unique_id = uuid.uuid4().hex
    tmp_input = os.path.join(tempfile.gettempdir(), f"shazam_in_{chat_id}_{unique_id}")

    try:
        # Tải file từ Telegram
        file_obj = await context.bot.get_file(media_obj.file_id)
        await file_obj.download_to_drive(tmp_input)

        # Chạy nhận diện Shazam
        track_info = await asyncio.to_thread(identify_song_from_path, tmp_input, 15)

        if track_info:
            # Ghi nhận lượt Shazam thành công vào DB
            database.record_shazam(user_id)
            card_text, reply_markup = build_shazam_card(track_info)
            await status_msg.edit_text(card_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.HTML)
        else:
            await status_msg.edit_text(
                "❌ <b>Không tìm thấy bài hát phù hợp.</b>\n"
                "<i>Đoạn âm thanh có thể quá ngắn, nhiều tạp âm hoặc là âm thanh gốc chưa phát hành.</i>",
                parse_mode=constants.ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Lỗi nhận diện Shazam: {e}")
        await status_msg.edit_text(f"❌ Đã xảy ra lỗi khi phân tích âm thanh: {str(e)}")
    finally:
        if os.path.exists(tmp_input):
            try: os.remove(tmp_input)
            except Exception: pass

# ==============================================================
# Helper: Send Downloaded Media (Video or Document)
# ==============================================================

async def send_downloaded_media(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    file_path: str,
    title: str,
    author_name: str,
    platform_name: str,
    thumb_path: Optional[str] = None,
    duration: int = 0,
    width: int = 1080,
    height: int = 1920,
    as_document: bool = False,
    status_msg: Optional[Any] = None
) -> None:
    """Gửi video hoặc document lên Telegram với xử lý giới hạn dung lượng & chống ô vuông đen."""
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    is_group = update.effective_chat.type in (constants.ChatType.GROUP, constants.ChatType.SUPERGROUP)
    user_settings = database.get_or_create_user(user_id)

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    caption = get_caption_text(title, author_name, platform_name, user_settings)
    reply_to = None if (is_group and user_settings.get("reply_mode") == "direct") else (update.message.message_id if update.message else None)
    silent_notify = is_group and (user_settings.get("reply_mode") == "silent")

    # Kiểm tra giới hạn 50MB của Telegram Bot API tiêu chuẩn
    if file_size_mb > 50.0 and not config.BOT_TOKEN.startswith("local:"):
        # Với file > 50MB không gửi qua Bot API chuẩn được, thông báo và cung cấp giải pháp
        msg_over = (
            f"📁 <b>FILE VIDEO RẤT LỚN ({file_size_mb:.1f} MB)!</b>\n"
            f"Telegram Bot API công khai giới hạn upload tối đa 50MB từ bot.\n"
            f"✨ File đã được tải hoàn tất trên server với chất lượng <b>{width}x{height}</b>."
        )
        if status_msg:
            await status_msg.edit_text(msg_over, parse_mode=constants.ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=chat_id, text=msg_over, parse_mode=constants.ParseMode.HTML)
        return

    # Mở thumbnail nếu có để chống ô vuông đen
    thumb_file = None
    if thumb_path and os.path.exists(thumb_path):
        try:
            thumb_file = open(thumb_path, "rb")
        except Exception:
            pass

    try:
        with open(file_path, "rb") as vf:
            if as_document or user_settings.get("doc_mode"):
                # Gửi dạng Document (File gốc không nén)
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=vf,
                    thumbnail=thumb_file,
                    caption=caption,
                    parse_mode=constants.ParseMode.HTML,
                    reply_to_message_id=reply_to,
                    disable_notification=silent_notify,
                    read_timeout=180.0,
                    write_timeout=180.0
                )
            else:
                # Gửi dạng Video chuẩn
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    duration=int(duration),
                    width=int(width),
                    height=int(height),
                    thumbnail=thumb_file,
                    caption=caption,
                    parse_mode=constants.ParseMode.HTML,
                    supports_streaming=True,
                    reply_to_message_id=reply_to,
                    disable_notification=silent_notify,
                    read_timeout=180.0,
                    write_timeout=180.0
                )

        # Xóa tin nhắn chờ
        if status_msg:
            try: await status_msg.delete()
            except Exception: pass

        # Ghi nhận lượt tải thành công vào Database
        database.record_download(user_id, platform_name)

    except Exception as e:
        logger.error(f"Lỗi khi gửi video lên Telegram: {e}")
        if status_msg:
            await status_msg.edit_text(f"❌ Không thể gửi video: {str(e)}")
    finally:
        if thumb_file:
            try: thumb_file.close()
            except Exception: pass

# ==============================================================
# Main Message Handler (Multi-Platform Link Processor)
# ==============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tin nhắn chứa link media đa nền tảng."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    media_url, platform = classify_media_url(text)

    # Nếu không phải link được hỗ trợ
    if not media_url or not platform:
        if not text.startswith("/") and update.effective_chat.type == constants.ChatType.PRIVATE:
            await update.message.reply_text(
                "💡 Vui lòng gửi link hợp lệ từ:\n"
                "• <b>TikTok</b> (Video / Nhạc)\n"
                "• <b>YouTube</b> (Shorts / 4K Video)\n"
                "• <b>Instagram</b> (Reels / Posts)\n"
                "• <b>Twitter / X</b> (Video)\n"
                "• <b>Pinterest</b> (Pin)\n"
                "• <b>Spotify</b> (Bài hát)\n"
                "<i>Hoặc gửi tin nhắn thoại/video để nhận diện nhạc Shazam!</i>",
                parse_mode=constants.ParseMode.HTML
            )
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0
    is_group = update.effective_chat.type in (constants.ChatType.GROUP, constants.ChatType.SUPERGROUP)
    user_settings = database.get_or_create_user(user_id)
    group_settings = database.get_group_settings(chat_id) if is_group else {}
    user_mode = user_settings.get("mode", config.DEFAULT_MODE)

    # ==============================================================
    # 1. SPOTIFY DOWNLOADER (MP3 320 KBPS)
    # ==============================================================
    if platform == "spotify":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang trích xuất thông tin bài hát Spotify & chuẩn bị MP3 320 kbps...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        ok, sp_data, err = await fetch_spotify_track(media_url)
        if not ok or not sp_data:
            await status_msg.edit_text(f"❌ {err or 'Không thể lấy thông tin bài hát Spotify.'}")
            return

        track_id = uuid.uuid4().hex[:8]
        MEDIA_CACHE[track_id] = {"data": sp_data, "time": asyncio.get_event_loop().time(), "type": "spotify"}

        if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
            await status_msg.edit_text("⚡ <b>Đang tải bản thu MP3 320 kbps chuẩn phòng thu...</b>", parse_mode=constants.ParseMode.HTML)
            tmp_mp3 = os.path.join(tempfile.gettempdir(), f"sp_{chat_id}_{track_id}.mp3")
            try:
                search_q = f"{sp_data['title']} {sp_data['artist']}"
                dl_ok, dl_err = await download_mp3_320kbps(search_q, tmp_mp3)
                if dl_ok and os.path.exists(tmp_mp3):
                    with open(tmp_mp3, "rb") as af:
                        await context.bot.send_audio(
                            chat_id=chat_id,
                            audio=af,
                            title=sp_data["title"],
                            performer=sp_data["artist"],
                            caption=f"🎵 <b>{sp_data['title']}</b> - <code>{sp_data['artist']}</code>\n💎 <b>MP3 320 kbps High Fidelity</b>\n🤖 <i>Tải bởi TikTok-Tweaks Bot</i>",
                            parse_mode=constants.ParseMode.HTML
                        )
                    database.record_download(user_id, "spotify")
                    await status_msg.delete()
                else:
                    await status_msg.edit_text(f"❌ Lỗi tải MP3 Spotify: {dl_err}")
            except Exception as e:
                await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
            finally:
                if os.path.exists(tmp_mp3):
                    try: os.remove(tmp_mp3)
                    except Exception: pass
            return

        # Hybrid Card Spotify
        sp_msg = build_spotify_stats_message(sp_data)
        keyboard = [
            [
                InlineKeyboardButton("⬇️ Tải MP3 320k", callback_data=f"dl_sp_mp3:{track_id}"),
                InlineKeyboardButton("🟢 Mở Spotify", url=media_url)
            ],
            [
                InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{track_id}"),
                InlineKeyboardButton("❌ Đóng", callback_data=f"close:{track_id}")
            ]
        ]
        await status_msg.edit_text(sp_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # ==============================================================
    # 2. YOUTUBE DOWNLOADER (FULL 4K & MP3 320K)
    # ==============================================================
    if platform == "youtube":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang phân tích định dạng YouTube (Hỗ trợ 4K, 1080p, MP3 320k)...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        ok, yt_data, err = await fetch_youtube_media(media_url)
        if not ok or not yt_data:
            await status_msg.edit_text(f"❌ {err or 'Không thể phân tích video YouTube.'}")
            return

        yt_id = str(yt_data.get("id") or uuid.uuid4().hex[:8])
        MEDIA_CACHE[yt_id] = {"data": yt_data, "time": asyncio.get_event_loop().time(), "type": "youtube"}

        if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
            await status_msg.edit_text("⚡ <b>Đang tải video YouTube chất lượng cao nhất...</b>", parse_mode=constants.ParseMode.HTML)
            tmp_yt = os.path.join(tempfile.gettempdir(), f"yt_{chat_id}_{yt_id}.mp4")
            try:
                dl_ok, dl_err = await download_youtube_to_path(media_url, "1080p", tmp_yt)
                if dl_ok and os.path.exists(tmp_yt):
                    await send_downloaded_media(
                        update, context, tmp_yt, yt_data["title"], yt_data["uploader"],
                        "YouTube", duration=yt_data.get("duration", 0), status_msg=status_msg
                    )
                else:
                    await status_msg.edit_text(f"❌ Lỗi tải YouTube: {dl_err}")
            except Exception as e:
                await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
            finally:
                if os.path.exists(tmp_yt):
                    try: os.remove(tmp_yt)
                    except Exception: pass
            return

        # Hybrid Card YouTube (2 hàng gọn gàng)
        yt_msg = build_youtube_stats_message(yt_data)
        buttons = []
        row1 = []
        if yt_data.get("is_4k"):
            row1.append(InlineKeyboardButton("🏆 4K", callback_data=f"dl_yt:4k:{yt_id}"))
        row1.append(InlineKeyboardButton("⚡ 1080p", callback_data=f"dl_yt:1080p:{yt_id}"))
        row1.append(InlineKeyboardButton("🎬 720p", callback_data=f"dl_yt:720p:{yt_id}"))
        row1.append(InlineKeyboardButton("🎵 MP3", callback_data=f"dl_yt_mp3:{yt_id}"))
        buttons.append(row1)

        buttons.append([
            InlineKeyboardButton("📁 Doc", callback_data=f"dl_yt_doc:{yt_id}"),
            InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{yt_id}"),
            InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_yt:{yt_id}"),
            InlineKeyboardButton("❌ Đóng", callback_data=f"close:{yt_id}")
        ])

        await status_msg.edit_text(yt_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # ==============================================================
    # 3. TWITTER / X DOWNLOADER
    # ==============================================================
    if platform == "twitter":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang phân tích bài viết Twitter / X...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        ok, tw_data, err = await fetch_twitter_media(media_url)
        if not ok or not tw_data:
            await status_msg.edit_text(f"❌ {err or 'Không tìm thấy video Twitter.'}")
            return

        tw_id = str(tw_data.get("id") or uuid.uuid4().hex[:8])
        MEDIA_CACHE[tw_id] = {"data": tw_data, "time": asyncio.get_event_loop().time(), "type": "twitter"}

        if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
            await status_msg.edit_text("⚡ <b>Đang tải video Twitter / X...</b>", parse_mode=constants.ParseMode.HTML)
            tmp_tw = os.path.join(tempfile.gettempdir(), f"tw_{chat_id}_{tw_id}.mp4")
            try:
                dl_ok, dl_err = await download_twitter_to_path(media_url, tmp_tw)
                if dl_ok and os.path.exists(tmp_tw):
                    await send_downloaded_media(
                        update, context, tmp_tw, tw_data["title"], tw_data["uploader"],
                        "Twitter / X", duration=tw_data.get("duration", 0), status_msg=status_msg
                    )
                else:
                    await status_msg.edit_text(f"❌ Lỗi tải Twitter: {dl_err}")
            except Exception as e:
                await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
            finally:
                if os.path.exists(tmp_tw):
                    try: os.remove(tmp_tw)
                    except Exception: pass
            return

        tw_msg = build_twitter_stats_message(tw_data)
        keyboard = [
            [
                InlineKeyboardButton("📥 Tải Video", callback_data=f"dl_tw:{tw_id}"),
                InlineKeyboardButton("📁 Doc", callback_data=f"dl_tw_doc:{tw_id}"),
                InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_tw:{tw_id}"),
                InlineKeyboardButton("❌ Đóng", callback_data=f"close:{tw_id}")
            ]
        ]
        await status_msg.edit_text(tw_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # ==============================================================
    # 4. PINTEREST DOWNLOADER
    # ==============================================================
    if platform == "pinterest":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang phân tích bài ghim Pinterest...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        ok, pin_data, err = await fetch_pinterest_media(media_url)
        if not ok or not pin_data:
            await status_msg.edit_text(f"❌ {err or 'Không thể lấy thông tin bài ghim Pinterest.'}")
            return

        pin_id = str(pin_data.get("id") or uuid.uuid4().hex[:8])
        MEDIA_CACHE[pin_id] = {"data": pin_data, "time": asyncio.get_event_loop().time(), "type": "pinterest"}

        if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
            await status_msg.edit_text("⚡ <b>Đang tải media Pinterest...</b>", parse_mode=constants.ParseMode.HTML)
            tmp_pin = os.path.join(tempfile.gettempdir(), f"pin_{chat_id}_{pin_id}.mp4")
            try:
                dl_ok, dl_err = await download_pinterest_to_path(media_url, tmp_pin)
                if dl_ok and os.path.exists(tmp_pin):
                    await send_downloaded_media(
                        update, context, tmp_pin, pin_data["title"], pin_data["uploader"],
                        "Pinterest", status_msg=status_msg
                    )
                else:
                    await status_msg.edit_text(f"❌ Lỗi tải Pinterest: {dl_err}")
            except Exception as e:
                await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
            finally:
                if os.path.exists(tmp_pin):
                    try: os.remove(tmp_pin)
                    except Exception: pass
            return

        pin_msg = build_pinterest_stats_message(pin_data)
        keyboard = [
            [
                InlineKeyboardButton("📥 Tải Về", callback_data=f"dl_pin:{pin_id}"),
                InlineKeyboardButton("📁 Doc", callback_data=f"dl_pin_doc:{pin_id}"),
                InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{pin_id}"),
                InlineKeyboardButton("❌ Đóng", callback_data=f"close:{pin_id}")
            ]
        ]
        await status_msg.edit_text(pin_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # ==============================================================
    # 5. TIKTOK MUSIC DOWNLOADER
    # ==============================================================
    if platform == "tiktok_music":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang trích xuất file âm thanh TikTok Music...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        unique_id = uuid.uuid4().hex
        tmp_music = os.path.join(tempfile.gettempdir(), f"tt_music_{chat_id}_{unique_id}.mp3")
        try:
            success, err = await download_file_to_path(media_url, tmp_music, max_size_mb=30)
            if success and os.path.exists(tmp_music):
                with open(tmp_music, "rb") as af:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=af,
                        title="TikTok Sound",
                        caption="🎵 <b>TikTok Music Track</b>\n🤖 <i>Tải bởi TikTok-Tweaks Bot</i>",
                        parse_mode=constants.ParseMode.HTML
                    )
                database.record_download(user_id, "tiktok")
                await status_msg.delete()
            else:
                await status_msg.edit_text(f"❌ Không thể tải âm thanh từ link này: {err}")
        except Exception as e:
            await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_music):
                try: os.remove(tmp_music)
                except Exception: pass
        return

    # ==============================================================
    # 6. INSTAGRAM DOWNLOADER
    # ==============================================================
    if platform == "instagram":
        status_msg = await update.message.reply_text(
            "⏳ <b>Đang phân tích link Instagram Reels/Post...</b>",
            parse_mode=constants.ParseMode.HTML
        )
        success, ig_data, err_msg = await fetch_instagram_media(media_url)
        if not success or not ig_data:
            await status_msg.edit_text(f"❌ {err_msg or 'Không tìm thấy video Instagram.'}")
            return

        ig_id = str(ig_data.get("id") or uuid.uuid4().hex[:8])
        MEDIA_CACHE[ig_id] = {"data": ig_data, "time": asyncio.get_event_loop().time(), "type": "instagram"}

        if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
            await status_msg.edit_text("⚡ <b>Đang tải video Instagram...</b>", parse_mode=constants.ParseMode.HTML)
            tmp_ig = os.path.join(tempfile.gettempdir(), f"ig_{chat_id}_{ig_id}.mp4")
            try:
                dl_ok, dl_err = await download_file_to_path(ig_data["video_url"], tmp_ig, max_size_mb=config.MAX_FILE_SIZE_MB)
                if dl_ok and os.path.exists(tmp_ig):
                    await send_downloaded_media(
                        update, context, tmp_ig, ig_data["title"], ig_data.get("author", {}).get("nickname", "Instagram User"),
                        "Instagram", duration=ig_data.get("duration", 0), status_msg=status_msg
                    )
                else:
                    await status_msg.edit_text(f"❌ Lỗi tải Instagram: {dl_err}")
            except Exception as e:
                await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
            finally:
                if os.path.exists(tmp_ig):
                    try: os.remove(tmp_ig)
                    except Exception: pass
            return

        ig_msg = build_instagram_stats_message(ig_data)
        keyboard = [
            [
                InlineKeyboardButton("📥 Tải Video", callback_data=f"dl_ig:{ig_id}"),
                InlineKeyboardButton("📁 Doc", callback_data=f"dl_ig_doc:{ig_id}"),
                InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{ig_id}"),
                InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_ig:{ig_id}")
            ]
        ]
        await status_msg.edit_text(ig_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # ==============================================================
    # 7. TIKTOK VIDEO DOWNLOADER (FULL 120FPS & VQSCORE CHECKER)
    # ==============================================================
    status_msg = await update.message.reply_text(
        "⏳ <b>Đang quét video TikTok, phân tích VQScore và kiểm tra thông số...</b>",
        parse_mode=constants.ParseMode.HTML
    )
    success, data, err_msg = await fetch_tiktok_video(media_url)
    if not success or not data:
        await status_msg.edit_text(f"❌ {err_msg or 'Không thể tải video TikTok.'}")
        return

    video_id = str(data.get("id") or uuid.uuid4().hex[:8])
    data["_source_url"] = media_url
    MEDIA_CACHE[video_id] = {"data": data, "time": asyncio.get_event_loop().time(), "type": "tiktok"}

    # Ghi nhận lượt kiểm tra checker
    database.record_check(user_id)

    meta = data.get("_meta") or {}
    app_size_mb = meta.get("app_size_mb", 0)
    browser_size_mb = meta.get("browser_size_mb", 0)

    # Nếu ở chế độ Downloader hoặc trong group có auto_download bật
    if user_mode == "downloader" or (is_group and group_settings.get("auto_download", 1)):
        await status_msg.edit_text("⚡ <b>Đang tải video TikTok chất lượng gốc (Original HD)...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_tt = os.path.join(tempfile.gettempdir(), f"tt_{chat_id}_{video_id}.mp4")
        thumb_tt = os.path.join(tempfile.gettempdir(), f"thumb_{chat_id}_{video_id}.jpg")
        try:
            dl_url, _, _ = get_download_url_by_quality(data, "original")
            cover_url = data.get("cover")
            if cover_url:
                await download_thumbnail_to_path(cover_url, thumb_tt)

            dl_ok, dl_err = await download_file_to_path(dl_url, tmp_tt, max_size_mb=config.MAX_FILE_SIZE_MB)
            if dl_ok and os.path.exists(tmp_tt):
                await send_downloaded_media(
                    update, context, tmp_tt, data.get("title", ""), data.get("author", {}).get("nickname", "TikTok User"),
                    "TikTok", thumb_path=thumb_tt, duration=data.get("duration", 0),
                    width=data.get("_width", 1080), height=data.get("_height", 1920),
                    status_msg=status_msg
                )
            else:
                await status_msg.edit_text(f"❌ Lỗi tải TikTok: {dl_err}")
        except Exception as e:
            await status_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            for p in (tmp_tt, thumb_tt):
                if os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass
        return

    # Chế độ Hybrid hoặc Checker: hiển thị card đầy đủ (2 hàng nút gọn gàng)
    tt_msg = build_video_stats_message(data)
    buttons = [
        [
            InlineKeyboardButton(f"📥 Gốc ({app_size_mb:.1f}M)", callback_data=f"dl_tt:original:{video_id}"),
            InlineKeyboardButton(f"⚡ Web ({browser_size_mb:.1f}M)", callback_data=f"dl_tt:standard:{video_id}"),
            InlineKeyboardButton("🎵 Nhạc", callback_data=f"dl_tt_audio:{video_id}")
        ],
        [
            InlineKeyboardButton("📁 Doc", callback_data=f"dl_tt_doc:{video_id}"),
            InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{video_id}"),
            InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_tt:{video_id}"),
            InlineKeyboardButton("📊 Kênh", callback_data=f"profile:{data.get('author', {}).get('unique_id', '')}")
        ]
    ]
    await status_msg.edit_text(tt_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)

# ==============================================================
# Callback Query Handler (Buttons Interactivity)
# ==============================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Xử lý tất cả các tương tác nút bấm callback query."""
    query = update.callback_query
    if not query or not query.data:
        return

    try:
        await query.answer()
    except Exception:
        pass
    data_str = query.data
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else 0

    # Đóng tin nhắn
    if data_str.startswith("close:") or data_str == "close_box":
        try: await query.message.delete()
        except Exception: pass
        return

    # Điều hướng menu
    if data_str == "back_to_start":
        await start_command(update, context)
        return
    if data_str == "mode_menu":
        await mode_command(update, context)
        return
    if data_str == "settings_menu":
        await settings_command(update, context)
        return
    if data_str == "help_menu":
        await help_command(update, context)
        return
    if data_str == "shazam_info":
        await shazam_command(update, context)
        return
    if data_str == "check_help":
        help_msg = (
            "🔍 <b>Video & Creator Inspector</b>\n\n"
            "Analyze video streams, MP4 headers, real codecs, bitrates, and creator metrics.\n\n"
            "<b>Usage:</b>\n"
            "• <code>/check &lt;TikTok/YouTube/IG Link&gt;</code>\n"
            "• <code>/check @username</code> (Analyze creator's last 12 videos)\n"
            "• Reply to any message containing a link with <code>/check</code>\n\n"
            "<b>Supported Platforms:</b>\n"
            "• <b>TikTok:</b> Full VQScore, 120 FPS, H.265/H.264 streams, exact counts\n"
            "• <b>TikTok Accounts:</b> 12-video performance analytics & engagement rate\n"
            "• <b>YouTube:</b> 4K check, stream formats, duration, views\n"
            "• <b>Instagram:</b> Reels resolution, audio, interaction stats"
        )
        await query.message.reply_text(help_msg, parse_mode=constants.ParseMode.HTML)
        return
    if data_str == "group_settings_menu":
        await group_settings_command(update, context)
        return

    # Profile & Mini App
    if data_str.startswith("user_profile:"):
        uid = int(data_str.split(":", 1)[1]) if ":" in data_str else user_id
        user_data = database.get_or_create_user(uid)
        profile_msg = build_user_profile_stats_message(user_data)
        buttons = []
        if config.WEBAPP_URL and config.WEBAPP_URL.startswith("https://"):
            webapp_link = f"{config.WEBAPP_URL}?user_id={uid}&dl={user_data.get('total_downloads', 0)}&ck={user_data.get('total_checks', 0)}"
            buttons.append([InlineKeyboardButton("📱 Mở Mini App (Full Screen)", web_app=WebAppInfo(url=webapp_link))])
        buttons.append([
            InlineKeyboardButton(f"📁 Doc: {'BẬT' if user_data.get('doc_mode') else 'TẮT'}", callback_data="toggle_opt:doc_mode"),
            InlineKeyboardButton(f"🛡️ No-Sig: {'BẬT' if user_data.get('no_signature') else 'TẮT'}", callback_data="toggle_opt:no_signature"),
            InlineKeyboardButton(f"💬 Gửi: {(user_data.get('reply_mode') or 'direct').capitalize()}", callback_data="cycle_opt:reply_mode")
        ])
        buttons.append([
            InlineKeyboardButton(f"📝 Chữ: {(user_data.get('caption_mode') or 'full').capitalize()}", callback_data="cycle_opt:caption_mode"),
            InlineKeyboardButton("🔄 Làm mới", callback_data=f"user_profile:{uid}"),
            InlineKeyboardButton("❌ Đóng", callback_data="close_box")
        ])
        await query.edit_message_text(profile_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # Toggles Cài Đặt Cá Nhân
    if data_str.startswith("toggle_opt:"):
        key = data_str.split(":", 1)[1]
        user_data = database.get_or_create_user(user_id)
        new_val = 0 if user_data.get(key) else 1
        database.update_user_setting(user_id, key, new_val)
        # Làm mới lại giao diện profile
        user_data[key] = new_val
        profile_msg = build_user_profile_stats_message(user_data)
        buttons = [
            [
                InlineKeyboardButton(f"📁 Doc: {'BẬT' if user_data.get('doc_mode') else 'TẮT'}", callback_data="toggle_opt:doc_mode"),
                InlineKeyboardButton(f"🛡️ No-Sig: {'BẬT' if user_data.get('no_signature') else 'TẮT'}", callback_data="toggle_opt:no_signature"),
                InlineKeyboardButton(f"💬 Gửi: {(user_data.get('reply_mode') or 'direct').capitalize()}", callback_data="cycle_opt:reply_mode")
            ],
            [
                InlineKeyboardButton(f"📝 Chữ: {(user_data.get('caption_mode') or 'full').capitalize()}", callback_data="cycle_opt:caption_mode"),
                InlineKeyboardButton("🔄 Làm mới", callback_data=f"user_profile:{user_id}"),
                InlineKeyboardButton("❌ Đóng", callback_data="close_box")
            ]
        ]
        await query.edit_message_text(profile_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    if data_str.startswith("cycle_opt:"):
        key = data_str.split(":", 1)[1]
        user_data = database.get_or_create_user(user_id)
        cycle_map = {
            "reply_mode": ["direct", "reply", "silent"],
            "caption_mode": ["full", "minimal", "none"],
            "language": ["vi", "en", "ru"]
        }
        options = cycle_map.get(key, [])
        curr = user_data.get(key, options[0])
        idx = (options.index(curr) + 1) % len(options) if curr in options else 0
        next_val = options[idx]
        database.update_user_setting(user_id, key, next_val)
        user_data[key] = next_val
        profile_msg = build_user_profile_stats_message(user_data)
        buttons = [
            [
                InlineKeyboardButton(f"📁 Doc: {'BẬT' if user_data.get('doc_mode') else 'TẮT'}", callback_data="toggle_opt:doc_mode"),
                InlineKeyboardButton(f"🛡️ No-Sig: {'BẬT' if user_data.get('no_signature') else 'TẮT'}", callback_data="toggle_opt:no_signature"),
                InlineKeyboardButton(f"💬 Gửi: {(user_data.get('reply_mode') or 'direct').capitalize()}", callback_data="cycle_opt:reply_mode")
            ],
            [
                InlineKeyboardButton(f"📝 Chữ: {(user_data.get('caption_mode') or 'full').capitalize()}", callback_data="cycle_opt:caption_mode"),
                InlineKeyboardButton("🔄 Làm mới", callback_data=f"user_profile:{user_id}"),
                InlineKeyboardButton("❌ Đóng", callback_data="close_box")
            ]
        ]
        await query.edit_message_text(profile_msg, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=constants.ParseMode.HTML)
        return

    # Toggles Cài Đặt Nhóm
    if data_str.startswith("toggle_grp:"):
        parts = data_str.split(":")
        key = parts[1]
        target_chat = int(parts[2])
        grp = database.get_group_settings(target_chat)
        new_v = 0 if grp.get(key) else 1
        database.update_group_setting(target_chat, key, new_v)
        grp[key] = new_v
        auto_dl = "✅ BẬT" if grp.get("auto_download") else "❌ TẮT"
        silent = "✅ BẬT" if grp.get("silent_mode") else "❌ TẮT"
        msg = (
            f"👥 <b>Cài đặt nhóm: {grp.get('title', 'Group')}</b>\n"
            f"• Tự động tải: <b>{auto_dl}</b> • Gửi im lặng: <b>{silent}</b>"
        )
        keyboard = [
            [
                InlineKeyboardButton(f"⚡ Tự động tải: {auto_dl}", callback_data=f"toggle_grp:auto_download:{target_chat}"),
                InlineKeyboardButton(f"🔕 Gửi im lặng: {silent}", callback_data=f"toggle_grp:silent_mode:{target_chat}")
            ],
            [InlineKeyboardButton("❌ Đóng", callback_data="close_box")]
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # Đổi chế độ
    if data_str.startswith("set_mode:"):
        mode = data_str.split(":", 1)[1]
        database.update_user_setting(user_id, "mode", mode)
        await query.edit_message_text(
            f"✅ <b>Đã đổi chế độ sang: {mode.upper()}!</b>\n\n"
            "Chế độ này sẽ được áp dụng cho tất cả các lần tải tiếp theo của bạn.",
            parse_mode=constants.ParseMode.HTML
        )
        return

    # ==============================================================
    # Media Download Callback Handlers
    # ==============================================================

    # Tải TikTok Video (Original / Standard / Document)
    if data_str.startswith("dl_tt:") or data_str.startswith("dl_tt_doc:"):
        is_doc = data_str.startswith("dl_tt_doc:")
        video_id = data_str.split(":")[-1]
        cached = MEDIA_CACHE.get(video_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu video đã hết hạn. Vui lòng gửi lại link.")
            return

        data = cached["data"]
        quality = "original" if is_doc else data_str.split(":")[1]
        wait_msg = await query.message.reply_text(f"⏳ <b>Đang tải video TikTok ({quality.upper()})...</b>", parse_mode=constants.ParseMode.HTML)

        tmp_tt = os.path.join(tempfile.gettempdir(), f"tt_{chat_id}_{video_id}_{quality}.mp4")
        thumb_tt = os.path.join(tempfile.gettempdir(), f"thumb_{chat_id}_{video_id}.jpg")
        try:
            dl_url, _, _ = get_download_url_by_quality(data, quality)
            cover_url = data.get("cover")
            if cover_url:
                await download_thumbnail_to_path(cover_url, thumb_tt)

            dl_ok, dl_err = await download_file_to_path(dl_url, tmp_tt, max_size_mb=config.MAX_FILE_SIZE_MB)
            if dl_ok and os.path.exists(tmp_tt):
                await send_downloaded_media(
                    update, context, tmp_tt, data.get("title", ""), data.get("author", {}).get("nickname", "TikTok User"),
                    "TikTok", thumb_path=thumb_tt, duration=data.get("duration", 0),
                    width=data.get("_width", 1080), height=data.get("_height", 1920),
                    as_document=is_doc, status_msg=wait_msg
                )
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải TikTok: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            for p in (tmp_tt, thumb_tt):
                if os.path.exists(p):
                    try: os.remove(p)
                    except Exception: pass
        return

    # Tải Nhạc TikTok MP3
    if data_str.startswith("dl_tt_audio:"):
        video_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(video_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        data = cached["data"]
        music_url = (data.get("music_info") or {}).get("play") or data.get("music")
        if not music_url:
            await query.message.reply_text("❌ Không tìm thấy luồng âm thanh cho video này.")
            return

        wait_msg = await query.message.reply_text("⏳ <b>Đang tải bản thu âm thanh MP3...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_mp3 = os.path.join(tempfile.gettempdir(), f"tt_mp3_{chat_id}_{video_id}.mp3")
        try:
            dl_ok, dl_err = await download_file_to_path(music_url, tmp_mp3, max_size_mb=30)
            if dl_ok and os.path.exists(tmp_mp3):
                with open(tmp_mp3, "rb") as af:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=af,
                        title=data.get("music_info", {}).get("title") or "TikTok Sound",
                        performer=data.get("music_info", {}).get("author") or "TikTok Artist",
                        caption=f"🎵 <b>{data.get('music_info', {}).get('title', 'Sound')}</b>\n🤖 <i>Tải bởi TikTok-Tweaks Bot</i>",
                        parse_mode=constants.ParseMode.HTML
                    )
                database.record_download(user_id, "tiktok")
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(f"❌ Lỗi: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_mp3):
                try: os.remove(tmp_mp3)
                except Exception: pass
        return

    # Tải YouTube Video (4K, 1080p, 720p, Document)
    if data_str.startswith("dl_yt:") or data_str.startswith("dl_yt_doc:"):
        is_doc = data_str.startswith("dl_yt_doc:")
        parts = data_str.split(":")
        quality = "1080p" if is_doc else parts[1]
        yt_id = parts[-1]
        cached = MEDIA_CACHE.get(yt_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        yt_data = cached["data"]
        wait_msg = await query.message.reply_text(f"⏳ <b>Đang tải video YouTube ({quality.upper()})...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_yt = os.path.join(tempfile.gettempdir(), f"yt_{chat_id}_{yt_id}_{quality}.mp4")
        try:
            dl_ok, dl_err = await download_youtube_to_path(yt_data["url"], quality, tmp_yt)
            if dl_ok and os.path.exists(tmp_yt):
                await send_downloaded_media(
                    update, context, tmp_yt, yt_data["title"], yt_data["uploader"],
                    "YouTube", duration=yt_data.get("duration", 0),
                    as_document=is_doc, status_msg=wait_msg
                )
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải YouTube: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_yt):
                try: os.remove(tmp_yt)
                except Exception: pass
        return

    # Tải YouTube MP3 320 kbps
    if data_str.startswith("dl_yt_mp3:"):
        yt_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(yt_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        yt_data = cached["data"]
        wait_msg = await query.message.reply_text("⏳ <b>Đang trích xuất và chuyển đổi sang MP3 320 kbps...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_mp3 = os.path.join(tempfile.gettempdir(), f"yt_{chat_id}_{yt_id}.mp3")
        try:
            dl_ok, dl_err = await download_mp3_320kbps(yt_data["url"], tmp_mp3)
            if dl_ok and os.path.exists(tmp_mp3):
                with open(tmp_mp3, "rb") as af:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=af,
                        title=yt_data["title"],
                        performer=yt_data["uploader"],
                        caption=f"🎵 <b>{yt_data['title']}</b>\n💎 <b>MP3 320 kbps High Fidelity</b>\n🤖 <i>Tải bởi TikTok-Tweaks Bot</i>",
                        parse_mode=constants.ParseMode.HTML
                    )
                database.record_download(user_id, "youtube")
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải MP3: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_mp3):
                try: os.remove(tmp_mp3)
                except Exception: pass
        return

    # Tải Spotify MP3 320 kbps
    if data_str.startswith("dl_sp_mp3:"):
        sp_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(sp_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu bài hát đã hết hạn. Vui lòng gửi lại link.")
            return

        sp_data = cached["data"]
        wait_msg = await query.message.reply_text(f"⏳ <b>Đang tải bản thu MP3 320 kbps cho '{sp_data['title']}'...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_mp3 = os.path.join(tempfile.gettempdir(), f"sp_{chat_id}_{sp_id}.mp3")
        try:
            search_q = f"{sp_data['title']} {sp_data['artist']}"
            dl_ok, dl_err = await download_mp3_320kbps(search_q, tmp_mp3)
            if dl_ok and os.path.exists(tmp_mp3):
                with open(tmp_mp3, "rb") as af:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=af,
                        title=sp_data["title"],
                        performer=sp_data["artist"],
                        caption=f"🎵 <b>{sp_data['title']}</b> - <code>{sp_data['artist']}</code>\n💎 <b>MP3 320 kbps High Fidelity</b>\n🤖 <i>Tải bởi TikTok-Tweaks Bot</i>",
                        parse_mode=constants.ParseMode.HTML
                    )
                database.record_download(user_id, "spotify")
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải MP3: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_mp3):
                try: os.remove(tmp_mp3)
                except Exception: pass
        return

    # Tải MP3 từ kết quả nhận diện Shazam (hỗ trợ cả short cache ID và legacy text)
    if data_str.startswith("dl_sh_mp3:") or data_str.startswith("dl_shazam_mp3:"):
        if data_str.startswith("dl_sh_mp3:"):
            s_id = data_str.split(":", 1)[1]
            cached_track = SHAZAM_CACHE.get(s_id, {})
            s_title = cached_track.get("title", "Unknown Track")
            s_artist = cached_track.get("artist", "")
        else:
            meta_str = data_str.split(":", 1)[1]
            parts = meta_str.split("|")
            s_title = parts[0]
            s_artist = parts[1] if len(parts) > 1 else ""

        wait_msg = await query.message.reply_text(f"⏳ <b>Đang tìm và tải MP3 320 kbps bài hát '{s_title}'...</b>", parse_mode=constants.ParseMode.HTML)
        unique_id = uuid.uuid4().hex[:8]
        tmp_mp3 = os.path.join(tempfile.gettempdir(), f"shazam_dl_{chat_id}_{unique_id}.mp3")
        try:
            search_q = f"{s_title} {s_artist}"
            dl_ok, dl_err = await download_mp3_320kbps(search_q, tmp_mp3)
            if dl_ok and os.path.exists(tmp_mp3):
                with open(tmp_mp3, "rb") as af:
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=af,
                        title=s_title,
                        performer=s_artist,
                        caption=f"🎵 <b>{s_title}</b> - <code>{s_artist}</code>\n💎 <b>MP3 320 kbps (Nhận diện bởi Shazam)</b>",
                        parse_mode=constants.ParseMode.HTML,
                        read_timeout=180.0,
                        write_timeout=180.0
                    )
                database.record_download(user_id, "shazam_mp3")
                await wait_msg.delete()
            else:
                await wait_msg.edit_text(f"❌ Lỗi: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_mp3):
                try: os.remove(tmp_mp3)
                except Exception: pass
        return

    # Tải Twitter / X Video
    if data_str.startswith("dl_tw:") or data_str.startswith("dl_tw_doc:"):
        is_doc = data_str.startswith("dl_tw_doc:")
        tw_id = data_str.split(":")[-1]
        cached = MEDIA_CACHE.get(tw_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        tw_data = cached["data"]
        wait_msg = await query.message.reply_text("⏳ <b>Đang tải video Twitter / X...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_tw = os.path.join(tempfile.gettempdir(), f"tw_{chat_id}_{tw_id}.mp4")
        try:
            dl_ok, dl_err = await download_twitter_to_path(tw_data["url"], tmp_tw)
            if dl_ok and os.path.exists(tmp_tw):
                await send_downloaded_media(
                    update, context, tmp_tw, tw_data["title"], tw_data["uploader"],
                    "Twitter / X", duration=tw_data.get("duration", 0),
                    as_document=is_doc, status_msg=wait_msg
                )
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải Twitter: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_tw):
                try: os.remove(tmp_tw)
                except Exception: pass
        return

    # Tải Pinterest Pin
    if data_str.startswith("dl_pin:") or data_str.startswith("dl_pin_doc:"):
        is_doc = data_str.startswith("dl_pin_doc:")
        pin_id = data_str.split(":")[-1]
        cached = MEDIA_CACHE.get(pin_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        pin_data = cached["data"]
        wait_msg = await query.message.reply_text("⏳ <b>Đang tải media Pinterest...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_pin = os.path.join(tempfile.gettempdir(), f"pin_{chat_id}_{pin_id}.mp4")
        try:
            dl_ok, dl_err = await download_pinterest_to_path(pin_data["url"], tmp_pin)
            if dl_ok and os.path.exists(tmp_pin):
                await send_downloaded_media(
                    update, context, tmp_pin, pin_data["title"], pin_data["uploader"],
                    "Pinterest", as_document=is_doc, status_msg=wait_msg
                )
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải Pinterest: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_pin):
                try: os.remove(tmp_pin)
                except Exception: pass
        return

    # Tải Instagram Video
    if data_str.startswith("dl_ig:") or data_str.startswith("dl_ig_doc:"):
        is_doc = data_str.startswith("dl_ig_doc:")
        ig_id = data_str.split(":")[-1]
        cached = MEDIA_CACHE.get(ig_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu Instagram đã hết hạn. Vui lòng gửi lại link.")
            return

        ig_data = cached["data"]
        wait_msg = await query.message.reply_text("⏳ <b>Đang tải video Instagram...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_ig = os.path.join(tempfile.gettempdir(), f"ig_{chat_id}_{ig_id}.mp4")
        try:
            dl_ok, dl_err = await download_file_to_path(ig_data["video_url"], tmp_ig, max_size_mb=config.MAX_FILE_SIZE_MB)
            if dl_ok and os.path.exists(tmp_ig):
                await send_downloaded_media(
                    update, context, tmp_ig, ig_data["title"], ig_data.get("author", {}).get("nickname", "Instagram User"),
                    "Instagram", duration=ig_data.get("duration", 0),
                    as_document=is_doc, status_msg=wait_msg
                )
            else:
                await wait_msg.edit_text(f"❌ Lỗi tải Instagram: {dl_err}")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_ig):
                try: os.remove(tmp_ig)
                except Exception: pass
        return

    # Tải Ảnh Bìa Gốc Full Size
    if data_str.startswith("dl_cover:"):
        media_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(media_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        cover_url = cached["data"].get("cover") or cached["data"].get("origin_cover")
        if not cover_url:
            await query.message.reply_text("❌ Không tìm thấy ảnh bìa gốc của media này.")
            return

        wait_msg = await query.message.reply_text("⏳ <b>Đang tải ảnh bìa gốc full size...</b>", parse_mode=constants.ParseMode.HTML)
        tmp_img = os.path.join(tempfile.gettempdir(), f"cover_{chat_id}_{media_id}.jpg")
        try:
            dl_ok, dl_err = await download_file_to_path(cover_url, tmp_img, max_size_mb=20)
            if not dl_ok and cached["data"].get("origin_cover") and cover_url != cached["data"].get("origin_cover"):
                cover_url = cached["data"].get("origin_cover")
                dl_ok, dl_err = await download_file_to_path(cover_url, tmp_img, max_size_mb=20)

            if dl_ok and os.path.exists(tmp_img):
                # Tự động nhận diện định dạng ảnh thực tế (WebP, PNG, JPG)
                ext = ".jpg"
                try:
                    with open(tmp_img, "rb") as tf:
                        header = tf.read(12)
                        if header.startswith(b"RIFF") and b"WEBP" in header:
                            ext = ".webp"
                        elif header.startswith(b"\x89PNG"):
                            ext = ".png"
                except Exception:
                    pass

                final_filename = f"cover_{media_id}{ext}"
                with open(tmp_img, "rb") as pf:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=pf,
                        filename=final_filename,
                        caption=f"🖼️ <b>Ảnh Bìa / Preview Frame Gốc (Full Size)</b>\n🤖 <i>TikTok-Tweaks Bot</i>",
                        parse_mode=constants.ParseMode.HTML,
                        read_timeout=180.0,
                        write_timeout=180.0
                    )
                await wait_msg.delete()
            else:
                await wait_msg.edit_text("❌ Không thể tải file ảnh bìa.")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi: {str(e)}")
        finally:
            if os.path.exists(tmp_img):
                try: os.remove(tmp_img)
                except Exception: pass
        return

    # Shazam Nhận Diện Nhạc Từ Video
    if data_str.startswith("shazam_tt:") or data_str.startswith("shazam_yt:") or data_str.startswith("shazam_ig:") or data_str.startswith("shazam_tw:"):
        media_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(media_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu media đã hết hạn. Vui lòng gửi lại link.")
            return

        data = cached["data"]
        wait_msg = await query.message.reply_text("🎧 <b>Đang trích xuất âm thanh và nhận diện bài hát qua Shazam...</b>", parse_mode=constants.ParseMode.HTML)
        audio_target = (data.get("music_info") or {}).get("play") or data.get("music") or data.get("video_url") or data.get("url")

        tmp_clip = os.path.join(tempfile.gettempdir(), f"shazam_sample_{chat_id}_{media_id}.mp4")
        try:
            # Tải 1 đoạn ngắn
            dl_ok, dl_err = await download_file_to_path(audio_target, tmp_clip, max_size_mb=20)
            if not dl_ok or not os.path.exists(tmp_clip):
                # Fallback YouTube or yt-dlp audio
                if "youtube" in str(cached.get("type")):
                    await download_youtube_to_path(data["url"], "360p", tmp_clip)

            if os.path.exists(tmp_clip):
                track_info = await asyncio.to_thread(identify_song_from_path, tmp_clip, 15)
                if track_info:
                    database.record_shazam(user_id)
                    card_text, reply_markup = build_shazam_card(track_info)
                    await wait_msg.edit_text(card_text, reply_markup=reply_markup, parse_mode=constants.ParseMode.HTML)
                else:
                    await wait_msg.edit_text(
                        "❌ <b>Shazam không tìm thấy bài hát phù hợp.</b>\n"
                        "<i>Có thể đây là âm thanh tự mix, nhạc chế hoặc giọng lồng tiếng không có trong cơ sở dữ liệu.</i>",
                        parse_mode=constants.ParseMode.HTML
                    )
            else:
                await wait_msg.edit_text("❌ Không thể trích xuất đoạn âm thanh để nhận diện.")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Lỗi phân tích: {str(e)}")
        finally:
            if os.path.exists(tmp_clip):
                try: os.remove(tmp_clip)
                except Exception: pass
        return

    # Quét lại TikTok (Recheck)
    if data_str.startswith("recheck:"):
        video_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(video_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link.")
            return

        source_url = cached["data"].get("_source_url") or f"https://www.tiktok.com/@tiktok/video/{video_id}"
        await query.edit_message_text("🔄 <b>Đang quét lại số liệu thời gian thực từ TikTok Studio...</b>", parse_mode=constants.ParseMode.HTML)
        success, new_data, _ = await fetch_tiktok_video(source_url)
        if success and new_data:
            new_data["_source_url"] = source_url
            MEDIA_CACHE[video_id] = {"data": new_data, "time": asyncio.get_event_loop().time(), "type": "tiktok"}
            new_msg = build_video_stats_message(new_data)
            meta = new_data.get("_meta") or {}
            app_size_mb = meta.get("app_size_mb", 0)
            browser_size_mb = meta.get("browser_size_mb", 0)

            keyboard = [
                [
                    InlineKeyboardButton(f"📥 Gốc ({app_size_mb:.1f}M)", callback_data=f"dl_tt:original:{video_id}"),
                    InlineKeyboardButton(f"⚡ Web ({browser_size_mb:.1f}M)", callback_data=f"dl_tt:standard:{video_id}"),
                    InlineKeyboardButton("🎵 Nhạc", callback_data=f"dl_tt_audio:{video_id}")
                ],
                [
                    InlineKeyboardButton("📁 Doc", callback_data=f"dl_tt_doc:{video_id}"),
                    InlineKeyboardButton("🖼️ Cover", callback_data=f"dl_cover:{video_id}"),
                    InlineKeyboardButton("🎧 Shazam", callback_data=f"shazam_tt:{video_id}"),
                    InlineKeyboardButton("📊 Kênh", callback_data=f"profile:{new_data.get('author', {}).get('unique_id', '')}")
                ]
            ]
            await query.edit_message_text(new_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        else:
            await query.edit_message_text("❌ Không thể quét lại dữ liệu video vào lúc này.")
        return

    # Profile analytics 12 video gần nhất
    if data_str.startswith("profile:"):
        username = data_str.split(":", 1)[1]
        wait_msg = await query.message.reply_text(f"⏳ <b>Đang trích xuất và phân tích 12 video gần nhất của @{username}...</b>", parse_mode=constants.ParseMode.HTML)
        videos = await fetch_author_recent_12_videos(username)
        report = build_profile_analytics_message(username, username, videos)
        keyboard = [[InlineKeyboardButton("❌ Đóng", callback_data=f"close:{username}")]]
        await wait_msg.edit_text(report, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML, disable_web_page_preview=True)
        return

    # Video tương tự (Similar Videos)
    if data_str.startswith("similar:"):
        video_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(video_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link video.")
            return
        sim_msg = build_similar_videos_message(cached["data"])
        keyboard = [[InlineKeyboardButton("❌ Đóng", callback_data=f"close:{video_id}")]]
        await query.message.reply_text(sim_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

    # Thông tin tác giả (User Info)
    if data_str.startswith("user_info:"):
        video_id = data_str.split(":", 1)[1]
        cached = MEDIA_CACHE.get(video_id)
        if not cached:
            await query.message.reply_text("⚠️ Dữ liệu đã hết hạn. Vui lòng gửi lại link video.")
            return
        user_msg = build_user_info_message(cached["data"])
        keyboard = [[InlineKeyboardButton("❌ Đóng", callback_data=f"close:{video_id}")]]
        await query.message.reply_text(user_msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML)
        return

# ==============================================================
# Error Handler
# ==============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bắt và ghi nhận các lỗi ngoại lệ chưa xử lý."""
    logger.error("Đã xảy ra lỗi chưa xử lý:", exc_info=context.error)

# ==============================================================
# Main Application Entry Point
# ==============================================================

def main() -> None:
    """Hàm khởi động chính của bot."""
    print("=" * 60)
    print("🚀 ĐANG KHỞI ĐỘNG TIKTOK-TWEAKS BOT 2.0 (FULL 4K & SHAZAM)...")
    print("=" * 60)

    if not config.is_token_valid():
        print("\n❌ LỖI: BOT_TOKEN chưa được cấu hình hoặc không hợp lệ!")
        print("👉 HƯỚNG DẪN CẤU HÌNH:")
        print("1. Mở file '.env' trong thư mục dự án.")
        print("2. Nhập Token lấy từ BotFather vào dòng: BOT_TOKEN=...")
        print("   Ví dụ: BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
        print("3. Lưu file và khởi động lại bot.")
        print("=" * 60)
        sys.exit(1)

    # Cấu hình HTTPXRequest với timeout dài để hỗ trợ upload video lớn không bị 'Timed out'
    req_builder = HTTPXRequest(
        read_timeout=180.0,
        write_timeout=180.0,
        connect_timeout=60.0,
        pool_timeout=60.0
    )
    app = ApplicationBuilder().token(config.BOT_TOKEN).request(req_builder).build()

    # Đăng ký các lệnh
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler(["check", "inspect", "analyze"], check_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler(["profile", "webapp", "app"], profile_command))
    app.add_handler(CommandHandler("group_settings", group_settings_command))
    app.add_handler(CommandHandler("shazam", shazam_command))

    # Đăng ký sự kiện bot tham gia nhóm mới (Greet Group)
    app.add_handler(ChatMemberHandler(chat_member_updated_handler, ChatMemberHandler.MY_CHAT_MEMBER))

    # Đăng ký nhận diện bài hát từ tin nhắn thoại, video note, audio, video
    app.add_handler(MessageHandler(
        filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE,
        handle_media_shazam
    ))

    # Đăng ký xử lý tin nhắn chứa link media đa nền tảng
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Đăng ký xử lý callback nút bấm
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Đăng ký bắt lỗi
    app.add_error_handler(error_handler)

    print("✅ Bot đã sẵn sàng nhận tin nhắn!")
    print("💎 Nền tảng: TikTok, YouTube (4K), Instagram, Twitter/X, Pinterest, Spotify (320k)")
    print("🎧 Nhận diện bài hát: Shazam Audio & Video Voice AI Engine")
    print("📱 Telegram Mini App & Profile Analytics: Sẵn sàng")
    print(f"📦 Giới hạn tải: {config.MAX_FILE_SIZE_MB} MB")
    print(f"👥 Tự động tải trong Group: {'BẬT' if config.GROUP_AUTO_DOWNLOAD else 'TẮT'}")
    print(" Nhấn Ctrl+C để dừng bot.")

    try:
        app.run_polling(drop_pending_updates=True)
    except Conflict:
        print("\n⚠️ CẢNH BÁO: Phát hiện phiên bản bot khác (hoặc dịch vụ gateway khác) đang chạy cùng lúc với BOT_TOKEN này (HTTP 409 Conflict)!")
        print("Vui lòng tắt phiên bot cũ trước khi khởi động lại.\n")

if __name__ == "__main__":
    main()
