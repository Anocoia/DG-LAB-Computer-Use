"""主窗口 - 整合所有组件"""
import asyncio
import json
import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QStackedWidget, QSlider, QLabel,
    QStatusBar, QGroupBox, QFormLayout, QComboBox,
    QScrollArea, QPushButton, QFileDialog, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer

from pydglab_ws import Channel

from app.connection import ConnectionManager
from app.strength_manager import StrengthManager, MixMode
from app.waveform import (
    get_preset_by_name, PRESET_WAVEFORMS,
    scale_waveform_strength, PulseOperation,
    interpolate_keyframes, pack_segments,
)

from app.monitors.system_monitor import SystemMonitor
from app.monitors.input_monitor import InputMonitor
from app.monitors.app_monitor import AppMonitor

from app.modules.system_module import SystemModule
from app.modules.input_module import InputModule
from app.modules.timer_module import TimerModule
from app.modules.idle_module import IdleModule
from app.modules.app_module import AppModule
from app.modules.rhythm_module import RhythmModule
from app.modules.dice_module import DiceModule

from app.widgets.connection_tab import ConnectionTab
from app.widgets.waveform_tab import WaveformTab
from app.widgets.system_tab import SystemTab
from app.widgets.input_tab import InputTab
from app.widgets.timer_tab import TimerTab
from app.widgets.idle_tab import IdleTab
from app.widgets.app_tab import AppTab
from app.widgets.rhythm_tab import RhythmTab
from app.widgets.dice_tab import DiceTab
from app.widgets.strength_bar import StrengthBar
from app.widgets.mini_monitor import MiniMonitor

logger = logging.getLogger(__name__)

