import threading
import time
import logging

from src.config import Config
from src.docker_api import get_monitored, get_executor
from src.model.api import Context as APIContext, Container as APIContainer
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

        for ctx in self.api_client.get_contexts(self.agent_id):
            self.registered_contexts[ctx.name] = ctx.id

        self.registered_containers = set() # id

        for cont in self.api_client.get_containers(self.agent_id):
            self.registered_containers.add(cont.id)

        self.container_statuses = {} # id -> status

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Discovery Service stopped.")

    def _discovery_loop(self):
        logger.info("Starting Discovery Service loop")
        executor = get_executor()

        if executor[0] == DiscoveryContext.host:
            logger.warning("Discovery Service is running on host context; cross-stack monitoring enabled.")

        def inner_loop():
            try:
                logger.debug("Running discovery...")
                monitored_data = get_monitored(cross_containerization_bounds=False)

                current_container_ids = set()
                all_containers_list = []

                for context_enum, stacks in monitored_data.items():
                    for context_name, containers in stacks.items():

                        # Check if context is registered
                        # If not, register it and get its ID
                        ctx_id: str | None = None

                        # Orphans have no context to register on server
                        if context_enum != DiscoveryContext.orphan:
                            if context_name not in self.registered_contexts:
                                # Register Context
                                api_context = APIContext(
                                    agent_id=self.agent_id,
                                    name=context_name,
                                    type=context_enum.value  # type: ignore
                                )
                                ctx_id = self.api_client.register_context(self.agent_id, api_context)
                                if ctx_id:
                                    self.registered_contexts[context_name] = ctx_id
                            else:
                                ctx_id = self.registered_contexts[context_name]

                            if ctx_id is None:
                                logger.error(f"Failed to register or retrieve context ID for {context_name}, skipping its containers.")
                                continue

                        # Process Containers in this context

                        for container in containers:
                            container.reload()

                            # Check if container is already registered
                            # If not, register it
                            # Then, check and update status if changed

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
                                    created_at=created_ts,
                                )
                                res = self.api_client.register_container(self.agent_id, api_container)
                                if res:
                                    self.registered_containers.add(container.id)
                                    self.container_statuses[container.id] = container.status

                            # Update Status
                            current_status = container.status
                            if self.container_statuses.get(container.id) != current_status:

                                self.api_client.update_container_status(self.agent_id, container.id, current_status, int(time.time()))
                                self.container_statuses[container.id] = current_status

                            # Add to all containers list for log collector
                            all_containers_list.append(container)
                            current_container_ids.add(container.id)

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
                import traceback
                traceback.print_exc()

        last_run = time.time() - Config.DISCOVERY_INTERVAL * 2
        while self.running:
            if time.time() - last_run < Config.DISCOVERY_INTERVAL:
                time.sleep(.25)
                continue
            inner_loop()
            last_run = time.time()

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
        logger.info("Heartbeat Service stopped.")

    def _heartbeat_loop(self):
        logger.info("Starting Heartbeat Service loop")
        last_run = time.time() - Config.HEARTBEAT_INTERVAL * 2
        while self.running:
            if time.time() - last_run < Config.HEARTBEAT_INTERVAL:
                time.sleep(.25)
                continue
            try:
                self.api_client.send_heartbeat(self.agent_id)
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
            finally:
                last_run = time.time()