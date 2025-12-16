import os
import time
import logging
import socket
import signal
import sys
from src.config import Config, config_load_id, config_save_id
from src.model.api import Agent
from src.api import APIClient
from src.services.log_collector import LogCollector
from src.services.agent_services import DiscoveryService, HeartbeatService
from src.docker_api import get_executor
from src.model.model import Context as DiscoveryContext

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Clogs Agent...")

    # Determine on_host
    executor = get_executor()
    on_host = executor[0] == DiscoveryContext.host

    api_client = APIClient()

    # Register Agent
    agent = Agent(
        hostname=socket.gethostname(),
        heartbeat_interval=Config.HEARTBEAT_INTERVAL,
        discovery_interval=Config.DISCOVERY_INTERVAL,
        on_host=on_host
    )

    # Read existing agent ID from file if exists
    agent.id = config_load_id()

    agent_id  = agent.id
    if not agent.id:
        a = api_client.get_agent(agent_id) if agent_id else None
        if not a:
            agent_id = api_client.register_agent(agent)
        else:
            agent_id = a.id

    if not agent_id:
        logger.error("Failed to register agent. Exiting.")
        sys.exit(1)

    if agent_id != config_load_id() and agent_id is not None:
        config_save_id(agent_id)


    logger.info(f"Agent registered with ID: {agent_id}")

    # Initialize Services
    log_collector = LogCollector(api_client, agent_id)
    discovery_service = DiscoveryService(api_client, log_collector, agent_id)
    heartbeat_service = HeartbeatService(api_client, agent_id)

    # Start Services
    log_collector.start()
    discovery_service.start()
    heartbeat_service.start()

    def signal_handler(sig, frame):
        logger.info("Received termination signal. Stopping Clogs Agent...")
        heartbeat_service.stop()
        discovery_service.stop()
        log_collector.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Handled by signal_handler or here if signal not caught
        logger.info("Stopping Clogs Agent...")
        heartbeat_service.stop()
        discovery_service.stop()
        log_collector.stop()
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        heartbeat_service.stop()
        discovery_service.stop()
        log_collector.stop()

if __name__ == "__main__":
    main()
