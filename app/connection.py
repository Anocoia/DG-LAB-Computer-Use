"""DG-LAB WebSocket 连接管理"""
import asyncio
import io
import logging
import socket
from typing import Optional

import qrcode
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage

from pydglab_ws import (
    DGLabWSConnect,
    DGLabWSServer,
    Channel,
    StrengthOperationType,
    StrengthData,
    FeedbackButton,
)

logger = logging.getLogger(__name__)

# WebSocket 操作超时，防止写入挂起阻塞调用方
_WS_OP_TIMEOUT: float = 2.0


class ConnectionManager(QObject):
    """管理与 DG-LAB App 的 WebSocket 连接"""

    # ---------- signals ----------
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    bind_ready = pyqtSignal(str)        # QR code URL
    device_bound = pyqtSignal()
    strength_data = pyqtSignal(object)   # StrengthData
    feedback_button = pyqtSignal(object) # FeedbackButton
    error = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    server_started = pyqtSignal(str, int)  # host, port

    # ---------- lifecycle ----------

    def __init__(self, parent=None):
        super().__init__(parent)
        self._client = None  # DGLabWSConnect or DGLabLocalClient
        self._context_manager = None
        self._server: Optional[DGLabWSServer] = None
        self._server_context = None
        self._server_mode: bool = False
        self._is_connected: bool = False
        self._is_bound: bool = False
        self._ws_url: str = ""

        # background tasks
        self._data_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._connect_task: Optional[asyncio.Task] = None

        # reconnection control
        self._should_reconnect: bool = True
        self._reconnect_delay: float = 3.0       # seconds between retries
        self._max_reconnect_delay: float = 30.0
        self._bind_timeout: float = 60.0          # seconds to wait for QR scan
        self._shutting_down: bool = False

    # ---------- properties ----------

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_bound(self) -> bool:
        return self._is_bound

    # ---------- public API ----------

    async def connect(self, ws_url: str) -> None:
        """连接到 WebSocket 服务器（可以是内嵌或远程）"""
        self._ws_url = ws_url
        self._shutting_down = False
        self._should_reconnect = True
        self._server_mode = False
        await self._do_connect()

    async def connect_local(self, host: str = "0.0.0.0", port: int = 5678,
                             qr_ip: str = "") -> None:
        """启动内置 WebSocket 服务器并创建本地客户端

        Args:
            host: 服务器监听地址
            port: 服务器监听端口
            qr_ip: 二维码中显示的 IP 地址，为空则自动检测
        """
        self._shutting_down = False
        self._should_reconnect = False
        self._server_mode = True
        await self._cleanup()

        self._set_status("正在启动内置服务器...")

        try:
            # 创建并启动服务器
            self._server = DGLabWSServer(host, port, heartbeat_interval=60)
            self._server_context = self._server
            await self._server.__aenter__()

            local_ip = qr_ip.strip() if qr_ip.strip() else self.get_local_ip()
            self.server_started.emit(local_ip, port)
            self._is_connected = True
            self.connected.emit()
            self._set_status(f"服务器已启动 ws://{local_ip}:{port}")

            # 创建本地客户端
            self._client = self._server.new_local_client()

            # 生成二维码 URL
            qr_url = self._client.get_qrcode(f"ws://{local_ip}:{port}")
            if qr_url:
                self.bind_ready.emit(qr_url)
                self._set_status("等待扫码绑定...")

                # 等待 App 扫码绑定
                await self._client.bind()

                self._is_bound = True
                self.device_bound.emit()
                self._set_status("设备已绑定")
                logger.info("DG-LAB 设备已绑定 (内置服务器模式)")

                # 启动数据监听
                self._data_task = asyncio.get_event_loop().create_task(self._data_loop())
            else:
                raise RuntimeError("生成二维码失败")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("内置服务器启动失败: %s", e)
            self.error.emit(f"服务器启动失败: {e}")
            self._set_status(f"服务器启动失败: {e}")
            await self._cleanup()

    async def disconnect(self) -> None:
        """优雅断开连接"""
        self._shutting_down = True
        self._should_reconnect = False
        await self._cleanup()
        self._set_status("已断开")

    async def set_strength(self, channel: Channel, value: int) -> None:
        """设置通道强度 (0-200)"""
        if not self._client or not self._is_bound:
            return
        value = max(0, min(200, value))
        try:
            await asyncio.wait_for(
                self._client.set_strength(channel, StrengthOperationType.SET_TO, value),
                timeout=_WS_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("set_strength 超时 (通道 %s)", channel)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("set_strength 失败: %s", e)

    async def add_pulses(self, channel: Channel, pulses) -> None:
        """向通道发送波形脉冲"""
        if not self._client or not self._is_bound:
            return
        try:
            await asyncio.wait_for(
                self._client.add_pulses(channel, pulses),
                timeout=_WS_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("add_pulses 超时 (通道 %s)", channel)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("add_pulses 失败: %s", e)

    async def add_pulses_batch(self, channel: Channel, pulse_list: list) -> None:
        """批量向通道发送多个波形脉冲（单条 WebSocket 消息）"""
        if not self._client or not self._is_bound or not pulse_list:
            return
        try:
            await asyncio.wait_for(
                self._client.add_pulses(channel, *pulse_list),
                timeout=_WS_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("add_pulses_batch 超时 (通道 %s)", channel)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("add_pulses_batch 失败: %s", e)

    async def clear_pulses(self, channel: Channel) -> None:
        """清空通道波形队列"""
        if not self._client or not self._is_bound:
            return
        try:
            await asyncio.wait_for(
                self._client.clear_pulses(channel),
                timeout=_WS_OP_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("clear_pulses 超时 (通道 %s)", channel)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("clear_pulses 失败: %s", e)

    # ---------- internal: connect / bind / listen ----------

    async def _do_connect(self) -> None:
        """执行一次完整的 连接 -> 绑定 -> 监听 流程"""
        await self._cleanup()
        self._set_status("正在连接...")

        try:
            self._context_manager = DGLabWSConnect(self._ws_url, self._bind_timeout)
            self._client = await self._context_manager.__aenter__()

            self._is_connected = True
            self.connected.emit()
            self._set_status("已连接，等待扫码绑定...")

            # 生成二维码 URL 并通知 UI
            qr_url = self._client.get_qrcode()
            self.bind_ready.emit(qr_url)

            # 等待 App 扫码绑定
            await self._client.bind()

            self._is_bound = True
            self.device_bound.emit()
            self._set_status("设备已绑定")
            logger.info("DG-LAB 设备已绑定")

            # 启动数据监听
            self._data_task = asyncio.get_event_loop().create_task(self._data_loop())

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("连接流程失败: %s", e)
            self.error.emit(f"连接失败: {e}")
            self._set_status(f"连接失败: {e}")
            await self._cleanup_client()
            self._schedule_reconnect()

    async def _data_loop(self) -> None:
        """持续接收 App 数据推送"""
        if not self._client:
            return
        try:
            async for data in self._client.data_generator():
                if isinstance(data, StrengthData):
                    self.strength_data.emit(data)
                elif isinstance(data, FeedbackButton):
                    self.feedback_button.emit(data)
        except asyncio.CancelledError:
            logger.debug("数据监听被取消")
        except Exception as e:
            logger.error("数据监听异常: %s", e)
            self.error.emit(f"数据流异常: {e}")
        finally:
            # 数据流结束意味着连接中断
            if not self._shutting_down:
                logger.warning("数据流结束，连接已断开")
                await self._handle_disconnect()

    async def _handle_disconnect(self) -> None:
        """连接中断后的清理与重连"""
        was_bound = self._is_bound
        await self._cleanup_client()

        if was_bound:
            self.disconnected.emit()
            self._set_status("连接已断开")

        self._schedule_reconnect()

    # ---------- internal: reconnection ----------

    def _schedule_reconnect(self) -> None:
        """安排一次重连尝试"""
        if not self._should_reconnect or self._shutting_down:
            return
        if self._reconnect_task and not self._reconnect_task.done():
            return  # 已有重连任务在等待
        self._reconnect_task = asyncio.get_event_loop().create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """指数退避重连"""
        delay = self._reconnect_delay
        while self._should_reconnect and not self._shutting_down:
            self._set_status(f"将在 {delay:.0f} 秒后重连...")
            logger.info("将在 %.0f 秒后尝试重连", delay)
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return

            if not self._should_reconnect or self._shutting_down:
                return

            self._set_status("正在重连...")
            try:
                await self._do_connect()
                return  # 重连成功，退出循环
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("重连失败: %s", e)
                self.error.emit(f"重连失败: {e}")
                delay = min(delay * 1.5, self._max_reconnect_delay)

    # ---------- internal: cleanup ----------

    async def _cleanup(self) -> None:
        """停止所有后台任务并关闭连接"""
        self._cancel_task("_reconnect_task")
        self._cancel_task("_data_task")
        self._cancel_task("_connect_task")
        await self._cleanup_client()
        await self._cleanup_server()

    def _cancel_task(self, attr: str) -> None:
        task: Optional[asyncio.Task] = getattr(self, attr, None)
        if task and not task.done():
            task.cancel()
        setattr(self, attr, None)

    async def _cleanup_client(self) -> None:
        """关闭 DGLabWSConnect 上下文"""
        self._is_bound = False
        self._is_connected = False

        if self._context_manager:
            try:
                await self._context_manager.__aexit__(None, None, None)
            except Exception as e:
                logger.debug("关闭上下文时出错 (可忽略): %s", e)
            self._context_manager = None
        self._client = None

    async def _cleanup_server(self) -> None:
        """关闭内置服务器"""
        if self._server_context:
            try:
                await self._server_context.__aexit__(None, None, None)
            except Exception as e:
                logger.debug("关闭服务器时出错 (可忽略): %s", e)
            self._server_context = None
        self._server = None
        self._server_mode = False

    # ---------- helpers ----------

    def _set_status(self, text: str) -> None:
        logger.info("状态: %s", text)
        self.status_changed.emit(text)

    @staticmethod
    def get_local_ip() -> str:
        """获取本机局域网 IP 地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    # ---------- QR code image generation ----------

    @staticmethod
    def generate_qr_pixmap(url: str, box_size: int = 6, border: int = 2) -> QPixmap:
        """将 URL 生成为 QPixmap 二维码图片"""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        qimage = QImage()
        qimage.loadFromData(buf.getvalue(), "PNG")
        return QPixmap.fromImage(qimage)
