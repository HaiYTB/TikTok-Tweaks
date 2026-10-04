import re
import json
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
    
    if any(k in text for k in ("game", "gaming", "tối ưu", "máy yếu", "mượt", "fps", "lag", "giật", "gpu", "cpu", "ram", "wuwa", "wuthering", "genshin", "mlbb", "roblox", "pubg", "ff", "free fire", "freefire", "garena", "brevent", "modun", "module", "anime", "manga", "edit", "animation", "minecraft", "play")):
        return "🎮 Video Games / Games / Entertainment (Trò chơi & Giải trí)"
    elif any(k in text for k in ("music", "song", "dance", "remix", "nhac", "beat", "audio", "sing", "cover")):
        return "🎵 Music & Performance (Âm nhạc & Vũ đạo)"
    elif any(k in text for k in ("fashion", "beauty", "makeup", "outfit", "vlog", "daily", "style", "food", "cook", "travel")):
        return "👗 Lifestyle & Culture (Đời sống & Văn hóa)"
    elif any(k in text for k in ("tech", "coding", "ai", "pc", "iphone", "review", "tip", "tool", "setup", "learn", "study")):
        return "💻 Technology & Science (Công nghệ & Khoa học)"
    elif any(k in text for k in ("funny", "meme", "haihuoc", "lol", "troll", "comedy", "joke")):
        return "🎭 Comedy & Entertainment (Hài hước & Giải trí)"
    
    return "🎬 General Entertainment (Giải trí Đa phương tiện)"

def calculate_original_resolution(w: int, h: int) -> str:
    """Tính toán độ phân giải gốc của thiết bị quay/dựng (Original Master)."""
    if w <= 0 or h <= 0:
        return "1080×1920"
    ratio = w / h
    # Landscape (màn hình ngang)
    if w > h:
        if abs(ratio - (20/9)) < 0.1:  # 2.22 chuẩn quay màn hình Gaming (Samsung/Xiaomi)
            return "1920×864"
        elif abs(ratio - (19.5/9)) < 0.08:  # 2.16 iPhone landscape
            return "1920×886"
        elif abs(ratio - (18/9)) < 0.08:  # 2.0
            return "1920×960"
        elif abs(ratio - (16/9)) < 0.08:  # 1.777 chuẩn 16:9
            return "1920×1080"
        elif abs(ratio - (4/3)) < 0.08:  # 1.333 iPad / Tablet
            return "1440×1080"
        else:
            scale = 1920 / w if w < 1920 else 1.0
            return f"{int(round(w * scale))}×{int(round(h * scale))}"
    # Portrait (màn hình dọc)
    elif h > w:
        inv_ratio = h / w
        if abs(inv_ratio - (20/9)) < 0.1:
            return "864×1920"
        elif abs(inv_ratio - (19.5/9)) < 0.08:
            return "886×1920"
        elif abs(inv_ratio - (16/9)) < 0.08:
            return "1080×1920"
        elif abs(inv_ratio - (4/3)) < 0.08:
            return "1080×1440"
        else:
            scale = 1920 / h if h < 1920 else 1.0
            return f"{int(round(w * scale))}×{int(round(h * scale))}"
    else:
        return "1080×1080"

def get_aspect_ratio_label(w: int, h: int) -> str:
    """Xác định tỷ lệ khung hình chuẩn xác của video."""
    if w <= 0 or h <= 0:
        return "9:16 (Chuẩn dọc TikTok)"
    r = w / h
    if abs(r - (20/9)) < 0.1:
        return "20:9 (Quay màn hình Gaming)"
    elif abs(r - (19.5/9)) < 0.08:
        return "19.5:9 (Màn hình iPhone ngang)"
    elif abs(r - (18/9)) < 0.08:
        return "18:9 (2:1 Widescreen)"
    elif abs(r - (16/9)) < 0.08:
        return "16:9 (Màn hình ngang chuẩn)"
    elif abs(r - (4/3)) < 0.08:
        return "4:3 (iPad / Tablet)"
    elif abs(r - (9/20)) < 0.1:
        return "9:20 (Dọc Full tràn viền)"
    elif abs(r - (9/19.5)) < 0.08:
        return "9:19.5 (Chuẩn iPhone dọc)"
    elif abs(r - (9/16)) < 0.08:
        return "9:16 (Chuẩn dọc TikTok)"
    elif abs(r - (3/4)) < 0.08:
        return "3:4 (Chuẩn dọc Portrait)"
    elif abs(r - 1.0) < 0.05:
        return "1:1 (Vuông Square)"
    else:
        return f"{w}:{h}"

