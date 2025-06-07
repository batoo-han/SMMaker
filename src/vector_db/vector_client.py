# src/vector_db/vector_client.py

"""
vector_client.py

Клиент для работы с ChromaDB, адаптированный к актуальной версии chromadb (>=0.4),
следуя рекомендациям из раздела "New Clients" миграционного руководства.
Теперь конфигурация передаётся в Client как позиционный аргумент Settings, а не через устаревшие ключи.
"""

from datetime import datetime
from typing import List, Optional, Dict

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from src.config.settings import settings


class VectorClient:
    """
    Клиент для взаимодействия с ChromaDB.
    """

    def __init__(
        self,
        persist_directory: str,
        collection_name: str,
        embedding_model: str
    ):
        """
        Инициализирует клиента ChromaDB и коллекцию.

        :param persist_directory: путь к каталогу для хранения данных ChromaDB (строка).
        :param collection_name:   имя коллекции (будет создана, если не существует).
        :param embedding_model:   имя модели для эмбеддингов (например, "text-embedding-ada-002").
        """
        # Проверка типов входных параметров
        if not isinstance(persist_directory, str):
            raise ValueError(f"persist_directory должен быть строкой, получено: {type(persist_directory)}")
        if not isinstance(collection_name, str):
            raise ValueError(f"collection_name должен быть строкой, получено: {type(collection_name)}")
        if not isinstance(embedding_model, str):
            raise ValueError(f"embedding_model должен быть строкой, получено: {type(embedding_model)}")

        # Создаём Settings для ChromaDB и инициализируем PersistentClient
        try:
            chroma_config = ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=persist_directory,
            )
            # Используем PersistentClient для сохранения данных на диск
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=chroma_config,
            )
        except Exception as e:
            raise RuntimeError(
                f"Не удалось инициализировать chromadb.PersistentClient: {e}"
            )

        # Функция эмбеддинга через OpenAI
        try:
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name=embedding_model
            )
        except Exception as e:
            raise RuntimeError(f"Не удалось инициализировать OpenAIEmbeddingFunction: {e}")

        # Получаем или создаём коллекцию
        try:
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_fn
            )
        except Exception as e:
            raise RuntimeError(f"Не удалось получить или создать коллекцию '{collection_name}': {e}")

    def add_post(
        self,
        network: str,
        post_id: str,
        text: str,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Добавляет запись (Post) в коллекцию.

        :param network:   сеть публикации, например "vk" или "telegram".
        :param post_id:   идентификатор поста (ScheduleConfig.id).
        :param text:      текст содержимого поста.
        :param url:       URL или ID опубликованного поста.
        :param metadata:  дополнительная метаинформация.
        """
        if metadata is None:
            metadata = {}

        # Проверяем типы
        if not isinstance(network, str):
            raise ValueError(f"network должен быть строкой, получено: {type(network)}")
        if not isinstance(post_id, str):
            raise ValueError(f"post_id должен быть строкой, получено: {type(post_id)}")
        if not isinstance(text, str):
            raise ValueError(f"text должен быть строкой, получено: {type(text)}")
        if url is not None and not isinstance(url, str):
            raise ValueError(f"url должен быть строкой или None, получено: {type(url)}")

        # Генерируем уникальный id для ChromaDB
        unique_id = f"{network}_{post_id}_{int(datetime.utcnow().timestamp())}"

        # Обновляем metadata обязательными полями
        metadata.update({
            "network": network,
            "post_id": post_id,
            "created_at": datetime.utcnow().isoformat(),
        })
        if url:
            metadata["url"] = url

        # Добавляем запись в коллекцию
        try:
            self.collection.add(
                ids=[unique_id],
                documents=[text],
                metadatas=[metadata]
            )
        except Exception as e:
            raise RuntimeError(f"Не удалось добавить в ChromaDB запись {unique_id}: {e}")

    def get_last_by_network(self, network: str) -> Optional[str]:
        """
        Возвращает текст последнего добавленного документа для указанной сети.

        :param network: сеть публикации, например "vk" или "telegram".
        :return: текст последнего документа (str) или None, если не найдено ни одной записи.
        """
        if not isinstance(network, str):
            raise ValueError(f"network должен быть строкой, получено: {type(network)}")

        try:
            results = self.collection.get(
                where={"network": network}
            )
        except Exception as e:
            raise RuntimeError(f"Ошибка при извлечении данных из ChromaDB: {e}")

        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        # Если нет записей
        if not documents or len(documents) == 0:
            return None

        doc_list = documents[0]
        meta_list = metadatas[0]

        latest_text = None
        latest_ts = None

        for idx, meta in enumerate(meta_list):
            created_str = meta.get("created_at")
            if not created_str:
                continue
            try:
                created = datetime.fromisoformat(created_str)
            except Exception:
                continue

            if latest_ts is None or created > latest_ts:
                latest_ts = created
                latest_text = doc_list[idx]

        return latest_text

    def query_similar(
        self,
        query_text: str,
        top_k: int = 5,
        network: Optional[str] = None
    ) -> List[Dict]:
        """
        Выполняет векторный поиск по заданному тексту.

        :param query_text: текст для поиска схожих документов.
        :param top_k:      количество возвращаемых результатов.
        :param network:    если указано, фильтруем по метаданному network.
        :return: список словарей с ключами: id, text, metadata, distance.
        """
        if not isinstance(query_text, str):
            raise ValueError(f"query_text должен быть строкой, получено: {type(query_text)}")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"top_k должен быть положительным целым, получено: {top_k}")
        if network is not None and not isinstance(network, str):
            raise ValueError(f"network должен быть строкой или None, получено: {type(network)}")

        try:
            if network:
                response = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k,
                    where={"network": network}
                )
            else:
                response = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k
                )
        except Exception as e:
            raise RuntimeError(f"Ошибка при запросе в ChromaDB: {e}")

        ids_list = response.get("ids", [[]])[0]
        documents_list = response.get("documents", [[]])[0]
        metadatas_list = response.get("metadatas", [[]])[0]
        distances_list = response.get("distances", [[]])[0]

        results = []
        for idx in range(len(ids_list)):
            results.append({
                "id": ids_list[idx],
                "text": documents_list[idx],
                "metadata": metadatas_list[idx],
                "distance": distances_list[idx]
            })

        return results
