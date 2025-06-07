import os, json
from .config import Settings

class Collection:
    def __init__(self, name, docs, client):
        self.name = name
        self._docs = docs
        self._client = client

    def add(self, ids, documents, metadatas):
        for idx in range(len(ids)):
            self._docs.append({
                'id': ids[idx],
                'document': documents[idx],
                'metadata': metadatas[idx]
            })
        self._client._save()

    def get(self, where=None):
        where = where or {}
        docs = [d for d in self._docs if all(d['metadata'].get(k)==v for k,v in where.items())]
        return {
            'ids': [[d['id'] for d in docs]],
            'documents': [[d['document'] for d in docs]],
            'metadatas': [[d['metadata'] for d in docs]]
        }

    def query(self, query_texts, n_results=5, where=None):
        where = where or {}
        docs = [d for d in self._docs if all(d['metadata'].get(k)==v for k,v in where.items())][:n_results]
        return {
            'ids': [[d['id'] for d in docs]],
            'documents': [[d['document'] for d in docs]],
            'metadatas': [[d['metadata'] for d in docs]],
            'distances': [[0.0 for _ in docs]]
        }

class Client:
    def __init__(self, settings: Settings=None):
        self._settings = settings
        self._dir = settings.persist_directory if settings else None
        self._collections = {}
        self._load()

    def _db_path(self):
        if not self._dir:
            return None
        return os.path.join(self._dir, 'chromadb.json')

    def _load(self):
        path = self._db_path()
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for name, docs in data.items():
                self._collections[name] = Collection(name, docs, self)

    def _save(self):
        path = self._db_path()
        if not path:
            return
        os.makedirs(self._dir, exist_ok=True)
        data = {name: coll._docs for name, coll in self._collections.items()}
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def get_or_create_collection(self, name, embedding_function=None):
        if name not in self._collections:
            self._collections[name] = Collection(name, [], self)
            self._save()
        return self._collections[name]
