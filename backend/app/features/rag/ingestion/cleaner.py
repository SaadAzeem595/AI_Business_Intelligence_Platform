import re
import unicodedata

class TextCleaner:
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes spacing, line breaks, quotes, and control chars while keeping layout structure."""
        if not text:
            return ""
            
        # Normalize unicode characters
        text = unicodedata.normalize("NFKC", text)
        
        # Replace stylized quotes and dashes with standard ones
        text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
        text = text.replace("—", "-").replace("–", "-")
        
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        
        # Collapse multiple consecutive empty lines to a max of two
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove trailing/leading whitespaces on each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)
        
        # Collapse spaces and tabs (but keep single newlines)
        text = re.sub(r'[ \t]+', ' ', text)
        
        return text.strip()
