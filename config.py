import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Chế độ hoạt động mặc định: hybrid | downloader | checker
DEFAULT_MODE = os.getenv("DEFAULT_MODE", "hybrid").strip().lower()

# Cài đặt chất lượng tải mặc định: ask | original | standard
DEFAULT_QUALITY = os.getenv("DEFAULT_QUALITY", "ask").strip().lower()

# Giới hạn kích thước file gửi qua Telegram Bot API (MB) - mặc định 512MB
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 512))

# Tự động tải trực tiếp trong nhóm chat (Group Auto-Download)
GROUP_AUTO_DOWNLOAD = os.getenv("GROUP_AUTO_DOWNLOAD", "true").strip().lower() in ("true", "1", "yes")

# Thời gian chờ tối đa khi kết nối (giây)
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

# Đường dẫn URL WebApp (HTTPS) nếu triển khai Telegram Mini App
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

def is_token_valid() -> bool:
    """Kiểm tra xem BOT_TOKEN đã được cấu hình hợp lệ hay chưa."""
    if not BOT_TOKEN:
        return False
    if BOT_TOKEN in ("YOUR_TELEGRAM_BOT_TOKEN_HERE", "YOUR_BOT_TOKEN", ""):
        return False
    return ":" in BOT_TOKEN
