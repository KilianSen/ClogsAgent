from enum import Enum
from typing import List

from pydantic import BaseModel


class CompoundMessage(BaseModel):
    pass

class LogMessage(BaseModel):
    container_id: str
    log: str
    stream: str # stdout or stderr
    timestamp: float

class Heartbeat(BaseModel):
    agent_id: str
    timestamp: float
    monitored_stacks: List['StackInfo']

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