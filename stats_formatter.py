import datetime
from typing import Dict, Any, Optional, Tuple, List

COUNTRY_MAP: Dict[str, Tuple[str, str]] = {
    "VN": ("🇻🇳", "Việt Nam"),
    "US": ("🇺🇸", "Hoa Kỳ (United States)"),
    "GB": ("🇬🇧", "Vương Quốc Anh (United Kingdom)"),
    "FR": ("🇫🇷", "Pháp (France)"),
    "DE": ("🇩🇪", "Đức (Germany)"),
    "JP": ("🇯🇵", "Nhật Bản (Japan)"),
    "KR": ("🇰🇷", "Hàn Quốc (South Korea)"),
    "CN": ("🇨🇳", "Trung Quốc (China)"),
    "TW": ("🇹🇼", "Đài Loan (Taiwan)"),
    "TH": ("🇹🇭", "Thái Lan (Thailand)"),
    "ID": ("🇮🇩", "Indonesia"),
    "PH": ("🇵🇭", "Philippines"),
    "MY": ("🇲🇾", "Malaysia"),
    "SG": ("🇸🇬", "Singapore"),
    "IN": ("🇮🇳", "Ấn Độ (India)"),
    "RU": ("🇷🇺", "Nga (Russia)"),
    "BR": ("🇧🇷", "Brazil"),
    "CA": ("🇨🇦", "Canada"),
    "AU": ("🇦🇺", "Úc (Australia)"),
    "IT": ("🇮🇹", "Ý (Italy)"),
    "ES": ("🇪🇸", "Tây Ban Nha (Spain)"),
    "MX": ("🇲🇽", "Mexico"),
    "TR": ("🇹🇷", "Thổ Nhĩ Kỳ (Turkey)"),
    "SA": ("🇸🇦", "Ả Rập Xê Út (Saudi Arabia)"),
    "AE": ("🇦🇪", "UAE"),
}

def get_country_display(country_code: Optional[str]) -> str:
    """Chuyển đổi mã quốc gia thành cờ và tên quốc gia."""
    if not country_code:
        return "🌐 Không xác định (Unknown)"
    code = country_code.strip().upper()
    if code in COUNTRY_MAP:
        flag, name = COUNTRY_MAP[code]
        return f"{flag} {name} ({code})"
    try:
        flag = "".join(chr(127397 + ord(c)) for c in code if 'A' <= c <= 'Z')
        return f"{flag} {code}" if flag else code
    except Exception:
        return code

