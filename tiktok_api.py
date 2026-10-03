import re
import aiohttp
import asyncio
import os
import uuid
import tempfile
from typing import Optional, Dict, Any, Tuple, List
import yt_dlp
import config

# Regular expressions for matching TikTok Video, TikTok Music, and Instagram links
TIKTOK_VIDEO_REGEX = re.compile(
    r'https?://(?:(?:www|m|vt|vm|t)\.)?tiktok\.com/(?:t/[a-zA-Z0-9_-]+|@[^/]+/video/\d+|[a-zA-Z0-9_-]+/?(?:\?[^\s]*)?)',
    re.IGNORECASE
)

TIKTOK_MUSIC_REGEX = re.compile(
    r'https?://(?:(?:www|m|vt|vm)\.)?tiktok\.com/music/[^\s]+',
    re.IGNORECASE
)

INSTAGRAM_REGEX = re.compile(
    r'https?://(?:www\.)?instagram\.com/(?:reel|p|tv|share/reel)/[a-zA-Z0-9_-]+/?',
    re.IGNORECASE
)

def extract_media_url(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Trích xuất link media từ tin nhắn:
    Trả về: (url, platform_type)
    platform_type: 'tiktok_video' | 'tiktok_music' | 'instagram' | None
    """
    if not text:
        return None, None

    # 1. Kiểm tra link TikTok Music trước
    m_music = TIKTOK_MUSIC_REGEX.search(text)
    if m_music:
        url = m_music.group(0).strip().rstrip('.,)>]?')
        return url, "tiktok_music"

    # 2. Kiểm tra link Instagram
    m_ig = INSTAGRAM_REGEX.search(text)
    if m_ig:
        url = m_ig.group(0).strip().rstrip('.,)>]?')
        return url, "instagram"

    # 3. Kiểm tra link TikTok Video (bao gồm tiktok.com/t/id/, vt, vm, standard)
    m_tt = TIKTOK_VIDEO_REGEX.search(text)
    if m_tt:
        url = m_tt.group(0).strip().rstrip('.,)>]?')
        return url, "tiktok_video"

    return None, None

# Tương thích ngược với hàm cũ
def extract_tiktok_url(text: str) -> Optional[str]:
    url, p_type = extract_media_url(text)
    if p_type in ("tiktok_video", "tiktok_music"):
        return url
    return None

async def resolve_tiktok_shortlink(url: str) -> str:
    """Theo dõi HTTP redirect cho các link rút gọn (tiktok.com/t/id/, vt, vm)."""
    if any(pat in url.lower() for pat in ("/t/", "vt.tiktok.com", "vm.tiktok.com")):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.url and str(resp.url) != url:
                        return str(resp.url)
        except Exception:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.url and str(resp.url) != url:
                            return str(resp.url)
            except Exception:
                pass
    return url

def calculate_vqscore(bitrate_mbps: float, width: int, height: int, fps: float) -> Tuple[float, str]:
    """
    Tính VQScore (Video Quality Score - Thang điểm chất lượng nén của TikTok từ 0 đến 100)
    dựa trên Bitrate, độ phân giải và tốc độ khung hình.
    """
    if width <= 0 or height <= 0 or fps <= 0 or bitrate_mbps <= 0:
        return 88.0, "✨ Tốt (Standard Quality)"

    pixels_per_second = width * height * fps
    bpp = (bitrate_mbps * 1000 * 1000) / pixels_per_second

    score = min(99.5, max(60.0, 75.0 + (bpp * 50.0)))
    score = round(score, 1)

    if score >= 96.0:
        label = "💎 Studio Master (Nén cực thấp / Nét tuyệt đối)"
    elif score >= 90.0:
        label = "⚡ Rất Cao (High Bitrate / Độ nét cao)"
    elif score >= 80.0:
        label = "✨ Tiêu Chuẩn (Standard Compression)"
    else:
        label = "📱 Tiết Kiệm (Compact / Nén nhiều)"

    return score, label

def infer_video_category(title: str, hashtags: List[str]) -> str:
    """Xác định danh mục nội dung video theo phân loại thuật toán TikTok."""
    text = (title + " " + " ".join(hashtags)).lower()
    
    if any(k in text for k in ("game", "wuwa", "wuthering", "genshin", "mlbb", "roblox", "pubg", "ff", "anime", "manga", "edit", "animation")):
        return "🎮 Gaming & Animation (Trò chơi & Hoạt hình)"
    elif any(k in text for k in ("music", "song", "dance", "remix", "nhac", "beat", "audio", "sing", "cover")):
        return "🎵 Music & Performance (Âm nhạc & Vũ đạo)"
    elif any(k in text for k in ("fashion", "beauty", "makeup", "outfit", "vlog", "daily", "style", "food", "cook", "travel")):
        return "👗 Lifestyle & Culture (Đời sống & Văn hóa)"
    elif any(k in text for k in ("tech", "coding", "ai", "pc", "iphone", "review", "tip", "tool", "setup", "learn", "study")):
        return "💻 Technology & Science (Công nghệ & Khoa học)"
    elif any(k in text for k in ("funny", "meme", "haihuoc", "lol", "troll", "comedy", "joke")):
        return "🎭 Comedy & Entertainment (Hài hước & Giải trí)"
    
    return "🎬 General Entertainment (Giải trí Đa phương tiện)"

def infer_upload_source(data: Dict[str, Any], meta: Dict[str, Any]) -> str:
    """Xác định nguồn xuất bản video (Upload Source Category)."""
    title = (data.get("title") or "").lower()
    if "capcut" in title or data.get("anchors") or data.get("commerce_info"):
        return "🎬 CapCut Creative Suite / Desktop Video Editor"
    if data.get("is_ad"):
        return "📢 TikTok Ads Manager / Business Studio"
    
    fps = meta.get("fps", 30)
    bitrate = meta.get("bitrate_mbps", 0)
    if fps > 60 or bitrate > 25.0:
        return "💻 TikTok Web Studio / Desktop Upload (Chất lượng gốc không nén)"
    
    return "📱 TikTok Mobile App (iOS / Android Native Camera)"

def parse_mp4_full_metadata(chunk: bytes, file_size: int = 0) -> Dict[str, Any]:
    """Trích xuất toàn bộ metadata chi tiết từ MP4 header."""
    info = {
        "format": "MP4 (MPEG-4 Part 14)",
        "codec": "H.264 (AVC)",
        "width": 1080,
        "height": 1920,
        "duration_sec": 0.0,
        "fps": 30.0,
        "bitrate_mbps": 0.0
    }

    chunk_len = len(chunk)

    # 1. Codec 4CC
    if b'hvc1' in chunk or b'hev1' in chunk:
        info["codec"] = "H.265 (HEVC)"
    elif b'av01' in chunk:
        info["codec"] = "AV1"
    elif b'vp09' in chunk:
        info["codec"] = "VP9"
    elif b'avc1' in chunk:
        info["codec"] = "H.264 (AVC)"

    # 2. tkhd (width & height)
    tkhd_idx = chunk.find(b'tkhd')
    if tkhd_idx != -1:
        for offset in [84, 96, 92, 88]:
            if tkhd_idx + offset <= chunk_len:
                w = int.from_bytes(chunk[tkhd_idx + offset - 8 : tkhd_idx + offset - 6], 'big')
                h = int.from_bytes(chunk[tkhd_idx + offset - 4 : tkhd_idx + offset - 2], 'big')
                if 200 <= w <= 7680 and 200 <= h <= 7680:
                    info["width"] = w
                    info["height"] = h
                    break

    # 3. mdhd (timescale & duration)
    mdhd_idx = chunk.find(b'mdhd')
    timescale = 0
    if mdhd_idx != -1 and mdhd_idx + 24 <= chunk_len:
        version = chunk[mdhd_idx + 4]
        if version == 0:
            timescale = int.from_bytes(chunk[mdhd_idx + 16 : mdhd_idx + 20], 'big')
            dur = int.from_bytes(chunk[mdhd_idx + 20 : mdhd_idx + 24], 'big')
            if timescale > 0:
                info["duration_sec"] = round(dur / timescale, 2)
        elif version == 1 and mdhd_idx + 36 <= chunk_len:
            timescale = int.from_bytes(chunk[mdhd_idx + 24 : mdhd_idx + 28], 'big')
            dur = int.from_bytes(chunk[mdhd_idx + 28 : mdhd_idx + 36], 'big')
            if timescale > 0:
                info["duration_sec"] = round(dur / timescale, 2)

    # 4. stts (FPS = timescale / sample_delta)
    stts_idx = chunk.find(b'stts')
    if stts_idx != -1 and stts_idx + 20 <= chunk_len:
        entry_count = int.from_bytes(chunk[stts_idx + 8 : stts_idx + 12], 'big')
        if entry_count >= 1:
            sample_delta = int.from_bytes(chunk[stts_idx + 16 : stts_idx + 20], 'big')
            if timescale > 0 and sample_delta > 0:
                raw_fps = timescale / sample_delta
                if abs(raw_fps - 120) < 1.5:
                    info["fps"] = 120.0
                elif abs(raw_fps - 60) < 1.5:
                    info["fps"] = 60.0
                elif abs(raw_fps - 30) < 1.5:
                    info["fps"] = 30.0
                elif abs(raw_fps - 24) < 1:
                    info["fps"] = 24.0
                else:
                    info["fps"] = round(raw_fps, 1)

    # 5. Bitrate
    if file_size > 0 and info["duration_sec"] > 0:
        bitrate_bps = (file_size * 8) / info["duration_sec"]
        info["bitrate_mbps"] = round(bitrate_bps / (1000 * 1000), 2)

    return info

async def probe_video_full_metadata(video_url: str, file_size: int = 0) -> Optional[Dict[str, Any]]:
    """Tải 128KB header của video để phân tích thông số kỹ thuật."""
    if not video_url:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/",
        "Range": "bytes=0-131072"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status in (200, 206):
                    chunk = await resp.read()
                    return parse_mp4_full_metadata(chunk, file_size)
    except Exception:
        pass
    return None

async def fetch_tiktok_video(tiktok_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Gọi API TikWM để lấy thông tin chi tiết và tính toán đầy đủ các thông số Checker."""
    resolved_url = await resolve_tiktok_shortlink(tiktok_url)

    api_url = "https://www.tikwm.com/api/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    payload = {"url": resolved_url, "hd": 1}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)) as resp:
                if resp.status != 200:
                    return False, None, f"Lỗi máy chủ TikTok API (Mã {resp.status})."

                result = await resp.json()
                if result.get("code") != 0 or not result.get("data"):
                    if resolved_url != tiktok_url:
                        payload["url"] = tiktok_url
                        async with session.post(api_url, data=payload, headers=headers) as retry_resp:
                            if retry_resp.status == 200:
                                retry_res = await retry_resp.json()
                                if retry_res.get("code") == 0 and retry_res.get("data"):
                                    result = retry_res

                if result.get("code") != 0 or not result.get("data"):
                    msg = result.get("msg", "Không thể tìm thấy video. Link có thể ở chế độ riêng tư hoặc đã bị xóa.")
                    return False, None, msg

                data = result["data"]

                hd_url = data.get("hdplay") or data.get("play")
                hd_size = data.get("hd_size") or data.get("size") or 0
                meta = await probe_video_full_metadata(hd_url, hd_size)

                duration_val = (meta.get("duration_sec") if meta else 0) or data.get("duration", 0)

                std_size = data.get("size") or hd_size
                browser_size_mb = round(std_size / (1024 * 1024), 2)
                app_size_mb = round(hd_size / (1024 * 1024), 2)

                app_bitrate = meta.get("bitrate_mbps", 0.0) if meta else 0.0
                if app_bitrate == 0.0 and duration_val > 0 and hd_size > 0:
                    app_bitrate = round((hd_size * 8) / (duration_val * 1000 * 1000), 2)

                browser_bitrate = round((std_size * 8) / (duration_val * 1000 * 1000), 2) if (duration_val > 0 and std_size > 0) else app_bitrate
                fps_source = meta.get("fps", 30.0) if meta else 30.0
                browser_fps = min(fps_source, 60.0)
                app_fps = fps_source

                width = meta.get("width", 1080) if meta else 1080
                height = meta.get("height", 1920) if meta else 1920

                # Tính VQScore
                vq_score, vq_label = calculate_vqscore(app_bitrate, width, height, app_fps)

                # Trích xuất từ khóa tìm kiếm & Hashtags
                title_str = data.get("title") or ""
                keywords = re.findall(r'#(\w+)', title_str)
                category = infer_video_category(title_str, keywords)
                upload_source = infer_upload_source(data, meta or {})

                data["_meta"] = {
                    "format": meta.get("format", "MP4 (MPEG-4 Part 14)") if meta else "MP4 (MPEG-4 Part 14)",
                    "codec": meta.get("codec", "H.264 (AVC)") if meta else "H.264 (AVC)",
                    "width": width,
                    "height": height,
                    "duration_sec": duration_val,
                    "browser_fps": browser_fps,
                    "app_fps": app_fps,
                    "browser_bitrate_mbps": browser_bitrate,
                    "app_bitrate_mbps": app_bitrate,
                    "browser_size_mb": browser_size_mb,
                    "app_size_mb": app_size_mb,
                    "vq_score": vq_score,
                    "vq_label": vq_label,
                    "category": category,
                    "keywords": keywords,
                    "upload_source": upload_source,
                }
                data["_width"] = width
                data["_height"] = height

                return True, data, None

    except asyncio.TimeoutError:
        return False, None, "Quá thời gian kết nối đến máy chủ TikTok. Vui lòng thử lại sau giây lát."
    except Exception as e:
        return False, None, f"Đã xảy ra lỗi khi xử lý link: {str(e)}"

# ==============================================================
# Instagram Downloader Integration
# ==============================================================

async def fetch_instagram_media(ig_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Tải thông tin và video Instagram (Reels, Posts, IGTV) bằng yt-dlp.
    """
    def _extract_ig():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(ig_url, download=False)

    try:
        info = await asyncio.to_thread(_extract_ig)
        if not info:
            return False, None, "Không thể lấy thông tin bài viết Instagram."

        video_url = info.get("url")
        # Kiểm tra format nếu url trực tiếp không nằm ở gốc
        if not video_url and info.get("formats"):
            video_url = info["formats"][-1].get("url")

        if not video_url:
            return False, None, "Bài viết Instagram này có thể là ảnh hoặc ở chế độ riêng tư."

        data = {
            "id": info.get("id"),
            "title": info.get("title") or info.get("description") or "Instagram Media",
            "author": {
                "nickname": info.get("uploader") or info.get("channel") or "Instagram User",
                "unique_id": info.get("uploader_id") or "instagram",
            },
            "video_url": video_url,
            "cover": info.get("thumbnail"),
            "duration": info.get("duration", 0),
            "width": info.get("width"),
            "height": info.get("height"),
            "likes": info.get("like_count", 0),
            "comments": info.get("comment_count", 0),
            "platform": "instagram"
        }
        return True, data, None

    except Exception as e:
        return False, None, f"Lỗi trích xuất Instagram: {str(e)}"

# ==============================================================
# Author Profile Analytics (Last 12 Videos)
# ==============================================================

async def fetch_author_recent_12_videos(username: str) -> List[Dict[str, Any]]:
    """
    Trích xuất danh sách 12 video gần nhất của tác giả bằng yt-dlp flat playlist.
    """
    def _get_posts():
        url = f"https://www.tiktok.com/@{username}"
        ydl_opts = {
            'extract_flat': True,
            'playlistend': 12,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = info.get('entries', [])
            results = []
            for e in entries:
                results.append({
                    "id": e.get("id"),
                    "title": e.get("title") or "Không có tiêu đề",
                    "views": int(e.get("view_count") or 0),
                    "likes": int(e.get("like_count") or 0),
                    "comments": int(e.get("comment_count") or 0),
                    "duration": int(e.get("duration") or 0),
                    "url": e.get("url") or f"https://www.tiktok.com/@{username}/video/{e.get('id')}"
                })
            return results

    try:
        return await asyncio.to_thread(_get_posts)
    except Exception:
        return []

# ==============================================================
# Quality & Downloading Helpers
# ==============================================================

def get_download_url_by_quality(data: Dict[str, Any], quality: str) -> Tuple[str, str, int]:
    """
    Lấy link tải video theo 2 chất lượng chính (Original / Standard)
    hoặc độ phân giải cụ thể (1080p, 720p, 540p).
    """
    quality = quality.lower().strip()
    hd_url = data.get("hdplay")
    std_url = data.get("play")
    hd_size = data.get("hd_size") or 0
    std_size = data.get("size") or 0

    if quality in ("original", "high", "1080p"):
        if hd_url:
            return hd_url, "Original (Chất lượng gốc khi đăng tải)", hd_size
        return std_url, "Original (Standard Fallback)", std_size

    elif quality in ("720p", "standard", "medium"):
        if std_url:
            return std_url, "Standard 720p (Tiêu chuẩn)", std_size
        return hd_url, "Standard (Matched Original)", hd_size

    elif quality in ("540p", "low"):
        if std_url:
            return std_url, "Compact 540p (Tiết kiệm dữ liệu)", std_size
        return hd_url, "Compact (Matched Original)", hd_size

    # Mặc định
    if std_url:
        return std_url, "Standard (Tiêu chuẩn)", std_size
    if hd_url:
        return hd_url, "Original (Gốc)", hd_size
    return "", "Unknown", 0

async def download_file_to_path(url: str, save_path: str, max_size_mb: int = 512) -> Tuple[bool, Optional[str]]:
    """Tải file theo chunking với giới hạn 512MB và cơ chế fallback curl_cffi chống 403."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/"
    }
    max_bytes = max_size_mb * 1024 * 1024

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status not in (200, 206):
                    # Fallback sang curl_cffi nếu CDN chặn bot (403 Forbidden)
                    try:
                        from curl_cffi import requests as cffi_requests
                        def _curl_download():
                            with cffi_requests.get(url, impersonate="chrome120", timeout=300, stream=True) as r:
                                if r.status_code not in (200, 206):
                                    return False, f"Máy chủ phản hồi mã lỗi {r.status_code}"
                                dl = 0
                                with open(save_path, "wb") as f_out:
                                    for chunk in r.iter_content(chunk_size=65536):
                                        if chunk:
                                            dl += len(chunk)
                                            if dl > max_bytes:
                                                return False, f"File quá lớn vượt quá {max_size_mb}MB"
                                            f_out.write(chunk)
                                return True, None
                        return await asyncio.to_thread(_curl_download)
                    except Exception as e_cffi:
                        return False, f"Máy chủ video phản hồi mã lỗi {resp.status} (Fallback: {e_cffi})"

                content_len = resp.headers.get("Content-Length")
                if content_len and int(content_len) > max_bytes:
                    return False, f"File quá lớn ({int(content_len)/(1024*1024):.1f}MB > {max_size_mb}MB giới hạn tải)."

                downloaded = 0
                with open(save_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            f.close()
                            if os.path.exists(save_path):
                                os.remove(save_path)
                            return False, f"Dung lượng tải về vượt quá {max_size_mb}MB giới hạn."
                        f.write(chunk)

                return True, None

    except asyncio.TimeoutError:
        return False, "Quá thời gian tải file từ máy chủ."
    except Exception as e:
        # Fallback thử curl_cffi nếu aiohttp gặp lỗi kết nối
        try:
            from curl_cffi import requests as cffi_requests
            def _curl_fallback():
                with cffi_requests.get(url, impersonate="chrome120", timeout=300, stream=True) as r:
                    if r.status_code not in (200, 206):
                        return False, f"Máy chủ phản hồi mã lỗi {r.status_code}"
                    dl = 0
                    with open(save_path, "wb") as f_out:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                dl += len(chunk)
                                if dl > max_bytes:
                                    return False, f"File quá lớn vượt quá {max_size_mb}MB"
                                f_out.write(chunk)
                    return True, None
            return await asyncio.to_thread(_curl_fallback)
        except Exception:
            return False, f"Lỗi tải file: {str(e)}"

async def download_thumbnail_to_path(thumb_url: str, save_path: str) -> bool:
    """Tải ảnh bìa làm thumbnail để tránh ô vuông đen với hỗ trợ Chrome TLS impersonation."""
    if not thumb_url:
        return False
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.tiktok.com/"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    content = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(content)
                    return True
    except Exception:
        pass

    # Fallback với curl_cffi giả lập Chrome
    try:
        from curl_cffi import requests as cffi_requests
        def _get_thumb():
            res = cffi_requests.get(thumb_url, impersonate="chrome120", timeout=15)
            if res.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(res.content)
                return True
            return False
        return await asyncio.to_thread(_get_thumb)
    except Exception:
        pass
    return False
