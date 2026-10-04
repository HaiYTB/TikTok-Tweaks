import re
import os
import sys
import shutil
import subprocess
import asyncio
import tempfile
import urllib.parse
from typing import Optional, Dict, Any, Tuple, List
import requests
import aiohttp
import yt_dlp
import imageio_ffmpeg

import config

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
bin_dir = os.path.dirname(ffmpeg_exe)
if bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

# Regular Expressions cho các nền tảng
TIKTOK_VIDEO_REGEX = re.compile(
    r'https?://(?:(?:www|m|vt|vm|t)\.)?tiktok\.com/(?:t/[a-zA-Z0-9_-]+|@[^/]+/(?:video|photo)/\d+(?:\?[^\s]*)?|[a-zA-Z0-9_-]+/?(?:\?[^\s]*)?)',
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

YOUTUBE_REGEX = re.compile(
    r'https?://(?:(?:www|m)\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)[a-zA-Z0-9_-]+',
    re.IGNORECASE
)

TWITTER_REGEX = re.compile(
    r'https?://(?:(?:www|mobile)\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+/status/\d+',
    re.IGNORECASE
)

PINTEREST_REGEX = re.compile(
    r'https?://(?:(?:[a-zA-Z0-9]+\.)?pinterest\.(?:com|[a-z]{2,3}(?:\.[a-z]{2})?)/pin/\d+|pin\.it/[a-zA-Z0-9]+)',
    re.IGNORECASE
)

SPOTIFY_REGEX = re.compile(
    r'https?://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([a-zA-Z0-9]+)',
    re.IGNORECASE
)

def classify_media_url(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Phân loại và trích xuất URL đa nền tảng:
    Trả về: (url, platform_type)
    platform_type: 'tiktok_video' | 'tiktok_music' | 'instagram' | 'youtube' | 'twitter' | 'pinterest' | 'spotify' | None
    """
    if not text:
        return None, None

    # 1. TikTok Music
    m = TIKTOK_MUSIC_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "tiktok_music"

    # 2. Instagram
    m = INSTAGRAM_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "instagram"

    # 3. YouTube (Shorts & Videos)
    m = YOUTUBE_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "youtube"

    # 4. Twitter / X
    m = TWITTER_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "twitter"

    # 5. Pinterest
    m = PINTEREST_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "pinterest"

    # 6. Spotify
    m = SPOTIFY_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "spotify"

    # 7. TikTok Video (hỗ trợ cả /t/id/ và standard)
    m = TIKTOK_VIDEO_REGEX.search(text)
    if m:
        return m.group(0).strip().rstrip('.,)>]?'), "tiktok_video"

    return None, None

# ==============================================================
# YouTube Downloader Integration (Full 4K & MP3 320k)
# ==============================================================

async def fetch_youtube_media(yt_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Trích xuất metadata video YouTube và thông số độ phân giải (hỗ trợ 4K, 1080p, 720p)."""
    def _extract():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_exe
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(yt_url, download=False)

    try:
        info = await asyncio.to_thread(_extract)
        if not info:
            return False, None, "Không thể lấy thông tin YouTube."

        # Tìm các độ phân giải có sẵn
        heights = set()
        for f in info.get("formats", []):
            h = f.get("height")
            if h:
                heights.add(h)

        max_height = max(heights) if heights else 1080
        is_4k = max_height >= 2160
        is_1080p = max_height >= 1080

        data = {
            "id": info.get("id"),
            "title": info.get("title", "YouTube Video"),
            "uploader": info.get("uploader", "YouTube Channel"),
            "duration": info.get("duration", 0),
            "cover": info.get("thumbnail"),
            "views": info.get("view_count", 0),
            "likes": info.get("like_count", 0),
            "max_height": max_height,
            "is_4k": is_4k,
            "url": yt_url,
            "platform": "youtube"
        }
        return True, data, None
    except Exception as e:
        return False, None, f"Lỗi trích xuất YouTube: {str(e)}"

async def download_youtube_to_path(yt_url: str, quality: str, save_path: str) -> Tuple[bool, Optional[str]]:
    """Tải video YouTube hợp nhất audio+video theo chất lượng (4k, 1080p, 720p, 360p) bằng yt-dlp."""
    def _download():
        quality_map = {
            "4k": "bestvideo[height<=2160]+bestaudio/best[height<=2160]/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
            "original": "bestvideo+bestaudio/best"
        }
        format_spec = quality_map.get(quality.lower(), "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best")

        ydl_opts = {
            'format': format_spec,
            'outtmpl': save_path,
            'ffmpeg_location': ffmpeg_exe,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([yt_url])

    try:
        await asyncio.to_thread(_download)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True, None
        return False, "File tải về rỗng hoặc không tồn tại."
    except Exception as e:
        return False, f"Lỗi tải YouTube: {str(e)}"

# ==============================================================
# Twitter / X Downloader
# ==============================================================

async def fetch_twitter_media(tw_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Trích xuất video Twitter/X."""
    def _extract():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_exe
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(tw_url, download=False)

    try:
        info = await asyncio.to_thread(_extract)
        if not info:
            return False, None, "Không tìm thấy video trong bài viết Twitter/X này."

        data = {
            "id": info.get("id"),
            "title": (info.get("title") or info.get("description") or "Twitter Media")[:100],
            "uploader": info.get("uploader", "Twitter User"),
            "duration": info.get("duration", 0),
            "cover": info.get("thumbnail"),
            "likes": info.get("like_count", 0),
            "url": tw_url,
            "platform": "twitter"
        }
        return True, data, None
    except Exception as e:
        return False, None, f"Lỗi trích xuất Twitter/X: {str(e)}"

async def download_twitter_to_path(tw_url: str, save_path: str) -> Tuple[bool, Optional[str]]:
    """Tải video chất lượng tốt nhất từ Twitter/X."""
    def _download():
        ydl_opts = {
            'format': 'best',
            'outtmpl': save_path,
            'ffmpeg_location': ffmpeg_exe,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([tw_url])

    try:
        await asyncio.to_thread(_download)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True, None
        return False, "Không thể tải video Twitter."
    except Exception as e:
        return False, f"Lỗi tải Twitter: {str(e)}"

# ==============================================================
# Pinterest Downloader
# ==============================================================

async def fetch_pinterest_media(pin_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Trích xuất thông tin bài ghim Pinterest."""
    def _extract():
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': ffmpeg_exe
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(pin_url, download=False)

    try:
        info = await asyncio.to_thread(_extract)
        if not info:
            return False, None, "Không thể lấy thông tin Pinterest."

        data = {
            "id": info.get("id"),
            "title": (info.get("title") or info.get("description") or "Pinterest Media")[:100],
            "uploader": info.get("uploader", "Pinterest Creator"),
            "cover": info.get("thumbnail"),
            "url": pin_url,
            "is_video": bool(info.get("formats")),
            "platform": "pinterest"
        }
        return True, data, None
    except Exception as e:
        return False, None, f"Lỗi trích xuất Pinterest: {str(e)}"

async def download_pinterest_to_path(pin_url: str, save_path: str) -> Tuple[bool, Optional[str]]:
    """Tải video hoặc ảnh gốc Pinterest."""
    def _download():
        ydl_opts = {
            'format': 'best',
            'outtmpl': save_path,
            'ffmpeg_location': ffmpeg_exe,
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([pin_url])

    try:
        await asyncio.to_thread(_download)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True, None
        return False, "Không thể tải file Pinterest."
    except Exception as e:
        return False, f"Lỗi tải Pinterest: {str(e)}"

# ==============================================================
# Spotify Downloader (MP3 320 kbps)
# ==============================================================

async def fetch_spotify_track(spotify_url: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """Lấy thông tin bài hát Spotify qua oEmbed."""
    def _oembed():
        oembed_url = f"https://open.spotify.com/oembed?url={spotify_url}"
        resp = requests.get(oembed_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        return None

    try:
        data = await asyncio.to_thread(_oembed)
        if not data:
            return False, None, "Không tìm thấy bài hát trên Spotify."

        track_info = {
            "title": data.get("title", "Spotify Track"),
            "artist": data.get("author_name", "Spotify Artist"),
            "cover": data.get("thumbnail_url"),
            "url": spotify_url,
            "platform": "spotify"
        }
        return True, track_info, None
    except Exception as e:
        return False, None, f"Lỗi lấy thông tin Spotify: {str(e)}"

def generate_audio_search_candidates(raw_query: str) -> List[str]:
    """Tạo danh sách các từ khóa tìm kiếm tối ưu từ tiêu đề và nghệ sĩ."""
    clean_q = re.sub(r'[*_#@!~]', '', raw_query).strip()
    candidates = [clean_q]

    # Bỏ hậu tố hãng thu âm/kênh media như '& MeMe Media', '& ACV Music', '& Official'
    no_media = re.sub(r'\s*&\s*[\w\s]*(Media|Music|Records|Entertainment|Official|Audio|Recordings|Channel)\b', '', clean_q, flags=re.IGNORECASE).strip()
    if no_media and no_media != clean_q:
        candidates.append(no_media)

    # Tách nghệ sĩ chính nếu có 'feat.', 'ft.', 'x', '&', ','
    split_artists = re.split(r'(\s+feat\.?\s+|\s+ft\.?\s+|\s+&\s+|\s+x\s+)', no_media or clean_q, flags=re.IGNORECASE)
    if len(split_artists) > 1 and len(split_artists[0].strip()) > 3:
        candidates.append(split_artists[0].strip())

    # Thử bỏ phần trong ngoặc tròn / ngoặc vuông như (ZoneH Remix), (Official MV)
    no_paren = re.sub(r'\(.*?\)|\[.*?\]', '', clean_q).strip()
    if no_paren and no_paren != clean_q:
        candidates.append(no_paren)
        no_paren_media = re.sub(r'\s*&\s*[\w\s]*(Media|Music|Records|Entertainment|Official|Audio)\b', '', no_paren, flags=re.IGNORECASE).strip()
        if no_paren_media and no_paren_media != no_paren:
            candidates.append(no_paren_media)

    # Khử trùng lặp từ khóa
    seen = set()
    deduped = []
    for c in candidates:
        norm = re.sub(r'\s+', ' ', c).strip()
        if norm and norm.lower() not in seen:
            seen.add(norm.lower())
            deduped.append(norm)
    return deduped

async def download_mp3_320kbps(search_query_or_url: str, save_path: str) -> Tuple[bool, Optional[str]]:
    """
    Tải âm thanh chất lượng cao nhất và chuyển đổi sang chuẩn MP3 320 kbps bằng FFmpeg.
    Hỗ trợ tìm kiếm thông minh nhiều tầng từ khóa hoặc link trực tiếp YouTube/SoundCloud/CDN.
    """
    def _dl_audio() -> Tuple[bool, Optional[str]]:
        is_direct_url = search_query_or_url.startswith("http://") or search_query_or_url.startswith("https://")

        base_path = save_path
        if base_path.endswith(".mp3"):
            base_path = base_path[:-4]

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': base_path + '.%(ext)s',
            'ffmpeg_location': ffmpeg_exe,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        }

        if is_direct_url:
            targets = [search_query_or_url]
        else:
            candidates = generate_audio_search_candidates(search_query_or_url)
            targets = [f"ytsearch1:{c}" for c in candidates]

        last_err = None
        for target in targets:
            try:
                # Kiểm tra trước xem có bài hát phù hợp không
                if target.startswith("ytsearch1:"):
                    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True}) as ydl_check:
                        chk = ydl_check.extract_info(target, download=False)
                        entries = chk.get('entries') if chk else None
                        if entries is not None and len(entries) == 0:
                            continue

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([target])

                expected_output = base_path + ".mp3"
                if os.path.exists(expected_output):
                    if expected_output != save_path:
                        shutil.move(expected_output, save_path)
                    return True, None

                # Fallback: kiểm tra xem có file audio thô nào được tải về không (.webm, .m4a, .opus)
                parent_dir = os.path.dirname(save_path) or "."
                prefix = os.path.basename(base_path)
                for fname in os.listdir(parent_dir):
                    if fname.startswith(prefix) and not fname.endswith(".mp3") and not fname.endswith(".part"):
                        raw_audio = os.path.join(parent_dir, fname)
                        try:
                            cmd = [ffmpeg_exe, "-y", "-i", raw_audio, "-vn", "-b:a", "320k", save_path]
                            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                            if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                                try: os.remove(raw_audio)
                                except Exception: pass
                                return True, None
                        except Exception:
                            pass
            except Exception as e:
                last_err = str(e)
                continue

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True, None
        return False, last_err or "Không tìm thấy nguồn nhạc phù hợp trên các nền tảng."

    try:
        ok, err = await asyncio.to_thread(_dl_audio)
        if ok and os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            return True, None
        return False, err or "Không thể chuyển đổi hoặc tải file MP3 320kbps."
    except Exception as e:
        return False, f"Lỗi tải MP3 320kbps: {str(e)}"
