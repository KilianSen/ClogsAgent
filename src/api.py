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

    def register_agent(self, agent: Agent) -> str | None:
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/",
                data=agent.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            agent.id = response.content.decode("utf-8")

            logger.info("Agent registered successfully")
            return response.json() # Returns agent_id
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register agent: {e}")
            return None

    def send_heartbeat(self, agent_id: str) -> bool:
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/{agent_id}/heartbeat",
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            logger.debug("Heartbeat sent successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def register_context(self, agent_id: str, context: Context) -> int | None:
        try:
            response = self.session.put(
                f"{self.base_url}/api/agent/{agent_id}/context/",
                data=context.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register context: {e}")
            return None

    def register_container(self, agent_id: str, container: Container) -> str | None:
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/{agent_id}/container",
                data=container.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 409:
                return container.id
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register container: {e}")
            return None

    def update_container_status(self, agent_id: str, container_id: str, status: str):
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/{agent_id}/container/{container_id}/status",
                params={"status": status},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update container status: {e}")

    def delete_container(self, agent_id: str, container_id: str):
        try:
            response = self.session.delete(
                f"{self.base_url}/api/agent/{agent_id}/container/{container_id}/"
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete container: {e}")

    def send_logs(self, agent_id: str, logs: MultiContainerLogTransfer) -> bool:
        if not logs.container_logs:
            return True
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/{agent_id}/logs",
                data=logs.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send logs: {e}")
            return False
