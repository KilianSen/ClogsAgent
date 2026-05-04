import threading
import time
import sqlite3
import logging
import json
import os
from docker.models.containers import Container
from src.api import APIClient
from src.model.api import Log, MultiContainerLogTransfer, MultilineLogTransfer
from src.config import Config

logger = logging.getLogger(__name__)

class LogCollector:
    def __init__(self, api_client: APIClient, agent_id: str):
        self.api_client = api_client
        self.agent_id = agent_id
        self.threads = {}
        self.stop_events = {}
        self.running = False
        self.sender_thread = None
        self.lock = threading.Lock()
        
        # Initialize SQLite for persistent queuing
        self.db_path = os.path.join(os.path.dirname(Config.AGENT_ID_FILE), 'logs.db')
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL')
            # Set a busy timeout (5 seconds) to wait for locks to clear
            conn.execute('PRAGMA busy_timeout=5000')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS pending_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT,
                    timestamp INTEGER,
                    level TEXT,
                    message TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_pending_logs_container_id ON pending_logs(container_id)')

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
        logger.info("LogCollector stopped.")

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
            
            # Open its own connection for this thread
            conn = sqlite3.connect(self.db_path)
            
            from datetime import datetime
            
            buffer = []
            last_flush = time.time()
            
            for line in logs:
                if stop_event.is_set():
                    break

                try:
                    line_str = line.decode('utf-8')
                    # Docker log format with timestamps: "2023-10-27T10:00:00.000000000Z log message"
                    parts = line_str.split(' ', 1)
                    if len(parts) == 2:
                        timestamp_str, log_content = parts
                        
                        try:
                            # Handle Docker RFC3339 timestamps (e.g., 2023-10-27T10:00:00.000000000Z)
                            # Python's fromisoformat is faster but may need minor tweaking for nanoseconds/Z
                            ts_fixed = timestamp_str.replace('Z', '+00:00')
                            # Docker often provides more than 6 digits for microseconds, truncate to 6
                            if '.' in ts_fixed:
                                base, rest = ts_fixed.split('.', 1)
                                micros = rest[:6]
                                offset = rest[rest.find('+'):] if '+' in rest else rest[rest.find('-'):] if '-' in rest else ''
                                ts_fixed = f"{base}.{micros}{offset}"
                            
                            dt = datetime.fromisoformat(ts_fixed)
                            ts_ns = int(dt.timestamp() * 10**9)
                        except Exception as te:
                            logger.debug(f"Failed to parse docker timestamp '{timestamp_str}', using fallback: {te}")
                            ts_ns = time.time_ns()

                        # Basic log level detection
                        level = "INFO"
                        lower_msg = log_content.lower()
                        if any(k in lower_msg for k in ["error", "crit", "fatal", "fail"]):
                            level = "ERROR"
                        elif any(k in lower_msg for k in ["warn", "warning"]):
                            level = "WARNING"
                        elif "debug" in lower_msg:
                            level = "DEBUG"

                        buffer.append((container.id, ts_ns, level, log_content.strip()))
                        
                        # Flush if buffer is large or time has passed
                        if len(buffer) >= 50 or (time.time() - last_flush > 1.0):
                            conn.executemany(
                                'INSERT INTO pending_logs (container_id, timestamp, level, message) VALUES (?, ?, ?, ?)',
                                buffer
                            )
                            conn.commit()
                            buffer = []
                            last_flush = time.time()
                except Exception as e:
                    logger.error(f"Error parsing log line: {e}")
            
            if buffer:
                conn.executemany(
                    'INSERT INTO pending_logs (container_id, timestamp, level, message) VALUES (?, ?, ?, ?)',
                    buffer
                )
                conn.commit()
                
            conn.close()

        except Exception as e:
            # This happens when container dies or is stopped
            logger.debug(f"Stream ended for {container.name}: {e}")
        finally:
            pass

    def _log_sender_loop(self):
        last_retention_cleanup = 0
        while self.running:
            try:
                # Batch logs from SQLite
                with sqlite3.connect(self.db_path) as conn:
                    # Periodically prune old logs (Retention: 7 days)
                    current_time = time.time()
                    if current_time - last_retention_cleanup > 3600: # Every hour
                        retention_threshold = int((current_time - (7 * 24 * 3600)) * 10**9)
                        conn.execute('DELETE FROM pending_logs WHERE timestamp < ?', (retention_threshold,))
                        conn.commit()
                        last_retention_cleanup = current_time

                    cursor = conn.cursor()
                    cursor.execute('SELECT id, container_id, timestamp, level, message FROM pending_logs LIMIT 100')
                    rows = cursor.fetchall()
                    
                    if not rows:
                        time.sleep(1)
                        continue

                    ids = [r[0] for r in rows]
                    batch = [
                        Log(container_id=r[1], timestamp=r[2], level=r[3], message=r[4])
                        for r in rows
                    ]

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

                    if self.api_client.upload_logs(self.agent_id, transfer):
                        # Delete sent logs
                        conn.execute(f'DELETE FROM pending_logs WHERE id IN ({",".join(map(str, ids))})')
                        conn.commit()
                    else:
                        logger.warning("Failed to send logs, will retry next interval")
                        time.sleep(5) # Backoff
            except Exception as e:
                logger.error(f"Error in log sender loop: {e}")
                time.sleep(1)
