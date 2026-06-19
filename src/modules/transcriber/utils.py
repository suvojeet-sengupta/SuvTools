import subprocess
import os
from src.utils.logger import logger

def format_timestamp(seconds: float) -> str:
    """Formats float seconds into standard [HH:]MM:SS.cc timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"
    else:
        return f"{minutes:02d}:{secs:05.2f}"

def convert_to_wav(input_path: str, output_path: str) -> bool:
    """
    Converts input audio file to 16kHz mono WAV file for Whisper / VAD consumption.
    Returns True if successful, False otherwise.
    """
    try:
        # Command parameters:
        # -y (overwrite existing file)
        # -i input_path
        # -ar 16000 (resample to 16kHz)
        # -ac 1 (downmix to mono)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            output_path
        ]
        logger.info(f"Running ffmpeg conversion: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode("utf-8", errors="ignore")
        logger.error(f"FFmpeg conversion process failed: {stderr_msg}")
        return False
    except Exception as e:
        logger.error(f"FFmpeg execution error: {e}")
        return False
