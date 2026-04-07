from pathlib import Path
from module.Dataclasses.config_dataclass import ConfigDataclass
import tomllib

CONFIG_PATH = "D:/Brokers/eksportplattform_aria/config/config.toml"

def get_config_object(path):
    config_obj_str = open(path, "rb")#.read()
    config_obj_dict = tomllib.load(config_obj_str)
    config_obj = ConfigDataclass(**config_obj_dict)
    return config_obj

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Config(metaclass=Singleton):
    def __init__(self, HF = None):
        self.config_object = get_config_object(CONFIG_PATH)

    @property
    def conquest_aria(self):
        return self.config_object.conquest_aria

    @property
    def conquest_krest(self):
        return self.config_object.conquest_krest

    @property
    def aria(self):
        return self.config_object.aria

    @property
    def log_db(self):
        return self.config_object.log_db

    @property
    def krest(self):
        return self.config_object.krest