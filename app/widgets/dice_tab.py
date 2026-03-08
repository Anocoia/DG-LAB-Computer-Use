"""骰子配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QProgressBar
)
from PyQt6.QtCore import pyqtSignal, Qt


class DiceTab(QWidget):
    """骰子随机惩罚配置标签页"""

    roll_requested = pyqtSignal()
    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("掷骰子随机触发惩罚效果，可自定义惩罚池，支持俄罗斯轮盘模式。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 启用开关 ---
        self._enable_cb = QCheckBox("启用骰子惩罚")
        self._enable_cb.stateChanged.connect(self._emit_config)
        main_layout.addWidget(self._enable_cb)

        # --- 掷骰子 ---
        roll_group = QGroupBox("掷骰子")
        roll_layout = QVBoxLayout()

        self._roll_btn = QPushButton("\U0001f3b2 掷骰子")
        self._roll_btn.setMinimumHeight(50)
        self._roll_btn.setStyleSheet("font-size: 18px; font-weight: bold;")
        self._roll_btn.clicked.connect(self.roll_requested.emit)
        roll_layout.addWidget(self._roll_btn)

        self._result_label = QLabel("等待掷骰子...")
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #333;")
        roll_layout.addWidget(self._result_label)

        roll_group.setLayout(roll_layout)
        main_layout.addWidget(roll_group)

        # --- 惩罚池 ---
        pool_group = QGroupBox("惩罚池")
        pool_layout = QVBoxLayout()

        self._pool_table = QTableWidget(0, 5)
        self._pool_table.setHorizontalHeaderLabels([
            "名称", "强度", "持续时间", "波形", "操作"
        ])
        header = self._pool_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._pool_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        pool_layout.addWidget(self._pool_table)

        add_btn = QPushButton("添加惩罚")
        add_btn.clicked.connect(self._add_punishment)
        pool_layout.addWidget(add_btn)

        pool_group.setLayout(pool_layout)
        main_layout.addWidget(pool_group)

        # --- 俄罗斯轮盘 ---
        roulette_group = QGroupBox("俄罗斯轮盘")
        roulette_form = QFormLayout()

        self._roulette_cb = QCheckBox("启用轮盘模式")
        self._roulette_cb.setToolTip("启用后每次掷骰子有概率触发高强度惩罚，类似俄罗斯轮盘")
        self._roulette_cb.stateChanged.connect(self._emit_config)
        roulette_form.addRow(self._roulette_cb)

        self._prob_slider, self._prob_label = self._create_slider(0, 100, 50)
        self._prob_label.setText("50%")
        self._prob_slider.valueChanged.connect(
            lambda v: self._prob_label.setText(f"{v}%")
        )
        roulette_form.addRow("触发概率:", self._make_slider_row(self._prob_slider, self._prob_label))

        self._roulette_str_slider, self._roulette_str_label = self._create_slider(0, 100, 60)
        roulette_form.addRow("轮盘强度:", self._make_slider_row(self._roulette_str_slider, self._roulette_str_label))

        roulette_group.setLayout(roulette_form)
        main_layout.addWidget(roulette_group)

        # --- 冷却与通道 ---
        misc_group = QGroupBox("其他设置")
        misc_form = QFormLayout()

        self._cooldown_spin = QSpinBox()
        self._cooldown_spin.setRange(0, 300)
        self._cooldown_spin.setValue(10)
        self._cooldown_spin.setSuffix(" 秒")
        self._cooldown_spin.valueChanged.connect(self._emit_config)
        misc_form.addRow("冷却时间:", self._cooldown_spin)

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._emit_config)
        misc_form.addRow("通道:", self._channel_combo)

        misc_group.setLayout(misc_form)
        main_layout.addWidget(misc_group)

        # --- 冷却进度 ---
        cooldown_group = QGroupBox("冷却状态")
        cooldown_layout = QVBoxLayout()

        self._cooldown_bar = QProgressBar()
        self._cooldown_bar.setRange(0, 100)
        self._cooldown_bar.setValue(0)
        self._cooldown_bar.setFormat("就绪")
        cooldown_layout.addWidget(self._cooldown_bar)

        cooldown_group.setLayout(cooldown_layout)
        main_layout.addWidget(cooldown_group)

        main_layout.addStretch()

        # Populate table with default punishments
        self._load_default_punishments()

    def _create_slider(self, min_val: int, max_val: int, default: int):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)

        label = QLabel(str(default))
        label.setMinimumWidth(40)
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

    def _add_punishment(self):
        self._add_punishment_row("惩罚 {}".format(self._pool_table.rowCount() + 1), 50, 3, "默认")
        self._emit_config()

    def _add_punishment_row(self, name: str, strength: int, duration: int, waveform: str):
        """Add a single punishment row to the table."""
        row = self._pool_table.rowCount()
        self._pool_table.insertRow(row)

        # 名称
        self._pool_table.setItem(row, 0, QTableWidgetItem(name))

        # 强度
        str_spin = QSpinBox()
        str_spin.setRange(0, 100)
        str_spin.setValue(strength)
        self._pool_table.setCellWidget(row, 1, str_spin)

        # 持续时间
        dur_spin = QSpinBox()
        dur_spin.setRange(1, 60)
        dur_spin.setValue(duration)
        dur_spin.setSuffix(" 秒")
        self._pool_table.setCellWidget(row, 2, dur_spin)

        # 波形
        wave_combo = QComboBox()
        wave_combo.addItems(["默认", "呼吸", "潮汐", "脉冲", "渐强"])
        wf_idx = wave_combo.findText(waveform)
        if wf_idx >= 0:
            wave_combo.setCurrentIndex(wf_idx)
        self._pool_table.setCellWidget(row, 3, wave_combo)

        # 删除
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda checked, r=row: self._remove_punishment(r))
        self._pool_table.setCellWidget(row, 4, del_btn)

    def _load_default_punishments(self):
        """Populate the table with default punishment entries."""
        defaults = [
            ("轻击", 20, 2, "脉冲"),
            ("中击", 50, 3, "默认"),
            ("重击", 80, 4, "默认"),
            ("电击", 100, 2, "默认"),
        ]
        for name, strength, duration, waveform in defaults:
            self._add_punishment_row(name, strength, duration, waveform)

    def _remove_punishment(self, row: int):
        self._pool_table.removeRow(row)
        # 重新绑定删除按钮索引
        for r in range(self._pool_table.rowCount()):
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, rr=r: self._remove_punishment(rr))
            self._pool_table.setCellWidget(r, 4, del_btn)
        self._emit_config()

    def _emit_config(self, *_args):
        self.config_changed.emit(self.get_config())

    def set_result(self, text: str):
        """设置掷骰子结果显示"""
        self._result_label.setText(text)

    def set_cooldown_progress(self, remaining: float, total: float):
        """更新冷却进度条"""
        if remaining <= 0:
            self._cooldown_bar.setValue(0)
            self._cooldown_bar.setFormat("就绪")
            self._roll_btn.setEnabled(True)
        else:
            pct = int((remaining / total) * 100)
            self._cooldown_bar.setValue(pct)
            self._cooldown_bar.setFormat(f"冷却中 {remaining:.0f}s")
            self._roll_btn.setEnabled(False)

    def get_config(self) -> dict:
        """获取完整骰子配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        punishments = []
        for r in range(self._pool_table.rowCount()):
            name_item = self._pool_table.item(r, 0)
            str_widget = self._pool_table.cellWidget(r, 1)
            dur_widget = self._pool_table.cellWidget(r, 2)
            wave_widget = self._pool_table.cellWidget(r, 3)
            if name_item and str_widget and dur_widget and wave_widget:
                punishments.append({
                    "name": name_item.text(),
                    "strength": str_widget.value(),
                    "duration": dur_widget.value(),
                    "waveform": wave_widget.currentText(),
                })

        return {
            "enabled": self._enable_cb.isChecked(),
            "roulette_mode": self._roulette_cb.isChecked(),
            "roulette_probability": self._prob_slider.value(),
            "roulette_strength": self._roulette_str_slider.value(),
            "cooldown": self._cooldown_spin.value(),
            "punishments": punishments,
            "channel": channel,
        }

    @property
    def roulette_mode(self) -> bool:
        return self._roulette_cb.isChecked()

    @property
    def cooldown(self) -> int:
        return self._cooldown_spin.value()

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

        # Rebuild pool table
        self._pool_table.setRowCount(0)
        for p in config.get("punishments", []):
            row = self._pool_table.rowCount()
            self._pool_table.insertRow(row)

            self._pool_table.setItem(row, 0, QTableWidgetItem(p.get("name", "")))

            str_spin = QSpinBox()
            str_spin.setRange(0, 100)
            str_spin.setValue(p.get("strength", 50))
            self._pool_table.setCellWidget(row, 1, str_spin)

            dur_spin = QSpinBox()
            dur_spin.setRange(1, 60)
            dur_spin.setValue(p.get("duration", 3))
            dur_spin.setSuffix(" 秒")
            self._pool_table.setCellWidget(row, 2, dur_spin)

            wave_combo = QComboBox()
            wave_combo.addItems(["默认", "呼吸", "潮汐", "脉冲", "渐强"])
            wf = p.get("waveform", "默认")
            wf_idx = wave_combo.findText(wf)
            if wf_idx >= 0:
                wave_combo.setCurrentIndex(wf_idx)
            self._pool_table.setCellWidget(row, 3, wave_combo)

            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, r=row: self._remove_punishment(r))
            self._pool_table.setCellWidget(row, 4, del_btn)

        self._roulette_cb.blockSignals(True)
        self._roulette_cb.setChecked(config.get("roulette_mode", False))
        self._roulette_cb.blockSignals(False)

        self._prob_slider.blockSignals(True)
        self._prob_slider.setValue(config.get("roulette_probability", 50))
        self._prob_label.setText(f"{self._prob_slider.value()}%")
        self._prob_slider.blockSignals(False)

        self._roulette_str_slider.blockSignals(True)
        self._roulette_str_slider.setValue(config.get("roulette_strength", 60))
        self._roulette_str_label.setText(str(self._roulette_str_slider.value()))
        self._roulette_str_slider.blockSignals(False)

        self._cooldown_spin.blockSignals(True)
        self._cooldown_spin.setValue(config.get("cooldown", 10))
        self._cooldown_spin.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
