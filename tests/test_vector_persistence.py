import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)
sys.path.insert(0, os.path.join(project_root, 'stubs'))

from src.vector_db.vector_client import VectorClient


def test_embeddings_persist(tmp_path):
    persist = tmp_path / "chroma"
    vc1 = VectorClient(persist_directory=str(persist), collection_name="test", embedding_model="dummy")
    vc1.add_post(network="vk", post_id="1", text="hello")

    # recreate client to load existing data
    vc2 = VectorClient(persist_directory=str(persist), collection_name="test", embedding_model="dummy")
    last = vc2.get_last_by_network("vk")
    assert last == "hello"
