"""定时/随机输出模块"""

import asyncio
import logging
import random
import time
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from app.waveform import PRESET_WAVEFORMS

logger = logging.getLogger(__name__)


class TimerModule(QObject):
    """Periodically fires strength pulses at fixed or random intervals."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b
    waveform_request = pyqtSignal(str)                # waveform preset name

    MODULE_NAME = "timer"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self.enabled: bool = False
        self.channel: str = "AB"

        # Interval settings
        self.mode: str = "fixed"               # "fixed" or "random"
        self.interval_fixed: float = 30.0      # seconds (1 ~ 300)
        self.interval_min: float = 10.0        # for random mode
        self.interval_max: float = 60.0        # for random mode

        # Strength range (each trigger picks a random strength in this range)
        self.strength_min: float = 0.3
        self.strength_max: float = 0.8

        # Duration range (how long each trigger stays active)
        self.duration_min: float = 1.0         # seconds
        self.duration_max: float = 5.0         # seconds

        # Waveform randomisation
        self.random_waveform: bool = False

        # Internal state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._active_strength: float = 0.0
        self._active_until: float = 0.0        # monotonic timestamp

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_interval(self) -> float:
        if self.mode == "random":
            lo = max(1.0, self.interval_min)
            hi = max(lo, self.interval_max)
            return random.uniform(lo, hi)
        return max(1.0, min(300.0, self.interval_fixed))

    def _trigger(self) -> None:
        """Fire a single timed pulse."""
        strength = random.uniform(
            max(0.0, self.strength_min),
            max(0.0, min(1.0, self.strength_max)),
        )
        duration = random.uniform(
            max(0.1, self.duration_min),
            max(0.1, self.duration_max),
        )

        self._active_strength = strength
        self._active_until = time.monotonic() + duration
        logger.debug("定时触发: 强度=%.3f 持续=%.1f秒", strength, duration)

        # Optionally request a random waveform
        if self.random_waveform and PRESET_WAVEFORMS:
            preset = random.choice(PRESET_WAVEFORMS)
            self.waveform_request.emit(preset.name)

    def _current_output(self) -> float:
        """Return the current strength (0 if the active pulse has expired)."""
        if time.monotonic() < self._active_until:
            return self._active_strength
        return 0.0

    # ------------------------------------------------------------------
    # Async loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            # Wait for the next interval
            interval = self._next_interval()
            # Sleep in small increments so we can emit output while waiting
            deadline = time.monotonic() + interval
            while self._running and time.monotonic() < deadline:
                self._emit()
                await asyncio.sleep(0.1)

            if not self._running:
                break

            # Fire trigger
            self._trigger()

            # Keep emitting while the pulse is active
            while self._running and time.monotonic() < self._active_until:
                self._emit()
                await asyncio.sleep(0.1)

    def _emit(self) -> None:
        if not self.enabled:
            return
        output = self._current_output()
        value_a = 0.0
        value_b = 0.0
        if self.channel in ("A", "AB"):
            value_a = output
        if self.channel in ("B", "AB"):
            value_b = output
        self.strength_output.emit(self.MODULE_NAME, value_a, value_b)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("定时模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._active_strength = 0.0
        self._active_until = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("定时模块已停止")
