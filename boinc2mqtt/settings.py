import os
import datetime
import yaml
import pydantic
import humanreadable

SETTINGS_FILE = os.getenv("SETTINGS_FILE", "settings.yaml")


class BaseHost(pydantic.BaseModel):
    class Scrape(pydantic.BaseModel):
        enabled: bool = True
        delay: datetime.timedelta = datetime.timedelta(seconds=5)

        def get_delay_seconds(self) -> float:
            return self.delay.total_seconds()

        @pydantic.field_validator("delay", mode="before")
        @classmethod
        def _parse_duration(cls, value):
            if isinstance(value, str):
                parsed = humanreadable.Time(value)
                return datetime.timedelta(seconds=parsed.seconds)
            return value

    name: str|None = None
    host: str
    port: int
    scrape: Scrape = pydantic.Field(default_factory=Scrape)

    def get_host_name(self) -> str:
        return self.name or f"{self.host}:{self.port}"


class BoincHost(BaseHost):
    port: int = 31416
    password: pydantic.SecretStr|None = None


class BoincSettings(pydantic.BaseModel):
    hosts: list[BoincHost] = []


class FaHHost(BaseHost):
    port: int = 7396


class FaHSettings(pydantic.BaseModel):
    hosts: list[FaHHost] = []


class MQTTSettings(pydantic.BaseModel):
    host: str
    port: int = 1883
    username: str|None = None
    password: pydantic.SecretStr|None = None
    topic: str = "boinc"
    qos: int = 0
    retain: bool = False
    extra_args: dict = {}


class Settings(pydantic.BaseModel):
    mqtt: MQTTSettings
    boinc: BoincSettings = pydantic.Field(default_factory=BoincSettings)
    foldingathome: FaHSettings = pydantic.Field(default_factory=FaHSettings)


def load_settings():
    with open(SETTINGS_FILE, "r") as f:
        data = yaml.safe_load(f)
        return Settings.model_validate(data)
