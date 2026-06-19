import os
from faster_whisper import WhisperModel
import config
from src.utils.logger import logger
from src.modules.transcriber.utils import format_timestamp

class TranscriptionService:
    def __init__(self):
        self._model = None

    def _get_model(self) -> WhisperModel:
        """Lazily loads and returns the WhisperModel instance."""
        if self._model is None:
            logger.info(
                f"Loading faster-whisper model '{config.WHISPER_MODEL_SIZE}' "
                f"on device '{config.WHISPER_DEVICE}' with compute_type '{config.WHISPER_COMPUTE_TYPE}'..."
            )
            # This downloads the model from Hugging Face if not present, and loads it into memory
            self._model = WhisperModel(
                config.WHISPER_MODEL_SIZE,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE
            )
            logger.info("Whisper model loaded successfully.")
        return self._model

    def transcribe(self, wav_path: str) -> str:
        """
        Transcribes the given WAV file.
        Returns a formatted transcript string with timestamps.
        """
        model = self._get_model()
        logger.info(f"Transcribing audio file: {wav_path}")

        # vad_filter=True removes silence dynamically using Silero VAD to speed up computation
        segments, info = model.transcribe(
            wav_path,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        transcript_lines = []
        for segment in segments:
            start_str = format_timestamp(segment.start)
            end_str = format_timestamp(segment.end)
            text = segment.text.strip()
            if text:
                transcript_lines.append(f"[{start_str} -> {end_str}] {text}")

        # Join the segments with newlines
        return "\n".join(transcript_lines)
