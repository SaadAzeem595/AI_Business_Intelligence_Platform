import os
import httpx
import logging

logger = logging.getLogger(__name__)

class LLMConfigurationError(Exception):
    """Custom exception raised when LLM is unconfigured, unreachable, or unauthorized."""
    pass

class LLMService:
    """Provides client wrappers for OpenAI and Gemini APIs using HTTP REST."""

    @staticmethod
    def get_api_key_and_provider():
        """Reads environment configurations to decide on LLM provider."""
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        
        # Check settings database or core settings as fallback
        if not gemini_key and not openai_key:
            try:
                from app.core.config import settings
                gemini_key = getattr(settings, "GEMINI_API_KEY", None)
                openai_key = getattr(settings, "OPENAI_API_KEY", None)
            except Exception:
                pass
            
        if gemini_key and gemini_key.strip():
            return gemini_key.strip(), "gemini"
        if openai_key and openai_key.strip():
            return openai_key.strip(), "openai"
        return None, None

    @classmethod
    def is_configured(cls) -> bool:
        """Indicates if a valid API key has been declared in the system environment."""
        key, provider = cls.get_api_key_and_provider()
        return key is not None

    @classmethod
    def generate_response(cls, system_prompt: str, user_prompt: str) -> str:
        """Sends chat completion query to the configured LLM provider synchronously."""
        key, provider = cls.get_api_key_and_provider()
        if not key:
            raise LLMConfigurationError("AI model configuration is unavailable.")

        if provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
            }
            try:
                with httpx.Client(timeout=25.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 401:
                        raise LLMConfigurationError("Invalid API key configured for OpenAI.")
                    elif response.status_code == 429:
                        raise LLMConfigurationError("OpenAI API rate limit exceeded.")
                    
                    response.raise_for_status()
                    res_json = response.json()
                    return res_json["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                err_detail = e.response.text
                logger.error(f"OpenAI API status error: {err_detail}")
                raise LLMConfigurationError(f"OpenAI LLM request failed with status {e.response.status_code}.")
            except httpx.RequestError as e:
                logger.error(f"OpenAI API connection error: {str(e)}")
                raise LLMConfigurationError(f"OpenAI LLM connection failed: {str(e)}")
                
        elif provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            headers = {
                "Content-Type": "application/json"
            }
            combined_text = f"System Instructions:\n{system_prompt}\n\nUser Message:\n{user_prompt}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": combined_text}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1
                }
            }
            try:
                with httpx.Client(timeout=25.0) as client:
                    response = client.post(url, headers=headers, json=payload)
                    
                    if response.status_code in (400, 403):
                        raise LLMConfigurationError("Invalid API key configured for Gemini or malformed request parameters.")
                    elif response.status_code == 429:
                        raise LLMConfigurationError("Gemini API rate limit exceeded.")
                    
                    response.raise_for_status()
                    res_json = response.json()
                    
                    candidates = res_json.get("candidates", [])
                    if not candidates or "content" not in candidates[0]:
                        raise LLMConfigurationError("Gemini returned an empty completion response.")
                    return candidates[0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                err_detail = e.response.text
                logger.error(f"Gemini API status error: {err_detail}")
                raise LLMConfigurationError(f"Gemini LLM request failed with status {e.response.status_code}.")
            except httpx.RequestError as e:
                logger.error(f"Gemini API connection error: {str(e)}")
                raise LLMConfigurationError(f"Gemini LLM connection failed: {str(e)}")
        else:
            raise LLMConfigurationError("Unknown LLM provider setup.")
