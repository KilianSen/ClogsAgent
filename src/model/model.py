from enum import Enum

from docker.models.containers import Container
class DockerContainerStatuses(Enum):
    CREATED = 'created'
    RUNNING = 'running'
    PAUSED = 'paused'
    RESTARTING = 'restarting'
    EXITED = 'exited'
    REMOVING = 'removing'
    DEAD = 'dead'
    CUSTOM = 'custom'

class Context(Enum):
    orphan = "orphan"
    compose = "compose"
    stack = "stack"
    host = "host"

MONITORING_TYPE = dict[Context, dict[str | None, list[Container]]]