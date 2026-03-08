"""应用聚焦配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSlider,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QLineEdit, QSpinBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class AppTab(QWidget):
    """应用程序窗口聚焦规则配置标签页"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("根据前台应用匹配规则自动调整强度，支持白/黑名单和窗口切换脉冲。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 启用开关 ---
        self._enable_cb = QCheckBox("启用应用聚焦")
        self._enable_cb.stateChanged.connect(self._emit_config)
        main_layout.addWidget(self._enable_cb)

        # --- 模式设置 ---
        mode_group = QGroupBox("模式设置")
        mode_form = QFormLayout()

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["白名单", "黑名单"])
        self._mode_combo.setToolTip("白名单=仅匹配的应用触发，黑名单=匹配的应用不触发")
        self._mode_combo.currentIndexChanged.connect(self._emit_config)
        mode_form.addRow("匹配模式:", self._mode_combo)

        mode_group.setLayout(mode_form)
        main_layout.addWidget(mode_group)

        # --- 切换惩罚 ---
        switch_group = QGroupBox("窗口切换惩罚")
        switch_form = QFormLayout()

        self._switch_cb = QCheckBox("切换时触发脉冲")
        self._switch_cb.setToolTip("切换前台窗口时触发一次短暂脉冲")
        self._switch_cb.stateChanged.connect(self._emit_config)
        switch_form.addRow(self._switch_cb)

        self._switch_slider, self._switch_label = self._create_slider(0, 100, 30)
        switch_form.addRow("切换强度:", self._make_slider_row(self._switch_slider, self._switch_label))

        switch_group.setLayout(switch_form)
        main_layout.addWidget(switch_group)

        # --- 规则列表 ---
        rules_group = QGroupBox("规则列表")
        rules_layout = QVBoxLayout()

        self._rules_table = QTableWidget(0, 6)
        self._rules_table.setHorizontalHeaderLabels([
            "模式", "关键字/正则", "强度", "波形", "通道", "操作"
        ])
        header = self._rules_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._rules_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        rules_layout.addWidget(self._rules_table)

        add_btn = QPushButton("添加规则")
        add_btn.clicked.connect(self._add_rule_row)
        rules_layout.addWidget(add_btn)

        rules_group.setLayout(rules_layout)
        main_layout.addWidget(rules_group)

        # --- 当前窗口 ---
        current_group = QGroupBox("当前前台应用")
        current_form = QFormLayout()

        self._current_app_label = QLabel("--")
        self._current_app_label.setStyleSheet("font-weight: bold;")
        self._current_app_label.setWordWrap(True)
        current_form.addRow("窗口标题:", self._current_app_label)

        current_group.setLayout(current_form)
        main_layout.addWidget(current_group)

        # --- 通道设置 ---
        channel_group = QGroupBox("默认通道")
        channel_form = QFormLayout()

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._emit_config)
        channel_form.addRow("通道:", self._channel_combo)

        channel_group.setLayout(channel_form)
        main_layout.addWidget(channel_group)

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

    def _add_rule_row(self):
        row = self._rules_table.rowCount()
        self._rules_table.insertRow(row)

        # 模式列
        pattern_combo = QComboBox()
        pattern_combo.addItems(["关键字", "正则表达式"])
        self._rules_table.setCellWidget(row, 0, pattern_combo)

        # 关键字/正则列
        self._rules_table.setItem(row, 1, QTableWidgetItem(""))

        # 强度列
        strength_spin = QSpinBox()
        strength_spin.setRange(0, 100)
        strength_spin.setValue(30)
        self._rules_table.setCellWidget(row, 2, strength_spin)

        # 波形列
        wave_combo = QComboBox()
        wave_combo.addItems(["默认", "呼吸", "潮汐", "脉冲"])
        self._rules_table.setCellWidget(row, 3, wave_combo)

        # 通道列
        ch_combo = QComboBox()
        ch_combo.addItems(["A", "B", "AB"])
        self._rules_table.setCellWidget(row, 4, ch_combo)

        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda checked, r=row: self._remove_rule(r))
        self._rules_table.setCellWidget(row, 5, del_btn)

        self._emit_config()

    def _remove_rule(self, row: int):
        self._rules_table.removeRow(row)
        # 重新绑定删除按钮索引
        for r in range(self._rules_table.rowCount()):
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, rr=r: self._remove_rule(rr))
            self._rules_table.setCellWidget(r, 5, del_btn)
        self._emit_config()

    def _emit_config(self, *_args):
        self.config_changed.emit(self.get_config())

    def update_current_app(self, title: str):
        """更新当前前台应用标题"""
        self._current_app_label.setText(title)

    def get_config(self) -> dict:
        """获取完整应用聚焦配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        rules = []
        for r in range(self._rules_table.rowCount()):
            pattern_widget = self._rules_table.cellWidget(r, 0)
            keyword_item = self._rules_table.item(r, 1)
            strength_widget = self._rules_table.cellWidget(r, 2)
            wave_widget = self._rules_table.cellWidget(r, 3)
            ch_widget = self._rules_table.cellWidget(r, 4)

            if keyword_item and pattern_widget and strength_widget and wave_widget and ch_widget:
                rules.append({
                    "pattern_type": pattern_widget.currentText(),
                    "keyword": keyword_item.text(),
                    "strength": strength_widget.value(),
                    "waveform": wave_widget.currentText(),
                    "channel": ch_widget.currentText(),
                })

        return {
            "enabled": self._enable_cb.isChecked(),
            "mode": self._mode_combo.currentText(),
            "switch_pulse": self._switch_cb.isChecked(),
            "switch_strength": self._switch_slider.value(),
            "rules": rules,
            "channel": channel,
        }

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

        mode = config.get("mode", "黑名单")
        mode_idx = 0 if mode == "白名单" else 1
        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(mode_idx)
        self._mode_combo.blockSignals(False)

        self._switch_cb.blockSignals(True)
        self._switch_cb.setChecked(config.get("switch_pulse", False))
        self._switch_cb.blockSignals(False)

        self._switch_slider.blockSignals(True)
        self._switch_slider.setValue(config.get("switch_strength", 30))
        self._switch_label.setText(str(self._switch_slider.value()))
        self._switch_slider.blockSignals(False)

        # Rebuild rules table
        self._rules_table.setRowCount(0)
        for rule in config.get("rules", []):
            row = self._rules_table.rowCount()
            self._rules_table.insertRow(row)

            pattern_combo = QComboBox()
            pattern_combo.addItems(["关键字", "正则表达式"])
            pt = rule.get("pattern_type", "关键字")
            pattern_combo.setCurrentIndex(0 if pt == "关键字" else 1)
            self._rules_table.setCellWidget(row, 0, pattern_combo)

            self._rules_table.setItem(row, 1, QTableWidgetItem(rule.get("keyword", "")))

            strength_spin = QSpinBox()
            strength_spin.setRange(0, 100)
            strength_spin.setValue(rule.get("strength", 30))
            self._rules_table.setCellWidget(row, 2, strength_spin)

            wave_combo = QComboBox()
            wave_combo.addItems(["默认", "呼吸", "潮汐", "脉冲"])
            wf = rule.get("waveform", "默认")
            wf_idx = wave_combo.findText(wf)
            if wf_idx >= 0:
                wave_combo.setCurrentIndex(wf_idx)
            self._rules_table.setCellWidget(row, 3, wave_combo)

            ch_combo = QComboBox()
            ch_combo.addItems(["A", "B", "AB"])
            ch = rule.get("channel", "AB")
            ch_idx = ch_combo.findText(ch)
            if ch_idx >= 0:
                ch_combo.setCurrentIndex(ch_idx)
            self._rules_table.setCellWidget(row, 4, ch_combo)

            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, r=row: self._remove_rule(r))
            self._rules_table.setCellWidget(row, 5, del_btn)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
