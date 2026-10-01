import os
import httpx
from dotenv import load_dotenv

load_dotenv("../.env")
load_dotenv(".env")
api_key = os.getenv("OPENROUTER_API_KEY")
print("API Key exists:", bool(api_key), f"Key prefix: {api_key[:10]}..." if api_key else "")

url = "https://openrouter.ai/api/v1/embeddings"
headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
for model in ["openai/text-embedding-3-small", "text-embedding-3-small", "baai/bge-small-en-v1.5", "amazon/titan-embed-text-v1"]:
    try:
        resp = httpx.post(url, headers=headers, json={"input": "Hello world", "model": model}, timeout=10)
        print(f"Model '{model}' status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            vec = data["data"][0]["embedding"]
            print(f"Success! Model {model} dimension: {len(vec)}")
            break
        else:
            print("Error:", resp.text)
    except Exception as e:
        print("Exception:", e)
