"""应用聚焦模块"""

import asyncio
import logging
import re
import time
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class AppRule:
    """A single rule that maps a foreground application to a strength value."""

    __slots__ = ("pattern", "is_regex", "strength", "waveform", "channel",
                 "_compiled")

    def __init__(
        self,
        pattern: str,
        is_regex: bool = False,
        strength: float = 0.5,
        waveform: str = "",
        channel: str = "AB",
    ) -> None:
        self.pattern = pattern
        self.is_regex = is_regex
        self.strength = max(0.0, min(1.0, strength))
        self.waveform = waveform        # preset name, or "" for no change
        self.channel = channel           # "A", "B", or "AB"
        self._compiled: Optional[re.Pattern] = None
        if is_regex:
            try:
                self._compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                self._compiled = None

    def matches(self, title: str, process: str) -> bool:
        """Return True if the rule matches the given window title or process."""
        text = f"{title} {process}"
        if self.is_regex and self._compiled is not None:
            return bool(self._compiled.search(text))
        return self.pattern.lower() in text.lower()

    def to_dict(self) -> Dict:
        return {
            "pattern": self.pattern,
            "is_regex": self.is_regex,
            "strength": self.strength,
            "waveform": self.waveform,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "AppRule":
        return cls(
            pattern=d.get("pattern", ""),
            is_regex=d.get("is_regex", False),
            strength=d.get("strength", 0.5),
            waveform=d.get("waveform", ""),
            channel=d.get("channel", "AB"),
        )


class AppModule(QObject):
    """Outputs strength based on which application is in the foreground."""

    strength_output = pyqtSignal(str, float, float)  # module_name, value_a, value_b
    waveform_request = pyqtSignal(str)                # waveform preset name

    MODULE_NAME = "app"

    def __init__(self, app_monitor, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._monitor = app_monitor

        self.enabled: bool = False
        self.channel: str = "AB"

        # Settings
        self.app_rules: List[AppRule] = []
        self.switch_pulse: bool = True       # trigger pulse on app switch
        self.switch_strength: float = 0.3    # pulse strength on switch
        self.mode: str = "blacklist"         # "whitelist" or "blacklist"

        # Internal state
        self._current_strength_a: float = 0.0
        self._current_strength_b: float = 0.0
        self._last_title: str = ""
        self._last_process: str = ""
        self._switch_pulse_remaining: float = 0.0  # seconds
        self._switch_pulse_duration: float = 1.0   # total decay time for switch pulse
        self._switch_pulse_until: float = 0.0      # monotonic timestamp when pulse expires
        self._base_strength_a: float = 0.0         # rule-based strength (without pulse)
        self._base_strength_b: float = 0.0

        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Connect to AppMonitor
        self._monitor.app_changed.connect(self._on_app_changed)

    # ------------------------------------------------------------------
    # Monitor signal handler
    # ------------------------------------------------------------------

    def _on_app_changed(self, title: str, process: str) -> None:
        if not self._running or not self.enabled:
            return

        is_switch = (title != self._last_title or process != self._last_process)
        self._last_title = title
        self._last_process = process
        if is_switch:
            logger.debug("前台应用切换: %s (%s)", title, process)

        # Find matching rule
        matched_rule: Optional[AppRule] = None
        for rule in self.app_rules:
            if rule.matches(title, process):
                matched_rule = rule
                break

        # Determine base strength from rule
        if matched_rule is not None:
            self._apply_rule(matched_rule)
        else:
            self._base_strength_a = 0.0
            self._base_strength_b = 0.0

        # Switch pulse: set expiry timestamp for timed decay
        if is_switch and self.switch_pulse:
            self._switch_pulse_until = time.monotonic() + self._switch_pulse_duration

        self._update_and_emit()

    def _apply_rule(self, rule: AppRule) -> None:
        """Apply a matched rule to set base strength values."""
        s = rule.strength
        ch = rule.channel

        self._base_strength_a = s if ch in ("A", "AB") else 0.0
        self._base_strength_b = s if ch in ("B", "AB") else 0.0

        # Request waveform change if the rule specifies one
        if rule.waveform:
            self.waveform_request.emit(rule.waveform)

    # ------------------------------------------------------------------
    # Strength computation with switch pulse decay
    # ------------------------------------------------------------------

    def _update_and_emit(self) -> None:
        """Compute current strength = base + decaying switch pulse, then emit."""
        now = time.monotonic()
        pulse_a = 0.0
        pulse_b = 0.0

        if self.switch_pulse and now < self._switch_pulse_until:
            remaining = self._switch_pulse_until - now
            factor = remaining / self._switch_pulse_duration
            pulse_val = max(0.0, min(1.0, self.switch_strength)) * factor
            if self.channel in ("A", "AB"):
                pulse_a = pulse_val
            if self.channel in ("B", "AB"):
                pulse_b = pulse_val

        self._current_strength_a = max(self._base_strength_a, pulse_a)
        self._current_strength_b = max(self._base_strength_b, pulse_b)
        self._emit()

    # ------------------------------------------------------------------
    # Async loop for switch pulse decay
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            if self.enabled and self._switch_pulse_until > 0:
                self._update_and_emit()
            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Emit
    # ------------------------------------------------------------------

    def _emit(self) -> None:
        self.strength_output.emit(
            self.MODULE_NAME,
            self._current_strength_a,
            self._current_strength_b,
        )

    # ------------------------------------------------------------------
    # Rule management helpers
    # ------------------------------------------------------------------

    def add_rule(
        self,
        pattern: str,
        is_regex: bool = False,
        strength: float = 0.5,
        waveform: str = "",
        channel: str = "AB",
    ) -> None:
        self.app_rules.append(
            AppRule(pattern, is_regex, strength, waveform, channel)
        )

    def remove_rule(self, index: int) -> None:
        if 0 <= index < len(self.app_rules):
            self.app_rules.pop(index)

    def clear_rules(self) -> None:
        self.app_rules.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("应用聚焦模块已启动")
        # Get initial foreground app
        try:
            title, process = self._monitor.get_current_app()
            self._on_app_changed(title, process)
        except Exception:
            logger.exception("获取初始前台应用失败")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._current_strength_a = 0.0
        self._current_strength_b = 0.0
        self._switch_pulse_until = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("应用聚焦模块已停止")
