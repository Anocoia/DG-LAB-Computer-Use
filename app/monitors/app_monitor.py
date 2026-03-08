"""前台应用/窗口监控"""

import asyncio
import ctypes
import ctypes.wintypes
import logging

import psutil
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# Windows API helpers
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_foreground_window_info() -> tuple[str, str]:
    """Return (window_title, process_name) for the current foreground window.

    Falls back to empty strings on failure.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")

    # --- Window title ---
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
    else:
        title = ""

    # --- Process name ---
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = ""
    if pid.value:
        try:
            proc = psutil.Process(pid.value)
            process_name = proc.name()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # Fallback: try via OpenProcess + QueryFullProcessImageNameW
            handle = kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if handle:
                buf_size = ctypes.wintypes.DWORD(512)
                buf = ctypes.create_unicode_buffer(512)
                success = kernel32.QueryFullProcessImageNameW(
                    handle, 0, buf, ctypes.byref(buf_size)
                )
                kernel32.CloseHandle(handle)
                if success:
                    # Extract just the filename
                    process_name = buf.value.rsplit("\\", 1)[-1]

    return (title, process_name)


class AppMonitor(QObject):
    """Polls the foreground window and emits a signal when it changes."""

    app_changed = pyqtSignal(str, str)  # (window_title, process_name)

    def __init__(self, interval: float = 1.0, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False

        self._last_title = ""
        self._last_process = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the polling loop as an asyncio task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._poll_loop())
        logger.info("AppMonitor 已启动 (间隔=%.1fs)", self._interval)

    def stop(self) -> None:
        """Cancel the polling task."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
        logger.info("AppMonitor 已停止")

    def get_current_app(self) -> tuple[str, str]:
        """Return (window_title, process_name) of the current foreground window."""
        return _get_foreground_window_info()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                title, process_name = _get_foreground_window_info()
                if title != self._last_title or process_name != self._last_process:
                    self._last_title = title
                    self._last_process = process_name
                    logger.debug("前台应用切换: %s (%s)", title[:50], process_name)
                    self.app_changed.emit(title, process_name)
            except Exception:
                logger.exception("前台应用检测异常")
            await asyncio.sleep(self._interval)
