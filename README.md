# TikTok-Tweaks

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API%2020.x-2CA5E0?logo=telegram&logoColor=white)](https://core.telegram.org/bots/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Clean](https://img.shields.io/badge/Code%20Style-PEP%208-brightgreen)](https://pep8.org)

High-performance Telegram bot for uncompressed media extraction, video stream inspection, real-time Shazam audio recognition, and Telegram Mini App integration.

---

## Overview

**TikTok-Tweaks** is an asynchronous Python bot engineered for content creators, video editors, and power users. It provides watermark-free media downloads across six major platforms, binary MP4 container inspection, creator engagement analytics, and instant audio identification directly from Telegram chats or groups.

### Highlights

- **Multi-Platform Support:** TikTok, YouTube (up to 4K Ultra HD), Instagram, Twitter/X, Pinterest, and Spotify.
- **Deep Stream Inspection (`/check`):** Probes binary MP4 atoms to extract real video codec (H.265/HEVC vs. H.264), bitrate, frame rates, and TikTok VQScore quality metric.
- **Shazam Engine:** In-memory PCM audio fingerprinting from voice messages, video notes, and forwarded clips.
- **Document Mode:** Delivers uncompressed original files without Telegram's native video transcoding.
- **Telegram Mini App:** Modern HTML5 glassmorphism interface syncing real-time SQLite statistics and user preferences.
- **Group Chat Automation:** Automatic media extraction without quote-reply clutter, configurable per group.

---

## Feature Matrix

| Platform | Max Resolution | Audio Format | Stream Inspection | Special Features |
| :--- | :--- | :--- | :--- | :--- |
| **TikTok** | 1080p @ 120 FPS | MP3 / AAC | Full (`/check`) | No watermark, VQScore, 12-video profile analytics |
| **YouTube** | 4K Ultra HD (2160p) | MP3 320 kbps | Format picker | Shorts & long-form, multi-resolution selection |
| **Instagram** | 1080p FHD | M4A / AAC | Metadata extraction | Reels, Posts, Stories |
| **Twitter / X** | Source Native | AAC | Stream info | Direct MP4 link extraction |
| **Pinterest** | Original Resolution | N/A | Image / Video probe | Pins, animated clips, full-size images |
| **Spotify** | N/A | MP3 320 kbps | Metadata & ID3 | Full tracks with album art & artist metadata |

---

## Technical Architecture

### 1. MP4 Atom Probing
Rather than relying solely on server headers, the inspector decodes binary MP4 boxes (`ftyp`, `tkhd`, `mdhd`) from initial stream bytes:
- Detects actual video codecs: `hvc1`/`hev1` (H.265), `avc1` (H.264), `av01` (AV1), and `vp09` (VP9).
- Accurately measures timescale, duration, exact frame rate (FPS), and bitrates for both mobile app and web browser streams.
- Calculates the proprietary **VQScore (0–100)** to determine compression quality.

### 2. TLS Impersonation & CDN Resilience
To prevent `403 Forbidden` and rate-limit blocks from TikTok CDNs:
- Primary downloads utilize chunked `aiohttp` streaming up to 512 MB.
- Automatic fallback routes through `curl_cffi` using Chrome TLS fingerprint impersonation.

### 3. In-Memory Audio Identification
The Shazam integration extracts PCM audio directly using `pydub` and `imageio-ffmpeg` without temporary disk I/O, generating signatures within milliseconds.

---

## Installation

### Prerequisites

- Python 3.10 or higher
- [FFmpeg](https://ffmpeg.org/) installed and available in system PATH (or via `imageio-ffmpeg`)
- Git

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/HaiYTB/TikTok-Tweaks.git
   cd TikTok-Tweaks
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to `.env` and fill in your bot token:
   ```bash
   cp .env.example .env
   ```

5. **Start the bot:**
   ```bash
   python bot.py
   ```

---

## Configuration

All configuration is managed through environment variables in `.env`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `BOT_TOKEN` | `string` | *(Required)* | Telegram Bot Token from [@BotFather](https://t.me/BotFather) |
| `DEFAULT_MODE` | `string` | `hybrid` | Default bot mode: `hybrid`, `downloader`, or `checker` |
| `MAX_FILE_SIZE_MB` | `integer` | `512` | Maximum file download limit in megabytes |
| `GROUP_AUTO_DOWNLOAD` | `boolean` | `true` | Automatically download media when links are sent in groups |
| `WEBAPP_URL` | `string` | `""` | Public HTTPS URL hosting `webapp/index.html` for Mini App |

---

## Command Reference

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/start` | None | Open the main interactive navigation dashboard. |
| `/check` | `<url>` or `@username` | Deep-inspect video stream specs, VQScore, or creator's last 12 uploads. |
| `/mode` | None | Switch operating mode between Hybrid, Downloader, and Checker. |
| `/profile` | None | Display personal download/inspection stats and launch the Mini App. |
| `/settings` | None | Toggle Document mode, clean captions, and response delivery mode. |
| `/shazam` | None | View audio recognition instructions. |
| `/group_settings` | None | Manage group-specific permissions (auto-download, silent delivery). |
| `/help` | None | Comprehensive guide for commands and media links. |

---

## Project Structure

```
TikTok-Tweaks/
├── bot.py                  # Core bot entrypoint (handlers, callbacks, group dispatch)
├── config.py               # Environment validation and application settings
├── database.py             # SQLite interface for user analytics and group settings
├── multi_platform_api.py   # Downloaders for YouTube (4K), Twitter, Pinterest, Spotify
├── tiktok_api.py           # TikTok & Instagram API, MP4 parser, and VQScore algorithm
├── shazam_service.py       # In-memory PCM Shazam recognition service
├── stats_formatter.py      # Minimalist message formatters and analytics cards
├── webapp/
│   └── index.html          # Telegram Mini App with Glassmorphism UI
├── requirements.txt        # Python dependency manifest
├── .env.example            # Environment configuration template
└── README.md               # Project documentation
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
