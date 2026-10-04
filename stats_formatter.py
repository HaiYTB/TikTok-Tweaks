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
    """Hiển thị số liệu phân cách hàng nghìn gọn gàng."""
    try:
        n = int(val)
        return f"{n:,}"
    except (ValueError, TypeError):
        return str(val) if val is not None else "0"

def format_duration_detailed(seconds_val: Any) -> str:
    """Định dạng thời lượng gọn gàng mm:ss."""
    try:
        s = float(seconds_val)
        mins = int(s) // 60
        secs = int(s) % 60
        return f"{mins:02d}:{secs:02d}"
    except Exception:
        return "00:00"

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

    # Số liệu tương tác & tính toán Engagement Rate
    views_val = int(data.get("play_count", 0) or 0)
    likes_val = int(data.get("digg_count", 0) or 0)
    comments_val = int(data.get("comment_count", 0) or 0)
    shares_val = int(data.get("share_count", 0) or 0)
    collects_val = int(data.get("collect_count", 0) or 0)

    # Công thức ER: (likes + comments + shares + saves) / views * 100
    total_eng = likes_val + comments_val + shares_val + collects_val
    er = (total_eng / views_val * 100) if views_val > 0 else 0.0
    save_rate = (collects_val / views_val * 100) if views_val > 0 else 0.0
    share_rate = (shares_val / views_val * 100) if views_val > 0 else 0.0

    if er >= 20.0:
        er_badge = "🔥 Siêu Viral"
    elif er >= 12.0:
        er_badge = "⚡ Rất Tốt"
    elif er >= 6.0:
        er_badge = "👍 Ổn định"
    else:
        er_badge = "📉 Thấp"

    views_exact = format_exact_number(views_val)
    likes_exact = format_exact_number(likes_val)
    comments_exact = format_exact_number(comments_val)
    shares_exact = format_exact_number(shares_val)
    collects_exact = format_exact_number(collects_val)

    downloads_val = int(data.get("download_count", 0) or 0)
    downloads_exact = format_exact_number(downloads_val)

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

    title_display = title if len(title) <= 150 else (title[:147] + "...")
    message = (
        f"{preview_tag}"
        f"🎬 <b>{title_display}</b>\n"
        f"🆔 <code>{video_id}</code> • 👤 {nickname} (<code>@{unique_id}</code>)\n"
        f"📍 {upload_country} • 📅 <code>{created_date}</code>\n\n"
        f"📊 <b>TƯƠNG TÁC & THUẬT TOÁN</b>\n"
        f"• 👁️ <code>{views_exact}</code> • ❤️ <code>{likes_exact}</code> • 💬 <code>{comments_exact}</code> • 🔄 <code>{shares_exact}</code> • ⭐ <code>{collects_exact}</code> • 📥 <code>{downloads_exact}</code>\n"
        f"• <b>ER: {er:.2f}%</b> ({er_badge}) • Lưu: <code>{save_rate:.1f}%</code> • Share: <code>{share_rate:.1f}%</code>\n\n"
        f"⚡ <b>THÔNG SỐ STREAM & CHẤT LƯỢNG</b>\n"
        f"• Độ phân giải: <code>{width}×{height}</code> ({fmt} • {codec})\n"
        f"• Mobile App: <code>{app_fps:.0f} FPS</code> • <code>{app_bitrate:.2f} Mbps</code> • <code>{app_size:.1f} MB</code> (HEVC Gốc)\n"
        f"• Web Browser: <code>{browser_fps:.0f} FPS</code> • <code>{browser_bitrate:.2f} Mbps</code> • <code>{browser_size:.1f} MB</code> (H.264)\n"
        f"• Điểm VQScore: <b>{vq_score}/100</b> — <i>{vq_label}</i>\n\n"
        f"🎯 <b>PHÂN LOẠI & KIỂM DUYỆT</b>\n"
        f"• Nguồn upload: <b>{upload_source}</b> • ⏱️ <code>{duration_str}</code>\n"
        f"• Danh mục: <b>{category}</b>\n"
        f"• Shadowban: {shadowban_status}\n"
        f"• Từ khóa: <i>{keywords_str}</i>\n"
        f"• Âm thanh: 🎵 <i>{music_display}</i>"
    )
    return message

