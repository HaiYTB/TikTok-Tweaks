import os
import sys
import subprocess
import urllib.parse
import uuid
from typing import Optional, Dict, Any, Tuple

# Bộ nhớ đệm lưu trữ kết quả Shazam theo ID ngắn (tránh lỗi Telegram Button_data_invalid > 64 bytes)
SHAZAM_CACHE: Dict[str, Dict[str, Any]] = {}

import imageio_ffmpeg

# Đảm bảo ffmpeg được cấu hình đúng
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
bin_dir = os.path.dirname(ffmpeg_exe)
if bin_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

# Tạo bản sao ffmpeg.exe trong bin_dir nếu chưa có
ffmpeg_alias = os.path.join(bin_dir, "ffmpeg.exe")
if not os.path.exists(ffmpeg_alias):
    try:
        import shutil
        shutil.copyfile(ffmpeg_exe, ffmpeg_alias)
    except Exception:
        pass

import audioop
from pydub import AudioSegment
AudioSegment.converter = ffmpeg_exe
AudioSegment.ffmpeg = ffmpeg_exe

from ShazamAPI import Shazam
from ShazamAPI.api import SignatureGenerator
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class FastPcmShazam(Shazam):
    """Bộ nhận diện Shazam tối ưu xử lý trực tiếp từ raw PCM stream, không cần ghi đĩa hay gọi ffprobe."""
    def __init__(self, audio_seg: AudioSegment):
        self.audio = audio_seg
        self.MAX_TIME_SECONDS = 8

    def recognizeSong(self):
        signatureGenerator = self.createSignatureGenerator(self.audio)
        while True:
            signature = signatureGenerator.get_next_signature()
            if not signature:
                break
            results = self.sendRecognizeRequest(signature)
            currentOffset = signatureGenerator.samples_processed / 16000
            yield currentOffset, results

def extract_pcm_from_media(media_path: str, max_duration_sec: int = 14) -> bytes:
    """
    Trích xuất luồng âm thanh PCM 16kHz mono 16-bit từ bất kỳ video, voice, audio nào
    bằng ffmpeg siêu tốc.
    """
    cmd = [
        ffmpeg_exe,
        "-y",
        "-ss", "0",
        "-t", str(max_duration_sec),
        "-i", media_path,
        "-vn",
        "-f", "s16le",
        "-ar", "16000",
        "-ac", "1",
        "pipe:1"
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"FFmpeg PCM extraction failed: {err[:200]}")
    return proc.stdout

def identify_song_from_path(media_path: str, max_duration_sec: int = 14) -> Optional[Dict[str, Any]]:
    """
    Nhận diện bài hát từ đường dẫn file media (video, voice note, clip, audio).
    Trả về dict thông tin bài hát hoặc None nếu không tìm thấy.
    """
    try:
        raw_pcm = extract_pcm_from_media(media_path, max_duration_sec=max_duration_sec)
        if not raw_pcm or len(raw_pcm) < 32000: # Ít nhất 1 giây âm thanh
            return None

        audio_seg = AudioSegment(
            data=raw_pcm,
            sample_width=2,
            frame_rate=16000,
            channels=1
        )

        shazam = FastPcmShazam(audio_seg)
        for offset, res in shazam.recognizeSong():
            track = res.get("track")
            if track:
                title = track.get("title", "Không rõ tên")
                artist = track.get("subtitle", "Không rõ nghệ sĩ")
                shazam_url = track.get("url")
                
                # Ảnh bìa album
                images = track.get("images", {})
                cover_url = images.get("coverarthq") or images.get("coverart") or images.get("background")

                # Thể loại nhạc
                genres = track.get("genres", {}).get("primary", "Music")

                # Trích xuất link Apple Music nếu có
                apple_music_url = None
                hub_options = track.get("hub", {}).get("options", [])
                for opt in hub_options:
                    for act in opt.get("actions", []):
                        if act.get("type") == "applemusicopen" or "apple" in act.get("uri", ""):
                            apple_music_url = act.get("uri")
                            break

                # Tạo link tìm kiếm Spotify và YouTube Music
                query_encoded = urllib.parse.quote(f"{title} {artist}")
                spotify_url = f"https://open.spotify.com/search/{query_encoded}"
                yt_music_url = f"https://music.youtube.com/search?q={query_encoded}"
                yt_search_url = f"https://www.youtube.com/results?search_query={query_encoded}"

                return {
                    "title": title,
                    "artist": artist,
                    "genres": genres,
                    "cover_url": cover_url,
                    "shazam_url": shazam_url,
                    "apple_music_url": apple_music_url,
                    "spotify_url": spotify_url,
                    "yt_music_url": yt_music_url,
                    "yt_search_url": yt_search_url,
                    "raw_track": track
                }

            if offset > 16:
                break

        return None
    except Exception as e:
        print(f"Error in identify_song_from_path: {e}")
        return None

def build_shazam_card(info: Dict[str, Any]) -> Tuple[str, InlineKeyboardMarkup]:
    """Tạo giao diện tin nhắn kết quả nhận diện nhạc Shazam với phong cách sang trọng."""
    title = info.get("title", "Không rõ")
    artist = info.get("artist", "Không rõ nghệ sĩ")
    genres = info.get("genres", "Âm nhạc")
    cover_url = info.get("cover_url")
    shazam_url = info.get("shazam_url")
    spotify_url = info.get("spotify_url")
    yt_music_url = info.get("yt_music_url")
    apple_music_url = info.get("apple_music_url")

    # Đặt preview ảnh bìa trên đầu
    preview_tag = f'<a href="{cover_url}">&#8205;</a>' if cover_url else ""

    text = (
        f"{preview_tag}🎧 <b>KẾT QUẢ NHẬN DIỆN BÀI HÁT (SHAZAM)</b> 🎶\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 <b>Bài hát:</b> <b>{title}</b>\n"
        f"🎤 <b>Nghệ sĩ:</b> <code>{artist}</code>\n"
        f"🏷️ <b>Thể loại:</b> <i>{genres}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✨ <i>Nhận diện thành công từ âm thanh / video / voice message!</i>\n"
        "🔗 <i>Bấm các nút bên dưới để nghe ngay trên các nền tảng:</i>"
    )

    buttons = []
    row1 = []
    if spotify_url:
        row1.append(InlineKeyboardButton("🟢 Mở trên Spotify", url=spotify_url))
    if yt_music_url:
        row1.append(InlineKeyboardButton("🔴 YouTube Music", url=yt_music_url))
    if row1:
        buttons.append(row1)

    row2 = []
    if apple_music_url:
        row2.append(InlineKeyboardButton("🍏 Apple Music", url=apple_music_url))
    if shazam_url:
        row2.append(InlineKeyboardButton("🔵 Shazam Web", url=shazam_url))
    if row2:
        buttons.append(row2)

    # Lưu cache để tránh vượt quá 64 bytes callback_data của Telegram
    s_id = uuid.uuid4().hex[:8]
    SHAZAM_CACHE[s_id] = info

    # Nút tìm kiếm tải mp3 với short id
    buttons.append([
        InlineKeyboardButton("⬇️ Tải MP3 320kbps bài hát này", callback_data=f"dl_sh_mp3:{s_id}")
    ])

    return text, InlineKeyboardMarkup(buttons)

