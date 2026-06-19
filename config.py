import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Whisper Model Config
# Options: tiny, base, small, medium, large-v1, large-v2, large-v3
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
# CPU optimization options: float32, int8, int8_float16
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
# Options: cpu, cuda
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

# CPU / Concurrency Control
# Recommended to be 1 or 2 on a 4 vCPU system to prevent thrashing
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "1"))

# Temp storage for downloads
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "/tmp/transcriptions")

# Web Monitor / Diagnostics Server Config
MONITOR_PORT = int(os.getenv("MONITOR_PORT", "8080"))
MONITOR_HOST = os.getenv("MONITOR_HOST", "0.0.0.0")

# Security / Access Control (Optional: comma-separated list of Telegram User IDs or Usernames)
# E.g. ALLOWED_USERS=12345678,your_username
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [x.strip() for x in ALLOWED_USERS_RAW.split(",") if x.strip()]

# Validate required variables
if not TELEGRAM_BOT_TOKEN:
    print("[WARNING] TELEGRAM_BOT_TOKEN is not set in environment or .env file.")
