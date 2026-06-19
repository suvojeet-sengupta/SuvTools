from faster_whisper import WhisperModel
import config
from src.utils.logger import logger

def main():
    logger.info(f"Pre-downloading and caching faster-whisper model '{config.WHISPER_MODEL_SIZE}'...")
    # Trigger loading to download and compile model in the HF cache directory
    model = WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device=config.WHISPER_DEVICE,
        compute_type=config.WHISPER_COMPUTE_TYPE
    )
    logger.info("Whisper model pre-downloaded and compiled successfully!")

if __name__ == "__main__":
    main()
