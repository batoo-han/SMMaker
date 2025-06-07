import sys
import types

# Stub for gspread module
if 'gspread' not in sys.modules:
    gspread = types.ModuleType('gspread')
    def authorize(creds):
        return None
    gspread.authorize = authorize
    sys.modules['gspread'] = gspread

# Stub for google.oauth2.service_account Credentials
if 'google.oauth2.service_account' not in sys.modules:
    google_pkg = types.ModuleType('google')
    oauth2_pkg = types.ModuleType('google.oauth2')
    service_account_pkg = types.ModuleType('google.oauth2.service_account')

    class DummyCredentials:
        @classmethod
        def from_service_account_file(cls, path, scopes=None):
            return cls()
    service_account_pkg.Credentials = DummyCredentials

    oauth2_pkg.service_account = service_account_pkg

    sys.modules.setdefault('google', google_pkg)
    sys.modules['google.oauth2'] = oauth2_pkg
    sys.modules['google.oauth2.service_account'] = service_account_pkg

# Stub for apscheduler modules used in scheduler
if 'apscheduler.schedulers.background' not in sys.modules:
    aps_pkg = types.ModuleType('apscheduler')
    schedulers_pkg = types.ModuleType('apscheduler.schedulers')
    background_pkg = types.ModuleType('apscheduler.schedulers.background')

    class DummyJob:
        def __init__(self, func, trigger, args, id):
            self.func = func
            self.trigger = trigger
            self.args = args
            self.id = id

    class DummyBackgroundScheduler:
        def __init__(self, timezone=None):
            self.jobs = {}
            self.timezone = timezone
        def add_job(self, func, trigger, args=None, id=None, replace_existing=False):
            job = DummyJob(func, trigger, args or [], id)
            self.jobs[id] = job
            return job
        def get_job(self, id):
            return self.jobs.get(id)
        def remove_job(self, id):
            self.jobs.pop(id, None)
        def start(self):
            pass
        def shutdown(self):
            pass

    background_pkg.BackgroundScheduler = DummyBackgroundScheduler
    schedulers_pkg.background = background_pkg

    triggers_pkg = types.ModuleType('apscheduler.triggers')
    cron_pkg = types.ModuleType('apscheduler.triggers.cron')

    class DummyCronTrigger:
        def __init__(self, expr, timezone=None):
            self.expr = expr
            self.timezone = timezone
        @classmethod
        def from_crontab(cls, expr, timezone=None):
            return cls(expr, timezone)
        def __str__(self):
            return self.expr

    cron_pkg.CronTrigger = DummyCronTrigger
    triggers_pkg.cron = cron_pkg

    aps_pkg.schedulers = schedulers_pkg
    aps_pkg.triggers = triggers_pkg

    sys.modules['apscheduler'] = aps_pkg
    sys.modules['apscheduler.schedulers'] = schedulers_pkg
    sys.modules['apscheduler.schedulers.background'] = background_pkg
    sys.modules['apscheduler.triggers'] = triggers_pkg
    sys.modules['apscheduler.triggers.cron'] = cron_pkg

# Stub for pytz module
if 'pytz' not in sys.modules:
    pytz = types.ModuleType('pytz')
    def timezone(name):
        return name
    pytz.timezone = timezone
    sys.modules['pytz'] = pytz

# Stub for requests.exceptions
if 'requests' not in sys.modules:
    requests = types.ModuleType('requests')
    exc = types.ModuleType('requests.exceptions')
    class ConnectionError(Exception):
        pass
    exc.ConnectionError = ConnectionError
    requests.exceptions = exc
    sys.modules['requests'] = requests
    sys.modules['requests.exceptions'] = exc

# Stub for yaml module
if 'yaml' not in sys.modules:
    yaml = types.ModuleType('yaml')
    def safe_load(stream):
        return {}
    yaml.safe_load = safe_load
    sys.modules['yaml'] = yaml

