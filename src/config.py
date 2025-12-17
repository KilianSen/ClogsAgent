import os

class Config:
    AGENT_ID_FILE = os.path.join(os.getenv('CLOGS_AGENT_DATA_DIR', '.'), '.clogs/agent/id')
    BACKEND_URL = os.getenv("CLOGS_BACKEND_URL", "http://localhost:8000")
    HEARTBEAT_INTERVAL = int(os.getenv("CLOGS_AGENT_HEARTBEAT_INTERVAL", "5"))
    DISCOVERY_INTERVAL = int(os.getenv("CLOGS_AGENT_DISCOVERY_INTERVAL", "1"))
    LOG_LEVEL = os.getenv("CLOGS_AGENT_LOG_LEVEL", os.getenv("CLOGS_LOG_LEVEL", "DEBUG"))
    API_KEY = os.getenv("CLOGS_AGENT_API_KEY", "")
    MONITORING_TAG = os.getenv("CLOGS_AGENTS_MONITORING_TAG", "clogs.monitoring.enabled=true")

    @classmethod
    def _ensure_data_dir(cls):
        data_dir = os.path.dirname(cls.AGENT_ID_FILE)
        os.makedirs(data_dir, exist_ok=True)

    @classmethod
    def load_id(cls) -> str | None:
        cls._ensure_data_dir()
        if os.path.exists(cls.AGENT_ID_FILE):
            with open(cls.AGENT_ID_FILE, 'r') as f:
                existing_id = f.read().strip()
                if existing_id:
                    return existing_id
        return None

    @classmethod
    def save_id(cls, agent_id: str):
        cls._ensure_data_dir()
        with open(cls.AGENT_ID_FILE, 'w') as f:
            f.write(agent_id)