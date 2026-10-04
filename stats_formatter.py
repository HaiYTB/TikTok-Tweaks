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
        f"<b>TikTok Inspector</b> • <code>{video_id}</code>\n"
        f"🎬 <b>{title}</b>\n"
        f"👤 By <b>{nickname}</b> (<code>@{unique_id}</code>) • {upload_country}\n\n"
        f"📊 <b>Engagement Metrics</b>\n"
        f"• Views: <code>{views_exact}</code> • Likes: <code>{likes_exact}</code>\n"
        f"• Comments: <code>{comments_exact}</code> • Shares: <code>{shares_exact}</code>\n"
        f"• Saves: <code>{collects_exact}</code> • Downloads: <code>{downloads_exact}</code>\n\n"
        f"⚡ <b>Stream Specifications</b>\n"
        f"• Resolution: <code>{width}×{height}</code> ({fmt} • {codec})\n"
        f"• Mobile App: <code>{app_fps:.0f} FPS</code> • <code>{app_bitrate:.2f} Mbps</code> (HEVC, {app_size:.1f} MB)\n"
        f"• Web Browser: <code>{browser_fps:.0f} FPS</code> • <code>{browser_bitrate:.2f} Mbps</code> (H.264, {browser_size:.1f} MB)\n"
        f"• Quality Score: <b>{vq_score}/100</b> ({vq_label})\n"
        f"• Source: <b>{upload_source}</b> • ⏱️ <code>{duration_str}</code>\n\n"
        f"🔍 <b>Details</b>\n"
        f"• Category: <b>{category}</b>\n"
        f"• Keywords: <i>{keywords_str}</i>\n"
        f"• Published (GMT+0): <code>{created_date}</code>\n"
        f"• Shadowban: {shadowban_status}\n"
        f"• Audio Track: {audio_direct_link}\n"
    )
    return message

def build_profile_analytics_message(username: str, nickname: str, videos: List[Dict[str, Any]]) -> str:
    """Tạo bảng phân tích thống kê 12 video gần nhất của tác giả (Profile Analytics)."""
    if not videos:
        return (
            f"📊 <b>Author Analytics</b> • <code>@{username}</code>\n\n"
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
        f"📊 <b>Author Analytics</b> • <code>@{username}</code>",
        f"👤 <b>Channel:</b> {nickname} • {count} recent uploads analyzed\n",
        f"📈 <b>Average Performance</b>",
        f"• Views / Video: <code>{avg_views:,}</code>",
        f"• Likes / Video: <code>{avg_likes:,}</code>",
        f"• Comments / Video: <code>{total_comments // count if count > 0 else 0:,}</code>",
        f"• Engagement Rate: <b>{avg_engagement:.2f}%</b>\n",
        f"🏆 <b>Top Performer:</b> <code>{best_vid['views']:,}</code> views (ID: <code>{best_vid['id']}</code>)",
        f"📉 <b>Lowest Performer:</b> <code>{worst_vid['views']:,}</code> views\n",
        f"🎬 <b>Recent Videos</b>"
    ]

    for i, v in enumerate(videos[:12], 1):
        v_title = v["title"][:32] + "..." if len(v["title"]) > 32 else v["title"]
        lines.append(
            f"{i:02d}. <a href='{v['url']}'>{v_title}</a>\n"
            f"    👁️ <code>{v['views']:,}</code> • ❤️ <code>{v['likes']:,}</code> • ⏱️ <code>{v['duration']}s</code>"
        )

    return "\n".join(lines)

def build_similar_videos_message(data: Dict[str, Any]) -> str:
    """Tạo bảng gợi ý video tương tự theo thuật toán TikTok (Similar Videos)."""
    meta = data.get("_meta") or {}
    category = meta.get("category", "Entertainment")
    keywords = meta.get("keywords") or []
    tags_str = ", ".join([f"#{k}" for k in keywords[:6]]) if keywords else "#fyp, #viral"

    msg = (
        f"🔮 <b>TikTok Recommendation Insights</b>\n\n"
        f"🎯 <b>Algorithmic Cluster:</b> <b>{category}</b>\n"
        f"🏷️ <b>Associated Keywords:</b> <i>{tags_str}</i>\n\n"
        f"📌 <b>Recommendation Factors:</b>\n"
        f"• <b>Audio Graph:</b> Videos utilizing this audio track are clustered into this FYP stream.\n"
        f"• <b>Search Context:</b> Indexed under query graph: <code>{tags_str}</code>\n"
        f"• <b>Audience Overlap:</b> Viewers of this video engage heavily in <b>{category}</b>.\n"
    )
    return msg

