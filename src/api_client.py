import requests
import logging
from src.config import Config
from src.model.api import Heartbeat, LogMessage

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.base_url = Config.BACKEND_URL
        self.session = requests.Session()

    def send_heartbeat(self, heartbeat: Heartbeat):
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/heartbeat",
                data=heartbeat.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.debug("Heartbeat sent successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send heartbeat: {e}")

    def send_logs(self, logs: list[LogMessage]):
        if not logs:
            return
        try:
            # Assuming the backend accepts a list of logs
            payload = [log.model_dump() for log in logs]
            response = self.session.post(
                f"{self.base_url}/api/agent/logs",
                json=payload
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send logs: {e}")

