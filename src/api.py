import requests
import logging
from src.config import Config
from src.model.api import *

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.base_url = Config.BACKEND_URL
        self.session = requests.Session()
        if Config.API_KEY:
            self.session.headers.update({"X-API-Key": Config.API_KEY})

    def register_agent(self, registration: AgentRegistration):
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/register",
                data=registration.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info("Agent registered successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register agent: {e}")
            # We might want to retry or fail hard here depending on requirements
            # For now, we log and continue, assuming the backend might handle unregistered heartbeats or we retry later

    def send_heartbeat(self, heartbeat: Heartbeat) -> bool:
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/heartbeat",
                data=heartbeat.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.debug("Heartbeat sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def send_state(self, state: AgentState):
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/state",
                data=state.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.info("Agent state sent successfully")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send agent state: {e}")

    def send_logs(self, logs: list[LogMessage], agent_id: str = None) -> bool:
        if not logs:
            return True
        try:
            # Assuming the backend accepts a list of logs
            payload = [log.model_dump() for log in logs]
            url = f"{self.base_url}/api/agent/logs"
            if agent_id:
                url += f"?agent_id={agent_id}"

            response = self.session.post(
                url,
                json=payload
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send logs: {e}")
            return False
