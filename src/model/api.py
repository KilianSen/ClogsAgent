from enum import Enum

from pydantic import BaseModel
import model


class CompoundMessage(BaseModel):
    ...


class DockerContainerStatuses(Enum):
    CREATED = 'created'
    RUNNING = 'running'
    PAUSED = 'paused'
    RESTARTING = 'restarting'
    EXITED = 'exited'
    REMOVING = 'removing'
    DEAD = 'dead'
    CUSTOM = 'custom'

class ContainerInfo(BaseModel):
    id: str
    name: str
    status: DockerContainerStatuses
    image: str
    ports: dict[str, str] | None = None
    labels: dict[str, str] | None = None

class StackInfo(BaseModel):
    name: str
    containers: list[ContainerInfo]