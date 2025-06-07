import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.vector_db.vector_client import VectorClient


class DummyCollection:
    def __init__(self, docs, metas):
        self.docs = docs
        self.metas = metas

    def add(self, **kwargs):
        pass

    def get(self, **kwargs):
        # chromadb returns list[str] and list[dict]
        return {"ids": ["1" for _ in self.docs], "documents": self.docs, "metadatas": self.metas}


class DummyPersistentClient:
    def __init__(self, path=None, settings=None):
        pass

    def get_or_create_collection(self, name, embedding_function=None):
        return self.collection


def test_get_last_by_network(monkeypatch):
    docs = [
        "first text",
        "second text",
        "third text",
    ]
    metas = [
        {"network": "vk", "created_at": "2024-06-01T10:00:00"},
        {"network": "vk", "created_at": "2024-06-02T09:00:00"},
        {"network": "vk", "created_at": "2024-05-30T08:00:00"},
    ]

    dummy_collection = DummyCollection(docs, metas)
    client = DummyPersistentClient()
    client.collection = dummy_collection

    # Подменяем chromadb.PersistentClient, чтобы вернуть dummy client
    monkeypatch.setattr("chromadb.PersistentClient", lambda *a, **k: client)

    vc = VectorClient(
        persist_directory="/tmp",
        collection_name="test",
        embedding_model="model",
    )

    last = vc.get_last_by_network("vk")
    assert last == "second text"