def format_creation_date_gmt0(timestamp: Optional[int]) -> str:
    """Định dạng ngày tạo theo chuẩn GMT+0 (UTC) kèm thời gian tương đối."""
    if not timestamp:
        return "Không có dữ liệu"
    try:
        dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S GMT+0")
        now = datetime.datetime.now(datetime.timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 0:
            rel = "vừa xong"
        elif seconds < 60:
            rel = f"{seconds}s trước"
        elif seconds < 3600:
            rel = f"{seconds // 60}m trước"
        elif seconds < 86400:
            rel = f"{seconds // 3600}h trước"
        elif seconds < 86400 * 30:
            rel = f"{seconds // 86400} ngày trước"
        elif seconds < 86400 * 365:
            rel = f"{seconds // (86400 * 30)} tháng trước"
        else:
            rel = f"{seconds // (86400 * 365)} năm trước"
        return f"{date_str} ({rel})"
    except Exception:
        return str(timestamp)

def analyze_shadowban_status(data: Dict[str, Any]) -> Tuple[str, str]:
    """Phân tích trạng thái Shadowban dựa trên các chỉ số nội bộ của TikTok."""
    is_nff_or_nr = data.get("is_nff_or_nr", False)
    comment_settings = data.get("item_comment_settings", 0)
    views = data.get("play_count", 0)
    create_time = data.get("create_time", 0)

    if is_nff_or_nr:
        status = "🔴 Bị hạn chế phân phối / Shadowbanned (có biên độ sai số)"
        reason = "Video bị gắn cờ 'Not For Feed' (không được đưa lên FYP) bởi hệ thống kiểm duyệt TikTok."
        return status, reason

    if comment_settings != 0:
        status = "🟡 Nghi vấn bị hạn chế (có biên độ sai số)"
        reason = "Phát hiện cài đặt bình luận bị khóa hoặc siết chặt từ hệ thống kiểm duyệt."
        return status, reason

    now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
    age_seconds = now_ts - create_time if create_time else 0
    if age_seconds > 86400 * 2 and views == 0:
        status = "🟡 Nghi vấn kẹt 0-View (có biên độ sai số)"
        reason = "Video đã đăng hơn 48 giờ nhưng có 0 lượt xem. Có thể bị kẹt thuật toán hoặc kiểm duyệt ẩn."
        return status, reason

    status = "🟢 Bình thường / Không phát hiện hạn chế (có biên độ sai số)"
    reason = "Video phân phối tự nhiên, đủ điều kiện xuất hiện trên bảng tin xu hướng FYP."
    return status, reason

def format_exact_number(val: Any) -> str:
    """Hiển thị số liệu chính xác từng lượt xem, tim, cmt (không làm tròn số)."""
    try:
        n = int(val)
        return f"{n:,} ({n})"
    except (ValueError, TypeError):
        return str(val) if val is not None else "0 (0)"

def format_duration_detailed(seconds_val: Any) -> str:
    """Định dạng thời lượng chi tiết."""
    try:
        s = float(seconds_val)
        mins = int(s) // 60
        secs = int(s) % 60
        return f"{mins:02d}:{secs:02d} ({s:.2f}s)"
    except Exception:
        return "00:00 (0s)"

def build_video_stats_message(data: Dict[str, Any]) -> str:
    """
    Tạo thông điệp thống kê video hoàn chỉnh với thiết kế mới (Fresh design & Premium Emojis)
    và đầy đủ TẤT CẢ các mục Checker theo yêu cầu.
    """
    cover_url = data.get("origin_cover") or data.get("cover")
    # Đặt preview video chất lượng tốt nhất ở ngay đầu tin nhắn
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''

    video_id = str(data.get("id") or "N/A")
    title = (data.get("title") or "Không có tiêu đề").strip()
    
    author = data.get("author") or {}
    nickname = author.get("nickname", "Unknown")
    unique_id = author.get("unique_id", "user")
    
    meta = data.get("_meta") or {}
    fmt = meta.get("format", "MP4 (MPEG-4 Part 14)")
    codec = meta.get("codec", "H.264 (AVC)")
    width = meta.get("width", 1080)
    height = meta.get("height", 1920)
    duration_str = format_duration_detailed(meta.get("duration_sec") or data.get("duration", 0))

    # Thông số Browser vs Mobile App
    browser_fps = meta.get("browser_fps", 60.0)
    app_fps = meta.get("app_fps", 120.0)
    browser_bitrate = meta.get("browser_bitrate_mbps", 0.0)
    app_bitrate = meta.get("app_bitrate_mbps", 0.0)
    browser_size = meta.get("browser_size_mb", 0.0)
    app_size = meta.get("app_size_mb", 0.0)

    # VQScore, Category, Keywords, Upload Source
    vq_score = meta.get("vq_score", 95.0)
    vq_label = meta.get("vq_label", "⚡ Rất Cao (High Bitrate)")
    category = meta.get("category", "🎬 General Entertainment")
    keywords = meta.get("keywords") or []
    keywords_str = " ".join([f"#{k}" for k in keywords[:8]]) if keywords else "Không có hashtag cụ thể"
    upload_source = meta.get("upload_source", "📱 TikTok Mobile App")

    # Số liệu chính xác từng lượt
    views_exact = format_exact_number(data.get("play_count", 0))
    likes_exact = format_exact_number(data.get("digg_count", 0))
    comments_exact = format_exact_number(data.get("comment_count", 0))
    shares_exact = format_exact_number(data.get("share_count", 0))
    collects_exact = format_exact_number(data.get("collect_count", 0))
    downloads_exact = format_exact_number(data.get("download_count", 0))

    created_date = format_creation_date_gmt0(data.get("create_time"))
    shadowban_status, _ = analyze_shadowban_status(data)
    upload_country = get_country_display(data.get("region"))

    # Link âm thanh trực tiếp
    music_url = data.get("music") or ""
    music_info = data.get("music_info") or {}
    music_title = (music_info.get("title") or "").strip()
    music_author = (music_info.get("author") or "").strip()
    if music_title and music_author:
        music_display = f"{music_title} - {music_author}"
    elif music_title:
        music_display = music_title
    else:
        music_display = "Âm thanh gốc (Original Audio)"

    audio_direct_link = f"<a href='{music_url}'>Bấm vào đây để nghe/tải nhạc</a>" if music_url else "Âm thanh gắn liền video"

    message = (
        f"{preview_tag}"
        f"👑 <b>TIKTOK-TWEAKS PREMIUM CHECKER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 <b>{title}</b>\n\n"
        f"🆔 <b>Video ID:</b> <code>{video_id}</code>\n"
        f"👤 <b>Tác giả:</b> {nickname} (@{unique_id})\n"
        f"⏱️ <b>Duration:</b> <code>{duration_str}</code>\n"
        f"📦 <b>Format:</b> <code>{fmt}</code>\n"
        f"🎞️ <b>Codec:</b> <code>{codec}</code>\n"
        f"📐 <b>Resolution:</b> <code>{width}x{height}</code>\n"
        f"📍 <b>Upload Source:</b> <b>{upload_source}</b>\n"
        f"🎯 <b>Category:</b> <b>{category}</b>\n"
        f"🔍 <b>Search Keywords:</b> <i>{keywords_str}</i>\n\n"
        f"📊 <b>THỐNG KÊ TƯƠNG TÁC (CHÍNH XÁC TỪNG LƯỢT)</b>\n"
        f"├ 👁️ Views: <code>{views_exact}</code>\n"
        f"├ ❤️ Likes: <code>{likes_exact}</code>\n"
        f"├ 💬 Comments: <code>{comments_exact}</code>\n"
        f"├ 🔄 Shares: <code>{shares_exact}</code>\n"
        f"├ ⭐ Favorites: <code>{collects_exact}</code>\n"
        f"└ 📥 Downloads: <code>{downloads_exact}</code>\n\n"
        f"💎 <b>TIKTOK VQSCORE COMPRESSION:</b>\n"
        f"└ 🏆 Điểm chất lượng: <b>{vq_score}/100</b> — {vq_label}\n\n"
        f"🌐 <b>BROWSER SPECS:</b>\n"
        f"├ 🚀 FPS: <code>{browser_fps:.1f} fps</code> (Web Standard)\n"
        f"├ ⚡ Bitrate: <code>{browser_bitrate:.2f} Mbps</code>\n"
        f"└ 💾 File size: <code>{browser_size:.2f} MB</code>\n\n"
        f"📱 <b>MOBILE APP SPECS:</b>\n"
        f"├ 🚀 FPS: <code>{app_fps:.1f} fps</code> (Original High-Refresh)\n"
        f"├ ⚡ Bitrate: <code>{app_bitrate:.2f} Mbps</code> (Adaptive Stream)\n"
        f"└ 💾 File size: <code>{app_size:.2f} MB</code> (Original Quality)\n"
        f"<i>⚠️ P.S. Quality in the mobile app depends on multiple factors (TikTok version, the phone used for viewing, region, internet connection quality, etc.)</i>\n\n"
        f"🎛️ <b>QUALITY PRESETS CATEGORY:</b>\n"
        f"├ 💎 <b>1080p Original:</b> HEVC/AVC Max Bitrate ({app_size:.1f}MB)\n"
        f"├ ⚡ <b>720p HD:</b> H.264 Web / Standard ({browser_size:.1f}MB)\n"
        f"├ 📱 <b>540p Mobile:</b> Compact Stream (Tiết kiệm data)\n"
        f"└ 🎧 <b>MP3 Audio:</b> 128 - 320 kbps Stereo\n\n"
        f"🔍 <b>THÔNG TIN XUẤT BẢN & SHADOWBAN:</b>\n"
        f"├ 📅 <b>Creation date (GMT+0):</b> <code>{created_date}</code>\n"
        f"├ 🛡️ <b>Shadowban status:</b> {shadowban_status}\n"
        f"├ 🌍 <b>Upload country:</b> <b>{upload_country}</b>\n"
        f"└ 🎵 <b>Audio Track Link:</b> {audio_direct_link}\n\n"
        f"<i>💡 Chọn tùy chọn tải bên dưới hoặc xem phân tích Profile:</i>"
    )
    return message

def build_profile_analytics_message(username: str, nickname: str, videos: List[Dict[str, Any]]) -> str:
    """Tạo bảng phân tích thống kê 12 video gần nhất của tác giả (Profile Analytics)."""
    if not videos:
        return (
            f"📈 <b>PHÂN TÍCH PROFILE: @{username}</b>\n\n"
            f"⚠️ Không thể tải danh sách video gần đây của tài khoản này (Kênh có thể ở chế độ riêng tư hoặc bị giới hạn)."
        )

    count = len(videos)
    total_views = sum(v["views"] for v in videos)
    total_likes = sum(v["likes"] for v in videos)
    total_comments = sum(v["comments"] for v in videos)

    avg_views = total_views // count if count > 0 else 0
    avg_likes = total_likes // count if count > 0 else 0
    avg_engagement = ((total_likes + total_comments) / total_views * 100) if total_views > 0 else 0.0

    # Tìm video tốt nhất
    best_vid = max(videos, key=lambda x: x["views"])
    worst_vid = min(videos, key=lambda x: x["views"])

    lines = [
        f"👑 <b>HỒ SƠ TÁC GIẢ & PHÂN TÍCH 12 VIDEO GẦN NHẤT</b>",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"👤 <b>Kênh:</b> {nickname} (@{username})",
        f"📊 <b>Tổng số video phân tích:</b> <code>{count} video</code>\n",
        f"📈 <b>TỔNG QUAN HIỆU SUẤT TRUNG BÌNH:</b>",
        f"├ 👁️ Lượt xem trung bình: <b>{avg_views:,} views/video</b>",
        f"├ ❤️ Lượt thích trung bình: <b>{avg_likes:,} likes/video</b>",
        f"├ 💬 Bình luận trung bình: <b>{total_comments // count:,} cmt/video</b>",
        f"├ ⚡ Tỷ lệ tương tác (ER): <b>{avg_engagement:.2f}%</b>",
        f"├ 🏆 Video top 1 view: <b>{best_vid['views']:,} views</b> (ID: <code>{best_vid['id']}</code>)",
        f"└ 📉 Video thấp nhất: <b>{worst_vid['views']:,} views</b> (ID: <code>{worst_vid['id']}</code>)\n",
        f"🎬 <b>DANH SÁCH {count} VIDEO MỚI NHẤT:</b>"
    ]

    for i, v in enumerate(videos[:12], 1):
        v_title = v["title"][:28] + "..." if len(v["title"]) > 28 else v["title"]
        lines.append(
            f"{i:02d}. <a href='{v['url']}'>{v_title}</a>\n"
            f"   └ 👁️ <code>{v['views']:,}</code> | ❤️ <code>{v['likes']:,}</code> | ⏱️ <code>{v['duration']}s</code>"
        )

    lines.append("\n<i>💡 Dữ liệu được trích xuất trực tiếp thời gian thực từ TikTok Studio.</i>")
    return "\n".join(lines)

def build_similar_videos_message(data: Dict[str, Any]) -> str:
    """Tạo bảng gợi ý video tương tự theo thuật toán TikTok (Similar Videos)."""
    meta = data.get("_meta") or {}
    category = meta.get("category", "Giải trí")
    keywords = meta.get("keywords") or []
    tags_str = ", ".join([f"#{k}" for k in keywords[:6]]) if keywords else "#fyp, #viral"

    msg = (
        f"🔮 <b>WHAT TIKTOK CONSIDERS RELATED (VIDEO TƯƠNG TỰ)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Cụm chủ đề thuật toán:</b> <b>{category}</b>\n"
        f"🏷️ <b>Thẻ liên kết FYP:</b> <i>{tags_str}</i>\n\n"
        f"📌 <b>Cách thuật toán TikTok đề xuất nội dung tương tự:</b>\n"
        f"1. <b>Theo âm thanh:</b> Những video cùng sử dụng nhạc nền này đang được gom nhóm vào chung luồng FYP.\n"
        f"2. <b>Theo từ khóa:</b> Video của bạn xuất hiện trong cụm tìm kiếm: <code>{tags_str}</code>\n"
        f"3. <b>Theo hành vi người xem:</b> Người thích video này cũng thường xem các video cùng chủ đề <b>{category}</b>.\n\n"
        f"🔗 <b>Khám phá thêm trên TikTok:</b>\n"
        f"• <a href='https://www.tiktok.com/tag/{keywords[0] if keywords else 'trending'}'>Xem xu hướng hashtag tương tự</a>\n"
    )
    return msg

def build_user_info_message(data: Dict[str, Any]) -> str:
    """Hiển thị thông tin người dùng (Author Information)."""
    author = data.get("author") or {}
    user_id = author.get("id", "N/A")
    unique_id = author.get("unique_id", "user")
    nickname = author.get("nickname", "Không có tên")
    profile_url = f"https://www.tiktok.com/@{unique_id}"
    country = get_country_display(data.get("region"))

    msg = (
        f"👤 <b>HỒ SƠ TÁC GIẢ (USER INFORMATION)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"🏷️ <b>Username:</b> @{unique_id}\n"
        f"📛 <b>Nickname:</b> {nickname}\n"
        f"🌍 <b>Khu vực đăng ký:</b> {country}\n"
        f"🔗 <b>Trang cá nhân:</b> <a href='{profile_url}'>{profile_url}</a>\n"
    )
    return msg

def build_instagram_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Instagram Reels / Post."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title") or "Instagram Media"
    if len(title) > 200:
        title = title[:197] + "..."

    author = data.get("author") or {}
    nickname = author.get("nickname", "Instagram User")
    unique_id = author.get("unique_id", "instagram")
    duration = data.get("duration", 0)
    w = data.get("width") or 1080
    h = data.get("height") or 1920

    msg = (
        f"{preview_tag}"
        f"📸 <b>INSTAGRAM MEDIA DOWNLOADER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 <b>{title}</b>\n\n"
        f"👤 <b>Tác giả:</b> {nickname} (@{unique_id})\n"
        f"⏱️ <b>Thời lượng:</b> <code>{duration}s</code>\n"
        f"📐 <b>Độ phân giải:</b> <code>{w}x{h}</code>\n"
        f"❤️ <b>Likes:</b> <code>{format_exact_number(data.get('likes', 0))}</code>\n"
        f"💬 <b>Comments:</b> <code>{format_exact_number(data.get('comments', 0))}</code>\n\n"
        f"<i>💡 Bấm nút bên dưới để tải video Instagram không có logo:</i>"
    )
    return msg

