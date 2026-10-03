import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent / "tiktok_tweaks.db"

def init_db():
    """Khởi tạo cấu trúc bảng dữ liệu SQLite nếu chưa tồn tại."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Bảng người dùng và cài đặt cá nhân
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        language TEXT DEFAULT 'vi',
        mode TEXT DEFAULT 'hybrid',
        quality TEXT DEFAULT 'original',
        doc_mode INTEGER DEFAULT 0,
        reply_mode TEXT DEFAULT 'direct',
        caption_mode TEXT DEFAULT 'full',
        no_signature INTEGER DEFAULT 0,
        total_downloads INTEGER DEFAULT 0,
        total_checks INTEGER DEFAULT 0,
        total_shazams INTEGER DEFAULT 0,
        dl_tiktok INTEGER DEFAULT 0,
        dl_instagram INTEGER DEFAULT 0,
        dl_youtube INTEGER DEFAULT 0,
        dl_twitter INTEGER DEFAULT 0,
        dl_pinterest INTEGER DEFAULT 0,
        dl_spotify INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Bảng cài đặt nhóm (Groups)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        title TEXT,
        auto_download INTEGER DEFAULT 1,
        default_quality TEXT DEFAULT 'original',
        silent_mode INTEGER DEFAULT 0,
        admin_only INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# Khởi tạo ngay khi module được import
init_db()

def get_or_create_user(user_id: int, username: str = "", full_name: str = "") -> Dict[str, Any]:
    """Lấy thông tin người dùng hoặc tạo mới nếu chưa tồn tại."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT INTO users (user_id, username, full_name)
        VALUES (?, ?, ?)
        """, (user_id, username or "", full_name or ""))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    else:
        # Cập nhật username / full_name nếu có thay đổi
        if (username and row["username"] != username) or (full_name and row["full_name"] != full_name):
            cursor.execute("""
            UPDATE users SET username = ?, full_name = ? WHERE user_id = ?
            """, (username or row["username"], full_name or row["full_name"], user_id))
            conn.commit()

    data = dict(row) if row else {}
    conn.close()
    return data

def update_user_setting(user_id: int, key: str, value: Any) -> bool:
    """Cập nhật một cài đặt của người dùng."""
    allowed_keys = {
        "language", "mode", "quality", "doc_mode", 
        "reply_mode", "caption_mode", "no_signature"
    }
    if key not in allowed_keys:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {key} = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()
    return True

def record_download(user_id: int, platform: str = "tiktok") -> None:
    """Ghi nhận lượt tải thành công theo nền tảng."""
    platform = platform.lower()
    col_map = {
        "tiktok": "dl_tiktok",
        "tiktok_video": "dl_tiktok",
        "tiktok_music": "dl_tiktok",
        "instagram": "dl_instagram",
        "youtube": "dl_youtube",
        "twitter": "dl_twitter",
        "x": "dl_twitter",
        "pinterest": "dl_pinterest",
        "spotify": "dl_spotify",
    }
    target_col = col_map.get(platform, "dl_tiktok")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Đảm bảo user tồn tại
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute(f"""
    UPDATE users 
    SET total_downloads = total_downloads + 1,
        {target_col} = {target_col} + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def record_check(user_id: int) -> None:
    """Ghi nhận lượt kiểm tra Checker/VQScore."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("""
    UPDATE users 
    SET total_checks = total_checks + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def record_shazam(user_id: int) -> None:
    """Ghi nhận lượt nhận diện nhạc Shazam."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    cursor.execute("""
    UPDATE users 
    SET total_shazams = total_shazams + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = ?
    """, (user_id,))
    conn.commit()
    conn.close()

def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Lấy dữ liệu thống kê của người dùng."""
    return get_or_create_user(user_id)

def get_group_settings(chat_id: int, title: str = "") -> Dict[str, Any]:
    """Lấy cài đặt nhóm hoặc tạo mặc định."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM groups WHERE chat_id = ?", (chat_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT INTO groups (chat_id, title)
        VALUES (?, ?)
        """, (chat_id, title or ""))
        conn.commit()
        cursor.execute("SELECT * FROM groups WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()

    data = dict(row) if row else {}
    conn.close()
    return data

def update_group_setting(chat_id: int, key: str, value: Any) -> bool:
    """Cập nhật cài đặt nhóm."""
    allowed_keys = {"auto_download", "default_quality", "silent_mode", "admin_only"}
    if key not in allowed_keys:
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE groups SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    conn.close()
    return True
