from enum import Enum

from docker.models.containers import Container


class Context(Enum):
    orphan = "orphan"
    compose = "compose"
    stack = "stack"
    host = "host"

MONITORING_TYPE = dict[Context, dict[str | None, list[Container]]]