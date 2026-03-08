"""定时器配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class TimerTab(QWidget):
    """定时触发器配置标签页"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("按固定或随机间隔自动触发输出脉冲，实现周期性刺激。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 基本设置 ---
        basic_group = QGroupBox("基本设置")
        basic_form = QFormLayout()

        self._enable_cb = QCheckBox("启用定时器")
        self._enable_cb.setToolTip("开启后会按设定间隔自动触发输出脉冲")
        self._enable_cb.stateChanged.connect(self._emit_config)
        basic_form.addRow(self._enable_cb)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["固定间隔", "随机间隔"])
        self._mode_combo.setToolTip("固定间隔=每隔固定秒数触发，随机间隔=在最小和最大值之间随机")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        basic_form.addRow("模式:", self._mode_combo)

        basic_group.setLayout(basic_form)
        main_layout.addWidget(basic_group)

        # --- 间隔设置 ---
        interval_group = QGroupBox("间隔设置")
        interval_form = QFormLayout()

        self._fixed_interval = QSpinBox()
        self._fixed_interval.setRange(1, 300)
        self._fixed_interval.setValue(30)
        self._fixed_interval.setSuffix(" 秒")
        self._fixed_interval.valueChanged.connect(self._emit_config)
        interval_form.addRow("固定间隔:", self._fixed_interval)

        self._random_min = QSpinBox()
        self._random_min.setRange(1, 300)
        self._random_min.setValue(10)
        self._random_min.setSuffix(" 秒")
        self._random_min.valueChanged.connect(self._emit_config)
        interval_form.addRow("随机最小间隔:", self._random_min)

        self._random_max = QSpinBox()
        self._random_max.setRange(1, 300)
        self._random_max.setValue(60)
        self._random_max.setSuffix(" 秒")
        self._random_max.valueChanged.connect(self._emit_config)
        interval_form.addRow("随机最大间隔:", self._random_max)

        interval_group.setLayout(interval_form)
        main_layout.addWidget(interval_group)

        # --- 强度设置 ---
        strength_group = QGroupBox("强度设置")
        strength_form = QFormLayout()

        self._str_min_slider, self._str_min_label = self._create_slider(0, 100, 10)
        strength_form.addRow("最小强度:", self._make_slider_row(self._str_min_slider, self._str_min_label))

        self._str_max_slider, self._str_max_label = self._create_slider(0, 100, 60)
        strength_form.addRow("最大强度:", self._make_slider_row(self._str_max_slider, self._str_max_label))

        strength_group.setLayout(strength_form)
        main_layout.addWidget(strength_group)

        # --- 持续时间 ---
        duration_group = QGroupBox("持续时间")
        duration_form = QFormLayout()

        self._dur_min = QSpinBox()
        self._dur_min.setRange(1, 60)
        self._dur_min.setValue(1)
        self._dur_min.setSuffix(" 秒")
        self._dur_min.valueChanged.connect(self._emit_config)
        duration_form.addRow("最短持续:", self._dur_min)

        self._dur_max = QSpinBox()
        self._dur_max.setRange(1, 60)
        self._dur_max.setValue(5)
        self._dur_max.setSuffix(" 秒")
        self._dur_max.valueChanged.connect(self._emit_config)
        duration_form.addRow("最长持续:", self._dur_max)

        duration_group.setLayout(duration_form)
        main_layout.addWidget(duration_group)

        # --- 波形与通道 ---
        misc_group = QGroupBox("其他设置")
        misc_form = QFormLayout()

        self._random_wave_cb = QCheckBox("随机波形")
        self._random_wave_cb.stateChanged.connect(self._emit_config)
        misc_form.addRow(self._random_wave_cb)

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._emit_config)
        misc_form.addRow("通道:", self._channel_combo)

        misc_group.setLayout(misc_form)
        main_layout.addWidget(misc_group)

        main_layout.addStretch()

        # 初始化模式显示
        self._on_mode_changed(0)

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

    def _on_mode_changed(self, index: int):
        is_fixed = index == 0
        self._fixed_interval.setEnabled(is_fixed)
        self._random_min.setEnabled(not is_fixed)
        self._random_max.setEnabled(not is_fixed)
        self._emit_config()

    def _emit_config(self, *_args):
        self.config_changed.emit(self.get_config())

    def get_config(self) -> dict:
        """获取完整定时器配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        return {
            "enabled": self._enable_cb.isChecked(),
            "mode": self._mode_combo.currentText(),
            "fixed_interval": self._fixed_interval.value(),
            "random_min": self._random_min.value(),
            "random_max": self._random_max.value(),
            "strength_min": self._str_min_slider.value(),
            "strength_max": self._str_max_slider.value(),
            "duration_min": self._dur_min.value(),
            "duration_max": self._dur_max.value(),
            "random_waveform": self._random_wave_cb.isChecked(),
            "channel": channel,
        }

    @property
    def enabled(self) -> bool:
        return self._enable_cb.isChecked()

    @property
    def mode(self) -> str:
        return self._mode_combo.currentText()

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

        mode = config.get("mode", "固定间隔")
        mode_idx = 0 if mode == "固定间隔" else 1
        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(mode_idx)
        self._mode_combo.blockSignals(False)
        # Update enabled state of interval fields
        self._fixed_interval.setEnabled(mode_idx == 0)
        self._random_min.setEnabled(mode_idx == 1)
        self._random_max.setEnabled(mode_idx == 1)

        self._fixed_interval.blockSignals(True)
        self._fixed_interval.setValue(config.get("fixed_interval", 30))
        self._fixed_interval.blockSignals(False)

        self._random_min.blockSignals(True)
        self._random_min.setValue(config.get("random_min", 10))
        self._random_min.blockSignals(False)

        self._random_max.blockSignals(True)
        self._random_max.setValue(config.get("random_max", 60))
        self._random_max.blockSignals(False)

        self._str_min_slider.blockSignals(True)
        self._str_min_slider.setValue(config.get("strength_min", 10))
        self._str_min_label.setText(str(self._str_min_slider.value()))
        self._str_min_slider.blockSignals(False)

        self._str_max_slider.blockSignals(True)
        self._str_max_slider.setValue(config.get("strength_max", 60))
        self._str_max_label.setText(str(self._str_max_slider.value()))
        self._str_max_slider.blockSignals(False)

        self._dur_min.blockSignals(True)
        self._dur_min.setValue(config.get("duration_min", 1))
        self._dur_min.blockSignals(False)

        self._dur_max.blockSignals(True)
        self._dur_max.setValue(config.get("duration_max", 5))
        self._dur_max.blockSignals(False)

        self._random_wave_cb.blockSignals(True)
        self._random_wave_cb.setChecked(config.get("random_waveform", False))
        self._random_wave_cb.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
