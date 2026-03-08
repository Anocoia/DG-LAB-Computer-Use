"""闲置惩罚配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class IdleTab(QWidget):
    """用户闲置检测与惩罚配置标签页"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("检测无操作状态，闲置超过阈值后强度逐渐增加，活动恢复后减弱。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 基本设置 ---
        basic_group = QGroupBox("基本设置")
        basic_form = QFormLayout()

        self._enable_cb = QCheckBox("启用闲置惩罚")
        self._enable_cb.setToolTip("开启后，无鼠标/键盘操作时会逐渐增加输出强度")
        self._enable_cb.stateChanged.connect(self._emit_config)
        basic_form.addRow(self._enable_cb)

        self._threshold_spin = QSpinBox()
        self._threshold_spin.setRange(5, 300)
        self._threshold_spin.setValue(30)
        self._threshold_spin.setSuffix(" 秒")
        self._threshold_spin.setToolTip("无操作超过此时间后开始增加强度")
        self._threshold_spin.valueChanged.connect(self._emit_config)
        basic_form.addRow("闲置阈值:", self._threshold_spin)

        basic_group.setLayout(basic_form)
        main_layout.addWidget(basic_group)

        # --- 增长设置 ---
        growth_group = QGroupBox("强度增长")
        growth_form = QFormLayout()

        self._growth_combo = QComboBox()
        self._growth_combo.addItems(["线性", "指数"])
        self._growth_combo.currentIndexChanged.connect(self._emit_config)
        growth_form.addRow("增长模式:", self._growth_combo)

        self._max_str_slider, self._max_str_label = self._create_slider(0, 100, 80)
        growth_form.addRow("最大强度:", self._make_slider_row(self._max_str_slider, self._max_str_label))

        growth_group.setLayout(growth_form)
        main_layout.addWidget(growth_group)

        # --- 恢复设置 ---
        recovery_group = QGroupBox("恢复设置")
        recovery_form = QFormLayout()

        self._recovery_combo = QComboBox()
        self._recovery_combo.addItems(["立即恢复", "渐进恢复"])
        self._recovery_combo.currentIndexChanged.connect(self._emit_config)
        recovery_form.addRow("恢复模式:", self._recovery_combo)

        self._recovery_speed = QSpinBox()
        self._recovery_speed.setRange(1, 30)
        self._recovery_speed.setValue(5)
        self._recovery_speed.setSuffix(" 秒")
        self._recovery_speed.valueChanged.connect(self._emit_config)
        recovery_form.addRow("恢复速度:", self._recovery_speed)

        recovery_group.setLayout(recovery_form)
        main_layout.addWidget(recovery_group)

        # --- 通道设置 ---
        channel_group = QGroupBox("通道设置")
        channel_form = QFormLayout()

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._emit_config)
        channel_form.addRow("目标通道:", self._channel_combo)

        channel_group.setLayout(channel_form)
        main_layout.addWidget(channel_group)

        # --- 状态显示 ---
        status_group = QGroupBox("当前状态")
        status_form = QFormLayout()

        self._idle_time_label = QLabel("0 秒")
        self._idle_time_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        status_form.addRow("闲置时间:", self._idle_time_label)

        status_group.setLayout(status_form)
        main_layout.addWidget(status_group)

        main_layout.addStretch()

    def _create_slider(self, min_val: int, max_val: int, default: int):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)

        label = QLabel(str(default))
        label.setMinimumWidth(35)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        slider.valueChanged.connect(lambda v: label.setText(str(v)))
        slider.valueChanged.connect(self._emit_config)
        return slider, label

    @staticmethod
    def _make_slider_row(slider: QSlider, label: QLabel) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(slider)
        layout.addWidget(label)
        return w

    def _emit_config(self, *_args):
        self.config_changed.emit(self.get_config())

    def update_idle_time(self, seconds: float):
        """更新闲置时间显示"""
        self._idle_time_label.setText(f"{seconds:.0f} 秒")

    def get_config(self) -> dict:
        """获取完整闲置惩罚配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        return {
            "enabled": self._enable_cb.isChecked(),
            "idle_threshold": self._threshold_spin.value(),
            "growth_mode": self._growth_combo.currentText(),
            "max_strength": self._max_str_slider.value(),
            "recovery_mode": self._recovery_combo.currentText(),
            "recovery_speed": self._recovery_speed.value(),
            "channel": channel,
        }

    @property
    def enabled(self) -> bool:
        return self._enable_cb.isChecked()

    @property
    def idle_threshold(self) -> int:
        return self._threshold_spin.value()

    @property
    def max_strength(self) -> int:
        return self._max_str_slider.value()

    @property
    def channel(self) -> str:
        text = self._channel_combo.currentText()
        if "AB" in text:
            return "AB"
        elif "A" in text:
            return "A"
        return "B"

    def set_config(self, config: dict):
        """从配置字典恢复所有 UI 控件"""
        self._enable_cb.blockSignals(True)
        self._enable_cb.setChecked(config.get("enabled", False))
        self._enable_cb.blockSignals(False)

        self._threshold_spin.blockSignals(True)
        self._threshold_spin.setValue(config.get("idle_threshold", 30))
        self._threshold_spin.blockSignals(False)

        growth = config.get("growth_mode", "线性")
        growth_idx = 1 if growth == "指数" else 0
        self._growth_combo.blockSignals(True)
        self._growth_combo.setCurrentIndex(growth_idx)
        self._growth_combo.blockSignals(False)

        self._max_str_slider.blockSignals(True)
        self._max_str_slider.setValue(config.get("max_strength", 80))
        self._max_str_label.setText(str(self._max_str_slider.value()))
        self._max_str_slider.blockSignals(False)

        recovery = config.get("recovery_mode", "立即恢复")
        recovery_idx = 1 if recovery == "渐进恢复" else 0
        self._recovery_combo.blockSignals(True)
        self._recovery_combo.setCurrentIndex(recovery_idx)
        self._recovery_combo.blockSignals(False)

        self._recovery_speed.blockSignals(True)
        self._recovery_speed.setValue(config.get("recovery_speed", 5))
        self._recovery_speed.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
