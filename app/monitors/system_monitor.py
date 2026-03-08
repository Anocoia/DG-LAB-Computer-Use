"""系统资源监控 - CPU/内存/网络/磁盘"""

import asyncio
import logging
import time

import psutil
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class SystemMonitor(QObject):
    """Monitors CPU, memory, network, and disk I/O at a configurable interval."""

    cpu_updated = pyqtSignal(float)        # CPU percentage 0-100
    memory_updated = pyqtSignal(float)     # Memory percentage 0-100
    network_updated = pyqtSignal(float, float)  # upload bytes/s, download bytes/s
    disk_updated = pyqtSignal(float)       # Disk IO percentage 0-100

    def __init__(self, interval: float = 2.0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False

        # Snapshot for computing network delta
        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.monotonic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the polling loop as an asyncio task."""
        if self._running:
            return
        self._running = True
        # Reset the network baseline so the first delta is accurate
        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.monotonic()
        self._task = asyncio.ensure_future(self._poll_loop())
        logger.info("SystemMonitor 已启动 (间隔=%.1fs)", self._interval)

    def stop(self) -> None:
        """Cancel the polling task."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("SystemMonitor 已停止")

    def set_interval(self, seconds: float) -> None:
        """Change the polling interval (takes effect on the next cycle)."""
        if seconds <= 0:
            raise ValueError("Interval must be positive")
        self._interval = seconds

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                self._collect()
            except Exception:
                logger.exception("系统资源采集异常")
            await asyncio.sleep(self._interval)

    def _collect(self) -> None:
        # --- CPU ---
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_updated.emit(float(cpu_percent))

        # --- Memory ---
        mem = psutil.virtual_memory()
        self.memory_updated.emit(float(mem.percent))

        # --- Network (bytes / second) ---
        now = time.monotonic()
        net = psutil.net_io_counters()
        dt = now - self._last_net_time
        if dt > 0:
            upload_speed = (net.bytes_sent - self._last_net.bytes_sent) / dt
            download_speed = (net.bytes_recv - self._last_net.bytes_recv) / dt
        else:
            upload_speed = 0.0
            download_speed = 0.0
        self._last_net = net
        self._last_net_time = now
        self.network_updated.emit(upload_speed, download_speed)

        # --- Disk IO ---
        # disk_io_counters can return None on some systems
        counters = psutil.disk_io_counters()
        if counters is not None:
            # Use the weighted time percentage as a rough activity metric.
            # psutil does not expose a direct "disk busy %" across platforms,
            # so we fall back to a heuristic: read_time + write_time delta
            # normalised against the poll interval.
            # A simpler cross-platform approach: report a 0-100 value
            # derived from the ratio of busy milliseconds to wall-clock ms.
            # We store previous counters for the delta.
            if not hasattr(self, "_last_disk"):
                self._last_disk = counters
                self._last_disk_time = now
                self.disk_updated.emit(0.0)
                return

            disk_dt = now - self._last_disk_time
            if disk_dt > 0:
                busy_ms = (
                    (counters.read_time - self._last_disk.read_time)
                    + (counters.write_time - self._last_disk.write_time)
                )
                # busy_ms is total across all disks; clamp to 0-100
                disk_pct = min(busy_ms / (disk_dt * 1000) * 100, 100.0)
            else:
                disk_pct = 0.0

            self._last_disk = counters
            self._last_disk_time = now
            self.disk_updated.emit(float(disk_pct))
        else:
            self.disk_updated.emit(0.0)