def format_stream_blocks(bitrate_info: List[Dict[str, Any]], play_url: str = "", hd_url: str = "") -> List[str]:
    """Tạo các khối link và thông số stream (play_addr, normal_540_0, adapt_540_1, etc.)."""
    blocks = []
    for b in bitrate_info:
        gear_name = b.get("GearName") or "stream"
        codec_raw = (b.get("CodecType") or "").lower()
        codec = "hevc" if any(x in codec_raw for x in ["h265", "bytevc1", "hevc"]) else "h264"
        
        play_addr = b.get("PlayAddr") or {}
        height = play_addr.get("Height") or 576
        fps = b.get("BitrateFPS") or 30
        res_str = f"{height}p{fps}"
        
        bitrate_bps = b.get("Bitrate") or 0
        bitrate_mbps = round(bitrate_bps / 1000000, 1)
        
        data_size = int(play_addr.get("DataSize") or 0)
        size_mb = round(data_size / (1024 * 1024), 1) if data_size > 0 else 0.0
        
        url_list = play_addr.get("UrlList") or []
        
        links = []
        if codec == "h264":
            if url_list:
                links.append(f'🌐📱<a href="{url_list[0]}">play_addr</a>')
            elif play_url:
                links.append(f'🌐📱<a href="{play_url}">play_addr</a>')
            if len(url_list) > 1:
                links.append(f'🌐<a href="{url_list[1]}">{gear_name}</a>')
            elif url_list:
                links.append(f'🌐<a href="{url_list[0]}">{gear_name}</a>')
            if len(url_list) > 2:
                links.append(f'📱<a href="{url_list[2]}">play_addr_h264</a>')
            elif hd_url:
                links.append(f'📱<a href="{hd_url}">play_addr_h264</a>')
            elif play_url:
                links.append(f'📱<a href="{play_url}">play_addr_h264</a>')
        else:
            if url_list:
                links.append(f'🌐📱<a href="{url_list[0]}">{gear_name}</a>')
            if len(url_list) > 1:
                links.append(f'📱<a href="{url_list[1]}">play_addr_bytevc1</a>')
            elif play_url:
                links.append(f'📱<a href="{play_url}">play_addr_bytevc1</a>')
        
        header_line = " ".join(links) if links else f"🌐📱 {gear_name}"
        detail_line = f"{res_str} • {bitrate_mbps} MBps • {codec} • {size_mb} MB"
        blocks.append(f"{header_line}\n{detail_line}")
    return blocks

def extract_tiktok_advanced_sync(url: str) -> Dict[str, Any]:
    """Trích xuất metadata chuyên sâu từ TikTok SSR qua yt-dlp hook."""
    custom_meta = {}
    orig_parse = yt_dlp.extractor.tiktok.TikTokIE._parse_aweme_video_web

    def capturing_parse(self, aweme_detail, webpage_url, video_id, extract_flat=False):
        v = aweme_detail.get('video') or {}
        custom_meta['tiktok_vq_score'] = v.get('VQScore')
        custom_meta['video_width'] = v.get('width')
        custom_meta['video_height'] = v.get('height')
        custom_meta['video_ratio'] = v.get('ratio')
        custom_meta['bitrate_info'] = v.get('bitrateInfo') or []
        custom_meta['diversification_labels'] = aweme_detail.get('diversificationLabels') or []
        
        is_aigc = bool(aweme_detail.get('IsAigc') or (str(aweme_detail.get('aigcLabelType')) == '1') or aweme_detail.get('ShowAIGC'))
        custom_meta['is_aigc'] = is_aigc

        # Source detection từ anchors logExtra
        anchors = aweme_detail.get('anchors') or []
        video_source = None
        for a in anchors:
            log_extra = a.get('logExtra') or ''
            if 'video_source' in log_extra:
                try:
                    le = json.loads(log_extra)
                    video_source = le.get('video_source')
                except Exception:
                    pass
        custom_meta['video_source'] = video_source
        custom_meta['anchors'] = anchors

        return orig_parse(self, aweme_detail, webpage_url, video_id, extract_flat)

    try:
        yt_dlp.extractor.tiktok.TikTokIE._parse_aweme_video_web = capturing_parse
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=False)
    except Exception:
        pass
    finally:
        yt_dlp.extractor.tiktok.TikTokIE._parse_aweme_video_web = orig_parse

    return custom_meta