def build_profile_analytics_message(username: str, nickname: str, videos: List[Dict[str, Any]]) -> str:
    """Tạo bảng phân tích chuyên sâu tài khoản: ER, Giờ đăng lý tưởng, Ngày đăng tốt nhất, Tần suất."""
    if not videos:
        return (
            f"📊 <b>Phân tích kênh:</b> @{username}\n"
            f"⚠️ Không thể tải danh sách video của kênh (Tài khoản có thể ở chế độ riêng tư hoặc chưa có video)."
        )

    count = len(videos)
    total_views = sum(v.get("views", 0) for v in videos)
    total_likes = sum(v.get("likes", 0) for v in videos)
    total_comments = sum(v.get("comments", 0) for v in videos)
    total_shares = sum(v.get("shares", 0) for v in videos)
    total_saves = sum(v.get("saves", 0) for v in videos)

    total_eng = total_likes + total_comments + total_shares + total_saves
    avg_views = total_views // count if count > 0 else 0
    channel_er = (total_eng / total_views * 100) if total_views > 0 else 0.0
    avg_dur = sum(v.get("duration", 0) for v in videos) // count if count > 0 else 0

    # Tính ER cho từng video
    for v in videos:
        v_v = v.get("views", 0)
        v_eng = v.get("likes", 0) + v.get("comments", 0) + v.get("shares", 0) + v.get("saves", 0)
        v["er"] = (v_eng / v_v * 100) if v_v > 0 else 0.0

    best_view_vid = max(videos, key=lambda x: x.get("views", 0))

    # Phân tích giờ đăng & ngày đăng tối ưu
    timed_vids = [v for v in videos if v.get("timestamp")]
    best_time_str = "18:00 - 21:00"
    best_days_str = "Cuối tuần"
    freq_str = "~1-2 ngày / video"

    if timed_vids:
        brackets = {
            "Trưa (11:30 - 13:30)": [],
            "Chiều (16:30 - 18:30)": [],
            "Tối (19:30 - 22:30)": [],
            "Sáng (07:00 - 09:30)": []
        }
        days_stat = {}
        day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]

        for v in timed_vids:
            dt = datetime.datetime.fromtimestamp(v["timestamp"], tz=datetime.timezone(datetime.timedelta(hours=7)))
            h = dt.hour
            dname = day_names[dt.weekday()]
            if dname not in days_stat:
                days_stat[dname] = {"views": 0, "count": 0}
            days_stat[dname]["views"] += v.get("views", 0)
            days_stat[dname]["count"] += 1

            if 11 <= h <= 14:
                brackets["Trưa (11:30 - 13:30)"].append(v)
            elif 16 <= h <= 18:
                brackets["Chiều (16:30 - 18:30)"].append(v)
            elif 19 <= h <= 23:
                brackets["Tối (19:30 - 22:30)"].append(v)
            else:
                brackets["Sáng (07:00 - 09:30)"].append(v)

        # Chọn khung giờ hiệu quả nhất theo views & ER
        active_brackets = {k: v for k, v in brackets.items() if len(v) > 0}
        if active_brackets:
            top_view_b = max(active_brackets.keys(), key=lambda k: sum(x.get("views", 0) for x in active_brackets[k]) / len(active_brackets[k]))
            top_er_b = max(active_brackets.keys(), key=lambda k: sum(x.get("er", 0) for x in active_brackets[k]) / len(active_brackets[k]))
            if top_view_b == top_er_b:
                best_time_str = f"{top_view_b} (Đỉnh View & ER)"
            else:
                best_time_str = f"{top_view_b} & {top_er_b}"

        # Chọn ngày hiệu quả nhất
        if days_stat:
            sorted_days = sorted(days_stat.keys(), key=lambda d: days_stat[d]["views"] / days_stat[d]["count"], reverse=True)
            best_days_str = ", ".join(sorted_days[:2])

        # Tần suất đăng
        timestamps = sorted([v["timestamp"] for v in timed_vids])
        span_days = (timestamps[-1] - timestamps[0]) / 86400.0
        if span_days >= 0.5 and len(timestamps) > 1:
            days_per_post = span_days / (len(timestamps) - 1)
            freq_str = f"~{days_per_post:.1f} ngày / video"

    lines = [
        f"📊 <b>Phân tích kênh:</b> @{username} ({nickname})",
        f"• Lượt xem TB: <code>{avg_views:,}</code> • Tổng view {count} video: <code>{total_views:,}</code>",
        f"• Tương tác kênh (ER): <b>{channel_er:.2f}%</b> (❤️ <code>{total_likes:,}</code> • 💬 <code>{total_comments:,}</code> • 🔄 <code>{total_shares:,}</code> • ⭐ <code>{total_saves:,}</code>)",
        f"• ⏰ <b>Giờ đăng lý tưởng:</b> <code>{best_time_str}</code> ({best_days_str})",
        f"• ⏱️ Thời lượng TB: <code>{avg_dur}s</code> • Tần suất: <code>{freq_str}</code>",
        f"• 🏆 Top 1 View: <code>{best_view_vid.get('views', 0):,}</code> (ER: <b>{best_view_vid.get('er', 0):.1f}%</b>)\n",
        f"<b>Gần đây ({count} video):</b>"
    ]

    for i, v in enumerate(videos[:6], 1):
        v_title = v["title"][:22] + "..." if len(v["title"]) > 22 else (v["title"] or "Video")
        lines.append(f"{i:02d}. <a href='{v['url']}'>{v_title}</a> (<code>{v['views']:,}</code> • ER: <b>{v.get('er', 0):.1f}%</b>)")

    return "\n".join(lines)