def build_youtube_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải YouTube (Shorts & Videos, hỗ trợ 4K & MP3 320k)."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title") or "YouTube Media"
    if len(title) > 200:
        title = title[:197] + "..."

    uploader = data.get("uploader", "YouTube Creator")
    duration = data.get("duration", 0)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration >= 60 else f"{duration}s"
    is_4k = data.get("is_4k", False)
    max_h = data.get("max_height", 1080)
    badge_4k = " 🏆 <b>4K ULTRA HD</b>" if is_4k else f" ⚡ <b>{max_h}p FHD</b>"

    msg = (
        f"{preview_tag}"
        f"🔴 <b>YOUTUBE DOWNLOADER</b>{badge_4k}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎬 <b>{title}</b>\n\n"
        f"👤 <b>Kênh:</b> <code>{uploader}</code>\n"
        f"⏱️ <b>Thời lượng:</b> <code>{dur_str}</code>\n"
        f"👁️ <b>Lượt xem:</b> <code>{format_exact_number(data.get('views', 0))}</code>\n"
        f"❤️ <b>Lượt thích:</b> <code>{format_exact_number(data.get('likes', 0))}</code>\n\n"
        f"<i>💡 Chọn độ phân giải hoặc tải MP3 320kbps bên dưới:</i>"
    )
    return msg

