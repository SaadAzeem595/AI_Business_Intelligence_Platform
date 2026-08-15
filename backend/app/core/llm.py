import os
import httpx
import logging

logger = logging.getLogger(__name__)

class LLMConfigurationError(Exception):
    """Custom exception raised when LLM is unconfigured, unreachable, or unauthorized."""
    pass

class LLMService:
    """Provides client wrappers for OpenRouter, OpenAI, and Gemini APIs using HTTP REST."""

    @staticmethod
    def get_api_key_and_provider():
        """Reads environment configurations to decide on LLM provider."""
        provider_override = os.environ.get("LLM_PROVIDER", "").strip().lower()
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        
        # Check settings database or core settings as fallback
        try:
            from app.core.config import settings
            if not openrouter_key:
                openrouter_key = getattr(settings, "OPENROUTER_API_KEY", None)
            if not gemini_key:
                gemini_key = getattr(settings, "GEMINI_API_KEY", None)
            if not openai_key:
                openai_key = getattr(settings, "OPENAI_API_KEY", None)
            if not provider_override:
                provider_override = (getattr(settings, "LLM_PROVIDER", None) or "").strip().lower()
        except Exception:
            pass

        # Respect explicit provider preference if specified
        if provider_override == "openrouter" and openrouter_key:
            return openrouter_key.strip(), "openrouter"
        if provider_override == "gemini" and gemini_key:
            return gemini_key.strip(), "gemini"
        if provider_override == "openai" and openai_key:
            return openai_key.strip(), "openai"
            
        # Default priority: OpenRouter -> Gemini -> OpenAI
        if openrouter_key and openrouter_key.strip():
            return openrouter_key.strip(), "openrouter"
        if gemini_key and gemini_key.strip():
            return gemini_key.strip(), "gemini"
        if openai_key and openai_key.strip():
            return openai_key.strip(), "openai"
        return None, None

    @classmethod
    def get_configured_model(cls) -> str:
        """Returns the configured model string for OpenRouter or default providers."""
        model = os.environ.get("OPENROUTER_MODEL")
        if not model:
            try:
                from app.core.config import settings
                model = getattr(settings, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
            except Exception:
                model = "openai/gpt-4o-mini"
        return model or "openai/gpt-4o-mini"

    @classmethod
    def get_base_url(cls) -> str:
        """Returns the OpenRouter base URL."""
        base_url = os.environ.get("OPENROUTER_BASE_URL")
        if not base_url:
            try:
                from app.core.config import settings
                base_url = getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
            except Exception:
                base_url = "https://openrouter.ai/api/v1"
        return (base_url or "https://openrouter.ai/api/v1").rstrip("/")

    @classmethod
    def is_configured(cls) -> bool:
        """Indicates if a valid API key has been declared in the system environment."""
        key, provider = cls.get_api_key_and_provider()
        return key is not None and len(key.strip()) > 0

    @classmethod
    def get_diagnostic_status(cls) -> dict:
        """Returns safe configuration diagnostic metadata without exposing secrets."""
        key, provider = cls.get_api_key_and_provider()
        model = cls.get_configured_model()
        base_url = cls.get_base_url()
        return {
            "provider": provider or "none",
            "provider_configured": provider is not None,
            "model": model,
            "api_key_configured": key is not None and len(key.strip()) > 0,
            "base_url": base_url,
        }

    @classmethod
    def health_check(cls) -> dict:
        """Makes a 1-token minimal test request to verify LLM connectivity."""
        import time
        key, provider = cls.get_api_key_and_provider()
        if not key:
            return {
                "status": "unconfigured",
                "error": "Missing OPENROUTER_API_KEY environment variable.",
                "latency_ms": 0
            }
        start = time.perf_counter()
        try:
            res_text = cls.generate_response("Respond with 'OK'.", "Health check probe")
            latency = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "healthy",
                "provider": provider,
                "model": cls.get_configured_model(),
                "latency_ms": latency
            }
        except Exception as e:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return {
                "status": "unhealthy",
                "provider": provider or "unknown",
                "error": str(e),
                "latency_ms": latency
            }

    @classmethod
    def generate_response(cls, system_prompt: str, user_prompt: str, model_override: str = None) -> str:
        """Sends chat completion query to the configured LLM provider synchronously with model fallbacks."""
        key, provider = cls.get_api_key_and_provider()
        if not key:
            raise LLMConfigurationError("OPENROUTER_API_KEY is not configured in backend environment variables.")

        if provider == "openrouter":
            base_url = cls.get_base_url()
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://datapilot.ai",
                "X-Title": "DataPilot AI"
            }
            
            primary_model = model_override or cls.get_configured_model()
            # Candidate models to try in sequence if primary is rate limited (429) or unavailable (404/503)
            candidate_models = [primary_model]
            fallback_defaults = [
                "meta-llama/llama-3.3-70b-instruct:free",
                "google/gemini-2.0-flash-lite-001",
                "qwen/qwen-2.5-72b-instruct:free",
                "openai/gpt-4o-mini"
            ]
            for fbm in fallback_defaults:
                if fbm not in candidate_models:
                    candidate_models.append(fbm)

            last_error = None
            with httpx.Client(timeout=30.0) as client:
                for model_name in candidate_models:
                    payload = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.1,
                    }
                    try:
                        logger.info(f"OPENROUTER_LLM_REQUEST: model={model_name} url={url}")
                        response = client.post(url, headers=headers, json=payload)
                        
                        if response.status_code == 401:
                            raise LLMConfigurationError("Invalid OPENROUTER_API_KEY configured for OpenRouter (HTTP 401).")
                        elif response.status_code == 429:
                            last_error = f"OpenRouter API rate limit exceeded for model '{model_name}' (HTTP 429)."
                            logger.warning(f"{last_error} Trying fallback model...")
                            continue
                        elif response.status_code in (404, 503):
                            last_error = f"OpenRouter model '{model_name}' is unavailable (HTTP {response.status_code})."
                            logger.warning(f"{last_error} Trying fallback model...")
                            continue
                        elif response.status_code >= 500:
                            last_error = f"OpenRouter upstream provider error (HTTP {response.status_code})."
                            logger.warning(f"{last_error} Trying fallback model...")
                            continue
                        
                        response.raise_for_status()
                        res_json = response.json()

                        if "error" in res_json:
                            err_obj = res_json["error"]
                            err_msg = err_obj.get("message") if isinstance(err_obj, dict) else str(err_obj)
                            last_error = f"OpenRouter provider error: {err_msg}"
                            logger.warning(f"{last_error} Trying fallback model...")
                            continue

                        choices = res_json.get("choices", [])
                        if not choices or "message" not in choices[0] or "content" not in choices[0]["message"]:
                            last_error = "OpenRouter returned an empty completion response structure."
                            continue

                        content = choices[0]["message"]["content"]
                        if not content or not content.strip():
                            last_error = "OpenRouter returned empty content."
                            continue

                        logger.info(f"OPENROUTER_LLM_SUCCESS: model={model_name} response_len={len(content)}")
                        return content
                    except (httpx.HTTPStatusError, httpx.RequestError) as e:
                        last_error = f"OpenRouter HTTP error with model '{model_name}': {str(e)}"
                        logger.warning(last_error)
                        continue

            raise LLMConfigurationError(last_error or "OpenRouter LLM request failed across all candidate models.")


        elif provider == "openai":
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