def build_user_info_message(data: Dict[str, Any]) -> str:
    """Hiển thị thông tin người dùng (Author Information)."""
    author = data.get("author") or {}
    user_id = author.get("id", "N/A")
    unique_id = author.get("unique_id", "user")
    nickname = author.get("nickname", "Unknown")
    profile_url = f"https://www.tiktok.com/@{unique_id}"
    country = get_country_display(data.get("region"))

    msg = (
        f"👤 <b>Author Profile</b>\n\n"
        f"• Username: @{unique_id} (ID: <code>{user_id}</code>)\n"
        f"• Nickname: <b>{nickname}</b>\n"
        f"• Region: {country}\n"
        f"• Link: <a href='{profile_url}'>{profile_url}</a>\n"
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
        f"📸 <b>Instagram Media</b>\n"
        f"🎬 <b>{title}</b>\n"
        f"👤 By <b>{nickname}</b> (<code>@{unique_id}</code>)\n\n"
        f"• Duration: <code>{duration}s</code> • Resolution: <code>{w}×{h}</code>\n"
        f"• Likes: <code>{format_exact_number(data.get('likes', 0))}</code> • Comments: <code>{format_exact_number(data.get('comments', 0))}</code>\n"
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
    badge_4k = " • 🏆 <b>4K Ultra HD</b>" if is_4k else f" • ⚡ <b>{max_h}p FHD</b>"

    msg = (
        f"{preview_tag}"
        f"🔴 <b>YouTube Media</b>{badge_4k}\n"
        f"🎬 <b>{title}</b>\n"
        f"👤 Channel: <code>{uploader}</code> • Duration: <code>{dur_str}</code>\n\n"
        f"• Views: <code>{format_exact_number(data.get('views', 0))}</code> • Likes: <code>{format_exact_number(data.get('likes', 0))}</code>\n"
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
        f"🐦 <b>Twitter / X Media</b>\n"
        f"💬 <b>{title}</b>\n"
        f"👤 By <code>{uploader}</code> • Duration: <code>{duration}s</code>\n"
        f"• Likes: <code>{format_exact_number(data.get('likes', 0))}</code>\n"
    )
    return msg

def build_pinterest_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Pinterest Pin (Video hoặc Ảnh gốc)."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title") or "Pinterest Pin"
    uploader = data.get("uploader", "Pinterest Creator")
    is_vid = data.get("is_video", False)
    media_type = "🎬 Video Pin" if is_vid else "🖼️ HD Image"

    msg = (
        f"{preview_tag}"
        f"📌 <b>Pinterest Media</b>\n"
        f"<b>{title}</b>\n"
        f"👤 By <code>{uploader}</code> • {media_type}\n"
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
        f"🟢 <b>Spotify Track</b> • <b>MP3 320 kbps</b>\n"
        f"🎵 <b>{title}</b>\n"
        f"🎤 <code>{artist}</code> • High Fidelity Audio (ID3 Tagged)\n"
    )
    return msg

def build_user_profile_stats_message(user_data: Dict[str, Any]) -> str:
    """Tạo thẻ Profile với số liệu thực tế (Real Numbers) và các cài đặt tương tác."""
    user_id = user_data.get("user_id", 0)
    full_name = user_data.get("full_name") or "User"
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
    doc_mode = "ON (Uncompressed)" if user_data.get("doc_mode") else "OFF (Standard Video)"
    no_sig = "ON (Clean Caption)" if user_data.get("no_signature") else "OFF (With Bot Link)"

    msg = (
        f"👤 <b>Account Profile</b> • <b>{full_name}</b>{uname_str}\n"
        f"🆔 ID: <code>{user_id}</code> • Tier: <b>PRO Member</b> 🚀\n\n"
        f"📊 <b>Usage Statistics</b>\n"
        f"• Total Downloads: <code>{total_dl:,}</code>\n"
        f"• Total Inspections: <code>{total_ck:,}</code>\n"
        f"• Shazam Recognitions: <code>{total_sh:,}</code>\n\n"
        f"🌐 <b>Downloads by Platform</b>\n"
        f"• TikTok: <code>{dl_tt:,}</code> • YouTube: <code>{dl_yt:,}</code> • Instagram: <code>{dl_ig:,}</code>\n"
        f"• Twitter: <code>{dl_tw:,}</code> • Pinterest: <code>{dl_pin:,}</code> • Spotify: <code>{dl_sp:,}</code>\n\n"
        f"⚙️ <b>Active Preferences</b>\n"
        f"• Mode: <b>{mode}</b> • Language: <b>{lang}</b>\n"
        f"• Delivery: <b>{reply}</b> • Caption Format: <b>{caption}</b>\n"
        f"• Document Mode: <b>{doc_mode}</b>\n"
        f"• Bot Signature: <b>{no_sig}</b>\n"
    )
    return msg

