from typing import Optional

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

    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent by its ID.
        Note: This is usually not called by the agent itself.
        :param agent_id: ID of the agent to delete
        :return: None
        """
        try:
            response = self.session.delete(
                f"{self.base_url}/api/agent/{agent_id}/"
            )
            response.raise_for_status()
            logger.info("Agent deleted successfully")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete agent: {e}")
            return False

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


    def update_container_status(self, agent_id: str, container_id: str, status: str, since: int) -> bool:
        try:
            response = self.session.post(
                f"{self.base_url}/api/agent/{agent_id}/container/{container_id}/status",
                params={"status": status, "since": since},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update container status: {e}")
            return False

    def update_container_state(self, agent_id: str, container_id: str, state: Container) -> bool:
        try:
            response = self.session.put(
                f"{self.base_url}/api/agent/{agent_id}/container/{container_id}/",
                data=state.model_dump_json(),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update container state: {e}")
            return False

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

    def delete_container(self, agent_id: str, container_id: str) -> bool:
        try:
            response = self.session.delete(
                f"{self.base_url}/api/agent/{agent_id}/container/{container_id}/"
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete container: {e}")
            return False


    def register_context(self, agent_id: str, context: Context) -> str | None:
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

    def delete_context(self, agent_id: str, context_id: int) -> bool:
        try:
            response = self.session.delete(
                f"{self.base_url}/api/agent/{agent_id}/context/{context_id}/"
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to delete context: {e}")
            return False


    def upload_agent_logs(self, agent_id: str, logs: MultiContainerLogTransfer) -> bool:
        """
        Upload logs for the agent across multiple containers.
        :param agent_id: ID of the agent
        :param logs: Logs to upload (MultiContainerLogTransfer)
        :return: True if upload was successful, False otherwise
        """
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

    def upload_container_logs(self, agent_id: str, container_logs: MultilineLogTransfer | Log) -> bool:
        """
        Upload logs for a specific container.
        :param agent_id: ID of the agent
        :param container_logs: Logs to upload (MultilineLogTransfer or Log)
        :return: True if upload was successful, False otherwise
        :raise: ValueError: If the log type is invalid
        """

        if isinstance(container_logs, MultilineLogTransfer):
            if not container_logs.logs:
                return True
            try:
                response = self.session.post(
                    f"/api/agent/{agent_id}/container/{container_logs.container_id}/logs",
                    data=container_logs.model_dump_json(),
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return True
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send container logs: {e}")
                return False
        elif isinstance(container_logs, Log):
            try:
                response = self.session.post(
                    f"/api/agent/{agent_id}/container/{container_logs.container_id}/logs",
                    data=container_logs.model_dump_json(),
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return True
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to send container log: {e}")
                return False
        raise ValueError("Invalid log type for upload_container_logs")

    def upload_logs(self, agent_id: str, logs: MultiContainerLogTransfer | MultilineLogTransfer | Log) -> bool:
        """
        Smart log uploader that routes to the correct upload method based on log type.
        :param agent_id: ID of the agent
        :param logs: Logs to upload
        :return: True if upload was successful, False otherwise
        :raise: ValueError: If the log type is invalid
        """

        if isinstance(logs, MultiContainerLogTransfer):
            return self.upload_agent_logs(agent_id, logs)
        elif isinstance(logs, MultilineLogTransfer) or isinstance(logs, Log):
            return self.upload_container_logs(agent_id, logs)
        raise ValueError("Invalid log type for upload_logs")


    def get_agent(self, agent_id: str) -> Agent | None:
        try:
            response = self.session.get(
                f"{self.base_url}/api/agent/{agent_id}/",
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            agent_data = response.json()
            return Agent.model_validate(agent_data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get agent: {e}")
            return None

    def get_contexts(self, agent_id: str) -> list[Context]:
        try:
            response = self.session.get(
                f"{self.base_url}/api/agent/{agent_id}/context/",
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            contexts_data = response.json()
            return [Context.model_validate(ctx) for ctx in contexts_data]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get contexts: {e}")
            return []

    def get_containers(self, agent_id: str, context_id: Optional[int] = None) -> list[Container]:
        try:
            response = self.session.get(
                f"{self.base_url}/api/agent/{agent_id}/container/",
                params={"context_id": context_id} if context_id is not None else {},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            containers_data = response.json()
            return [Container.model_validate(ctn) for ctn in containers_data]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get containers: {e}")
            return []