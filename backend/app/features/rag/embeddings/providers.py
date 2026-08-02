from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib
import numpy as np
import logging

logger = logging.getLogger(__name__)

class BaseEmbeddingProvider(ABC):
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """Generates embedding vector for a single text."""
        pass
        
    @abstractmethod
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embedding vectors for a batch of texts."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension

    def get_embedding(self, text: str) -> List[float]:
        # Generate deterministic mock embedding based on SHA-256 hash of text
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:4], "big")
        np.random.seed(seed)
        
        vec = np.random.normal(0, 1, self.dimension)
        # Normalize to unit length for standard cosine similarity
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self.get_embedding(t) for t in texts]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model
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
            "model": self.model
        }
        resp = httpx.post(self.url, headers=headers, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.api_key = api_key
        self.model = model
        self.url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
        self._local_model = None
        
        # Check if sentence-transformers is installed locally
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("sentence-transformers installed locally. Using local execution.")
            self._local_model = SentenceTransformer(self.model)
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
