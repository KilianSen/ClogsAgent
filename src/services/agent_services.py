import threading
import time
import logging

from src.config import Config
from src.docker_api import get_monitored, get_executor
from src.model.api import Context as APIContext, Container as APIContainer, Agent
from src.api import APIClient
from src.services.log_collector import LogCollector
from src.model.model import Context as DiscoveryContext

logger = logging.getLogger(__name__)

class DiscoveryService:
    def __init__(self, api_client: APIClient, log_collector: LogCollector, agent_id: str):
        self.api_client = api_client
        self.log_collector = log_collector
        self.agent_id = agent_id
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # Local state to track what's registered
        self.registered_contexts = {} # name -> id
        self.registered_containers = set() # id
        self.container_statuses = {} # id -> status

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _discovery_loop(self):
        logger.info("Starting Discovery Service loop")
        executor = get_executor()

        if executor[0] == DiscoveryContext.host:
            logger.warning("Discovery Service is running on host context; cross-stack monitoring enabled.")

        while self.running:
            try:
                logger.debug("Running discovery...")
                monitored_data = get_monitored(cross_stack_bounds=False)

                current_container_ids = set()
                all_containers_list = []

                for context_enum, stacks in monitored_data.items():
                    for stack_name, containers in stacks.items():
                        # Determine Context Name and Type
                        ctx_name = stack_name if stack_name else f"{context_enum.value}_default"
                        ctx_type = "compose"
                        if context_enum == DiscoveryContext.stack:
                            ctx_type = "swarm"

                        # Register Context
                        if ctx_name not in self.registered_contexts:
                            api_context = APIContext(
                                agent_id=self.agent_id,
                                name=ctx_name,
                                type=ctx_type
                            )
                            ctx_id = self.api_client.register_context(self.agent_id, api_context)
                            if ctx_id is not None:
                                self.registered_contexts[ctx_name] = ctx_id
                            else:
                                logger.warning(f"Failed to register context {ctx_name}")
                                continue

                        ctx_id = self.registered_contexts.get(ctx_name)
                        if not ctx_id:
                            continue

                        for container in containers:
                            all_containers_list.append(container)
                            current_container_ids.add(container.id)

                            # Register Container
                            if container.id not in self.registered_containers:
                                try:
                                    created_str = container.attrs['Created'][:19]
                                    created_ts = int(time.mktime(time.strptime(created_str, "%Y-%m-%dT%H:%M:%S")))
                                except Exception as e:
                                    logger.warning(f"Failed to parse created timestamp for {container.name}: {e}")
                                    created_ts = int(time.time())

                                api_container = APIContainer(
                                    id=container.id,
                                    agent_id=self.agent_id,
                                    context=ctx_id,
                                    name=container.name,
                                    image=str(container.image.tags[0]) if container.image.tags else "unknown",
                                    created_at=created_ts
                                )
                                res = self.api_client.register_container(self.agent_id, api_container)
                                if res:
                                    self.registered_containers.add(container.id)
                                    self.container_statuses[container.id] = container.status

                            # Update Status
                            current_status = container.status
                            if self.container_statuses.get(container.id) != current_status:
                                self.api_client.update_container_status(self.agent_id, container.id, current_status)
                                self.container_statuses[container.id] = current_status

                # Update log collector
                self.log_collector.update_monitored_containers(all_containers_list)

                # Handle removed containers
                removed_containers = self.registered_containers - current_container_ids
                for container_id in removed_containers:
                    logger.info(f"Container {container_id} removed, deleting from server")
                    self.api_client.delete_container(self.agent_id, container_id)
                    self.registered_containers.remove(container_id)
                    if container_id in self.container_statuses:
                        del self.container_statuses[container_id]

            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")

            time.sleep(Config.DISCOVERY_INTERVAL)

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
                self.api_client.send_heartbeat(self.agent_id)
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
            time.sleep(Config.HEARTBEAT_INTERVAL)
