"""骰子/随机惩罚模块"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


@dataclass
class Punishment:
    """A single entry in the punishment pool."""
    name: str
    strength: float = 0.5       # 0.0 ~ 1.0
    duration: float = 3.0       # seconds
    waveform: str = ""          # preset name, or "" for no change

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "strength": self.strength,
            "duration": self.duration,
            "waveform": self.waveform,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Punishment":
        return cls(
            name=d.get("name", "unknown"),
            strength=d.get("strength", 0.5),
            duration=d.get("duration", 3.0),
            waveform=d.get("waveform", ""),
        )


class DiceModule(QObject):
    """Roll-the-dice random punishment module."""

    strength_output = pyqtSignal(str, float, float)     # module_name, value_a, value_b
    roll_result = pyqtSignal(str, float, float)          # punishment_name, strength, duration
    waveform_request = pyqtSignal(str)                   # waveform preset name

    MODULE_NAME = "dice"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self.enabled: bool = False
        self.channel: str = "AB"

        # Punishment pool
        self.punishment_pool: List[Punishment] = [
            Punishment("轻击", 0.2, 2.0, "pulse"),
            Punishment("中击", 0.5, 3.0, "sawtooth"),
            Punishment("重击", 0.8, 4.0, "heartbeat"),
            Punishment("电击", 1.0, 2.0, "continuous"),
        ]

        # Roulette mode: chance of a high-strength hit on every roll
        self.roulette_mode: bool = False
        self.roulette_probability: float = 0.1     # 0.0 ~ 1.0
        self.roulette_strength: float = 1.0

        # Cooldown between rolls (seconds)
        self.cooldown: float = 10.0

        # Internal state
        self._active_punishment: Optional[Punishment] = None
        self._active_until: float = 0.0             # monotonic timestamp
        self._last_roll_time: float = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Roll logic
    # ------------------------------------------------------------------

    def roll(self) -> Optional[Punishment]:
        """Manually triggered roll. Picks a random punishment from the pool.

        Returns the selected Punishment or None if on cooldown or pool is empty.
        """
        now = time.monotonic()

        # Check cooldown
        if now - self._last_roll_time < self.cooldown and self._last_roll_time > 0:
            return None

        self._last_roll_time = now

        # Roulette check
        if self.roulette_mode and random.random() < self.roulette_probability:
            punishment = Punishment(
                name="JACKPOT",
                strength=max(0.0, min(1.0, self.roulette_strength)),
                duration=5.0,
                waveform="random",
            )
        elif self.punishment_pool:
            punishment = random.choice(self.punishment_pool)
        else:
            return None

        self._active_punishment = punishment
        self._active_until = now + punishment.duration
        logger.debug("骰子结果: %s 强度=%.3f 持续=%.1f秒",
                     punishment.name, punishment.strength, punishment.duration)

        # Emit signals
        self.roll_result.emit(punishment.name, punishment.strength, punishment.duration)
        if punishment.waveform:
            self.waveform_request.emit(punishment.waveform)

        return punishment

    def can_roll(self) -> bool:
        """Return True if the cooldown has elapsed and a roll is possible."""
        if not self.punishment_pool:
            return False
        if self._last_roll_time <= 0:
            return True
        return time.monotonic() - self._last_roll_time >= self.cooldown

    def cooldown_remaining(self) -> float:
        """Return seconds remaining before the next roll is allowed."""
        if self._last_roll_time <= 0:
            return 0.0
        elapsed = time.monotonic() - self._last_roll_time
        return max(0.0, self.cooldown - elapsed)

    # ------------------------------------------------------------------
    # Computation
    # ------------------------------------------------------------------

    def _current_output(self) -> float:
        """Return the current strength from the active punishment."""
        now = time.monotonic()
        if self._active_punishment is not None and now < self._active_until:
            remaining = self._active_until - now
            total = self._active_punishment.duration
            if total > 0:
                # Strength decays linearly over the punishment duration
                factor = remaining / total
                return self._active_punishment.strength * factor
            return 0.0
        # Punishment expired
        if self._active_punishment is not None:
            self._active_punishment = None
        return 0.0

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
    # Async loop (keeps emitting while a punishment is active)
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        while self._running:
            self._emit()
            await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Pool management helpers
    # ------------------------------------------------------------------

    def add_punishment(
        self,
        name: str,
        strength: float = 0.5,
        duration: float = 3.0,
        waveform: str = "",
    ) -> None:
        self.punishment_pool.append(
            Punishment(name, max(0.0, min(1.0, strength)), duration, waveform)
        )

    def remove_punishment(self, index: int) -> None:
        if 0 <= index < len(self.punishment_pool):
            self.punishment_pool.pop(index)

    def clear_pool(self) -> None:
        self.punishment_pool.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_roll_time = 0.0
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._loop())
        logger.info("骰子模块已启动")

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._active_punishment = None
        self._active_until = 0.0
        self.strength_output.emit(self.MODULE_NAME, 0.0, 0.0)
        logger.info("骰子模块已停止")
