"""系统资源→强度模块"""

import asyncio
import logging
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class _SubSource:
    """Internal descriptor for a single system metric sub-source."""

    __slots__ = ("name", "enabled", "channel", "curve", "weight", "value")

    def __init__(self, name: str) -> None:
        self.name = name
        self.enabled: bool = True
        self.channel: str = "AB"       # "A", "B", or "AB"
        self.curve: str = "linear"     # "linear", "exponential", "step"
        self.weight: float = 1.0       # 0.0 ~ 1.0
        self.value: float = 0.0        # raw normalised 0.0 ~ 1.0


def _apply_curve(value: float, curve: str) -> float:
    """Map a normalised value through the selected curve function."""
    v = max(0.0, min(1.0, value))
    if curve == "exponential":
        return v * v
    if curve == "step":
        if v < 0.3:
            return 0.0
        if v < 0.7:
            return 0.5
        return 1.0
    # linear (default)
    return v


class SystemModule(QObject):
    """Maps CPU / memory / network / disk metrics to output strength."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b

    MODULE_NAME = "system"

    # Upper bound used to normalise raw network speed (bytes/s) to 0.0-1.0.
    # 100 MB/s feels like a sensible ceiling for most desktop NICs.
    NETWORK_SPEED_CEIL: float = 100_000_000.0

    def __init__(self, system_monitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = system_monitor

        self.enabled: bool = False
        self.channel: str = "AB"  # module-level default (overridden per sub-source)

        # Sub-sources
        self._cpu = _SubSource("cpu")
        self._mem = _SubSource("mem")
        self._net = _SubSource("net")
        self._disk = _SubSource("disk")
        self._sub_sources = [self._cpu, self._mem, self._net, self._disk]

        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Connect monitor signals
        self._monitor.cpu_updated.connect(self._on_cpu)
        self._monitor.memory_updated.connect(self._on_mem)
        self._monitor.network_updated.connect(self._on_net)
        self._monitor.disk_updated.connect(self._on_disk)

    # ------------------------------------------------------------------
    # Properties for sub-source configuration
    # ------------------------------------------------------------------

    @property
    def cpu(self) -> _SubSource:
        return self._cpu

    @property
    def mem(self) -> _SubSource:
        return self._mem

    @property
    def net(self) -> _SubSource:
        return self._net

    @property
    def disk(self) -> _SubSource:
        return self._disk

    # ------------------------------------------------------------------
    # Monitor signal handlers
    # ------------------------------------------------------------------

    def _on_cpu(self, percent: float) -> None:
        self._cpu.value = percent / 100.0

    def _on_mem(self, percent: float) -> None:
        self._mem.value = percent / 100.0

    def _on_net(self, upload: float, download: float) -> None:
        total_speed = upload + download
        self._net.value = min(total_speed / self.NETWORK_SPEED_CEIL, 1.0)

    def _on_disk(self, percent: float) -> None:
        self._disk.value = percent / 100.0

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _compute(self) -> tuple[float, float]:
        """Compute combined output using weighted-max of enabled sub-sources."""
        value_a = 0.0
        value_b = 0.0

        for src in self._sub_sources:
            if not src.enabled:
                continue

            curved = _apply_curve(src.value, src.curve) * src.weight

            if src.channel in ("A", "AB"):
                value_a = max(value_a, curved)
            if src.channel in ("B", "AB"):
                value_b = max(value_b, curved)

        return (max(0.0, min(1.0, value_a)), max(0.0, min(1.0, value_b)))

    def _emit(self) -> None:
        if not self.enabled:
            return
        value_a, value_b = self._compute()
        logger.debug("系统资源输出: A=%.3f B=%.3f", value_a, value_b)
        self.strength_output.emit(self.MODULE_NAME, value_a, value_b)

    # ------------------------------------------------------------------
    # Async loop (emits at ~10 Hz to match StrengthManager)
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            self._emit()
            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("系统资源模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        # Reset sub-source values
        for src in self._sub_sources:
            src.value = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("系统资源模块已停止")
