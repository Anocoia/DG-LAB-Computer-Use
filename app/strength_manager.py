"""强度计算与混合引擎"""
import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional, Callable, Awaitable

from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# 下发超时: WebSocket 写入最多等待此时长，超过则跳过本轮
_SEND_TIMEOUT: float = 0.5


class MixMode(Enum):
    MAX = "max"
    SUM = "sum"
    AVG = "avg"


class StrengthManager(QObject):
    """管理所有模块的强度输出，混合并下发"""
    strength_updated = pyqtSignal(float, float)  # channel_a, channel_b (0.0~1.0 mixed)
    final_strength_updated = pyqtSignal(int, int)  # channel_a, channel_b (0~200 final)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 各模块输出: module_name -> (channel_a_value, channel_b_value)  0.0~1.0
        self._module_outputs: Dict[str, tuple[float, float]] = {}
        self._mix_mode = MixMode.MAX
        self._global_limit_a: int = 200
        self._global_limit_b: int = 200
        self._link_channels: bool = False  # A/B 联动
        self._multiplier: float = 1.0  # 全局倍率

        # 平滑
        self._smoothing: float = 0.3  # 0=无平滑, 1=极慢
        self._current_a: float = 0.0
        self._current_b: float = 0.0

        # 下发回调
        self._set_strength_callback: Optional[Callable[[int, int], Awaitable[None]]] = None

        # 定时器
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 日志节流
        self._log_counter: int = 0

    def set_callback(self, callback: Callable[[int, int], Awaitable[None]]):
        self._set_strength_callback = callback

    def set_mix_mode(self, mode: MixMode):
        logger.info("混合模式 → %s", mode.value)
        self._mix_mode = mode

    def set_global_limit(self, channel_a: int, channel_b: int):
        self._global_limit_a = max(0, min(200, channel_a))
        self._global_limit_b = max(0, min(200, channel_b))
        logger.info("全局上限 → A=%d  B=%d", self._global_limit_a, self._global_limit_b)

    def set_multiplier(self, value: float):
        self._multiplier = max(0.0, min(5.0, value))
        logger.info("全局倍率 → %.2f", self._multiplier)

    def set_link_channels(self, linked: bool):
        self._link_channels = linked

    def set_smoothing(self, value: float):
        self._smoothing = max(0.0, min(0.95, value))

    def update_module(self, module_name: str, value_a: float, value_b: float):
        """模块更新其强度输出"""
        self._module_outputs[module_name] = (
            max(0.0, min(1.0, value_a)),
            max(0.0, min(1.0, value_b)),
        )

    def remove_module(self, module_name: str):
        self._module_outputs.pop(module_name, None)

    def get_active_sources(self) -> dict[str, tuple[float, float]]:
        """返回当前有输出的模块名和其 A/B 通道归一化值"""
        return {k: v for k, v in self._module_outputs.items()
                if v[0] > 0.001 or v[1] > 0.001}

    def _mix(self) -> tuple[float, float]:
        if not self._module_outputs:
            return (0.0, 0.0)

        values_a = [v[0] for v in self._module_outputs.values()]
        values_b = [v[1] for v in self._module_outputs.values()]

        if self._mix_mode == MixMode.MAX:
            mixed_a = max(values_a) if values_a else 0.0
            mixed_b = max(values_b) if values_b else 0.0
        elif self._mix_mode == MixMode.SUM:
            mixed_a = min(1.0, sum(values_a))
            mixed_b = min(1.0, sum(values_b))
        else:  # AVG
            mixed_a = sum(values_a) / len(values_a) if values_a else 0.0
            mixed_b = sum(values_b) / len(values_b) if values_b else 0.0

        if self._link_channels:
            linked = max(mixed_a, mixed_b)
            mixed_a = mixed_b = linked

        return (mixed_a, mixed_b)

    def _smooth(self, target_a: float, target_b: float) -> tuple[float, float]:
        alpha = 1.0 - self._smoothing
        self._current_a += (target_a - self._current_a) * alpha
        self._current_b += (target_b - self._current_b) * alpha
        return (self._current_a, self._current_b)

    def compute(self) -> tuple[int, int]:
        """计算最终强度值 (0~200)"""
        mixed_a, mixed_b = self._mix()
        smooth_a, smooth_b = self._smooth(mixed_a, mixed_b)
        self.strength_updated.emit(smooth_a, smooth_b)

        # 应用上限，再乘以全局倍率
        final_a = int(smooth_a * self._global_limit_a * self._multiplier)
        final_b = int(smooth_b * self._global_limit_b * self._multiplier)
        final_a = max(0, min(200, final_a))
        final_b = max(0, min(200, final_b))
        self.final_strength_updated.emit(final_a, final_b)

        # 每 50 次（约5秒）打印一次详细状态
        self._log_counter += 1
        if self._log_counter >= 50:
            self._log_counter = 0
            active = {k: (f"{v[0]:.2f}", f"{v[1]:.2f}")
                      for k, v in self._module_outputs.items()
                      if v[0] > 0.001 or v[1] > 0.001}
            logger.debug(
                "强度计算: mix=(%.3f,%.3f) smooth=(%.3f,%.3f) "
                "limit=(%d,%d) mult=%.2f → final=(%d,%d) 活跃模块=%s",
                mixed_a, mixed_b, smooth_a, smooth_b,
                self._global_limit_a, self._global_limit_b,
                self._multiplier, final_a, final_b, active or "无",
            )

        return (final_a, final_b)

    async def _loop(self):
        logger.info("StrengthManager 主循环启动 (limit=A:%d B:%d, mult=%.2f)",
                     self._global_limit_a, self._global_limit_b, self._multiplier)
        try:
            while self._running:
                # 1) 计算并更新 UI（不受下发阻塞影响）
                final_a, final_b = self.compute()

                # 2) 带超时地下发强度，防止 WebSocket 挂起阻塞整个循环
                if self._set_strength_callback:
                    try:
                        await asyncio.wait_for(
                            self._set_strength_callback(final_a, final_b),
                            timeout=_SEND_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("强度下发超时 (%.1fs)，跳过本轮", _SEND_TIMEOUT)
                    except asyncio.CancelledError:
                        raise  # 正常取消，不要吞掉
                    except Exception:
                        logger.debug("强度下发异常", exc_info=True)

                await asyncio.sleep(0.1)  # 100ms
        except asyncio.CancelledError:
            logger.debug("StrengthManager 主循环被取消")
        except Exception:
            logger.exception("StrengthManager 主循环异常退出")
        finally:
            # 确保 _running 重置，使 start() 可以重新启动
            self._running = False
            logger.info("StrengthManager 主循环已停止")

    def start(self):
        if not self._running:
            self._running = True
            loop = asyncio.get_event_loop()
            self._task = loop.create_task(self._loop())
            logger.info("StrengthManager 已启动")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self._current_a = 0.0
        self._current_b = 0.0
        self._module_outputs.clear()
        logger.info("StrengthManager 已停止")
