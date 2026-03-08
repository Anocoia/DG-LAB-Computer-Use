"""闲置惩罚模块"""

import asyncio
import logging
import time
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class IdleModule(QObject):
    """Increases strength when the user is idle; resets on input activity."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b

    MODULE_NAME = "idle"

    def __init__(self, input_monitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = input_monitor

        self.enabled: bool = False
        self.channel: str = "AB"

        # Settings
        self.idle_threshold: float = 30.0       # seconds before punishment (5 ~ 300)
        self.growth_mode: str = "linear"        # "linear" or "exponential"
        self.max_strength: float = 1.0          # 0.0 ~ 1.0
        self.recovery_mode: str = "instant"     # "instant" or "gradual"
        self.recovery_speed: float = 3.0        # seconds for full gradual recovery

        # Internal state
        self._last_input_time: float = time.monotonic()
        self._current_strength: float = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Connect to all input signals to detect activity
        self._monitor.mouse_click.connect(self._on_activity)
        self._monitor.mouse_move.connect(self._on_activity_speed)
        self._monitor.mouse_scroll.connect(self._on_activity_delta)
        self._monitor.key_press.connect(self._on_activity_key)

    # ------------------------------------------------------------------
    # Activity detection (any input resets the idle timer)
    # ------------------------------------------------------------------

    def _touch(self) -> None:
        self._last_input_time = time.monotonic()

    def _on_activity(self, *_args) -> None:
        self._touch()

    def _on_activity_speed(self, _speed: float) -> None:
        self._touch()

    def _on_activity_delta(self, _delta: int) -> None:
        self._touch()

    def _on_activity_key(self, _key: str) -> None:
        self._touch()

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _compute(self, dt: float) -> float:
        """Return the target strength given the current idle time."""
        now = time.monotonic()
        idle_secs = now - self._last_input_time
        threshold = max(5.0, min(300.0, self.idle_threshold))

        if idle_secs <= threshold:
            # User is active -- recover
            if self.recovery_mode == "gradual" and self._current_strength > 0.0:
                # Decrease gradually over recovery_speed seconds
                recovery_rate = self.max_strength / max(0.1, self.recovery_speed)
                self._current_strength = max(
                    0.0, self._current_strength - recovery_rate * dt
                )
            else:
                # Instant recovery
                self._current_strength = 0.0
            return self._current_strength

        # User is idle past threshold -- grow strength
        elapsed_past = idle_secs - threshold
        if self.growth_mode == "exponential":
            # Exponential: reaches max_strength at roughly threshold seconds of
            # idle time past the threshold (t^2 normalised).
            raw = (elapsed_past / max(1.0, threshold)) ** 2
        else:
            # Linear: reaches max_strength after threshold seconds past idle.
            raw = elapsed_past / max(1.0, threshold)

        target = min(self.max_strength, raw * self.max_strength)
        self._current_strength = target
        return self._current_strength

    def _emit(self, dt: float) -> None:
        if not self.enabled:
            return
        strength = self._compute(dt)
        value_a = 0.0
        value_b = 0.0
        if self.channel in ("A", "AB"):
            value_a = strength
        if self.channel in ("B", "AB"):
            value_b = strength
        if strength > 0.0:
            logger.debug("闲置惩罚输出: 强度=%.3f 闲置时间=%.1f秒",
                         strength, time.monotonic() - self._last_input_time)
        self.strength_output.emit(self.MODULE_NAME, value_a, value_b)

    # ------------------------------------------------------------------
    # Async loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        interval = 0.1  # 10 Hz
        while self._running:
            self._emit(interval)
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_input_time = time.monotonic()
        self._current_strength = 0.0
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("闲置惩罚模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._current_strength = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("闲置惩罚模块已停止")