def build_similar_videos_message(data: Dict[str, Any]) -> str:
    """Tạo bảng gợi ý video tương tự theo thuật toán TikTok (Similar Videos)."""
    meta = data.get("_meta") or {}
    category = meta.get("category", "Entertainment")
    keywords = meta.get("keywords") or []
    tags_str = " ".join([f"#{k}" for k in keywords[:6]]) if keywords else "#fyp #viral"

    return (
        f"🔮 <b>Recommendation Signals</b>\n"
        f"• Cluster: <b>{category}</b>\n"
        f"• Keywords: <i>{tags_str}</i>"
    )

def build_user_info_message(data: Dict[str, Any]) -> str:
    """Hiển thị thông tin người dùng (Author Information)."""
    author = data.get("author") or {}
    user_id = author.get("id", "N/A")
    unique_id = author.get("unique_id", "user")
    nickname = author.get("nickname", "Unknown")
    profile_url = f"https://www.tiktok.com/@{unique_id}"
    country = get_country_display(data.get("region"))

    return (
        f"👤 <b>{nickname}</b> (<code>@{unique_id}</code>)\n"
        f"🆔 ID: <code>{user_id}</code> • 📍 {country}\n"
        f"🔗 <a href='{profile_url}'>{profile_url}</a>"
    )

def build_instagram_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Instagram Reels / Post."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = (data.get("title") or "Instagram Media").strip()
    title_disp = title if len(title) <= 55 else (title[:52] + "...")

    author = data.get("author") or {}
    nickname = author.get("nickname", "Instagram User")
    unique_id = author.get("unique_id", "instagram")
    duration = data.get("duration", 0)
    dur_str = f" • ⏱️ {duration}s" if duration else ""
    w = data.get("width") or 1080
    h = data.get("height") or 1920
    likes = format_exact_number(data.get("likes", 0))
    comments = format_exact_number(data.get("comments", 0))

    return (
        f"{preview_tag}"
        f"📸 <b>{title_disp}</b>\n"
        f"👤 {nickname} (<code>@{unique_id}</code>){dur_str}\n"
        f"📐 <code>{w}×{h}</code> • ❤️ <code>{likes}</code> • 💬 <code>{comments}</code>"
    )