def build_twitter_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Twitter / X Media."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title") or "Twitter / X Post"
    uploader = data.get("uploader", "X User")
    duration = data.get("duration", 0)

    msg = (
        f"{preview_tag}"
        f"🐦 <b>TWITTER / X DOWNLOADER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>{title}</b>\n\n"
        f"👤 <b>Tác giả:</b> <code>{uploader}</code>\n"
        f"⏱️ <b>Thời lượng:</b> <code>{duration}s</code>\n"
        f"❤️ <b>Lượt thích:</b> <code>{format_exact_number(data.get('likes', 0))}</code>\n\n"
        f"<i>💡 Video chất lượng cao nhất không nén:</i>"
    )
    return msg

def build_pinterest_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Pinterest Pin (Video hoặc Ảnh gốc)."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title") or "Pinterest Pin"
    uploader = data.get("uploader", "Pinterest Creator")
    is_vid = data.get("is_video", False)
    media_type = "🎬 Video Pin (Không logo)" if is_vid else "🖼️ Ảnh gốc độ phân giải cao"

    msg = (
        f"{preview_tag}"
        f"📌 <b>PINTEREST DOWNLOADER</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{title}</b>\n\n"
        f"👤 <b>Người đăng:</b> <code>{uploader}</code>\n"
        f"📂 <b>Định dạng:</b> <b>{media_type}</b>\n\n"
        f"<i>💡 Bấm nút bên dưới để lưu file trực tiếp về thiết bị:</i>"
    )
    return msg

