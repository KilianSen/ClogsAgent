from typing import Literal

from pydantic import BaseModel, Field

class Agent(BaseModel):
    id: str | None = Field(default=None)
    hostname: str | None = Field(default=None)
    heartbeat_interval: int = Field(default=30, )
    discovery_interval: int = Field(default=30, )
    on_host: bool = Field()

class Heartbeat(BaseModel):
    id: int | None = Field(default=None)
    agent_id: str = Field()
    timestamp: int = Field()

### Context ###
class Context(BaseModel):
    id: int | None = Field(default=None)
    agent_id: str | None = Field(default=None)
    name: str = Field()
    type: Literal["compose", "swarm"] = Field()


### Container Models ###

class Container(BaseModel):
    """
    Represents a container being monitored by an agent.
    """
    id: str | None = Field(default=None)
    agent_id: str = Field()
    context: int = Field()
    name: str = Field()
    image: str = Field()
    created_at: int = Field()

class ContainerState(BaseModel):
    id: int | None = Field(default=None)
    status: str = Field()

### Logging Models ###

class Log(BaseModel):
    """
    Represents a single log entry from a container.
    """
    id: int | None = Field(default=None)
    container_id: str = Field()
    timestamp: int = Field()
    level: str = Field()
    message: str = Field()

class MultilineLogTransfer(BaseModel):
    """
    This class is used by the api endpoint to receive multiline log entries in a single transfer.
    """
    container_id: str
    logs: list[Log]

class MultiContainerLogTransfer(BaseModel):
    """
    This class is used by the api endpoint to receive logs from multiple containers in a single transfer.
    """
    agent_id: str
    container_logs: list[MultilineLogTransfer]