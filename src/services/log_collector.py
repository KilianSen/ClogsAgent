import threading
import time
import queue
import logging
from docker.models.containers import Container
from src.api import APIClient
from src.model.api import Log, MultiContainerLogTransfer, MultilineLogTransfer

logger = logging.getLogger(__name__)

class LogCollector:
    def __init__(self, api_client: APIClient, agent_id: str):
        self.api_client = api_client
        self.agent_id = agent_id
        self.threads = {}
        self.stop_events = {}
        self.log_queue = queue.Queue()
        self.running = False
        self.sender_thread = None
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.sender_thread = threading.Thread(target=self._log_sender_loop)
        self.sender_thread.daemon = True
        self.sender_thread.start()

    def stop(self):
        with self.lock:
            self.running = False
            for stop_event in self.stop_events.values():
                stop_event.set()
        if self.sender_thread:
            self.sender_thread.join()

    def update_monitored_containers(self, containers: list[Container]):
        with self.lock:
            if not self.running:
                return
            current_ids = set(self.threads.keys())
            new_ids = set(c.id for c in containers)

            # Stop monitoring removed containers
            for container_id in current_ids - new_ids:
                self._stop_collecting(container_id)

            # Start monitoring new containers
            for container in containers:
                if container.id not in self.threads:
                    self._start_collecting(container)

    def _start_collecting(self, container: Container):
        logger.info(f"Starting log collection for container {container.name} ({container.id[:12]})")
        stop_event = threading.Event()
        t = threading.Thread(target=self._stream_logs, args=(container, stop_event))
        t.daemon = True
        t.start()
        self.threads[container.id] = t
        self.stop_events[container.id] = stop_event

    def _stop_collecting(self, container_id: str):
        logger.info(f"Stopping log collection for container {container_id[:12]}")
        if container_id in self.stop_events:
            self.stop_events[container_id].set()
            del self.stop_events[container_id]
            del self.threads[container_id]

    def _stream_logs(self, container: Container, stop_event: threading.Event):
        try:
            # tail='0' to only get new logs, follow=True to stream
            # timestamps=True to get timestamp from docker
            logs = container.logs(stream=True, follow=True, tail=0, timestamps=True)
            for line in logs:
                if stop_event.is_set():
                    break

                try:
                    line_str = line.decode('utf-8')
                    # Docker log format with timestamps: "2023-10-27T10:00:00.000000000Z log message"
                    parts = line_str.split(' ', 1)
                    if len(parts) == 2:
                        timestamp_str, log_content = parts

                        log_message = Log(
                            container_id=container.id,
                            timestamp=time.time_ns(), # Using current time as parsing docker timestamp is complex
                            level="INFO", # Defaulting to INFO
                            message=log_content.strip()
                        )
                        self.log_queue.put(log_message)
                except Exception as e:
                    logger.error(f"Error parsing log line: {e}")

        except Exception as e:
            # This happens when container dies or is stopped
            logger.debug(f"Stream ended for {container.name}: {e}")
        finally:
            pass

    def _log_sender_loop(self):
        batch = []
        while self.running:
            try:
                # Collect logs for a batch
                try:
                    while len(batch) < 100:
                        log = self.log_queue.get(timeout=1)
                        batch.append(log)
                except queue.Empty:
                    pass

                if batch:
                    # Group by container
                    logs_by_container = {}
                    for log in batch:
                        if log.container_id not in logs_by_container:
                            logs_by_container[log.container_id] = []
                        logs_by_container[log.container_id].append(log)

                    container_logs_list = []
                    for container_id, logs in logs_by_container.items():
                        container_logs_list.append(MultilineLogTransfer(
                            container_id=container_id,
                            logs=logs
                        ))

                    transfer = MultiContainerLogTransfer(
                        agent_id=self.agent_id,
                        container_logs=container_logs_list
                    )

                    if self.api_client.send_logs(self.agent_id, transfer):
                        batch = []
                    else:
                        logger.warning("Failed to send logs, dropping batch")
                        batch = []
            except Exception as e:
                logger.error(f"Error in log sender loop: {e}")
                time.sleep(5)
