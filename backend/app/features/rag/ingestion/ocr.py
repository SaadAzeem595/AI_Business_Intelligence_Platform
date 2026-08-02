from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class BaseOCRProvider(ABC):
    @abstractmethod
    def extract_text(self, file_bytes: bytes) -> str:
        """Extracts text from scanned files or images."""
        pass

class MockOCRProvider(BaseOCRProvider):
    def extract_text(self, file_bytes: bytes) -> str:
        logger.info("Executing MockOCRProvider - returning mock scanned text content.")
        return "[Scanned Document OCR Text: Sales revenue for Q4 reached $1.2M with standard operating costs at $300k. Marketing conversions are active at 8%.]"

class TesseractOCRProvider(BaseOCRProvider):
    def extract_text(self, file_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
            import io
            
            logger.info("Executing TesseractOCRProvider...")
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)
            return text
        except ImportError:
            logger.warning("pytesseract or PIL is not installed. Falling back to MockOCRProvider.")
            return MockOCRProvider().extract_text(file_bytes)
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {str(e)}")
            return f"[OCR Error: {str(e)}]"
