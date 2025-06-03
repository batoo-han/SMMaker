# src/vector_db/vector_client.py

"""
vector_client.py

Клиент для работы с ChromaDB (новая версия API):
  - Инициализация PersistentClient через chromadb.PersistentClient.
  - Добавление нового документа (текста статьи) с указанием сети (network).
  - Получение последнего документа для заданной сети (для стиля).
  - Векторный поиск (query) для получения top_k похожих текстов.
"""

import os
from typing import List, Optional, Dict
from datetime import datetime

import chromadb
from chromadb.utils import embedding_functions

from src.config.settings import settings
import uuid
import logging

from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorClient:
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None
    ):
        """
        Инициализирует ChromaDB (PersistentClient):
          - persist_directory: каталог для хранения (берётся из настроек, если не указан).
          - collection_name: имя коллекции (берётся из настройках, если не указан).
          - embedding_model: модель эмбеддингов (например, "text-embedding-ada-002").
        """
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.embedding_model = embedding_model or settings.OPENAI_EMBEDDING_MODEL
        self.client = chromadb.Client(Settings(anonymized_telemetry=False))

        # Создаём каталог для хранения (persistent) если не существует
        os.makedirs(self.persist_directory, exist_ok=True)

        # Создаём embedding function через OpenAI
        try:
            openai_ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name=self.embedding_model
            )
        except Exception as e:
            logger.error(f"[Chroma] Ошибка инициализации OpenAIEmbeddingFunction: {e}")
            raise

        # --- Новый способ: PersistentClient ---
        try:
            self.client = chromadb.PersistentClient(path=self.persist_directory)
        except Exception as e:
            logger.error(f"[Chroma] Ошибка инициализации Chroma PersistentClient: {e}")
            raise

        # Пытаемся получить или создать коллекцию
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=openai_ef
            )
        except Exception as e:
            logger.error(f"[Chroma] Ошибка при получении или создании коллекции: {e}")
            raise

    def add_document(self, text: str, network: str, created_at: Optional[str] = None) -> None:
        """
        Добавляет новый документ (статью) в коллекцию:
          - text: полный текст статьи (заголовок + тело).
          - network: "vk" или "telegram".
          - created_at: ISO-строка времени публикации; если None, ставится текущее UTC-время.
        """
        if not created_at:
            created_at = datetime.utcnow().isoformat()

        doc_id = str(uuid.uuid4())
        try:
            self.collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[{"network": network, "created_at": created_at}],
                embeddings=None  # Chroma сама рассчитает эмбеддинги через OpenAIEmbeddingFunction
            )
            logger.info(f"[Chroma] Добавлен документ id={doc_id}, network={network}")
        except Exception as e:
            logger.error(f"[Chroma] Ошибка при добавлении документа: {e}")
            raise

    def get_last_by_network(self, network: str) -> Optional[str]:
        """
        Возвращает текст (documents) самого последнего добавленного документа
        для заданной сети (`network`), либо None, если таких документов ещё нет.
        """
        try:
            results = self.collection.get(
                where={"network": network},
                include=["metadatas", "documents"]
            )
        except Exception as e:
            logger.error(f"[Chroma] Ошибка при get (network={network}): {e}")
            return None

        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        if not metadatas or not documents or len(metadatas) != len(documents):
            return None

        latest_idx = None
        latest_time = None
        for idx, meta in enumerate(metadatas):
            try:
                ts = datetime.fromisoformat(meta.get("created_at", ""))
            except Exception:
                continue
            if latest_time is None or ts > latest_time:
                latest_time = ts
                latest_idx = idx

        if latest_idx is not None:
            return documents[latest_idx]
        return None

    def query(self, text: str, top_k: int = 3) -> List[Dict]:
        """
        Выполняет векторный поиск по тексту:
          - text: поисковая строка (например, тема).
          - top_k: число возвращаемых похожих документов.
        Возвращает список словарей вида {'id': ..., 'text': ..., 'metadata': {...}, 'distance': ...}.
        """
        try:
            response = self.collection.query(
                query_texts=[text],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
        except Exception as e:
            logger.error(f"[Chroma] Ошибка при query: {e}")
            return []

        docs = []
        ids_list = response.get("ids", [[]])[0]
        documents_list = response.get("documents", [[]])[0]
        metadatas_list = response.get("metadatas", [[]])[0]
        distances_list = response.get("distances", [[]])[0]

        for idx in range(len(ids_list)):
            docs.append({
                "id": ids_list[idx],
                "text": documents_list[idx],
                "metadata": metadatas_list[idx],
                "distance": distances_list[idx]
            })
        return docs
