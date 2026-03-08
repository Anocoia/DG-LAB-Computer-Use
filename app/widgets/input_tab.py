"""输入事件配置标签页"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QCheckBox, QSlider, QLabel,
    QLineEdit, QPushButton, QSpinBox, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt


class InputTab(QWidget):
    """鼠标和键盘输入事件配置标签页"""

    config_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel("将鼠标和键盘操作映射为输出脉冲。支持按键规则和连击加成。")
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 启用开关 ---
        self._enable_cb = QCheckBox("启用输入事件")
        self._enable_cb.stateChanged.connect(self._emit_config)
        main_layout.addWidget(self._enable_cb)

        # --- 鼠标点击 ---
        click_group = QGroupBox("鼠标点击")
        click_form = QFormLayout()

        self._left_cb = QCheckBox("左键")
        self._left_cb.setChecked(True)
        self._left_cb.stateChanged.connect(self._emit_config)
        self._left_slider, self._left_label = self._create_slider(0, 100, 30)
        click_form.addRow(self._left_cb, self._make_slider_row(self._left_slider, self._left_label))

        self._right_cb = QCheckBox("右键")
        self._right_cb.stateChanged.connect(self._emit_config)
        self._right_slider, self._right_label = self._create_slider(0, 100, 20)
        click_form.addRow(self._right_cb, self._make_slider_row(self._right_slider, self._right_label))

        self._middle_cb = QCheckBox("中键")
        self._middle_cb.stateChanged.connect(self._emit_config)
        self._middle_slider, self._middle_label = self._create_slider(0, 100, 10)
        click_form.addRow(self._middle_cb, self._make_slider_row(self._middle_slider, self._middle_label))

        click_group.setLayout(click_form)
        main_layout.addWidget(click_group)

        # --- 鼠标移动 ---
        move_group = QGroupBox("鼠标移动")
        move_form = QFormLayout()

        self._move_cb = QCheckBox("启用")
        self._move_cb.stateChanged.connect(self._emit_config)
        move_form.addRow(self._move_cb)

        self._speed_slider, self._speed_label = self._create_slider(1, 100, 50)
        move_form.addRow("速度阈值:", self._make_slider_row(self._speed_slider, self._speed_label))

        move_group.setLayout(move_form)
        main_layout.addWidget(move_group)

        # --- 鼠标滚轮 ---
        scroll_group = QGroupBox("鼠标滚轮")
        scroll_form = QFormLayout()

        self._scroll_cb = QCheckBox("启用")
        self._scroll_cb.stateChanged.connect(self._emit_config)
        scroll_form.addRow(self._scroll_cb)

        self._scroll_slider, self._scroll_label = self._create_slider(0, 100, 20)
        scroll_form.addRow("强度:", self._make_slider_row(self._scroll_slider, self._scroll_label))

        scroll_group.setLayout(scroll_form)
        main_layout.addWidget(scroll_group)

        # --- 键盘 ---
        kb_group = QGroupBox("键盘")
        kb_form = QFormLayout()

        self._kb_cb = QCheckBox("启用")
        self._kb_cb.stateChanged.connect(self._emit_config)
        kb_form.addRow(self._kb_cb)

        self._kb_slider, self._kb_label = self._create_slider(0, 100, 20)
        kb_form.addRow("按键强度:", self._make_slider_row(self._kb_slider, self._kb_label))

        kb_group.setLayout(kb_form)
        main_layout.addWidget(kb_group)

        # --- 特定按键规则 ---
        key_group = QGroupBox("特定按键规则")
        key_layout = QVBoxLayout()

        add_row = QHBoxLayout()
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("按键名称 (如: Enter, Space, A)")
        add_row.addWidget(self._key_edit)

        self._key_strength_spin = QSpinBox()
        self._key_strength_spin.setRange(0, 100)
        self._key_strength_spin.setValue(50)
        self._key_strength_spin.setPrefix("强度: ")
        add_row.addWidget(self._key_strength_spin)

        self._add_key_btn = QPushButton("添加规则")
        self._add_key_btn.clicked.connect(self._add_key_rule)
        add_row.addWidget(self._add_key_btn)

        key_layout.addLayout(add_row)

        self._key_table = QTableWidget(0, 3)
        self._key_table.setHorizontalHeaderLabels(["按键", "强度", "删除"])
        self._key_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._key_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._key_table.setMaximumHeight(150)
        key_layout.addWidget(self._key_table)

        key_group.setLayout(key_layout)
        main_layout.addWidget(key_group)

        # --- 连击 ---
        combo_group = QGroupBox("连击设置")
        combo_form = QFormLayout()

        self._combo_threshold = QSpinBox()
        self._combo_threshold.setRange(2, 50)
        self._combo_threshold.setValue(5)
        self._combo_threshold.setSuffix(" 次")
        self._combo_threshold.setToolTip("在短时间内连续点击达到此次数后触发连击加成")
        self._combo_threshold.valueChanged.connect(self._emit_config)
        combo_form.addRow("连击阈值:", self._combo_threshold)

        self._combo_slider, self._combo_label = self._create_slider(0, 100, 30)
        combo_form.addRow("额外强度:", self._make_slider_row(self._combo_slider, self._combo_label))

        combo_group.setLayout(combo_form)
        main_layout.addWidget(combo_group)

        # --- 通道选择 ---
        channel_group = QGroupBox("通道设置")
        channel_form = QFormLayout()

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.currentIndexChanged.connect(self._emit_config)
        channel_form.addRow("目标通道:", self._channel_combo)

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

    def _add_key_rule(self):
        key = self._key_edit.text().strip()
        if not key:
            return
        strength = self._key_strength_spin.value()

        row = self._key_table.rowCount()
        self._key_table.insertRow(row)
        self._key_table.setItem(row, 0, QTableWidgetItem(key))
        self._key_table.setItem(row, 1, QTableWidgetItem(str(strength)))

        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda checked, r=row: self._remove_key_rule(r))
        self._key_table.setCellWidget(row, 2, del_btn)

        self._key_edit.clear()
        self._emit_config()

    def _remove_key_rule(self, row: int):
        self._key_table.removeRow(row)
        # 重新绑定删除按钮
        for r in range(self._key_table.rowCount()):
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, rr=r: self._remove_key_rule(rr))
            self._key_table.setCellWidget(r, 2, del_btn)
        self._emit_config()

    def _emit_config(self, *_args):
        self.config_changed.emit(self.get_config())

    def get_config(self) -> dict:
        """获取完整输入事件配置"""
        channel_text = self._channel_combo.currentText()
        if "AB" in channel_text:
            channel = "AB"
        elif "A" in channel_text:
            channel = "A"
        else:
            channel = "B"

        key_rules = []
        for r in range(self._key_table.rowCount()):
            key_item = self._key_table.item(r, 0)
            str_item = self._key_table.item(r, 1)
            if key_item and str_item:
                key_rules.append({
                    "key": key_item.text(),
                    "strength": int(str_item.text()),
                })

        return {
            "enabled": self._enable_cb.isChecked(),
            "mouse": {
                "left": {"enabled": self._left_cb.isChecked(), "strength": self._left_slider.value()},
                "right": {"enabled": self._right_cb.isChecked(), "strength": self._right_slider.value()},
                "middle": {"enabled": self._middle_cb.isChecked(), "strength": self._middle_slider.value()},
                "move": {"enabled": self._move_cb.isChecked(), "speed_threshold": self._speed_slider.value()},
                "scroll": {"enabled": self._scroll_cb.isChecked(), "strength": self._scroll_slider.value()},
            },
            "keyboard": {
                "enabled": self._kb_cb.isChecked(),
                "strength": self._kb_slider.value(),
                "key_rules": key_rules,
            },
            "combo": {
                "threshold": self._combo_threshold.value(),
                "bonus_strength": self._combo_slider.value(),
            },
            "channel": channel,
        }

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

        mouse = config.get("mouse", {})
        left = mouse.get("left", {})
        self._left_cb.blockSignals(True)
        self._left_cb.setChecked(left.get("enabled", True))
        self._left_cb.blockSignals(False)
        self._left_slider.blockSignals(True)
        self._left_slider.setValue(left.get("strength", 30))
        self._left_label.setText(str(self._left_slider.value()))
        self._left_slider.blockSignals(False)

        right = mouse.get("right", {})
        self._right_cb.blockSignals(True)
        self._right_cb.setChecked(right.get("enabled", False))
        self._right_cb.blockSignals(False)
        self._right_slider.blockSignals(True)
        self._right_slider.setValue(right.get("strength", 20))
        self._right_label.setText(str(self._right_slider.value()))
        self._right_slider.blockSignals(False)

        middle = mouse.get("middle", {})
        self._middle_cb.blockSignals(True)
        self._middle_cb.setChecked(middle.get("enabled", False))
        self._middle_cb.blockSignals(False)
        self._middle_slider.blockSignals(True)
        self._middle_slider.setValue(middle.get("strength", 10))
        self._middle_label.setText(str(self._middle_slider.value()))
        self._middle_slider.blockSignals(False)

        move = mouse.get("move", {})
        self._move_cb.blockSignals(True)
        self._move_cb.setChecked(move.get("enabled", False))
        self._move_cb.blockSignals(False)
        self._speed_slider.blockSignals(True)
        self._speed_slider.setValue(move.get("speed_threshold", 50))
        self._speed_label.setText(str(self._speed_slider.value()))
        self._speed_slider.blockSignals(False)

        scroll = mouse.get("scroll", {})
        self._scroll_cb.blockSignals(True)
        self._scroll_cb.setChecked(scroll.get("enabled", False))
        self._scroll_cb.blockSignals(False)
        self._scroll_slider.blockSignals(True)
        self._scroll_slider.setValue(scroll.get("strength", 20))
        self._scroll_label.setText(str(self._scroll_slider.value()))
        self._scroll_slider.blockSignals(False)

        kb = config.get("keyboard", {})
        self._kb_cb.blockSignals(True)
        self._kb_cb.setChecked(kb.get("enabled", False))
        self._kb_cb.blockSignals(False)
        self._kb_slider.blockSignals(True)
        self._kb_slider.setValue(kb.get("strength", 20))
        self._kb_label.setText(str(self._kb_slider.value()))
        self._kb_slider.blockSignals(False)

        # Rebuild key rules table
        self._key_table.setRowCount(0)
        for rule in kb.get("key_rules", []):
            row = self._key_table.rowCount()
            self._key_table.insertRow(row)
            self._key_table.setItem(row, 0, QTableWidgetItem(rule.get("key", "")))
            self._key_table.setItem(row, 1, QTableWidgetItem(str(rule.get("strength", 50))))
            del_btn = QPushButton("删除")
            del_btn.clicked.connect(lambda checked, r=row: self._remove_key_rule(r))
            self._key_table.setCellWidget(row, 2, del_btn)

        combo = config.get("combo", {})
        self._combo_threshold.blockSignals(True)
        self._combo_threshold.setValue(combo.get("threshold", 5))
        self._combo_threshold.blockSignals(False)
        self._combo_slider.blockSignals(True)
        self._combo_slider.setValue(combo.get("bonus_strength", 30))
        self._combo_label.setText(str(self._combo_slider.value()))
        self._combo_slider.blockSignals(False)

        ch = config.get("channel", "AB")
        idx = {"A": 0, "B": 1, "AB": 2}.get(ch, 2)
        self._channel_combo.blockSignals(True)
        self._channel_combo.setCurrentIndex(idx)
        self._channel_combo.blockSignals(False)

        self._emit_config()
