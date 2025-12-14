import threading
import time
import logging
from typing import List

from docker.models.containers import Container

from src.config import Config
from src.docker_api import get_monitored, get_executor
from src.model.api import StackInfo, ContainerInfo, DockerContainerStatuses, Heartbeat, AgentState
from src.api import APIClient
from src.services.log_collector import LogCollector
from src.model.model import Context

logger = logging.getLogger(__name__)

def map_container_to_info(container: Container) -> ContainerInfo:
    status = DockerContainerStatuses.CUSTOM
    for st in DockerContainerStatuses:
        if container.status == st.value:
            status = st
            break

    return ContainerInfo(
        id=container.id,
        name=container.name,
        status=status,
        image=str(container.image.tags[0]) if container.image.tags else "unknown",
        ports=None \
        if not container.ports else \
        {port: "" if mappings is None else ",".join(set([str(mapping['HostPort']) for mapping in mappings]))
         for port, mappings in container.ports.items()},
        labels=container.labels
    )

class DiscoveryService:
    def __init__(self, api_client: APIClient, log_collector: LogCollector, agent_id: str):
        self.api_client = api_client
        self.log_collector = log_collector
        self.agent_id = agent_id
        self.running = False
        self.thread = None
        self.last_monitored_stacks: List[StackInfo] = []
        self.last_sent_stacks_hash = None
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def get_last_stacks(self) -> List[StackInfo]:
        with self.lock:
            return self.last_monitored_stacks

    def _discovery_loop(self):
        logger.info("Starting Discovery Service loop")
        executor = get_executor()

        if executor[0] == Context.host:
            logger.warning("Discovery Service is running on host context; cross-stack monitoring enabled.")

        while self.running:
            try:
                logger.debug("Running discovery...")
                monitored_data = get_monitored(cross_stack_bounds=False)

                all_containers = []
                stacks_info = []

                for context, stacks in monitored_data.items():
                    for stack_name, containers in stacks.items():
                        stack_containers_info = []
                        for container in containers:
                            all_containers.append(container)
                            stack_containers_info.append(map_container_to_info(container))

                        # Use context value if stack_name is None (e.g. orphan)
                        final_stack_name = stack_name if stack_name else f"{context.value}_default"

                        stacks_info.append(StackInfo(
                            name=final_stack_name,
                            type=context.value,
                            containers=stack_containers_info
                        ))

                with self.lock:
                    self.last_monitored_stacks = stacks_info

                # Check for changes and send state update
                current_stacks_json = [s.model_dump_json() for s in stacks_info]
                current_hash = hash(tuple(sorted(current_stacks_json)))

                if self.last_sent_stacks_hash != current_hash:
                    logger.info("State changed, sending agent state update")
                    state = AgentState(
                        agent_id=self.agent_id,
                        timestamp=time.time(),
                        monitored_stacks=stacks_info
                    )
                    self.api_client.send_state(state)
                    self.last_sent_stacks_hash = current_hash
                else:
                    logger.debug("State unchanged, skipping update")

                # Update log collector
                self.log_collector.update_monitored_containers(all_containers)

            except Exception as e:
                logger.error(f"Error in discovery loop: {e}", exc_info=True)

            # Sleep for the interval, checking running flag
            for _ in range(Config.DISCOVERY_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

class HeartbeatService:
    def __init__(self, api_client: APIClient, agent_id: str):
        self.api_client = api_client
        self.agent_id = agent_id
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _heartbeat_loop(self):
        logger.info("Starting Heartbeat Service loop")
        while self.running:
            try:
                heartbeat = Heartbeat(
                    agent_id=self.agent_id,
                    timestamp=time.time()
                )
                if self.api_client.send_heartbeat(heartbeat):
                    try:
                        with open("/tmp/healthy", "w") as f:
                            f.write(str(time.time()))
                    except Exception:
                        pass # Ignore file errors

            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

            # Sleep for the interval
            for _ in range(Config.HEARTBEAT_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