def build_youtube_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải YouTube (Shorts & Videos, hỗ trợ 4K & MP3 320k)."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = (data.get("title") or "YouTube Media").strip()
    title_disp = title if len(title) <= 55 else (title[:52] + "...")

    uploader = data.get("uploader", "YouTube Creator")
    duration = data.get("duration", 0)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration >= 60 else f"{duration}s"
    is_4k = data.get("is_4k", False)
    max_h = data.get("max_height", 1080)
    badge_4k = "🏆 <b>4K UHD</b>" if is_4k else f"⚡ <b>{max_h}p</b>"
    views = format_exact_number(data.get("views", 0))
    likes = format_exact_number(data.get("likes", 0))

    return (
        f"{preview_tag}"
        f"🔴 <b>{title_disp}</b>\n"
        f"👤 <code>{uploader}</code> • ⏱️ {dur_str} • {badge_4k}\n"
        f"👁️ <code>{views}</code> • ❤️ <code>{likes}</code>"
    )

def build_twitter_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Twitter / X Media."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = (data.get("title") or "Twitter / X Post").strip()
    title_disp = title if len(title) <= 55 else (title[:52] + "...")
    uploader = data.get("uploader", "X User")
    duration = data.get("duration", 0)
    dur_str = f" • ⏱️ {duration}s" if duration else ""
    likes = format_exact_number(data.get("likes", 0))

    return (
        f"{preview_tag}"
        f"🐦 <b>{title_disp}</b>\n"
        f"👤 <code>@{uploader}</code>{dur_str} • ❤️ <code>{likes}</code>"
    )

def build_pinterest_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải Pinterest Pin (Video hoặc Ảnh gốc)."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = (data.get("title") or "Pinterest Pin").strip()
    title_disp = title if len(title) <= 55 else (title[:52] + "...")
    uploader = data.get("uploader", "Pinterest Creator")
    is_vid = data.get("is_video", False)
    media_type = "🎬 Video Pin" if is_vid else "🖼️ HD Image"

    return (
        f"{preview_tag}"
        f"📌 <b>{title_disp}</b>\n"
        f"👤 <code>{uploader}</code> • {media_type}"
    )

def build_spotify_stats_message(data: Dict[str, Any]) -> str:
    """Tạo bảng thông tin tải nhạc Spotify MP3 320kbps."""
    cover_url = data.get("cover")
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ''
    title = data.get("title", "Spotify Track")
    artist = data.get("artist", "Spotify Artist")

    return (
        f"{preview_tag}"
        f"🟢 <b>{title}</b>\n"
        f"🎤 <code>{artist}</code> • 🎵 <b>MP3 320 kbps</b>"
    )

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
        f"👤 <b>{full_name}</b>{uname_str} • <code>{user_id}</code>\n\n"
        f"📊 <b>Activity:</b> <code>{total_dl:,}</code> DLs • <code>{total_ck:,}</code> Checks • <code>{total_sh:,}</code> Shazams\n"
        f"🌐 <b>Platforms:</b> TT: <code>{dl_tt}</code> • YT: <code>{dl_yt}</code> • IG: <code>{dl_ig}</code> • X: <code>{dl_tw}</code> • Pin: <code>{dl_pin}</code> • SP: <code>{dl_sp}</code>\n"
        f"⚙️ <b>Settings:</b> Mode: <b>{mode}</b> • Doc: <b>{doc_mode}</b> • No-Sig: <b>{no_sig}</b>"
    )
    return msg