def infer_upload_source(data: Dict[str, Any], meta: Dict[str, Any], video_source_code: Optional[int] = None) -> str:
    """Xác định nguồn xuất bản video (Upload Source)."""
    # 1. Từ mã video_source nội bộ của TikTok
    if video_source_code == 1:
        return "Phone (Gallery)"
    elif video_source_code == 0:
        return "Phone (Camera)"

    title = (data.get("title") or "").lower()
    anchors = data.get("anchors") or []
    has_capcut_anchor = any("capcut" in str(a).lower() for a in anchors) if isinstance(anchors, list) else False
    
    if data.get("is_ad"):
        return "TikTok Ads"
    
    # Đăng từ Web Browser / Desktop (wm_size == 0)
    if data.get("wm_size") == 0:
        return "Web Browser"
    
    if "capcut" in title or has_capcut_anchor:
        return "CapCut"
    
    # Phân tích tỷ lệ khung hình màn hình điện thoại
    w = meta.get("width") or 1080
    h = meta.get("height") or 1920
    if w > 0 and h > 0:
        ratio = w / h if w > h else h / w
        if ratio >= 2.0 or (w > h and abs(w/h - 4/3) < 0.05):
            return "Phone (Gallery)"

    return "Phone (Gallery)"

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

    # 2. tkhd (width & height across all tracks)
    pos = 0
    while True:
        idx = chunk.find(b'tkhd', pos)
        if idx == -1:
            break
        # Fixed point 16.16: integer part is at idx + 80 (2 bytes) for width, idx + 84 (2 bytes) for height
        if idx + 86 <= chunk_len:
            w = int.from_bytes(chunk[idx + 80 : idx + 82], 'big')
            h = int.from_bytes(chunk[idx + 84 : idx + 86], 'big')
            if 100 <= w <= 7680 and 100 <= h <= 7680:
                info["width"] = w
                info["height"] = h
                break
        pos = idx + 4

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

