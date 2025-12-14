import threading
import time
import queue
import logging
from docker.models.containers import Container
from src.api_client import APIClient
from src.model.api import LogMessage

logger = logging.getLogger(__name__)

class LogCollector:
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
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

                        log_message = LogMessage(
                            container_id=container.id,
                            log=log_content.strip(),
                            stream='stdout', # Defaulting to stdout for now
                            timestamp=time.time()
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
        last_send = time.time()

        while self.running:
            try:
                # Wait for logs with timeout to allow batch sending
                log = self.log_queue.get(timeout=1.0)
                batch.append(log)
            except queue.Empty:
                pass

            current_time = time.time()
            if batch and (len(batch) >= 100 or current_time - last_send >= 5.0):
                if self.api_client.send_logs(batch):
                    batch = []
                    last_send = current_time
                else:
                    # If sending fails, keep the batch and retry later
                    # Sleep briefly to avoid tight loop if backend is down
                    time.sleep(2)
                    # If batch gets too large, we might need to drop old logs or just keep growing until OOM
                    # For now, let's cap it at 1000 to prevent memory issues
                    if len(batch) > 1000:
                        logger.warning("Log batch too large, dropping oldest 100 logs")
                        batch = batch[100:]