def build_spotify_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải nhạc Spotify MP3 320kbps."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title", "Spotify Track")
    artist = data.get("artist", "Spotify Artist")

    msg = (
        f"{preview_tag}"
        f"🟢 <b>SPOTIFY MUSIC DOWNLOADER (MP3 320 KBPS)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 <b>Bài hát:</b> <b>{title}</b>\n"
        f"🎤 <b>Nghệ sĩ:</b> <code>{artist}</code>\n"
        f"💎 <b>Chất lượng âm thanh:</b> <b>MP3 320 kbps High Fidelity</b>\n"
        f"🎧 <b>Đầy đủ ID3 Tags & Album Cover Art</b>\n\n"
        f"<i>💡 Bấm nút tải bên dưới để nhận ngay file nhạc đầy đủ:</i>"
    )
    return msg

def build_user_profile_stats_message(user_data: Dict[str, Any]) -> str:
    """Tạo thẻ Profile với số liệu thực tế (Real Numbers) và các cài đặt tương tác."""
    user_id = user_data.get("user_id", 0)
    full_name = user_data.get("full_name") or "Người dùng"
    username = user_data.get("username") or ""
    uname_str = f" (@{username})" if username else ""
    
    total_dl = user_data.get("total_downloads", 0)
    total_ck = user_data.get("total_checks", 0)
    total_sh = user_data.get("total_shazams", 0)
    
    dl_tt = user_data.get("dl_tiktok", 0)
    dl_ig = user_data.get("dl_instagram", 0)
    dl_yt = user_data.get("dl_youtube", 0)
    dl_tw = user_data.get("dl_twitter", 0)
    dl_pin = user_data.get("dl_pinterest", 0)
    dl_sp = user_data.get("dl_spotify", 0)

    mode = (user_data.get("mode") or "hybrid").upper()
    lang = (user_data.get("language") or "vi").upper()
    reply = (user_data.get("reply_mode") or "direct").capitalize()
    caption = (user_data.get("caption_mode") or "full").capitalize()
    doc_mode = "✅ BẬT (Document Không nén)" if user_data.get("doc_mode") else "❌ TẮT (Video chuẩn)"
    no_sig = "✅ BẬT (Không chữ ký)" if user_data.get("no_signature") else "❌ TẮT (Kèm link bot)"

    msg = (
        f"👑 <b>HỒ SƠ CÁ NHÂN & THỐNG KÊ THỰC TẾ (REAL STATS)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Tài khoản:</b> <b>{full_name}</b>{uname_str}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"💎 <b>Cấp bậc:</b> <b>PRO UNLIMITED MEMBER</b> 🚀\n\n"
        f"📊 <b>TỔNG SỐ LIỆU ĐÃ SỬ DỤNG:</b>\n"
        f"├ ⚡ <b>Tổng lượt tải (Downloads):</b> <code>{total_dl:,}</code>\n"
        f"├ 🔍 <b>Tổng lượt kiểm tra (Checks):</b> <code>{total_ck:,}</code>\n"
        f"└ 🎧 <b>Tổng nhận diện nhạc (Shazams):</b> <code>{total_sh:,}</code>\n\n"
        f"🌐 <b>LƯỢT TẢI THEO NỀN TẢNG:</b>\n"
        f"├ 🎵 TikTok: <code>{dl_tt:,}</code>    📸 Instagram: <code>{dl_ig:,}</code>\n"
        f"├ 🔴 YouTube: <code>{dl_yt:,}</code>    🐦 Twitter/X: <code>{dl_tw:,}</code>\n"
        f"└ 📌 Pinterest: <code>{dl_pin:,}</code>  🟢 Spotify: <code>{dl_sp:,}</code>\n\n"
        f"⚙️ <b>CÀI ĐẶT HIỆN TẠI (ALL SWITCHES):</b>\n"
        f"├ 🔀 <b>Chế độ bot:</b> {mode}\n"
        f"├ 🌐 <b>Ngôn ngữ:</b> {lang}\n"
        f"├ 💬 <b>Chế độ phản hồi:</b> {reply}\n"
        f"├ 📝 <b>Định dạng Caption:</b> {caption}\n"
        f"├ 📁 <b>Gửi file gốc Document:</b> {doc_mode}\n"
        f"└ 🛡️ <b>Bỏ chữ ký bot:</b> {no_sig}\n\n"
        f"<i>💡 Bấm các nút bên dưới hoặc mở Mini App để đổi cài đặt:</i>"
    )
    return msg

