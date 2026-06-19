# Multitool Telegram Transcription Bot

A modular, production-ready, and highly optimized Telegram Bot hosted on a VPS (Ubuntu) that acts as an automated Audio-to-Text Transcription Bot with precise timestamps. 

Equipped with `faster-whisper` using CPU optimizations (`int8` quantization), a dynamic concurrency queue to prevent server lockup, and Voice Activity Detection (VAD) to ignore silences.

---

## 🛠️ System Architecture & Optimization

This bot is designed to be hosted on a standard VPS (e.g. 4 vCPUs, 8GB RAM). 

- **CPU Optimization**: The transcription model runs using `compute_type="int8"` on CPU, which keeps RAM usage under 2GB and uses standard CPU vector instructions (AVX/AVX2) for rapid calculation.
- **Concurrency Guard**: Since transcription is CPU-intensive, running multiple transcription jobs concurrently will saturate 4 vCPUs, causing CPU thrashing and lag. We implement a sequential/concurrency `QueueManager` utilizing an `asyncio.Semaphore` (configurable) to process files safely.
- **Smart Formatting**: Timestamps are parsed to `[MM:SS.cc -> MM:SS.cc]` or `[HH:MM:SS.cc -> HH:MM:SS.cc]` format.
- **Smart Response Delivery**: Sends directly as a Telegram message if under 4,000 characters; otherwise compiles the transcription into a neat `.txt` document.
- **Storage Management**: Automatically removes downloaded source audio, converted wave files, and transient text files using standard cleanup routines in a `finally` block.

---

## 📂 Modular Structure (Multitool Blueprint)

The bot is structured to support adding other features/tools folder-wise:

```
/root/SuvTools/
├── requirements.txt            # Package dependencies
├── config.py                   # Environment and config loader
├── main.py                     # Entry point
├── README.md                   # Operational Manual
└── src/
    ├── __init__.py
    ├── bot.py                  # Dynamically registers modules
    ├── modules/
    │   ├── __init__.py
    │   ├── base.py             # Interface/Abstract base class for all modules
    │   └── transcriber/        # Audio-to-Text Module
    │       ├── __init__.py
    │       ├── handlers.py     # Message handlers (voice, audio, doc)
    │       ├── services.py     # Whisper/VAD Transcription service
    │       └── utils.py        # FFmpeg and formatting helpers
    └── utils/
        ├── __init__.py
        ├── logger.py           # Stream + File logging config
        └── queue_manager.py    # Queue control for CPU jobs
```

---

## 🚀 Installation & Setup

### 1. Pre-requisites (Ubuntu)
Install system packages for handling media processing (FFmpeg) and setting up virtual environments:
```bash
sudo apt update
sudo apt install -y ffmpeg python3-pip python3-venv python3-full
```

### 2. Install Project Dependencies
Initialize a virtual environment and install python packages:
```bash
# Navigate to project root
cd /root/SuvTools

# Create virtual environment
python3 -m venv venv

# Activate and install dependencies
./venv/bin/pip install -r requirements.txt
```

### 3. Configure the Environment
Create your `.env` configuration file from the template:
```bash
cp .env.example .env
nano .env
```
Fill in your `TELEGRAM_BOT_TOKEN`. You can optionally restrict usage to specific Telegram handles/user IDs under the `ALLOWED_USERS` variable.

### 4. Cache Whisper Models (Pre-Download)
Run the helper script to pre-download the model. This guarantees that your bot responds instantly to the first transcription request instead of stalling on startup:
```bash
./venv/bin/python download_model.py
```

---

## 🔄 Running 24/7 in Production

Choose **one** of the methods below to run the bot 24/7 on Ubuntu.

### Method A: Running with `systemd` (Recommended)

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/telegram-bot.service
   ```

2. Paste the following configuration:
   ```ini
   [Unit]
   Description=Multitool Telegram Transcription Bot
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/SuvTools
   ExecStart=/root/SuvTools/venv/bin/python main.py
   Restart=always
   RestartSec=5
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

3. Reload the systemd daemon, enable the service, and start it:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot.service
   sudo systemctl start telegram-bot.service
   ```

4. Monitor live logs:
   ```bash
   sudo journalctl -u telegram-bot.service -f
   ```

---

### Method B: Running with PM2 (Process Manager)

If you use Node/PM2 on your server, you can manage the Python bot using PM2.

1. Install PM2 (if not already installed):
   ```bash
   npm install pm2 -g
   ```

2. Start the bot under PM2, using your virtualenv Python interpreter:
   ```bash
   pm2 start /root/SuvTools/main.py --name "telegram-transcriber-bot" --interpreter /root/SuvTools/venv/bin/python
   ```

3. Configure PM2 to restart the bot automatically on server reboots:
   ```bash
   pm2 save
   pm2 startup
   ```
   *(Run the command outputted by `pm2 startup` to complete configuration)*

4. Manage the process:
   ```bash
   pm2 status
   pm2 logs telegram-transcriber-bot
   pm2 restart telegram-transcriber-bot
   ```

---

## ➕ Adding a New Tool/Module

To add a new tool (e.g. an AI summarizer, weather forecaster, etc.) to this multitool bot:

1. Create a new directory under `src/modules/` (e.g., `src/modules/summarizer/`).
2. Implement your tool class inside a file, subclassing `BaseModule`:
   ```python
   # src/modules/summarizer/handlers.py
   from telegram.ext import Application, CommandHandler
   from src.modules.base import BaseModule

   class SummarizerModule(BaseModule):
       @property
       def name(self) -> str:
           return "summarizer"

       def register_handlers(self, application: Application) -> None:
           application.add_handler(CommandHandler("summarize", self.summarize_handler))

       async def summarize_handler(self, update, context):
           await update.message.reply_text("Feature coming soon!")
   ```
3. Export it in `src/modules/summarizer/__init__.py`.
4. Import and register it inside the `modules` array in [bot.py](file:///root/SuvTools/src/bot.py):
   ```python
   from src.modules.summarizer import SummarizerModule
   # ...
   modules = [
       TranscriberModule(),
       SummarizerModule()  # Added here
   ]
   ```
