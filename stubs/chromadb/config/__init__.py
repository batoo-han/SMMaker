class Settings:
    def __init__(self, chroma_db_impl=None, persist_directory=None):
        self.chroma_db_impl = chroma_db_impl
        self.persist_directory = persist_directory
