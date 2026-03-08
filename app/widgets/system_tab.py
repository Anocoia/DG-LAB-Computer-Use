"""系统监控配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class _SourceConfig(QGroupBox):
    """单个监控源的配置组件"""

    changed = pyqtSignal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._init_ui()

    def _init_ui(self):
        form = QFormLayout()

        self._enable_cb = QCheckBox("启用")
        self._enable_cb.setToolTip("是否启用此监控源作为强度输入")
        self._enable_cb.stateChanged.connect(self._on_changed)
        form.addRow(self._enable_cb)

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("通道:", self._channel_combo)

        self._curve_combo = QComboBox()
        self._curve_combo.addItems(["线性", "指数", "阶梯"])
        self._curve_combo.setToolTip("数值到强度的映射曲线：线性=等比例，指数=高值敏感，阶梯=分档")
        self._curve_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("曲线类型:", self._curve_combo)

        weight_layout = QHBoxLayout()
        self._weight_slider = QSlider(Qt.Orientation.Horizontal)
        self._weight_slider.setRange(0, 100)
        self._weight_slider.setValue(50)
        self._weight_slider.valueChanged.connect(self._on_weight_changed)
        weight_layout.addWidget(self._weight_slider)

        self._weight_label = QLabel("0.50")
        self._weight_label.setMinimumWidth(35)
        self._weight_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        weight_layout.addWidget(self._weight_label)

        form.addRow("权重:", weight_layout)
        self.setLayout(form)

    def _on_weight_changed(self, value: int):
        self._weight_label.setText(f"{value / 100:.2f}")
        self._on_changed()

    def _on_changed(self):
        self.changed.emit()

    def get_config(self) -> dict:
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"
        return {
            "enabled": self._enable_cb.isChecked(),
            "channel": channel,
            "curve": self._curve_combo.currentText(),
            "weight": self._weight_slider.value() / 100.0,
        }

    def set_config(self, config: dict):
        self._enable_cb.blockSignals(True)
        self._enable_cb.setChecked(config.get("enabled", True))
        self._enable_cb.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        curve = config.get("curve", "线性")
        curve_map = {"线性": 0, "指数": 1, "阶梯": 2}
        self._curve_combo.blockSignals(True)
        self._curve_combo.setCurrentIndex(curve_map.get(curve, 0))
        self._curve_combo.blockSignals(False)

        weight = int(config.get("weight", 0.5) * 100)
        self._weight_slider.blockSignals(True)
        self._weight_slider.setValue(weight)
        self._weight_label.setText(f"{weight / 100:.2f}")
        self._weight_slider.blockSignals(False)

        self.changed.emit()

    @property
    def enabled(self) -> bool:
        return self._enable_cb.isChecked()


class SystemTab(QWidget):
    """系统资源监控配置标签页"""

    config_changed = pyqtSignal(dict)

    SOURCE_NAMES = {
        "cpu": "CPU 使用率",
        "memory": "内存使用率",
        "network": "网络流量",
        "disk": "磁盘使用率",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sources = {}
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("根据系统资源使用情况自动调整输出强度。CPU/内存/网络/磁盘占用越高，强度越大。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 启用开关 ---
        self._enable_cb = QCheckBox("启用系统监控")
        self._enable_cb.stateChanged.connect(self._emit_config)
        main_layout.addWidget(self._enable_cb)

        # --- 各监控源 ---
        for key, label in self.SOURCE_NAMES.items():
            source_widget = _SourceConfig(label)
            source_widget.changed.connect(self._emit_config)
            self._sources[key] = source_widget
            main_layout.addWidget(source_widget)

        # --- 采样间隔 ---
        interval_group = QGroupBox("采样设置")
        interval_form = QFormLayout()

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 10)
        self._interval_spin.setValue(2)
        self._interval_spin.setSuffix(" 秒")
        self._interval_spin.setToolTip("系统资源数据采集频率，值越小更新越快但占用更多 CPU")
        self._interval_spin.valueChanged.connect(self._emit_config)
        interval_form.addRow("采样间隔:", self._interval_spin)

        interval_group.setLayout(interval_form)
        main_layout.addWidget(interval_group)

        # --- 当前读数 ---
        readings_group = QGroupBox("当前读数")
        readings_form = QFormLayout()

        self._cpu_reading = QLabel("--")
        readings_form.addRow("CPU:", self._cpu_reading)

        self._mem_reading = QLabel("--")
        readings_form.addRow("内存:", self._mem_reading)

        self._net_reading = QLabel("--")
        readings_form.addRow("网络:", self._net_reading)

        self._disk_reading = QLabel("--")
        readings_form.addRow("磁盘:", self._disk_reading)

        readings_group.setLayout(readings_form)
        main_layout.addWidget(readings_group)

        main_layout.addStretch()

    def _emit_config(self):
        self.config_changed.emit(self.get_config())

    def get_config(self) -> dict:
        """获取完整配置字典"""
        config = {
            "enabled": self._enable_cb.isChecked(),
            "interval": self._interval_spin.value(),
            "sources": {},
        }
        for key, source in self._sources.items():
            config["sources"][key] = source.get_config()
        return config

    def update_readings(self, cpu: float, memory: float, network: float, disk: float):
        """更新当前系统读数显示"""
        self._cpu_reading.setText(f"{cpu:.1f}%")
        self._mem_reading.setText(f"{memory:.1f}%")
        self._net_reading.setText(f"{network:.1f} KB/s")
        self._disk_reading.setText(f"{disk:.1f}%")

    @property
    def sampling_interval(self) -> int:
        return self._interval_spin.value()

    def set_config(self, config: dict):
        """从配置字典恢复所有 UI 控件"""
        self._enable_cb.blockSignals(True)
        self._enable_cb.setChecked(config.get("enabled", False))
        self._enable_cb.blockSignals(False)

        sources = config.get("sources", {})
        for key, source_widget in self._sources.items():
            if key in sources:
                source_widget.set_config(sources[key])

        self._interval_spin.blockSignals(True)
        self._interval_spin.setValue(config.get("interval", 2))
        self._interval_spin.blockSignals(False)

        self._emit_config()
