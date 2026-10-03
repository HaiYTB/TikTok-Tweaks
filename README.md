# TikTok-Tweaks: Premium Multi-Platform Bot & Shazam Music Recognition

> **TikTok-Tweaks Bot** là trợ lý bot Telegram bằng Python toàn diện và mạnh mẽ nhất: Tải media không logo từ **TikTok**, **YouTube (Full 4K Ultra HD)**, **Instagram**, **Twitter/X**, **Pinterest**, **Spotify (MP3 320 kbps)**, nhận diện bài hát **Shazam** từ âm thanh / voice / video, tích hợp **Telegram Mini App** với số liệu thực tế và hỗ trợ nhóm chat (Groups) chuyên sâu.

---

## 🌟 BẢNG TÍNH NĂNG NÂNG CẤP MỚI NHẤT

### 🧲 1. Tải Video 4K & Đa Nền Tảng (Multi-Platform Downloader)
- 🏆 **Full 4K Ultra HD & 120fps Support:** Hỗ trợ video độ phân giải cao lên đến 4K (2160p), 1440p, 1080p FHD, tốc độ khung hình 120fps, video dài và file lên tới **512 MB**.
- 📁 **Original file, without Telegram compression (Document Mode):** Tùy chọn gửi file gốc nguyên bản qua Document (`send_document`), giữ nguyên 100% độ nét và màu sắc mà không bị Telegram nén giảm chất lượng.
- 🖼️ **Covers and preview frames at full size:** Tải ảnh bìa và khung hình preview chất lượng gốc (Full Size).
- 🌐 **Hỗ trợ 6 nền tảng lớn:**
  - 🎵 **TikTok:** Video không logo, 120fps, âm thanh tách rời, VQScore.
  - 🔴 **YouTube:** Tải Shorts và video thường với lựa chọn 4K, 1080p, 720p, hoặc MP3 320 kbps.
  - 📸 **Instagram:** Tải mượt mà Reels, Posts, Stories không dính logo.
  - 🐦 **Twitter / X:** Tải video từ tweet với chất lượng cao nhất.
  - 📌 **Pinterest:** Tải video pin hoặc ảnh tĩnh độ phân giải cao.
  - 🟢 **Spotify Music:** Tải trọn vẹn track nhạc chuẩn **MP3 320 kbps High Fidelity** kèm ID3 tags và album cover art!

---

### ❤️ 2. Nhận Diện Âm Nhạc Shazam (Shazam Engine 🆕)
- 🎧 **Videos, photos & audio recognition:** Nhận diện bài hát từ bất kỳ nguồn nào có nhạc.
- 🎤 **Đa dạng định dạng:** Gửi hoặc chuyển tiếp tin nhắn thoại (Voice note), video tròn (Video note), video clip hoặc file audio — bot sẽ nghe và gửi lại tên track ngay lập tức!
- 🎛️ **Edits and voiceovers:** Nhận diện được cả các bản nhạc remix, speed up, nhạc nền lồng tiếng.
- 🔗 **Direct streaming links:** Cung cấp link nghe trực tiếp trên Spotify, Apple Music, YouTube Music, Shazam Web và nút tải ngay bản thu **MP3 320 kbps**.

---

### 📱 3. Telegram Mini App & Profile Analytics (Mini App 🆕)
- 📊 **Real Numbers Profile:** Bảng hồ sơ thống kê số liệu thực tế được lưu vào SQLite Database:
  - Tổng số lượt tải (Downloads)
  - Tổng số lượt phân tích (Checks)
  - Tổng số lượt nhận diện nhạc (Shazams)
  - Phân loại chi tiết theo nền tảng (TikTok, YouTube, Instagram, Twitter, Pinterest, Spotify).
