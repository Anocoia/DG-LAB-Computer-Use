"""输入事件→强度模块"""

import asyncio
import logging
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class InputModule(QObject):
    """Maps mouse and keyboard input events to output strength."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b

    MODULE_NAME = "input"

    # Decay time for a pulse (seconds)
    PULSE_DECAY: float = 0.5

    # Window for combo detection (seconds)
    COMBO_WINDOW: float = 2.0

    def __init__(self, input_monitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = input_monitor

        self.enabled: bool = False
        self.channel: str = "AB"

        # Sub-source toggles
        self.mouse_click_enabled: bool = True
        self.mouse_move_enabled: bool = True
        self.mouse_scroll_enabled: bool = True
        self.key_press_enabled: bool = True

        # Configurable strengths per button type
        self.click_strengths: Dict[str, float] = {
            "left": 0.3,
            "right": 0.5,
            "middle": 0.4,
        }

        # Maximum mouse speed that maps to 1.0 (pixels / second)
        self.mouse_speed_ceil: float = 3000.0

        # Scroll pulse strength
        self.scroll_strength: float = 0.3

        # Keyboard pulse strength (generic keypress)
        self.key_strength: float = 0.2

        # Special keys with custom strength
        self.specific_keys: Dict[str, float] = {}

        # Combo bonus settings
        self.combo_threshold: int = 10
        self.combo_bonus: float = 0.3

        # Internal state
        self._pulses: List[tuple[float, float]] = []  # (timestamp, strength)
        self._mouse_speed_value: float = 0.0
        self._event_timestamps: List[float] = []      # for combo tracking
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Connect monitor signals
        self._monitor.mouse_click.connect(self._on_click)
        self._monitor.mouse_move.connect(self._on_move)
        self._monitor.mouse_scroll.connect(self._on_scroll)
        self._monitor.key_press.connect(self._on_key_press)

    # ------------------------------------------------------------------
    # Monitor signal handlers
    # ------------------------------------------------------------------

    def _add_pulse(self, strength: float) -> None:
        now = time.monotonic()
        self._pulses.append((now, max(0.0, min(1.0, strength))))
        self._event_timestamps.append(now)

    def _on_click(self, x: int, y: int, button_name: str) -> None:
        if not self.mouse_click_enabled:
            return
        strength = self.click_strengths.get(button_name, 0.3)
        self._add_pulse(strength)

    def _on_move(self, speed: float) -> None:
        if not self.mouse_move_enabled:
            return
        self._mouse_speed_value = min(speed / self.mouse_speed_ceil, 1.0)

    def _on_scroll(self, delta: int) -> None:
        if not self.mouse_scroll_enabled:
            return
        self._add_pulse(self.scroll_strength)

    def _on_key_press(self, key_name: str) -> None:
        if not self.key_press_enabled:
            return
        # Check for specific key override
        if key_name in self.specific_keys:
            strength = self.specific_keys[key_name]
        else:
            strength = self.key_strength
        self._add_pulse(strength)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _compute(self) -> tuple[float, float]:
        now = time.monotonic()

        # Decay old pulses and compute max active pulse strength
        active_pulses: List[tuple[float, float]] = []
        max_pulse = 0.0
        for ts, strength in self._pulses:
            age = now - ts
            if age < self.PULSE_DECAY:
                # Linear decay: full strength at t=0, zero at t=PULSE_DECAY
                decayed = strength * (1.0 - age / self.PULSE_DECAY)
                active_pulses.append((ts, strength))
                max_pulse = max(max_pulse, decayed)
        self._pulses = active_pulses

        # Mouse move contributes continuously (decays naturally as speed drops)
        move_value = self._mouse_speed_value
        # Gradually decay mouse speed when no new move events arrive
        self._mouse_speed_value *= 0.9

        # Combo bonus: count events in the combo window
        cutoff = now - self.COMBO_WINDOW
        self._event_timestamps = [t for t in self._event_timestamps if t > cutoff]
        combo_value = 0.0
        if len(self._event_timestamps) > self.combo_threshold:
            combo_value = self.combo_bonus

        # Combined output = max of all sources (clamped to 1.0)
        combined = min(1.0, max(max_pulse, move_value) + combo_value)

        # Route to channels
        value_a = 0.0
        value_b = 0.0
        if self.channel in ("A", "AB"):
            value_a = combined
        if self.channel in ("B", "AB"):
            value_b = combined

        return (value_a, value_b)

    def _emit(self) -> None:
        if not self.enabled:
            return
        value_a, value_b = self._compute()
        logger.debug("输入事件输出: A=%.3f B=%.3f", value_a, value_b)
        self.strength_output.emit(self.MODULE_NAME, value_a, value_b)

    # ------------------------------------------------------------------
    # Async loop
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            self._emit()
            await asyncio.sleep(0.05)  # 20 Hz for responsive pulse decay

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("输入事件模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._pulses.clear()
        self._event_timestamps.clear()
        self._mouse_speed_value = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("输入事件模块已停止")
