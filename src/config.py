import os

class Config:
    AGENT_ID_FILE = os.path.join(os.getenv('CLOGS_AGENT_DATA_DIR', '.'), 'agent_id.dat')
    BACKEND_URL = os.getenv("CLOGS_BACKEND_URL", "http://localhost:8000")
    HEARTBEAT_INTERVAL = int(os.getenv("CLOGS_AGENT_HEARTBEAT_INTERVAL", "5"))
    DISCOVERY_INTERVAL = int(os.getenv("CLOGS_AGENT_DISCOVERY_INTERVAL", "1"))
    LOG_LEVEL = os.getenv("CLOGS_AGENT_LOG_LEVEL", os.getenv("CLOGS_LOG_LEVEL", "INFO"))
    API_KEY = os.getenv("CLOGS_AGENT_API_KEY", "")
    MONITORING_TAG = os.getenv("CLOGS_AGENTS_MONITORING_TAG", "clogs.monitoring.enabled=true")

def config_load_id(path: str = Config.AGENT_ID_FILE) -> str | None:
    if os.path.exists(path):
        with open(path, 'r') as f:
            existing_id = f.read().strip()
            if existing_id:
                return existing_id
    return None

def config_save_id(agent_id: str, path: str = Config.AGENT_ID_FILE):
    with open(path, 'w') as f:
        f.write(agent_id)