import os

class Config:
    BACKEND_URL = os.getenv("CLOGS_BACKEND_URL", "http://localhost:8000")
    HEARTBEAT_INTERVAL = int(os.getenv("CLOGS_AGENT_HEARTBEAT_INTERVAL", "30"))
    DISCOVERY_INTERVAL = int(os.getenv("CLOGS_AGENT_DISCOVERY_INTERVAL", "60"))
    LOG_LEVEL = os.getenv("CLOGS_AGENT_LOG_LEVEL", os.getenv("CLOGS_LOG_LEVEL", "INFO"))
    API_KEY = os.getenv("CLOGS_AGENT_API_KEY", "")
    MONITORING_TAG = os.getenv("CLOGS_AGENTS_MONITORING_TAG", "clogs.monitoring.enabled=true")
