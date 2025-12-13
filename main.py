import time
import logging
import socket
from src.config import Config
from src.docker_api import get_monitored
from src.model.api import Heartbeat, StackInfo, ContainerInfo, DockerContainerStatuses
from src.api_client import APIClient
from src.log_collector import LogCollector

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def map_container_to_info(container) -> ContainerInfo:
    # Map docker container status to our enum
    status_map = {
        'created': DockerContainerStatuses.CREATED,
        'running': DockerContainerStatuses.RUNNING,
        'paused': DockerContainerStatuses.PAUSED,
        'restarting': DockerContainerStatuses.RESTARTING,
        'exited': DockerContainerStatuses.EXITED,
        'removing': DockerContainerStatuses.REMOVING,
        'dead': DockerContainerStatuses.DEAD
    }

    status = status_map.get(container.status, DockerContainerStatuses.CUSTOM)

    # Ports can be complex, simplifying for now
    ports: dict[str, str] = {}
    if container.ports:
        for k, v in container.ports.items():
            if v:
                ports[k] = str(v)

    return ContainerInfo(
        id=container.id,
        name=container.name,
        status=status,
        image=str(container.image.tags[0]) if container.image.tags else "unknown",
        ports=ports,
        labels=container.labels
    )

def main():
    logger.info("Starting Clogs Agent...")

    api_client = APIClient()
    log_collector = LogCollector(api_client)
    log_collector.start()

    agent_id = socket.gethostname()

    try:
        while True:
            logger.info("Running discovery...")
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
                        containers=stack_containers_info
                    ))

            # Update log collector
            log_collector.update_monitored_containers(all_containers)

            # Send heartbeat
            heartbeat = Heartbeat(
                agent_id=agent_id,
                timestamp=time.time(),
                monitored_stacks=stacks_info
            )
            api_client.send_heartbeat(heartbeat)

            time.sleep(Config.HEARTBEAT_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Stopping Clogs Agent...")
        log_collector.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        log_collector.stop()

if __name__ == "__main__":
    main()