async def _fetch_tikwm_api(url: str, original_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Hàm phụ trách gọi API TikWM."""
    api_url = "https://www.tikwm.com/api/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    payload = {"url": url, "hd": 1}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, data=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)) as resp:
                if resp.status != 200:
                    return False, None, f"Lỗi máy chủ TikTok API (Mã {resp.status})."

                result = await resp.json()
                if result.get("code") != 0 or not result.get("data"):
                    if url != original_url:
                        payload["url"] = original_url
                        async with session.post(api_url, data=payload, headers=headers) as retry_resp:
                            if retry_resp.status == 200:
                                retry_res = await retry_resp.json()
                                if retry_res.get("code") == 0 and retry_res.get("data"):
                                    result = retry_res

                if result.get("code") != 0 or not result.get("data"):
                    msg = result.get("msg", "Không thể tìm thấy video. Link có thể ở chế độ riêng tư hoặc đã bị xóa.")
                    return False, None, msg

                return True, result["data"], None
    except asyncio.TimeoutError:
        return False, None, "Quá thời gian kết nối đến máy chủ TikTok. Vui lòng thử lại sau giây lát."
    except Exception as e:
        return False, None, f"Đã xảy ra lỗi khi xử lý link: {str(e)}"

async def fetch_tiktok_video(tiktok_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Gọi API TikWM kết hợp đồng thời trích xuất metadata TikTok SSR để tính toán đầy đủ thông số Checker."""
    resolved_url = await resolve_tiktok_shortlink(tiktok_url)
    clean_url = re.sub(r'\?.*$', '', resolved_url)

    # Chạy song song TikWM và yt-dlp SSR hook để tối ưu tốc độ
    tikwm_task = asyncio.create_task(_fetch_tikwm_api(resolved_url, tiktok_url))
    adv_task = asyncio.create_task(asyncio.to_thread(extract_tiktok_advanced_sync, clean_url))

    done, pending = await asyncio.wait([tikwm_task, adv_task], timeout=12.0)
    for p in pending:
        p.cancel()

    tikwm_res = tikwm_task.result() if (tikwm_task in done and not tikwm_task.exception()) else (False, None, "Quá thời gian kết nối API.")
    if not tikwm_res[0] or not tikwm_res[1]:
        return False, None, tikwm_res[2]

    data = tikwm_res[1]
    adv_meta = adv_task.result() if (adv_task in done and not adv_task.exception()) else {}

    hd_url = data.get("hdplay") or data.get("play")
    play_url = data.get("play") or hd_url
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

    width = adv_meta.get("video_width") or (meta.get("width", 1080) if meta else 1080)
    height = adv_meta.get("video_height") or (meta.get("height", 1920) if meta else 1920)

    # Tính điểm VQScore từ thuật toán
    bot_vq_score, vq_label = calculate_vqscore(app_bitrate, width, height, app_fps)

    # Trích xuất VQScore từ TikTok AI (nếu có, ví dụ 74.82 hoặc 0)
    tiktok_vq_score = adv_meta.get("tiktok_vq_score")

    # Tính độ phân giải Original Master & Tỷ lệ khung hình
    orig_res = calculate_original_resolution(width, height)
    aspect_ratio_str = get_aspect_ratio_label(width, height)

    # Khối link stream chi tiết (H.264 & HEVC)
    bitrate_info = adv_meta.get("bitrate_info") or []
    stream_blocks = format_stream_blocks(bitrate_info, play_url, hd_url)

    # Nguồn xuất bản
    video_source_code = adv_meta.get("video_source")
    upload_source = infer_upload_source(data, {"width": width, "height": height}, video_source_code)

    # Phân loại danh mục
    title_str = data.get("title") or ""
    keywords = re.findall(r'#(\w+)', title_str)
    diversification_labels = adv_meta.get("diversification_labels") or []
    if diversification_labels:
        category = " / ".join(diversification_labels)
    else:
        category = infer_video_category(title_str, keywords)

    # AI Generated flag
    is_aigc = bool(adv_meta.get("is_aigc") or data.get("ai_dynamic_cover") or data.get("is_ai_created"))

    # FPS hiển thị cho Browser và Phone stream
    stream_fps = (bitrate_info[0].get("BitrateFPS") if bitrate_info else None) or int(round(app_fps))
    browser_fps_display = min(stream_fps, 60)
    phone_fps_display = stream_fps

    browser_res = f"{height}p{browser_fps_display}"
    phone_res = f"{height}p{phone_fps_display}"

    data["_meta"] = {
        "format": meta.get("format", "MP4 (MPEG-4 Part 14)") if meta else "MP4 (MPEG-4 Part 14)",
        "codec": meta.get("codec", "H.264 (AVC)") if meta else "H.264 (AVC)",
        "width": width,
        "height": height,
        "orig_res": orig_res,
        "aspect_ratio_str": aspect_ratio_str,
        "browser_res": browser_res,
        "phone_res": phone_res,
        "duration_sec": duration_val,
        "browser_fps": browser_fps,
        "app_fps": app_fps,
        "browser_bitrate_mbps": browser_bitrate,
        "app_bitrate_mbps": app_bitrate,
        "browser_size_mb": browser_size_mb,
        "app_size_mb": app_size_mb,
        "bot_vq_score": bot_vq_score,
        "vq_score": bot_vq_score,
        "tiktok_vq_score": tiktok_vq_score,
        "vq_label": vq_label,
        "stream_blocks": stream_blocks,
        "category": category,
        "keywords": keywords,
        "upload_source": upload_source,
        "is_aigc": is_aigc,
    }
    data["_width"] = width
    data["_height"] = height

    return True, data, None

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
                    "id": str(e.get("id") or ""),
                    "title": (e.get("title") or "Không có tiêu đề").strip(),
                    "views": int(e.get("view_count") or 0),
                    "likes": int(e.get("like_count") or 0),
                    "comments": int(e.get("comment_count") or 0),
                    "shares": int(e.get("repost_count") or 0),
                    "saves": int(e.get("save_count") or 0),
                    "timestamp": int(e.get("timestamp") or 0),
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
                    # Fallback với curl_cffi impersonate Chrome để vượt qua 403/TLS restriction của CDN
                    try:
                        from curl_cffi import requests as c_requests
                        c_resp = await asyncio.to_thread(c_requests.get, url, impersonate="chrome", timeout=60)
                        if c_resp.status_code in (200, 206) and len(c_resp.content) > 0:
                            if len(c_resp.content) > max_bytes:
                                return False, f"File quá lớn ({len(c_resp.content)/(1024*1024):.1f}MB > {max_size_mb}MB giới hạn tải)."
                            with open(save_path, "wb") as f:
                                f.write(c_resp.content)
                            return True, None
                    except Exception:
                        pass
                    return False, f"Máy chủ video phản hồi mã lỗi {resp.status}"

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
        # Fallback với curl_cffi impersonate Chrome để vượt qua 403/TLS restriction của CDN
        try:
            from curl_cffi import requests as c_requests
            c_resp = await asyncio.to_thread(c_requests.get, url, impersonate="chrome", timeout=60)
            if c_resp.status_code in (200, 206) and len(c_resp.content) > 0:
                if len(c_resp.content) > max_bytes:
                    return False, f"File quá lớn ({len(c_resp.content)/(1024*1024):.1f}MB > {max_size_mb}MB giới hạn tải)."
                with open(save_path, "wb") as f:
                    f.write(c_resp.content)
                return True, None
        except Exception:
            pass
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

    # Fallback với curl_cffi impersonate Chrome để vượt qua 403
    try:
        from curl_cffi import requests as c_requests
        c_resp = await asyncio.to_thread(c_requests.get, thumb_url, impersonate="chrome", timeout=15)
        if c_resp.status_code == 200 and len(c_resp.content) > 0:
            with open(save_path, "wb") as f:
                f.write(c_resp.content)
            return True
    except Exception:
        pass
    return False
