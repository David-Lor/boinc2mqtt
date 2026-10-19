import datetime
import pydantic
import humanreadable


class BaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        str_min_length=1,
    )


class WorkUnit(BaseModel):
    host: str
    project: str
    name: str
    percentage: float
    running: bool
    start_timestamp: datetime.datetime
    total_time_seconds: int
    run_seconds: int | None = None
    remaining_seconds: int  # ETA
    timeout_seconds: int
    expire_seconds: int
    cpu_count: int
    gpu_count: int

    @pydantic.field_validator("percentage", mode="after")
    @classmethod
    def _limit_percentage_decimals(cls, value):
        if isinstance(value, float):
            return round(value, 2)
        return value


class FaHResponseWorkUnit(BaseModel):

    class Assignment(BaseModel):
        project: str | int
        deadline: int
        timeout: int

    class Wu(BaseModel):
        time: datetime.datetime

    id: str
    pause_reason: str | None = None
    assignment: Assignment
    wu: Wu
    wu_progress: float
    eta: datetime.timedelta
    # start_time: datetime.datetime
    cpus: int
    gpus: list

    @pydantic.field_validator("eta", mode="before")
    @classmethod
    def _parse_eta(cls, value):
        if isinstance(value, str):
            parsed = humanreadable.Time(value)
            return datetime.timedelta(seconds=parsed.seconds)
        return value
