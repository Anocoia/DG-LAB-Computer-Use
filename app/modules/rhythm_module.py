"""打字节奏同步模块"""

import asyncio
import logging
import time
from collections import deque
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


# Keys that trigger an extra pulse
_SPECIAL_KEYS = frozenset({"enter", "return", "space", "backspace"})


class RhythmModule(QObject):
    """Synchronises strength output to typing rhythm and speed."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b
    waveform_request = pyqtSignal(str)                # dynamic waveform frequency hint

    MODULE_NAME = "rhythm"

    # Sliding window length (seconds) for measuring typing speed
    WINDOW_SIZE: float = 5.0

    # Typing speed that maps to 1.0 (keys per second)
    MAX_KEYS_PER_SEC: float = 12.0

    # Special-key pulse decay (seconds)
    SPECIAL_PULSE_DECAY: float = 0.4

    def __init__(self, input_monitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = input_monitor

        self.enabled: bool = False
        self.channel: str = "AB"

        # Settings
        self.base_strength: float = 0.1           # 0.0 ~ 1.0
        self.speed_multiplier: float = 1.0        # how much typing speed affects output
        self.special_key_strength: float = 0.6    # pulse strength for Enter/Space/Backspace
        self.sustained_bonus: float = 0.2         # extra strength after sustained typing
        self.sustained_threshold: float = 5.0     # seconds of continuous typing required

        # Internal state
        self._key_times: deque = deque()           # timestamps of recent keypresses
        self._sustained_start: Optional[float] = None  # when continuous typing began
        self._last_key_time: float = 0.0
        self._special_pulse: float = 0.0           # current special-key pulse level
        self._special_pulse_time: float = 0.0       # when the last special pulse fired

        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Connect to InputMonitor key events
        self._monitor.key_press.connect(self._on_key_press)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _on_key_press(self, key_name: str) -> None:
        now = time.monotonic()
        self._key_times.append(now)
        self._last_key_time = now

        # Track sustained typing
        # If there was a long gap (> 1.5s), reset the sustained timer
        if self._sustained_start is None:
            self._sustained_start = now
        else:
            if len(self._key_times) >= 2:
                prev = self._key_times[-2]
                if now - prev > 1.5:
                    self._sustained_start = now

        # Special key pulse
        if key_name.lower() in _SPECIAL_KEYS:
            self._special_pulse = self.special_key_strength
            self._special_pulse_time = now

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _compute(self) -> float:
        now = time.monotonic()

        # Prune old entries from the sliding window
        cutoff = now - self.WINDOW_SIZE
        while self._key_times and self._key_times[0] < cutoff:
            self._key_times.popleft()

        # Typing speed (keys per second)
        if len(self._key_times) >= 2:
            span = self._key_times[-1] - self._key_times[0]
            if span > 0:
                keys_per_sec = (len(self._key_times) - 1) / span
            else:
                keys_per_sec = 0.0
        else:
            keys_per_sec = 0.0

        # Speed-based strength
        speed_ratio = min(keys_per_sec / self.MAX_KEYS_PER_SEC, 1.0)
        speed_strength = speed_ratio * self.speed_multiplier

        # If no key was pressed recently (> 2s), fade out speed contribution
        if now - self._last_key_time > 2.0:
            speed_strength = 0.0
            self._sustained_start = None

        # Base + speed
        output = self.base_strength + speed_strength

        # Sustained typing bonus
        if (self._sustained_start is not None
                and now - self._sustained_start >= self.sustained_threshold
                and keys_per_sec > 1.0):
            output += self.sustained_bonus

        # Special key pulse (decaying)
        if self._special_pulse > 0.0:
            age = now - self._special_pulse_time
            if age < self.SPECIAL_PULSE_DECAY:
                decayed = self._special_pulse * (1.0 - age / self.SPECIAL_PULSE_DECAY)
                output = max(output, decayed)
            else:
                self._special_pulse = 0.0

        # If there has been no typing at all recently, just return 0
        if now - self._last_key_time > 3.0:
            output = 0.0

        return max(0.0, min(1.0, output))

    def _emit(self) -> None:
        if not self.enabled:
            return
        strength = self._compute()
        value_a = 0.0
        value_b = 0.0
        if self.channel in ("A", "AB"):
            value_a = strength
        if self.channel in ("B", "AB"):
            value_b = strength
        if strength > 0.0:
            logger.debug("打字节奏输出: 强度=%.3f", strength)
        self.strength_output.emit(self.MODULE_NAME, value_a, value_b)

        # Emit waveform frequency hint based on typing speed
        # Faster typing -> higher-frequency waveform suggestion
        if self._key_times and len(self._key_times) >= 2:
            span = self._key_times[-1] - self._key_times[0]
            if span > 0:
                kps = (len(self._key_times) - 1) / span
                if kps > 8.0:
                    self.waveform_request.emit("pulse")
                elif kps > 4.0:
                    self.waveform_request.emit("heartbeat")

    # ------------------------------------------------------------------
    # Async loop
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
        self._key_times.clear()
        self._sustained_start = None
        self._last_key_time = 0.0
        self._special_pulse = 0.0
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("打字节奏模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._key_times.clear()
        self._sustained_start = None
        self._special_pulse = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("打字节奏模块已停止")
