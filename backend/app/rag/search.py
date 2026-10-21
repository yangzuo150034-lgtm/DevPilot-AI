import hashlib
import math
import re
from collections import Counter
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from app.core.config import Settings


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", text.lower())


def hash_vector(text: str, size: int = 256) -> list[float]:
    """Offline lexical hashing for demos; deliberately not called semantic embeddings."""
    vector = [0.0] * size
    for token, count in Counter(tokens(text)).items():
        hashed = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big")
        vector[hashed % size] += count * (1 if (hashed >> 8) % 2 else -1)
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def keyword_scores(chunks: list[dict], query: str) -> list[tuple[int, float]]:
    documents = [tokens(chunk["path"] + " " + chunk["text"]) for chunk in chunks]
    average = sum(map(len, documents)) / max(1, len(documents)) or 1
    scores = []
    for index, doc in enumerate(documents):
        freq = Counter(doc)
        score = 0.0
        for token in set(tokens(query)):
            df = sum(token in other for other in documents)
            idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
            tf = freq[token]
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * len(doc) / average))
        if score > 0:
            scores.append((index, score))
    return sorted(scores, key=lambda value: value[1], reverse=True)


class CodeSearch:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = (
            QdrantClient(url=settings.qdrant_url)
            if settings.qdrant_url
            else QdrantClient(":memory:")
        )
        self.indexed: set[str] = set()
        self.embedder = None
        if settings.embedding_provider == "openai":
            if not settings.openai_api_key.get_secret_value():
                raise ValueError("OpenAI embeddings require a configured API key")
            from langchain_openai import OpenAIEmbeddings

            self.embedder = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key.get_secret_value(),
                base_url=settings.openai_base_url,
                request_timeout=settings.model_timeout,
                max_retries=1,
                chunk_size=64,
            )

    def vectors(self, texts: list[str]) -> list[list[float]]:
        return (
            self.embedder.embed_documents(texts)
            if self.embedder
            else [hash_vector(x) for x in texts]
        )

    def search(self, repository_id: str, chunks: list[dict], query: str, mode="hybrid", limit=5):
        if not chunks:
            return []
        keyword = keyword_scores(chunks, query)
        dense = []
        if mode in {"vector", "hybrid"}:
            name = "repo_" + repository_id + "_" + self.settings.embedding_provider
            if name not in self.indexed:
                vectors = self.vectors([c["path"] + "\n" + c["text"] for c in chunks])
                if not self.client.collection_exists(name):
                    self.client.create_collection(
                        name,
                        vectors_config=models.VectorParams(
                            size=len(vectors[0]),
                            distance=models.Distance.COSINE,
                        ),
                    )
                self.client.upsert(
                    name,
                    points=[
                        models.PointStruct(
                            id=str(uuid5(NAMESPACE_URL, chunk["id"])),
                            vector=vector,
                            payload={"index": i},
                        )
                        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False))
                    ],
                    wait=True,
                )
                self.indexed.add(name)
            vector = self.embedder.embed_query(query) if self.embedder else hash_vector(query)
            response = self.client.query_points(name, query=vector, limit=min(20, len(chunks)))
            dense = [(point.payload["index"], float(point.score)) for point in response.points]
        if mode == "keyword":
            ranked = keyword
        elif mode == "vector":
            ranked = dense
        else:
            fused = Counter()
            for ranking in [keyword[:20], dense]:
                for rank, (index, _) in enumerate(ranking):
                    fused[index] += 1 / (60 + rank + 1)
            # Deterministic lexical reranking is explicit; no claim of a learned cross-encoder.
            terms = set(tokens(query))
            ranked = sorted(
                fused.items(),
                key=lambda item: (
                    item[1] + 0.002 * len(terms & set(tokens(chunks[item[0]]["path"]))),
                ),
                reverse=True,
            )
        return [
            {
                **chunks[index],
                "score": round(score, 6),
                "retrieval": mode,
                "embedding": self.settings.embedding_provider,
            }
            for index, score in ranked[:limit]
        ]

    def close(self):
        self.client.close()