# Module list entries: (key, display_name)
MODULE_LIST = [
    ("connection", "连接管理"),
    ("waveform", "波形编辑"),
    ("system", "系统监控"),
    ("input", "输入事件"),
    ("timer", "定时触发"),
    ("idle", "闲置惩罚"),
    ("app", "应用聚焦"),
    ("rhythm", "打字节奏"),
    ("dice", "骰子惩罚"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DG-LAB 电脑互动控制器")
        self.setMinimumSize(900, 650)

        # ── Core components ──
        self._conn = ConnectionManager(self)
        self._strength_mgr = StrengthManager(self)

        # Monitors
        self._sys_monitor = SystemMonitor(parent=self)
        self._input_monitor = InputMonitor(parent=self)
        self._app_monitor = AppMonitor(parent=self)

        # Modules
        self._system_mod = SystemModule(self._sys_monitor, parent=self)
        self._input_mod = InputModule(self._input_monitor, parent=self)
        self._timer_mod = TimerModule(parent=self)
        self._idle_mod = IdleModule(self._input_monitor, parent=self)
        self._app_mod = AppModule(self._app_monitor, parent=self)
        self._rhythm_mod = RhythmModule(self._input_monitor, parent=self)
        self._dice_mod = DiceModule(parent=self)

        self._all_modules = [
            self._system_mod, self._input_mod, self._timer_mod,
            self._idle_mod, self._app_mod, self._rhythm_mod, self._dice_mod,
        ]

        # Active waveform preset per channel
        self._active_waveform_a: str = "breathing"
        self._active_waveform_b: str = "breathing"
        # Custom pulse list per channel (used when active waveform is "_custom")
        self._custom_pulses_a: list | None = None
        self._custom_pulses_b: list | None = None

        # Waveform playback cursor state
        self._cursor_a: float = 0.0
        self._cursor_b: float = 0.0
        self._pingpong_dir_a: int = 1
        self._pingpong_dir_b: int = 1
        self._playback_mode: str = "loop"
        self._playback_speed: float = 1.0

        # Build UI
        self._build_ui()
        self._connect_signals()

        # 初始化同步：确保 StrengthManager 收到初始上限值和倍率
        self._on_limit_changed()
        self._on_multiplier_changed(self._mult_slider.value())
        self._strength_mgr.set_smoothing(self._smooth_slider.value() / 100.0)
        logger.info("MainWindow 初始化完成: 上限 A=%d B=%d, 倍率=%.2f, 平滑=%.2f",
                     self._limit_a_slider.value(), self._limit_b_slider.value(),
                     self._mult_slider.value() / 100.0,
                     self._smooth_slider.value() / 100.0)

        # Waveform feeder timer: 10 pulses = 1s data, sent every 800ms
        # keeps ~200ms buffer per cycle; queue accumulates slowly (capped at
        # 500 by the App) so output never interrupts.
        self._wave_timer = QTimer(self)
        self._wave_timer.setInterval(800)
        self._wave_timer.timeout.connect(self._feed_waveform)

        # 启动预览模式：监视器、模块、强度管理器始终运行，无需等待设备连接
        self._start_preview()

    # ──────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)

        # ── Top: global controls + strength bars ──
        top_widget = self._build_top_bar()
        root_layout.addWidget(top_widget)

        # ── Middle: sidebar + stacked config panels ──
        middle_layout = QHBoxLayout()

        self._module_list = QListWidget()
        self._module_list.setMaximumWidth(140)
        for _, display in MODULE_LIST:
            self._module_list.addItem(display)
        self._module_list.currentRowChanged.connect(self._on_module_selected)
        middle_layout.addWidget(self._module_list)

        self._stack = QStackedWidget()

        # Create tabs
        self._conn_tab = ConnectionTab()
        self._waveform_tab = WaveformTab()
        self._system_tab = SystemTab()
        self._input_tab = InputTab()
        self._timer_tab = TimerTab()
        self._idle_tab = IdleTab()
        self._app_tab = AppTab()
        self._rhythm_tab = RhythmTab()
        self._dice_tab = DiceTab()

        tabs = [
            self._conn_tab, self._waveform_tab, self._system_tab,
            self._input_tab, self._timer_tab, self._idle_tab,
            self._app_tab, self._rhythm_tab, self._dice_tab,
        ]
        for tab in tabs:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(tab)
            self._stack.addWidget(scroll)

        middle_layout.addWidget(self._stack, 1)
        root_layout.addLayout(middle_layout, 1)

        # ── Status bar ──
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("未连接")
        self._status_bar.addWidget(self._status_label, 1)

        # Select first tab
        self._module_list.setCurrentRow(0)

    def _build_top_bar(self) -> QWidget:
        top = QGroupBox("全局控制")
        layout = QVBoxLayout(top)

        # Strength bars
        bars_layout = QHBoxLayout()
        self._bar_a = StrengthBar(label="A 通道")
        self._bar_b = StrengthBar(label="B 通道")
        bars_layout.addWidget(self._bar_a)
        bars_layout.addWidget(self._bar_b)
        layout.addLayout(bars_layout)

        # Controls row
        ctrl_layout = QHBoxLayout()

        # Global limit A
        ctrl_layout.addWidget(QLabel("A 上限:"))
        self._limit_a_slider = QSlider(Qt.Orientation.Horizontal)
        self._limit_a_slider.setRange(0, 200)
        self._limit_a_slider.setValue(30)
        self._limit_a_slider.setToolTip("A 通道的最大输出强度 (0-200)，所有模块的混合结果不会超过此值")
        self._limit_a_label = QLabel("30")
        self._limit_a_slider.valueChanged.connect(
            lambda v: (self._limit_a_label.setText(str(v)), self._on_limit_changed())
        )
        ctrl_layout.addWidget(self._limit_a_slider)
        ctrl_layout.addWidget(self._limit_a_label)

        # Global limit B
        ctrl_layout.addWidget(QLabel("B 上限:"))
        self._limit_b_slider = QSlider(Qt.Orientation.Horizontal)
        self._limit_b_slider.setRange(0, 200)
        self._limit_b_slider.setValue(30)
        self._limit_b_slider.setToolTip("B 通道的最大输出强度 (0-200)，所有模块的混合结果不会超过此值")
        self._limit_b_label = QLabel("30")
        self._limit_b_slider.valueChanged.connect(
            lambda v: (self._limit_b_label.setText(str(v)), self._on_limit_changed())
        )
        ctrl_layout.addWidget(self._limit_b_slider)
        ctrl_layout.addWidget(self._limit_b_label)

        # Mix mode
        ctrl_layout.addWidget(QLabel("混合:"))
        self._mix_combo = QComboBox()
        self._mix_combo.addItems(["最大值", "叠加", "平均"])
        self._mix_combo.setToolTip("多个模块同时输出时的混合策略：最大值取最高、叠加求和、平均取均值")
        self._mix_combo.currentIndexChanged.connect(self._on_mix_changed)
        ctrl_layout.addWidget(self._mix_combo)

        # Smoothing
        ctrl_layout.addWidget(QLabel("平滑:"))
        self._smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self._smooth_slider.setRange(0, 95)
        self._smooth_slider.setValue(30)
        self._smooth_slider.setMaximumWidth(100)
        self._smooth_slider.setToolTip("强度变化的平滑系数 (0-95%)，值越大强度变化越平缓，避免突变")
        self._smooth_slider.valueChanged.connect(
            lambda v: self._strength_mgr.set_smoothing(v / 100.0)
        )
        ctrl_layout.addWidget(self._smooth_slider)

        # Global multiplier
        ctrl_layout.addWidget(QLabel("倍率:"))
        self._mult_slider = QSlider(Qt.Orientation.Horizontal)
        self._mult_slider.setRange(0, 500)   # 0.00x ~ 5.00x (值 / 100)
        self._mult_slider.setValue(100)       # 默认 1.0x
        self._mult_slider.setMaximumWidth(100)
        self._mult_slider.setToolTip("全局强度倍率 (0.00-5.00)，计算后的强度乘以此值再发送到设备")
        self._mult_label = QLabel("1.00")
        self._mult_slider.valueChanged.connect(self._on_multiplier_changed)
        ctrl_layout.addWidget(self._mult_slider)
        ctrl_layout.addWidget(self._mult_label)

        # Save/Load config buttons
        self._save_btn = QPushButton("保存配置")
        self._save_btn.clicked.connect(self._save_config)
        ctrl_layout.addWidget(self._save_btn)

        self._load_btn = QPushButton("加载配置")
        self._load_btn.clicked.connect(self._load_config)
        ctrl_layout.addWidget(self._load_btn)

        # Mini monitor toggle
        self._mini_monitor = MiniMonitor()
        self._mini_btn = QPushButton("小窗")
        self._mini_btn.clicked.connect(self._toggle_mini_monitor)
        ctrl_layout.addWidget(self._mini_btn)

        self._mini_src_cb = QCheckBox("小窗来源")
        self._mini_src_cb.setChecked(True)
        self._mini_src_cb.toggled.connect(
            lambda v: setattr(self._mini_monitor, 'show_sources', v)
        )
        ctrl_layout.addWidget(self._mini_src_cb)

        layout.addLayout(ctrl_layout)
        return top

    # ──────────────────────────────────────────────
    # Signal wiring
    # ──────────────────────────────────────────────

    def _connect_signals(self):
        # ── Connection signals ──
        self._conn_tab.connect_requested.connect(self._on_connect)
        self._conn_tab.disconnect_requested.connect(self._on_disconnect)
        self._conn_tab.connect_local_requested.connect(self._on_connect_local)
        self._conn.status_changed.connect(self._on_status)
        self._conn.bind_ready.connect(self._on_qr_ready)
        self._conn.device_bound.connect(self._on_bound)
        self._conn.disconnected.connect(self._on_disconnected)
        self._conn.strength_data.connect(self._on_strength_data)
        self._conn.error.connect(lambda e: self._status_label.setText(f"错误: {e}"))
        self._conn.server_started.connect(
            lambda ip, port: self._conn_tab.update_local_ip(ip)
        )

        # ── Strength manager ──
        self._strength_mgr.set_callback(self._send_strength)
        self._strength_mgr.final_strength_updated.connect(self._update_bars)

        # ── Module strength outputs -> manager ──
        for mod in self._all_modules:
            mod.strength_output.connect(self._on_module_output)

        # ── Waveform requests from modules ──
        self._timer_mod.waveform_request.connect(self._on_waveform_request)
        self._app_mod.waveform_request.connect(self._on_waveform_request)
        self._rhythm_mod.waveform_request.connect(self._on_waveform_request)
        self._dice_mod.waveform_request.connect(self._on_waveform_request)

        # ── Tab configs -> modules ──
        self._system_tab.config_changed.connect(self._apply_system_config)
        self._input_tab.config_changed.connect(self._apply_input_config)
        self._timer_tab.config_changed.connect(self._apply_timer_config)
        self._idle_tab.config_changed.connect(self._apply_idle_config)
        self._app_tab.config_changed.connect(self._apply_app_config)
        self._rhythm_tab.config_changed.connect(self._apply_rhythm_config)
        self._dice_tab.config_changed.connect(self._apply_dice_config)
        self._dice_tab.roll_requested.connect(self._on_dice_roll)

        # ── Waveform tab ──
        self._waveform_tab.waveform_changed.connect(self._on_waveform_manual)
        self._waveform_tab.preset_selected.connect(self._on_preset_selected)
        self._waveform_tab.playback_changed.connect(self._on_playback_changed)

        # ── Monitor live data -> tabs ──
        self._sys_monitor.cpu_updated.connect(self._update_sys_readings)
        self._app_monitor.app_changed.connect(
            lambda t, p: self._app_tab.update_current_app(f"{t} ({p})")
        )

        # Periodic UI updates
        self._ui_timer = QTimer(self)
        self._ui_timer.setInterval(1000)
        self._ui_timer.timeout.connect(self._periodic_ui_update)
        self._ui_timer.start()

    # ──────────────────────────────────────────────
    # Slots
    # ──────────────────────────────────────────────

    def _on_module_selected(self, row: int):
        self._stack.setCurrentIndex(row)

    def _on_connect(self, url: str):
        logger.info("用户请求连接远程服务器: %s", url)
        asyncio.ensure_future(self._conn.connect(url))

    def _on_connect_local(self, host: str, port: int, qr_ip: str):
        logger.info("用户请求启动内置服务器: %s:%d (QR IP: %s)", host, port, qr_ip or "自动")
        asyncio.ensure_future(self._conn.connect_local(host, port, qr_ip))

    def _on_disconnect(self):
        logger.info("用户请求断开连接")
        asyncio.ensure_future(self._conn.disconnect())

    def _on_status(self, text: str):
        self._status_label.setText(text)
        self._conn_tab.set_status(text, self._conn.is_bound)

    def _on_qr_ready(self, url: str):
        pixmap = ConnectionManager.generate_qr_pixmap(url)
        self._conn_tab.show_qrcode(pixmap)

    def _on_bound(self):
        logger.info("设备已绑定，启动波形发送")
        self._conn_tab.set_status("设备已绑定", True)
        self._wave_timer.start()
        # Pre-fill device queue with 2s of data so output starts immediately
        self._feed_waveform()
        self._feed_waveform()

    def _on_disconnected(self):
        logger.warning("连接已断开，停止波形发送")
        self._conn_tab.set_status("连接断开", False)
        self._wave_timer.stop()

    def _on_strength_data(self, data):
        self._conn_tab.update_strength_info(
            data.a, data.b, data.a_limit, data.b_limit
        )
        # 注意：不再用设备上限覆盖 StrengthBar 的 max_value
        # StrengthBar 的 max_value 由软件上限滑块控制
        logger.debug("设备反馈: A=%d B=%d 设备上限=(%d,%d)",
                      data.a, data.b, data.a_limit, data.b_limit)

    def _on_module_output(self, name: str, val_a: float, val_b: float):
        self._strength_mgr.update_module(name, val_a, val_b)

    def _on_limit_changed(self):
        a = self._limit_a_slider.value()
        b = self._limit_b_slider.value()
        self._strength_mgr.set_global_limit(a, b)
        # 同步 StrengthBar 的最大值显示
        self._bar_a.max_value = a
        self._bar_b.max_value = b
        # 同步小窗的最大值
        self._mini_monitor.update_strength(
            self._bar_a.value, self._bar_b.value, a, b
        )
        logger.debug("上限已更新: A=%d B=%d", a, b)

    def _on_multiplier_changed(self, v: int):
        mult = v / 100.0
        self._mult_label.setText(f"{mult:.2f}")
        self._strength_mgr.set_multiplier(mult)
        logger.debug("全局倍率已更新: %.2f", mult)

    def _on_mix_changed(self, idx: int):
        modes = [MixMode.MAX, MixMode.SUM, MixMode.AVG]
        self._strength_mgr.set_mix_mode(modes[idx])

    def _update_bars(self, a: int, b: int):
        self._bar_a.value = a
        self._bar_b.value = b
        self._mini_monitor.update_strength(
            a, b, self._bar_a.max_value, self._bar_b.max_value
        )
        # 将模块归一化输出转换为实际强度数值
        limit_a = self._limit_a_slider.value()
        limit_b = self._limit_b_slider.value()
        mult = self._mult_slider.value() / 100.0
        raw = self._strength_mgr.get_active_sources()
        display = {
            name: (
                min(200, int(va * limit_a * mult)),
                min(200, int(vb * limit_b * mult)),
            )
            for name, (va, vb) in raw.items()
        }
        self._mini_monitor.update_sources(display)

    def _toggle_mini_monitor(self):
        if self._mini_monitor.isVisible():
            self._mini_monitor.hide()
        else:
            self._mini_monitor.show()

    # ── Waveform handling ──

    def _on_waveform_request(self, name: str):
        self._active_waveform_a = name
        self._active_waveform_b = name
        self._cursor_a = 0.0
        self._cursor_b = 0.0
        self._pingpong_dir_a = 1
        self._pingpong_dir_b = 1
        # Clear old buffered data and push new waveform immediately
        if self._conn.is_bound:
            asyncio.ensure_future(self._clear_and_refeed())

    def _on_waveform_manual(self, channel: str, data: dict):
        freq = data.get("frequency", 10)
        keyframes = data.get("keyframes", [(1, 50)])
        strengths = interpolate_keyframes(keyframes)
        pulses = pack_segments(freq, strengths)
        if channel in ("A", "AB"):
            self._active_waveform_a = "_custom"
            self._custom_pulses_a = pulses
            self._cursor_a = 0.0
            self._pingpong_dir_a = 1
        if channel in ("B", "AB"):
            self._active_waveform_b = "_custom"
            self._custom_pulses_b = pulses
            self._cursor_b = 0.0
            self._pingpong_dir_b = 1
        # Clear old buffered data and push new waveform immediately
        if self._conn.is_bound:
            asyncio.ensure_future(self._clear_and_refeed(channel))

    def _on_preset_selected(self, name: str):
        # Find preset by display name and activate it
        for preset in PRESET_WAVEFORMS:
            if preset.display_name == name:
                channel = self._waveform_tab.selected_channel
                if channel in ("A", "AB"):
                    self._active_waveform_a = preset.name
                    self._cursor_a = 0.0
                    self._pingpong_dir_a = 1
                if channel in ("B", "AB"):
                    self._active_waveform_b = preset.name
                    self._cursor_b = 0.0
                    self._pingpong_dir_b = 1
                # Clear old buffered data and push new waveform immediately
                if self._conn.is_bound:
                    asyncio.ensure_future(self._clear_and_refeed(channel))
                return

    def _feed_waveform(self):
        """Periodically feed waveform pulses using cursor-based playback."""
        if not self._conn.is_bound:
            return
        for ch, name, custom_pulses, cursor_attr, dir_attr in [
            (Channel.A, self._active_waveform_a, self._custom_pulses_a,
             "_cursor_a", "_pingpong_dir_a"),
            (Channel.B, self._active_waveform_b, self._custom_pulses_b,
             "_cursor_b", "_pingpong_dir_b"),
        ]:
            pulses = self._sample_pulses(name, custom_pulses, cursor_attr, dir_attr)
            if pulses:
                asyncio.ensure_future(self._conn.add_pulses_batch(ch, pulses))

    def _sample_pulses(self, name: str, custom_pulses, cursor_attr: str,
                       dir_attr: str) -> list:
        """从当前游标位置采样 10 个脉冲（1s 数据）并推进游标。"""
        # Resolve pulse list from preset or custom
        if name == "_custom":
            pulse_list = custom_pulses
        else:
            preset = get_preset_by_name(name)
            pulse_list = preset.pulses if preset else None

        if not pulse_list:
            return []

        total = len(pulse_list)
        cursor = getattr(self, cursor_attr)
        direction = getattr(self, dir_attr)
        speed = self._playback_speed
        mode = self._playback_mode

        sampled = []
        for _ in range(10):
            idx = int(cursor) % total
            sampled.append(pulse_list[idx])

            # Advance cursor
            cursor += speed * direction

            if mode == "loop":
                cursor = cursor % total
            elif mode == "once":
                if cursor >= total:
                    cursor = total - 1
                elif cursor < 0:
                    cursor = 0
            elif mode == "pingpong":
                if cursor >= total:
                    cursor = 2 * total - cursor - 2
                    if cursor < 0:
                        cursor = 0
                    direction = -1
                elif cursor < 0:
                    cursor = -cursor
                    if cursor >= total:
                        cursor = total - 1
                    direction = 1

        setattr(self, cursor_attr, cursor)
        setattr(self, dir_attr, direction)
        return sampled

    def _on_playback_changed(self, config: dict):
        self._playback_mode = config.get("mode", "loop")
        self._playback_speed = config.get("speed", 1.0)

    async def _clear_and_refeed(self, channel: str = "AB"):
        """Clear pulse queue for the given channel(s) and immediately push new data."""
        if channel in ("A", "AB"):
            await self._conn.clear_pulses(Channel.A)
        if channel in ("B", "AB"):
            await self._conn.clear_pulses(Channel.B)
        self._feed_waveform()

    # ── Dice ──

    def _on_dice_roll(self):
        result = self._dice_mod.roll()
        if result is None:
            self._dice_tab.set_result("冷却中...")
        else:
            self._dice_tab.set_result(
                f"{result.name}  强度:{result.strength:.0%}  "
                f"持续:{result.duration:.0f}秒"
            )

    # ── Config apply methods ──

    def _apply_system_config(self, config: dict):
        self._system_mod.enabled = config.get("enabled", False)
        curve_map = {"线性": "linear", "指数": "exponential", "阶梯": "step"}
        sources = config.get("sources", {})
        for key, src_cfg in sources.items():
            sub = getattr(self._system_mod, key.replace("memory", "mem").replace("network", "net"), None)
            if sub is None:
                # Try direct mapping
                attr_map = {"cpu": "cpu", "memory": "mem", "network": "net", "disk": "disk"}
                sub = getattr(self._system_mod, attr_map.get(key, key), None)
            if sub:
                sub.enabled = src_cfg.get("enabled", True)
                sub.channel = src_cfg.get("channel", "AB")
                sub.curve = curve_map.get(src_cfg.get("curve", "线性"), "linear")
                sub.weight = src_cfg.get("weight", 1.0)

        interval = config.get("interval", 2)
        self._sys_monitor.set_interval(float(interval))

    def _apply_input_config(self, config: dict):
        self._input_mod.enabled = config.get("enabled", False)
        mouse = config.get("mouse", {})
        self._input_mod.mouse_click_enabled = (
            mouse.get("left", {}).get("enabled", True)
            or mouse.get("right", {}).get("enabled", False)
            or mouse.get("middle", {}).get("enabled", False)
        )
        self._input_mod.click_strengths["left"] = mouse.get("left", {}).get("strength", 30) / 100.0
        self._input_mod.click_strengths["right"] = mouse.get("right", {}).get("strength", 20) / 100.0
        self._input_mod.click_strengths["middle"] = mouse.get("middle", {}).get("strength", 10) / 100.0
        self._input_mod.mouse_move_enabled = mouse.get("move", {}).get("enabled", False)
        self._input_mod.mouse_scroll_enabled = mouse.get("scroll", {}).get("enabled", False)
        self._input_mod.scroll_strength = mouse.get("scroll", {}).get("strength", 20) / 100.0

        kb = config.get("keyboard", {})
        self._input_mod.key_press_enabled = kb.get("enabled", False)
        self._input_mod.key_strength = kb.get("strength", 20) / 100.0

        # Specific key rules
        self._input_mod.specific_keys.clear()
        for rule in kb.get("key_rules", []):
            self._input_mod.specific_keys[rule["key"]] = rule["strength"] / 100.0

        combo = config.get("combo", {})
        self._input_mod.combo_threshold = combo.get("threshold", 5)
        self._input_mod.combo_bonus = combo.get("bonus_strength", 30) / 100.0

        self._input_mod.channel = config.get("channel", "AB")

    def _apply_timer_config(self, config: dict):
        self._timer_mod.enabled = config.get("enabled", False)
        mode = config.get("mode", "固定间隔")
        self._timer_mod.mode = "fixed" if mode == "固定间隔" else "random"
        self._timer_mod.interval_fixed = float(config.get("fixed_interval", 30))
        self._timer_mod.interval_min = float(config.get("random_min", 10))
        self._timer_mod.interval_max = float(config.get("random_max", 60))
        self._timer_mod.strength_min = config.get("strength_min", 10) / 100.0
        self._timer_mod.strength_max = config.get("strength_max", 60) / 100.0
        self._timer_mod.duration_min = float(config.get("duration_min", 1))
        self._timer_mod.duration_max = float(config.get("duration_max", 5))
        self._timer_mod.random_waveform = config.get("random_waveform", False)
        self._timer_mod.channel = config.get("channel", "AB")

    def _apply_idle_config(self, config: dict):
        self._idle_mod.enabled = config.get("enabled", False)
        self._idle_mod.idle_threshold = float(config.get("idle_threshold", 30))
        growth = config.get("growth_mode", "线性")
        self._idle_mod.growth_mode = "exponential" if growth == "指数" else "linear"
        self._idle_mod.max_strength = config.get("max_strength", 80) / 100.0
        recovery = config.get("recovery_mode", "立即恢复")
        self._idle_mod.recovery_mode = "gradual" if recovery == "渐进恢复" else "instant"
        self._idle_mod.recovery_speed = float(config.get("recovery_speed", 5))
        self._idle_mod.channel = config.get("channel", "AB")

    def _apply_app_config(self, config: dict):
        self._app_mod.enabled = config.get("enabled", False)
        mode = config.get("mode", "黑名单")
        self._app_mod.mode = "whitelist" if mode == "白名单" else "blacklist"
        self._app_mod.switch_pulse = config.get("switch_pulse", False)
        self._app_mod.switch_strength = config.get("switch_strength", 30) / 100.0
        self._app_mod.channel = config.get("channel", "AB")

        self._app_mod.clear_rules()
        for rule in config.get("rules", []):
            is_regex = rule.get("pattern_type", "关键字") == "正则表达式"
            self._app_mod.add_rule(
                pattern=rule.get("keyword", ""),
                is_regex=is_regex,
                strength=rule.get("strength", 30) / 100.0,
                waveform=rule.get("waveform", ""),
                channel=rule.get("channel", "AB"),
            )

    def _apply_rhythm_config(self, config: dict):
        self._rhythm_mod.enabled = config.get("enabled", False)
        self._rhythm_mod.base_strength = config.get("base_strength", 20) / 100.0
        self._rhythm_mod.speed_multiplier = float(config.get("speed_multiplier", 3))
        self._rhythm_mod.special_key_strength = config.get("special_key_strength", 40) / 100.0
        if config.get("sustained_typing", False):
            self._rhythm_mod.sustained_bonus = config.get("sustained_bonus", 30) / 100.0
        else:
            self._rhythm_mod.sustained_bonus = 0.0
        self._rhythm_mod.sustained_threshold = float(config.get("sustained_threshold", 10))
        self._rhythm_mod.channel = config.get("channel", "AB")

    def _apply_dice_config(self, config: dict):
        self._dice_mod.enabled = config.get("enabled", False)
        self._dice_mod.roulette_mode = config.get("roulette_mode", False)
        self._dice_mod.roulette_probability = config.get("roulette_probability", 50) / 100.0
        self._dice_mod.roulette_strength = config.get("roulette_strength", 60) / 100.0
        self._dice_mod.cooldown = float(config.get("cooldown", 10))
        self._dice_mod.channel = config.get("channel", "AB")

        # Sync punishment pool from UI table to module
        waveform_name_map = {
            "默认": "", "呼吸": "breathing", "潮汐": "tidal",
            "脉冲": "pulse", "渐强": "sawtooth",
        }
        self._dice_mod.clear_pool()
        for p in config.get("punishments", []):
            wf_display = p.get("waveform", "默认")
            self._dice_mod.add_punishment(
                name=p.get("name", "unknown"),
                strength=p.get("strength", 50) / 100.0,
                duration=float(p.get("duration", 3)),
                waveform=waveform_name_map.get(wf_display, ""),
            )

    # ── Monitor readings -> UI ──

    _last_cpu = 0.0
    _last_mem = 0.0
    _last_net = 0.0
    _last_disk = 0.0

    def _update_sys_readings(self, cpu: float):
        self._last_cpu = cpu

    def _periodic_ui_update(self):
        # Update system readings display
        import psutil
        mem = psutil.virtual_memory().percent
        self._last_mem = mem
        self._system_tab.update_readings(
            self._last_cpu, self._last_mem,
            self._last_net, self._last_disk,
        )

        # Dice cooldown
        remaining = self._dice_mod.cooldown_remaining()
        self._dice_tab.set_cooldown_progress(remaining, self._dice_mod.cooldown)

    # ── Lifecycle ──

    async def _send_strength(self, val_a: int, val_b: int):
        if not self._conn.is_bound:
            return
        await self._conn.set_strength(Channel.A, val_a)
        await self._conn.set_strength(Channel.B, val_b)

    def _start_preview(self):
        """启动监视器、模块和强度管理器（预览模式，无需设备连接）"""
        logger.info("启动预览模式...")
        self._sys_monitor.start()
        self._input_monitor.start()
        self._app_monitor.start()

        for mod in self._all_modules:
            mod.start()
            logger.debug("模块已启动: %s", mod.__class__.__name__)

        self._strength_mgr.start()
        logger.info("预览模式已启动")

    def _stop_all(self):
        """Stop everything on disconnect."""
        logger.info("停止所有组件...")
        self._wave_timer.stop()
        self._strength_mgr.stop()

        for mod in self._all_modules:
            mod.stop()
            logger.debug("模块已停止: %s", mod.__class__.__name__)

        self._sys_monitor.stop()
        self._input_monitor.stop()
        self._app_monitor.stop()

        self._bar_a.value = 0
        self._bar_b.value = 0
        logger.info("所有组件已停止")

    # ── Config save/load ──

    def get_full_config(self) -> dict:
        """收集全局控件和所有 tab 的配置"""
        mix_texts = ["最大值", "叠加", "平均"]
        return {
            "version": 1,
            "global": {
                "limit_a": self._limit_a_slider.value(),
                "limit_b": self._limit_b_slider.value(),
                "mix_mode": mix_texts[self._mix_combo.currentIndex()],
                "smoothing": self._smooth_slider.value(),
                "multiplier": self._mult_slider.value(),
            },
            "system": self._system_tab.get_config(),
            "input": self._input_tab.get_config(),
            "timer": self._timer_tab.get_config(),
            "idle": self._idle_tab.get_config(),
            "app": self._app_tab.get_config(),
            "rhythm": self._rhythm_tab.get_config(),
            "dice": self._dice_tab.get_config(),
            "waveform": self._waveform_tab.get_config(),
            "connection": self._conn_tab.get_config(),
        }

    def apply_full_config(self, config: dict):
        """从完整配置字典恢复所有控件"""
        g = config.get("global", {})

        self._limit_a_slider.blockSignals(True)
        self._limit_a_slider.setValue(g.get("limit_a", 30))
        self._limit_a_label.setText(str(self._limit_a_slider.value()))
        self._limit_a_slider.blockSignals(False)

        self._limit_b_slider.blockSignals(True)
        self._limit_b_slider.setValue(g.get("limit_b", 30))
        self._limit_b_label.setText(str(self._limit_b_slider.value()))
        self._limit_b_slider.blockSignals(False)

        self._on_limit_changed()

        mix_text = g.get("mix_mode", "最大值")
        mix_map = {"最大值": 0, "叠加": 1, "平均": 2}
        self._mix_combo.blockSignals(True)
        self._mix_combo.setCurrentIndex(mix_map.get(mix_text, 0))
        self._mix_combo.blockSignals(False)
        self._on_mix_changed(self._mix_combo.currentIndex())

        self._smooth_slider.blockSignals(True)
        self._smooth_slider.setValue(g.get("smoothing", 30))
        self._smooth_slider.blockSignals(False)
        self._strength_mgr.set_smoothing(self._smooth_slider.value() / 100.0)

        self._mult_slider.blockSignals(True)
        self._mult_slider.setValue(g.get("multiplier", 100))
        self._mult_slider.blockSignals(False)
        self._on_multiplier_changed(self._mult_slider.value())

        # Restore each tab (set_config emits config_changed -> triggers _apply_*_config)
        if "system" in config:
            self._system_tab.set_config(config["system"])
        if "input" in config:
            self._input_tab.set_config(config["input"])
        if "timer" in config:
            self._timer_tab.set_config(config["timer"])
        if "idle" in config:
            self._idle_tab.set_config(config["idle"])
        if "app" in config:
            self._app_tab.set_config(config["app"])
        if "rhythm" in config:
            self._rhythm_tab.set_config(config["rhythm"])
        if "dice" in config:
            self._dice_tab.set_config(config["dice"])
        if "waveform" in config:
            self._waveform_tab.set_config(config["waveform"])
        if "connection" in config:
            self._conn_tab.set_config(config["connection"])

        logger.info("配置已加载并应用")

    def _save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            config = self.get_full_config()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._status_label.setText(f"配置已保存: {path}")
            logger.info("配置已保存到 %s", path)
        except Exception as e:
            self._status_label.setText(f"保存失败: {e}")
            logger.exception("保存配置失败")

    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载配置", "", "JSON 文件 (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.apply_full_config(config)
            self._status_label.setText(f"配置已加载: {path}")
            logger.info("配置已从 %s 加载", path)
        except Exception as e:
            self._status_label.setText(f"加载失败: {e}")
            logger.exception("加载配置失败")

    # ── Lifecycle ──

    def closeEvent(self, event):
        self._mini_monitor.close()
        self._stop_all()
        asyncio.ensure_future(self._conn.disconnect())
        super().closeEvent(event)
