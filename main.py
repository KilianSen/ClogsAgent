import time
import logging
import socket
import signal
import sys
from src.config import Config
from src.model.api import AgentRegistration
from src.api import APIClient
from src.services.log_collector import LogCollector
from src.services.agent_services import DiscoveryService, HeartbeatService

# Configure logging
logging.basicConfig(level=Config.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting Clogs Agent...")

    agent_id = socket.gethostname()
    start_time = time.time()

    api_client = APIClient()

    # Register Agent
    registration = AgentRegistration(
        agent_id=agent_id,
        hostname=socket.gethostname(),
        heartbeat_interval=Config.HEARTBEAT_INTERVAL,
        discovery_interval=Config.DISCOVERY_INTERVAL,
        started_at=start_time
    )
    api_client.register_agent(registration)

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
