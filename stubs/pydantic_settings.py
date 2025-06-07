from pydantic.fields import FieldInfo

class BaseSettings:
    def __init__(self, **kwargs):
        cls = self.__class__
        for name, val in cls.__dict__.items():
            if isinstance(val, FieldInfo):
                setattr(self, name, kwargs.get(name, val.default))
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)
