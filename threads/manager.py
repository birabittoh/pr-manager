import logging
import threading
import time
from typing import Callable

from modules import config
from modules.notify import notify_admin

logger = logging.getLogger(__name__)

SUPERVISOR_INTERVAL = 10
BACKOFF_INITIAL = 10
BACKOFF_MAX = 300
FAILURE_WARN_THRESHOLD = 3
# Stop restarting a thread after this many consecutive failures: at this point the
# error is almost certainly unrecoverable (bad credentials, changed login flow, ...)
# and blindly respawning only wastes resources and spams retries.
FAILURE_GIVEUP_THRESHOLD = 10


class ThreadManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._factories: dict[str, Callable] = {}
        self._instances: dict[str, threading.Thread | None] = {}
        self._backoff: dict[str, int] = {}
        self._failures: dict[str, int] = {}
        self._next_restart: dict[str, float] = {}
        self._gaveup: set[str] = set()
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
            # A manual start re-enables a thread the supervisor had given up on.
            self._gaveup.discard(name)
            self._failures[name] = 0
            self._backoff[name] = BACKOFF_INITIAL
            self._next_restart[name] = 0.0
            self._spawn(name)
            return {"status": "started"}

    def _spawn(self, name: str) -> None:
        """Create and start a new instance. Must be called under self._lock."""
        instance = self._factories[name]()
        instance.daemon = True
        instance.start()
        self._instances[name] = instance
        logger.warning(f"Thread {name} spawned (restart #{self._failures[name]})")

    @staticmethod
    def _heartbeat_age(instance: threading.Thread | None) -> float | None:
        """Seconds since the thread last reported a heartbeat, or None if unsupported."""
        last = getattr(instance, "last_heartbeat", None)
        if last is None:
            return None
        return time.monotonic() - last

    def list(self) -> list[dict]:
        result = []
        with self._lock:
            for name, instance in self._instances.items():
                status = getattr(instance, "status", "unknown") if instance else "stopped"
                age = self._heartbeat_age(instance)
                is_alive = instance.is_alive() if instance else False
                if name in self._gaveup:
                    status = "failed"
                elif is_alive and age is not None and age > config.HEARTBEAT_TIMEOUT:
                    status = "stuck"
                result.append({
                    "name": name,
                    "status": status,
                    "is_alive": is_alive,
                    "heartbeat_age": round(age, 1) if age is not None else None,
                })
            if self._supervisor:
                result.append({
                    "name": "Supervisor",
                    "status": "running" if self._supervisor.is_alive() else "stopped",
                    "is_alive": self._supervisor.is_alive(),
                    "heartbeat_age": None,
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
                            age = self._heartbeat_age(instance)
                            if age is not None and age > config.HEARTBEAT_TIMEOUT:
                                logger.error(
                                    f"Thread {name} appears stuck: no heartbeat for "
                                    f"{age:.0f}s (threshold {config.HEARTBEAT_TIMEOUT}s). "
                                    "It is alive but not making progress."
                                )
                                notify_admin(
                                    f"Thread '{name}' appears stuck (no heartbeat for "
                                    f"{age:.0f}s). It is alive but not making progress and may "
                                    "need a service restart.",
                                    dedupe_key=f"stuck:{name}",
                                )
                            self._backoff[name] = BACKOFF_INITIAL
                            self._failures[name] = 0
                            continue
                        # Thread is dead. Stop retrying once we've given up on it.
                        if name in self._gaveup:
                            continue
                        if now < self._next_restart[name]:
                            continue
                        self._failures[name] += 1
                        fail_count = self._failures[name]
                        if fail_count >= FAILURE_GIVEUP_THRESHOLD:
                            self._gaveup.add(name)
                            logger.critical(
                                f"Thread {name} has failed {fail_count} time(s); giving up "
                                "and no longer restarting it. Manual intervention required."
                            )
                            notify_admin(
                                f"Thread '{name}' failed {fail_count} times in a row and looks "
                                "unrecoverable. The supervisor has stopped restarting it — manual "
                                "intervention is required (fix the cause, then restart the thread "
                                "or the service).",
                                dedupe_key=f"gaveup:{name}",
                            )
                            continue
                        if fail_count >= FAILURE_WARN_THRESHOLD:
                            logger.error(
                                f"Thread {name} has failed {fail_count} time(s) and keeps dying. "
                                "Check logs for errors."
                            )
                            notify_admin(
                                f"Thread '{name}' keeps crashing ({fail_count} failures) and "
                                "is being restarted repeatedly. Check the logs — manual "
                                "intervention is likely needed.",
                                dedupe_key=f"dying:{name}",
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