# Stub for pydantic_settings.BaseSettings if package is missing
if 'pydantic_settings' not in sys.modules:
    from pydantic import BaseModel
    ps = types.ModuleType('pydantic_settings')

    class BaseSettings(BaseModel):
        class Config:
            extra = 'allow'

        def __init__(self, **data):
            env_values = {
                name: os.environ.get(name)
                for name in self.__class__.__fields__
                if os.environ.get(name) is not None
            }
            env_values.update(data)
            super().__init__(**env_values)

    ps.BaseSettings = BaseSettings
    sys.modules['pydantic_settings'] = ps

import os

os.environ.setdefault('GOOGLE_CREDENTIALS_PATH', 'dummy.json')
os.environ.setdefault('SHEETS_SPREADSHEET', 'dummy_sheet')
os.environ.setdefault('VK_SHEETS_TAB', 'vk')
os.environ.setdefault('TG_SHEETS_TAB', 'tg')
os.environ.setdefault('OPENAI_API_KEY', 'key')
os.environ.setdefault('YANDEX_API_KEY', 'key')
os.environ.setdefault('YANDEX_CLOUD_FOLDER_ID', 'folder')
os.environ.setdefault('FUSIONBRAIN_API_SECRET', 'secret')

# Stub for openai module
if 'openai' not in sys.modules:
    openai = types.ModuleType('openai')
    chat_pkg = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=""))], usage=types.SimpleNamespace(total_tokens=0))))
    images_pkg = types.SimpleNamespace(generate=lambda **kwargs: types.SimpleNamespace(data=[{"b64_json": ""}]))
    openai.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kwargs: types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=""))], usage=types.SimpleNamespace(total_tokens=0))))
    openai.images = types.SimpleNamespace(generate=lambda **kwargs: types.SimpleNamespace(data=[{"b64_json": ""}]))
    sys.modules['openai'] = openai

# Stub for telegram module
if 'telegram' not in sys.modules:
    telegram = types.ModuleType('telegram')
    telegram.Bot = object
    telegram.InputFile = object
    constants = types.ModuleType('telegram.constants')
    constants.ParseMode = types.SimpleNamespace(MARKDOWN='Markdown')
    error_pkg = types.ModuleType('telegram.error')
    class TelegramError(Exception):
        pass
    error_pkg.TelegramError = TelegramError
    telegram.constants = constants
    telegram.error = error_pkg
    sys.modules['telegram'] = telegram
    sys.modules['telegram.constants'] = constants
    sys.modules['telegram.error'] = error_pkg

# Stub for chromadb module
if 'chromadb' not in sys.modules:
    chromadb = types.ModuleType('chromadb')
    class PersistentClient:
        def __init__(self, path=None, settings=None):
            self.path = path
            self.settings = settings
        def get_or_create_collection(self, name, embedding_function=None):
            return types.SimpleNamespace(
                add=lambda **kwargs: None,
                get=lambda **kwargs: {"ids": [], "documents": [], "metadatas": []},
            )
    chromadb.PersistentClient = PersistentClient
    config_pkg = types.ModuleType('chromadb.config')
    class Settings:
        def __init__(self, **kwargs):
            pass
    config_pkg.Settings = Settings
    utils_pkg = types.ModuleType('chromadb.utils')
    ef_pkg = types.ModuleType('chromadb.utils.embedding_functions')
    class OpenAIEmbeddingFunction:
        def __init__(self, api_key=None, model_name=None):
            pass
    ef_pkg.OpenAIEmbeddingFunction = OpenAIEmbeddingFunction
    utils_pkg.embedding_functions = ef_pkg
    sys.modules['chromadb'] = chromadb
    sys.modules['chromadb.config'] = config_pkg
    sys.modules['chromadb.utils'] = utils_pkg
    sys.modules['chromadb.utils.embedding_functions'] = ef_pkg

# Stub for PIL.Image
if 'PIL' not in sys.modules:
    PIL = types.ModuleType('PIL')
    image_pkg = types.ModuleType('PIL.Image')
    class Image:
        LANCZOS = 1
        @staticmethod
        def open(fp):
            class Img:
                def thumbnail(self, size, resample):
                    pass
                def save(self, buf, format=None, quality=85):
                    pass
            return Img()
    image_pkg.Image = Image
    PIL.Image = Image
    sys.modules['PIL'] = PIL
    sys.modules['PIL.Image'] = image_pkg
