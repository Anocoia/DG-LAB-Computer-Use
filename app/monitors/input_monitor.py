"""鼠标/键盘输入监听"""

import logging
import math
import time
import threading

from pynput import mouse, keyboard
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class InputMonitor(QObject):
    """Listens for mouse and keyboard events via pynput and emits Qt signals."""

    mouse_click = pyqtSignal(int, int, str)   # x, y, button_name
    mouse_move = pyqtSignal(float)            # movement speed (pixels/sec)
    mouse_scroll = pyqtSignal(int)            # scroll delta
    key_press = pyqtSignal(str)               # key name
    key_release = pyqtSignal(str)             # key name

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None

        # State for computing mouse movement speed
        self._last_mouse_x: float | None = None
        self._last_mouse_y: float | None = None
        self._last_mouse_time: float | None = None

        self._running = False

        # 日志节流：鼠标移动事件过于频繁，每 N 次才记录一次
        self._move_log_counter: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start mouse and keyboard listeners (each in its own daemon thread)."""
        if self._running:
            return
        self._running = True
        logger.info("InputMonitor 启动中...")

        try:
            self._mouse_listener = mouse.Listener(
                on_click=self._on_click,
                on_move=self._on_move,
                on_scroll=self._on_scroll,
            )
            self._mouse_listener.daemon = True
            self._mouse_listener.start()
            logger.info("鼠标监听器已启动 (线程: %s)", self._mouse_listener.name)
        except Exception:
            logger.exception("鼠标监听器启动失败")

        try:
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._keyboard_listener.daemon = True
            self._keyboard_listener.start()
            logger.info("键盘监听器已启动 (线程: %s)", self._keyboard_listener.name)
        except Exception:
            logger.exception("键盘监听器启动失败")

    def stop(self) -> None:
        """Stop both listeners."""
        self._running = False
        logger.info("InputMonitor 停止中...")

        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
            logger.info("鼠标监听器已停止")

        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
            logger.info("键盘监听器已停止")

        # Reset movement tracking
        self._last_mouse_x = None
        self._last_mouse_y = None
        self._last_mouse_time = None

    # ------------------------------------------------------------------
    # Mouse callbacks (called from the pynput listener thread)
    # ------------------------------------------------------------------

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        try:
            if not pressed:
                return  # Only emit on press, not release
            button_map = {
                mouse.Button.left: "left",
                mouse.Button.right: "right",
                mouse.Button.middle: "middle",
            }
            name = button_map.get(button, str(button))
            logger.debug("鼠标点击: (%d, %d) 按钮=%s", x, y, name)
            self.mouse_click.emit(int(x), int(y), name)
        except Exception:
            logger.exception("鼠标点击回调异常")

    def _on_move(self, x: int, y: int) -> None:
        try:
            now = time.monotonic()

            if self._last_mouse_x is not None and self._last_mouse_time is not None:
                dx = x - self._last_mouse_x
                dy = y - self._last_mouse_y
                dt = now - self._last_mouse_time
                if dt > 0:
                    distance = math.hypot(dx, dy)
                    speed = distance / dt  # pixels per second
                    self.mouse_move.emit(speed)

                    self._move_log_counter += 1
                    if self._move_log_counter >= 200:
                        self._move_log_counter = 0
                        logger.debug("鼠标移动: (%d, %d) 速度=%.0f px/s", x, y, speed)

            self._last_mouse_x = float(x)
            self._last_mouse_y = float(y)
            self._last_mouse_time = now
        except Exception:
            logger.exception("鼠标移动回调异常")

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        try:
            logger.debug("鼠标滚轮: (%d, %d) dy=%d", x, y, dy)
            self.mouse_scroll.emit(int(dy))
        except Exception:
            logger.exception("鼠标滚轮回调异常")

    # ------------------------------------------------------------------
    # Keyboard callbacks (called from the pynput listener thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _key_name(key) -> str:
        """Return a human-readable string for a pynput key."""
        if hasattr(key, "char") and key.char is not None:
            return key.char
        if hasattr(key, "name"):
            return key.name
        return str(key)

    def _on_key_press(self, key) -> None:
        try:
            name = self._key_name(key)
            logger.debug("按键按下: %s", name)
            self.key_press.emit(name)
        except Exception:
            logger.exception("按键按下回调异常")

    def _on_key_release(self, key) -> None:
        try:
            name = self._key_name(key)
            logger.debug("按键释放: %s", name)
            self.key_release.emit(name)
        except Exception:
            logger.exception("按键释放回调异常")
