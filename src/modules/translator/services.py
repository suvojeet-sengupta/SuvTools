import urllib.parse
import urllib.request
import json
from src.utils.logger import logger

class TranslationService:
    def translate(self, text: str, target_lang: str = "en") -> str:
        """
        Translates text to the target language code using Google's translation API.
        Does not require external API keys.
        """
        try:
            logger.info(f"Translating text to target language: {target_lang}")
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={urllib.parse.quote(text)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                # Google Translate returns segments. Join the translated sentences together.
                translated_text = "".join([segment[0] for segment in data[0] if segment and segment[0]])
                return translated_text
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            raise RuntimeError(f"Translation failed: {str(e)}")