- ⚙️ **All Switches in One Screen:** Điều khiển toàn bộ cài đặt trên một giao diện thống nhất (trong Mini App HTML5 hoặc ngay trong chat Telegram):
  - 🌐 **Ngôn ngữ:** Tiếng Việt / English / Русский
  - 💬 **Chế độ phản hồi:** Trực tiếp (Direct) / Reply / Im lặng (Silent)
  - 📝 **Định dạng Caption:** Đầy đủ / Rút gọn / Tắt chữ
  - 📁 **Document Mode:** Bật/Tắt gửi file gốc không nén
  - 🛡️ **No Signature:** Bật/Tắt gỡ bỏ chữ ký quảng bá của bot khỏi caption.

---

### 👥 4. Tối Ưu Hóa Nhóm Chat (Groups 🆕)
- 👋 **Group Greet:** Bot tự động gửi lời chào mừng khi được thêm vào nhóm chat kèm hướng dẫn nhanh.
- ⚡ **Auto-Download:** Tự động tải thẳng video/audio vào nhóm chat khi thành viên gửi link mà không cần quote reply rườm rà.
- 🎛️ **Group Settings vs Member Settings:**
  - Quản trị viên dùng `/group_settings` để cài đặt mặc định cho cả nhóm (bật/tắt tự động tải, chế độ im lặng).
  - Từng thành viên vẫn giữ cài đặt cá nhân riêng (Document Mode, Caption, v.v.).
- 🚀 **Không giới hạn (No Limits):** Không giới hạn số lượt tải hàng ngày, hỗ trợ file 512MB, chất lượng vượt 1080p (4K).

---

## 📁 Cấu Trúc Dự Án

```
TikTok-Tweaks/
├── bot.py                  # Điểm khởi chạy chính (Handlers, Callbacks, Commands, Groups, Shazam)
├── config.py               # Biến môi trường, BOT_TOKEN, WEBAPP_URL, giới hạn 512MB
├── database.py             # Cơ sở dữ liệu SQLite lưu trữ Real Stats & Cài đặt cá nhân/nhóm
├── multi_platform_api.py   # Bộ trích xuất & tải YouTube (4K), Twitter, Pinterest, Spotify MP3 320k
├── tiktok_api.py           # Module API TikTok, Instagram, Author 12-videos, VQScore, MP4 atoms
├── shazam_service.py       # Bộ nhận diện âm nhạc Shazam siêu tốc từ PCM Stream
├── stats_formatter.py      # Định dạng tin nhắn Checker, Profile Cards, Emojis cao cấp
├── webapp/
│   └── index.html          # Telegram Mini App giao diện Glassmorphism với số liệu thực tế
├── requirements.txt        # Danh sách thư viện cần thiết
├── .env.example            # Mẫu cấu hình
└── README.md               # Hướng dẫn chi tiết
```

---

## 🚀 Hướng Dẫn Cài Đặt & Sử Dụng

### 1. Chuẩn Bị Môi Trường
```shell
pip install -r requirements.txt
```

### 2. Cấu Hình Bot Token
Mở file `.env` và điền token lấy từ [@BotFather](https://t.me/BotFather):
```env
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
DEFAULT_MODE=hybrid
MAX_FILE_SIZE_MB=512
GROUP_AUTO_DOWNLOAD=true
WEBAPP_URL=
```

### 3. Khởi Chạy Bot
```shell
python bot.py
```

### 4. Danh Sách Lệnh
- `/start` - Chào mừng và mở menu điều hướng chính.
- `/mode` - Chuyển đổi 3 chế độ hoạt động (Hybrid, Downloader, Checker).
- `/settings` - Tùy chỉnh cài đặt cá nhân (Document mode, Reply, Caption, No signature).
- `/profile` (hoặc `/webapp`, `/app`) - Xem số liệu thực tế và mở Telegram Mini App.
- `/shazam` - Hướng dẫn nhận diện bài hát qua âm thanh/video.
- `/group_settings` - Cấu hình bot cho nhóm chat (dành cho Admin).
- `/help` - Hướng dẫn chi tiết sử dụng.

---

## 🛡️ Giấy Phép (License)
Dự án được phân phối dưới giấy phép [MIT License](LICENSE).
