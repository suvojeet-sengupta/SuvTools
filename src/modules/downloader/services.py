import os
import uuid
import yt_dlp
from src.utils.logger import logger

class DownloaderService:
    def download_video(self, url: str, download_dir: str) -> tuple[str, str]:
        """
        Downloads a video from YouTube, Facebook, Instagram, TikTok, etc.
        Enforces 720p limit and MP4 container format.
        Returns a tuple (file_path, video_title).
        """
        # Generate a unique filename prefix to avoid collisions
        file_id = str(uuid.uuid4())
        out_template = os.path.join(download_dir, f"{file_id}.%(ext)s")

        # Configure yt-dlp to prioritize compatible MP4 format (h264 + aac) and limit resolution to 720p
        ydl_opts = {
            'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
            'outtmpl': out_template,
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
        }

        # Check for cookies file to authenticate and bypass rate limits/login requirements
        cookies_paths = [
            os.path.join(os.getcwd(), "cookies.txt"),
            "/root/SuvTools/cookies.txt"
        ]
        for path in cookies_paths:
            if os.path.exists(path):
                ydl_opts['cookiefile'] = path
                logger.info(f"Loaded yt-dlp cookies from: {path}")
                break

        logger.info(f"Initiating video download via yt-dlp for URL: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract video metadata and download
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Video Download')
            
            # Locate the downloaded file in the output folder
            for file in os.listdir(download_dir):
                if file.startswith(file_id):
                    actual_path = os.path.join(download_dir, file)
                    logger.info(f"Video download complete: {actual_path} | Title: '{title}'")
                    return actual_path, title
            
            raise FileNotFoundError("Failed to locate downloaded video output file.")
