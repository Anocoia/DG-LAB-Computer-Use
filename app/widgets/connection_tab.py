"""连接配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QLineEdit, QPushButton, QLabel,
    QRadioButton, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap


class ConnectionTab(QWidget):
    """WebSocket 连接配置与状态显示标签页"""

    connect_requested = pyqtSignal(str)
    disconnect_requested = pyqtSignal()
    connect_local_requested = pyqtSignal(str, int, str)  # host, port, qr_ip

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("管理与 DG-LAB App 的 WebSocket 连接。选择内置服务器或远程服务器模式，扫描二维码完成设备绑定。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 连接模式选择 ---
        mode_group = QGroupBox("连接模式")
        mode_layout = QVBoxLayout()

        mode_row = QHBoxLayout()
        self._local_radio = QRadioButton("内置服务器")
        self._local_radio.setToolTip("在本机启动 WebSocket 服务器，适合手机和电脑在同一局域网的场景")
        self._local_radio.setChecked(True)
        self._local_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self._local_radio)

        self._remote_radio = QRadioButton("远程服务器")
        self._remote_radio.setToolTip("连接到已有的 WebSocket 服务器，适合使用公共服务器或自建远程服务器")
        mode_row.addWidget(self._remote_radio)

        mode_layout.addLayout(mode_row)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # --- 内置服务器设置 ---
        self._local_group = QGroupBox("内置服务器设置")
        local_form = QFormLayout()

        self._host_edit = QLineEdit("0.0.0.0")
        self._host_edit.setToolTip("服务器监听地址，0.0.0.0 表示监听所有网络接口")
        local_form.addRow("监听地址:", self._host_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(5678)
        self._port_spin.setToolTip("服务器监听端口，确保端口未被占用且防火墙已放行")
        local_form.addRow("端口:", self._port_spin)

        self._local_ip_edit = QLineEdit()
        self._local_ip_edit.setPlaceholderText("自动检测，可手动修改")
        self._local_ip_edit.setToolTip(
            "二维码中显示的本机 IP 地址。留空则自动检测。\n"
            "如果自动检测不正确（如有 VPN 或多网卡），请手动填入正确的局域网 IP。"
        )
        local_form.addRow("二维码 IP:", self._local_ip_edit)

        self._start_server_btn = QPushButton("启动服务器")
        self._start_server_btn.setToolTip("启动内置 WebSocket 服务器并生成二维码")
        self._start_server_btn.clicked.connect(self._on_start_server)
        local_form.addRow(self._start_server_btn)

        self._local_group.setLayout(local_form)
        main_layout.addWidget(self._local_group)

        # --- 远程服务器设置 ---
        self._remote_group = QGroupBox("远程服务器设置")
        remote_form = QFormLayout()

        self._url_edit = QLineEdit("ws://192.168.1.1:5678")
        self._url_edit.setPlaceholderText("WebSocket 地址")
        self._url_edit.setToolTip("远程 WebSocket 服务器地址，格式: ws://IP:端口")
        remote_form.addRow("WebSocket 地址:", self._url_edit)

        self._connect_btn = QPushButton("连接")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        remote_form.addRow(self._connect_btn)

        self._remote_group.setLayout(remote_form)
        main_layout.addWidget(self._remote_group)

        # --- 连接状态 ---
        status_group = QGroupBox("连接状态")
        status_form = QFormLayout()

        self._status_label = QLabel("未连接")
        self._status_label.setStyleSheet("color: #999999; font-weight: bold;")
        status_form.addRow("状态:", self._status_label)

        status_group.setLayout(status_form)
        main_layout.addWidget(status_group)

        # --- 二维码显示 ---
        qr_group = QGroupBox("二维码")
        qr_layout = QVBoxLayout()

        self._qr_label = QLabel("等待连接后显示二维码...")
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setMinimumSize(200, 200)
        self._qr_label.setStyleSheet("border: 1px dashed #FFB6C1; background: white; border-radius: 6px;")
        qr_layout.addWidget(self._qr_label)

        qr_group.setLayout(qr_layout)
        main_layout.addWidget(qr_group)

        # --- 设备信息 ---
        info_group = QGroupBox("设备反馈信息")
        info_form = QFormLayout()

        self._strength_a_label = QLabel("--")
        info_form.addRow("A 通道强度:", self._strength_a_label)

        self._strength_b_label = QLabel("--")
        info_form.addRow("B 通道强度:", self._strength_b_label)

        self._limit_a_label = QLabel("--")
        info_form.addRow("A 通道上限:", self._limit_a_label)

        self._limit_b_label = QLabel("--")
        info_form.addRow("B 通道上限:", self._limit_b_label)

        info_group.setLayout(info_form)
        main_layout.addWidget(info_group)

        # --- 使用教程（可折叠） ---
        self._help_group = QGroupBox("使用教程")
        self._help_group.setCheckable(True)
        self._help_group.setChecked(False)
        help_layout = QVBoxLayout()

        help_text = QLabel(
            "<b>快速开始：</b><br>"
            "1. 确保手机和电脑在同一局域网 (WiFi)<br>"
            "2. 选择「内置服务器」模式，点击「启动服务器」<br>"
            "3. 打开 DG-LAB App → 扫描屏幕上的二维码<br>"
            "4. 等待绑定成功，即可开始使用<br><br>"
            "<b>远程服务器模式：</b><br>"
            "如果使用第三方 WebSocket 服务器，选择「远程服务器」，"
            "输入服务器地址后点击「连接」。<br><br>"
            "<b>网络要求：</b><br>"
            "• 内置服务器：手机和电脑需在同一局域网<br>"
            "• 确保防火墙放行对应端口 (默认 5678)<br>"
            "• 如连接失败，尝试关闭 VPN 或代理<br><br>"
            "<b>常见问题：</b><br>"
            "• 扫码后无响应：检查网络连通性，确认 IP 和端口正确<br>"
            "• 频繁断开：检查 WiFi 信号稳定性<br>"
            "• 端口被占用：更换其他端口号"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-size: 12px; padding: 8px;")
        help_text.setTextFormat(Qt.TextFormat.RichText)
        help_layout.addWidget(help_text)

        self._help_group.setLayout(help_layout)
        main_layout.addWidget(self._help_group)

        main_layout.addStretch()

        # Initialize mode display
        self._on_mode_changed(True)

    def _on_mode_changed(self, _checked):
        is_local = self._local_radio.isChecked()
        self._local_group.setVisible(is_local)
        self._remote_group.setVisible(not is_local)

    def _on_start_server(self):
        if self._connected:
            self.disconnect_requested.emit()
        else:
            host = self._host_edit.text().strip() or "0.0.0.0"
            port = self._port_spin.value()
            qr_ip = self._local_ip_edit.text().strip()
            self.connect_local_requested.emit(host, port, qr_ip)

    def _on_connect_clicked(self):
        if self._connected:
            self.disconnect_requested.emit()
        else:
            url = self._url_edit.text().strip()
            if url:
                self.connect_requested.emit(url)

    def update_local_ip(self, ip: str):
        """更新自动检测到的本机 IP（显示为占位提示文字）"""
        self._local_ip_edit.setPlaceholderText(f"自动检测: {ip}")

    def show_qrcode(self, pixmap: QPixmap):
        """显示二维码图片"""
        scaled = pixmap.scaled(
            200, 200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._qr_label.setPixmap(scaled)

    def set_status(self, text: str, connected: bool):
        """更新连接状态显示"""
        self._connected = connected
        self._status_label.setText(text)
        if connected:
            self._status_label.setStyleSheet("color: #FF69B4; font-weight: bold;")
            self._connect_btn.setText("断开")
            self._start_server_btn.setText("断开服务器")
            self._url_edit.setEnabled(False)
            self._host_edit.setEnabled(False)
            self._port_spin.setEnabled(False)
            self._local_ip_edit.setEnabled(False)
        else:
            self._status_label.setStyleSheet("color: #C71585; font-weight: bold;")
            self._connect_btn.setText("连接")
            self._start_server_btn.setText("启动服务器")
            self._url_edit.setEnabled(True)
            self._host_edit.setEnabled(True)
            self._port_spin.setEnabled(True)
            self._local_ip_edit.setEnabled(True)

    def update_strength_info(self, a: int, b: int, a_limit: int, b_limit: int):
        """更新设备强度反馈信息"""
        self._strength_a_label.setText(str(a))
        self._strength_b_label.setText(str(b))
        self._limit_a_label.setText(str(a_limit))
        self._limit_b_label.setText(str(b_limit))

    @property
    def url(self) -> str:
        return self._url_edit.text().strip()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def get_config(self) -> dict:
        """获取连接配置"""
        return {
            "mode": "local" if self._local_radio.isChecked() else "remote",
            "host": self._host_edit.text().strip(),
            "port": self._port_spin.value(),
            "qr_ip": self._local_ip_edit.text().strip(),
            "remote_url": self._url_edit.text().strip(),
        }

    def set_config(self, config: dict):
        """从配置字典恢复连接设置"""
        mode = config.get("mode", "local")
        self._local_radio.blockSignals(True)
        self._remote_radio.blockSignals(True)
        if mode == "remote":
            self._remote_radio.setChecked(True)
        else:
            self._local_radio.setChecked(True)
        self._local_radio.blockSignals(False)
        self._remote_radio.blockSignals(False)
        self._on_mode_changed(True)

        self._host_edit.setText(config.get("host", "0.0.0.0"))
        self._port_spin.setValue(config.get("port", 5678))
        self._local_ip_edit.setText(config.get("qr_ip", ""))
        self._url_edit.setText(config.get("remote_url", "ws://192.168.1.1:5678"))
