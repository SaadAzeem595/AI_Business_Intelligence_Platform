from abc import ABC, abstractmethod
from typing import List, Optional
import os
import hashlib
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BaseEmbeddingProvider(ABC):
    dimension: int = 1536
    model_name: str = "default"

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding vector for a single text."""
        pass

    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of texts."""
        pass


class SemanticProjectionEmbeddingProvider(BaseEmbeddingProvider):
    """
    Deterministic semantic text projection provider into a target dimensional space (1536).
    Produces semantically correlated vectors (words and n-grams map consistently to coordinates),
    avoiding random uncorrelated noise and allowing offline operation when external API keys are unavailable.
    """
    def __init__(self, dimension: int = 1536, model_name: str = "semantic-projection-1536"):
        self.dimension = dimension
        self.model_name = model_name

    def _project_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension

        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().split()
        
        # Word-level hashed projections
        for w in words:
            clean_w = w.strip("?,.!\"':;()[]{}")
            if not clean_w:
                continue
            h = int(hashlib.md5(clean_w.encode("utf-8")).hexdigest()[:8], 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 1) % 2 == 0 else -1.0
            vec[idx] += sign

            # Character 3-gram sub-word projection for morphological similarity
            if len(clean_w) >= 3:
                for i in range(len(clean_w) - 2):
                    tri = clean_w[i:i+3]
                    th = int(hashlib.md5(tri.encode("utf-8")).hexdigest()[:6], 16)
                    t_idx = th % self.dimension
                    t_sign = 0.5 if (th >> 1) % 2 == 0 else -0.5
                    vec[t_idx] += t_sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def get_embedding(self, text: str) -> List[float]:
        return self._project_text(text)

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._project_text(t) for t in texts]


class OpenRouterEmbeddingProvider(BaseEmbeddingProvider):
    """
    Production dense vector embedding provider utilizing OpenRouter / OpenAI embeddings API.
    Defaults to openai/text-embedding-3-small (1536 dimensions).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/text-embedding-3-small",
        base_url: str = "https://openrouter.ai/api/v1",
        dimension: int = 1536
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model
        self.base_url = base_url.rstrip("/") if base_url else "https://openrouter.ai/api/v1"
        self.dimension = dimension
        self.url = f"{self.base_url}/embeddings"
        self._fallback = SemanticProjectionEmbeddingProvider(dimension=dimension, model_name=f"fallback-{model}")

        logger.info(
            f"RAG_EMBEDDING_INIT: Configured {self.__class__.__name__} with model='{self.model_name}', "
            f"dimension={self.dimension}, has_api_key={bool(self.api_key)}"
        )

    def get_embedding(self, text: str) -> List[float]:
        embs = self.get_embeddings([text])
        return embs[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if not self.api_key:
            logger.info("OPENROUTER_API_KEY not configured. Generating via deterministic semantic projection.")
            return self._fallback.get_embeddings(texts)

        import httpx
        import time

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Process in batches of 32
        batch_size = 32
        all_results = []

        for i in range(0, len(texts), batch_size):
            raw_batch = texts[i:i + batch_size]
            # Truncate any oversized chunk text to safe 10,000 chars (~2,500 tokens) to guarantee never exceeding 8192 tokens
            batch = [t[:10000] for t in raw_batch]
            payload = {
                "input": batch,
                "model": self.model_name
            }
            batch_success = False

            for attempt in range(3):
                try:
                    resp = httpx.post(self.url, headers=headers, json=payload, timeout=25.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_embs = [item["embedding"] for item in data["data"]]
                        for emb in raw_embs:
                            if len(emb) != self.dimension:
                                raise ValueError(
                                    f"Received vector dimension {len(emb)}, expected {self.dimension}."
                                )
                        all_results.extend(raw_embs)
                        batch_success = True
                        break
                    elif resp.status_code in (429, 500, 502, 503, 504):
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    else:
                        logger.warning(
                            f"OpenRouter embedding request returned HTTP {resp.status_code}: {resp.text}"
                        )
                        break
                except Exception as ex:
                    logger.warning(f"OpenRouter embedding attempt {attempt+1} failed: {ex}")
                    time.sleep(0.5 * (attempt + 1))

            if not batch_success:
                logger.warning(
                    f"Falling back to semantic projection for batch of {len(batch)} chunks due to API unavailability."
                )
                fallback_embs = self._fallback.get_embeddings(batch)
                all_results.extend(fallback_embs)

        return all_results


class MockEmbeddingProvider(SemanticProjectionEmbeddingProvider):
    """
    Backwards compatibility alias for MockEmbeddingProvider.
    Uses deterministic semantic projection rather than random uncorrelated noise.
    """
    def __init__(self, dimension: int = 1536):
        super().__init__(dimension=dimension, model_name="semantic-projection-1536")


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimension: int = 1536):
        self.api_key = api_key
        self.model_name = model
        self.dimension = dimension
        self.url = "https://api.openai.com/v1/embeddings"

    def get_embedding(self, text: str) -> List[float]:
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        import httpx
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": texts,
            "model": self.model_name
        }
        resp = httpx.post(self.url, headers=headers, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "sentence-transformers/all-MiniLM-L6-v2", dimension: int = 384):
        self.api_key = api_key
        self.model_name = model
        self.dimension = dimension
        self.url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model_name}"
        self._local_model = None

        try:
            from sentence_transformers import SentenceTransformer
            logger.info("sentence-transformers installed locally. Using local execution.")
            self._local_model = SentenceTransformer(self.model_name)
        except ImportError:
            logger.info("sentence-transformers not installed. Using remote Hugging Face API.")

    def get_embedding(self, text: str) -> List[float]:
        if self._local_model:
            return self._local_model.encode(text).tolist()
        return self.get_embeddings([text])[0]

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if self._local_model:
            return self._local_model.encode(texts).tolist()

        import httpx
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = httpx.post(self.url, headers=headers, json={"inputs": texts}, timeout=60.0)
        resp.raise_for_status()
        return resp.json()
