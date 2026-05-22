import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

SUPERVISOR_INTERVAL = 10
BACKOFF_INITIAL = 10
BACKOFF_MAX = 300
FAILURE_WARN_THRESHOLD = 3


class ThreadManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._factories: dict[str, Callable] = {}
        self._instances: dict[str, threading.Thread | None] = {}
        self._backoff: dict[str, int] = {}
        self._failures: dict[str, int] = {}
        self._next_restart: dict[str, float] = {}
        self._supervisor: threading.Thread | None = None

    def register(self, factory: Callable) -> None:
        instance = factory()
        name = instance.name
        self._factories[name] = factory
        self._instances[name] = instance
        self._backoff[name] = BACKOFF_INITIAL
        self._failures[name] = 0
        self._next_restart[name] = 0.0

    def start_all(self) -> None:
        for name, instance in self._instances.items():
            instance.daemon = True
            instance.start()
            logger.info(f"Started thread: {name}")

    def start(self, name: str) -> dict:
        with self._lock:
            if name not in self._factories:
                return {"status": "not_found"}
            instance = self._instances.get(name)
            if instance is not None and instance.is_alive():
                return {"status": "already_running"}
            self._spawn(name)
            return {"status": "started"}

    def _spawn(self, name: str) -> None:
        """Create and start a new instance. Must be called under self._lock."""
        instance = self._factories[name]()
        instance.daemon = True
        instance.start()
        self._instances[name] = instance
        logger.warning(f"Thread {name} spawned (restart #{self._failures[name]})")

    def list(self) -> list[dict]:
        result = []
        with self._lock:
            for name, instance in self._instances.items():
                result.append({
                    "name": name,
                    "status": getattr(instance, "status", "unknown") if instance else "stopped",
                    "is_alive": instance.is_alive() if instance else False,
                })
            if self._supervisor:
                result.append({
                    "name": "Supervisor",
                    "status": "running" if self._supervisor.is_alive() else "stopped",
                    "is_alive": self._supervisor.is_alive(),
                })
        return result

    def _supervisor_loop(self) -> None:
        logger.info("Supervisor thread running")
        while True:
            try:
                now = time.monotonic()
                with self._lock:
                    for name, instance in self._instances.items():
                        if instance is not None and instance.is_alive():
                            self._backoff[name] = BACKOFF_INITIAL
                            self._failures[name] = 0
                            continue
                        if now < self._next_restart[name]:
                            continue
                        self._failures[name] += 1
                        fail_count = self._failures[name]
                        if fail_count >= FAILURE_WARN_THRESHOLD:
                            logger.error(
                                f"Thread {name} has failed {fail_count} time(s) and keeps dying. "
                                "Check logs for errors."
                            )
                        else:
                            logger.warning(f"Thread {name} is dead, restarting (attempt {fail_count})")
                        self._spawn(name)
                        backoff = min(self._backoff[name] * 2, BACKOFF_MAX)
                        self._backoff[name] = backoff
                        self._next_restart[name] = now + backoff
            except Exception as e:
                logger.error(f"Error in supervisor loop: {e}")
            time.sleep(SUPERVISOR_INTERVAL)

    def start_supervisor(self) -> None:
        self._supervisor = threading.Thread(
            target=self._supervisor_loop,
            name="Supervisor",
            daemon=True,
        )
        self._supervisor.start()
        logger.info("Supervisor thread started")
