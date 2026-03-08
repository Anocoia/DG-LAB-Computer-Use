"""打字节奏配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class RhythmTab(QWidget):
    """打字节奏检测与强度映射配置标签页"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("打字速度映射为输出强度，特殊按键触发额外脉冲，持续打字可获得加成。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 基本设置 ---
        basic_group = QGroupBox("基本设置")
        basic_form = QFormLayout()

        self._enable_cb = QCheckBox("启用打字节奏")
        self._enable_cb.setToolTip("开启后根据打字速度实时调整输出强度")
        self._enable_cb.stateChanged.connect(self._emit_config)
        basic_form.addRow(self._enable_cb)

        self._base_slider, self._base_label = self._create_slider(0, 100, 20)
        basic_form.addRow("基础强度:", self._make_slider_row(self._base_slider, self._base_label))

        basic_group.setLayout(basic_form)
        main_layout.addWidget(basic_group)

        # --- 速度设置 ---
        speed_group = QGroupBox("速度映射")
        speed_form = QFormLayout()

        self._speed_slider, self._speed_label = self._create_slider(1, 10, 3)
        speed_form.addRow("速度倍率:", self._make_slider_row(self._speed_slider, self._speed_label))

        speed_group.setLayout(speed_form)
        main_layout.addWidget(speed_group)

        # --- 特殊按键 ---
        special_group = QGroupBox("特殊按键 (Enter/Space/Backspace)")
        special_form = QFormLayout()

        self._special_slider, self._special_label = self._create_slider(0, 100, 40)
        special_form.addRow("特殊按键强度:", self._make_slider_row(self._special_slider, self._special_label))

        special_group.setLayout(special_form)
        main_layout.addWidget(special_group)

        # --- 持续打字加成 ---
        sustained_group = QGroupBox("持续打字加成")
        sustained_form = QFormLayout()

        self._sustained_cb = QCheckBox("启用持续打字加成")
        self._sustained_cb.setToolTip("连续打字超过阈值时间后获得额外强度加成")
        self._sustained_cb.stateChanged.connect(self._emit_config)
        sustained_form.addRow(self._sustained_cb)

        self._sustained_threshold = QSpinBox()
        self._sustained_threshold.setRange(1, 60)
        self._sustained_threshold.setValue(10)
        self._sustained_threshold.setSuffix(" 秒")
        self._sustained_threshold.valueChanged.connect(self._emit_config)
        sustained_form.addRow("持续阈值:", self._sustained_threshold)

        self._sustained_slider, self._sustained_label = self._create_slider(0, 100, 30)
        sustained_form.addRow("加成强度:", self._make_slider_row(self._sustained_slider, self._sustained_label))

        sustained_group.setLayout(sustained_form)
        main_layout.addWidget(sustained_group)

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

        self._typing_speed_label = QLabel("0 次/分钟")
        self._typing_speed_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        status_form.addRow("打字速度:", self._typing_speed_label)

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

    def update_typing_speed(self, speed: float):
        """更新打字速度显示"""
        self._typing_speed_label.setText(f"{speed:.0f} 次/分钟")

    def get_config(self) -> dict:
        """获取完整打字节奏配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        return {
            "enabled": self._enable_cb.isChecked(),
            "base_strength": self._base_slider.value(),
            "speed_multiplier": self._speed_slider.value(),
            "special_key_strength": self._special_slider.value(),
            "sustained_typing": self._sustained_cb.isChecked(),
            "sustained_threshold": self._sustained_threshold.value(),
            "sustained_bonus": self._sustained_slider.value(),
            "channel": channel,
        }

    @property
    def enabled(self) -> bool:
        return self._enable_cb.isChecked()

    @property
    def base_strength(self) -> int:
        return self._base_slider.value()

    @property
    def speed_multiplier(self) -> int:
        return self._speed_slider.value()

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

        self._base_slider.blockSignals(True)
        self._base_slider.setValue(config.get("base_strength", 20))
        self._base_label.setText(str(self._base_slider.value()))
        self._base_slider.blockSignals(False)

        self._speed_slider.blockSignals(True)
        self._speed_slider.setValue(config.get("speed_multiplier", 3))
        self._speed_label.setText(str(self._speed_slider.value()))
        self._speed_slider.blockSignals(False)

        self._special_slider.blockSignals(True)
        self._special_slider.setValue(config.get("special_key_strength", 40))
        self._special_label.setText(str(self._special_slider.value()))
        self._special_slider.blockSignals(False)

        self._sustained_cb.blockSignals(True)
        self._sustained_cb.setChecked(config.get("sustained_typing", False))
        self._sustained_cb.blockSignals(False)

        self._sustained_threshold.blockSignals(True)
        self._sustained_threshold.setValue(config.get("sustained_threshold", 10))
        self._sustained_threshold.blockSignals(False)

        self._sustained_slider.blockSignals(True)
        self._sustained_slider.setValue(config.get("sustained_bonus", 30))
        self._sustained_label.setText(str(self._sustained_slider.value()))
        self._sustained_slider.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
