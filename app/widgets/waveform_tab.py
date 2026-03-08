"""波形编辑标签页 — 关键帧编辑器"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QComboBox, QSlider, QLabel, QPushButton, QSpinBox,
)
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QPointF
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPainterPath, QPolygonF

from app.waveform import PRESET_WAVEFORMS, interpolate_keyframes


class WaveformPreview(QWidget):
    """波形可视化预览 — 强度曲线"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strengths = [50]
        self.setMinimumHeight(100)
        self.setMaximumHeight(130)

    def set_data(self, strengths: list):
        self._strengths = strengths if strengths else [0]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        pad = 10
        chart_w = w - pad * 2
        chart_h = h - pad * 2 - 16

        # Background
        painter.setPen(QPen(QColor(255, 182, 193), 1))
        painter.setBrush(QColor(255, 250, 252))
        painter.drawRoundedRect(0, 0, w, h, 6, 6)

        n = len(self._strengths)
        if n == 0:
            painter.end()
            return

        # Build points
        points = []
        for i, s in enumerate(self._strengths):
            x = pad + (i / max(n - 1, 1)) * chart_w
            y = pad + chart_h - (s / 100.0) * chart_h
            points.append(QPointF(x, y))

        # Filled area
        polygon = QPolygonF()
        polygon.append(QPointF(pad, pad + chart_h))
        for p in points:
            polygon.append(p)
        polygon.append(QPointF(pad + chart_w, pad + chart_h))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 182, 193, 80))
        painter.drawPolygon(polygon)

        # Curve line
        if len(points) > 1:
            path = QPainterPath()
            path.moveTo(points[0])
            for p in points[1:]:
                path.lineTo(p)
            painter.setPen(QPen(QColor(199, 21, 133), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # Duration label
        painter.setPen(QColor(100, 100, 100))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        total_ms = n * 100
        if total_ms >= 1000:
            time_str = f"{total_ms / 1000:.1f}s"
        else:
            time_str = f"{total_ms}ms"
        painter.drawText(
            QRect(pad, h - 14, chart_w, 12),
            Qt.AlignmentFlag.AlignRight, f"时长: {time_str}",
        )

        painter.end()


class WaveformTab(QWidget):
    """波形参数编辑与预设选择标签页"""

    waveform_changed = pyqtSignal(str, object)  # (channel, data_dict)
    preset_selected = pyqtSignal(str)
    playback_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._keyframe_rows = []  # [(QSpinBox, QSlider, QLabel, QHBoxLayout)]
        self._updating_preset = False
        self._init_ui()

    # ──────────────────────────────────────────────
    # UI construction
    # ──────────────────────────────────────────────

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # --- 功能描述 ---
        desc = QLabel(
            "编辑输出波形。定义关键帧控制点，系统在相邻关键帧之间"
            "线性插值生成平滑波形。低频率 (10) 产生持续平滑输出。"
        )
        desc.setObjectName("tabDescription")
        desc.setWordWrap(True)
        main_layout.addWidget(desc)

        # --- 预设选择 ---
        preset_group = QGroupBox("波形预设")
        preset_layout = QVBoxLayout()

        preset_form = QFormLayout()
        self._preset_combo = QComboBox()
        self._preset_combo.setToolTip("选择预设波形，或手动编辑关键帧后自动切换为「自定义」")
        self._preset_combo.addItem("自定义")
        for preset in PRESET_WAVEFORMS:
            self._preset_combo.addItem(preset.display_name)
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_form.addRow("预设波形:", self._preset_combo)
        preset_layout.addLayout(preset_form)

        self._preset_desc_label = QLabel("")
        self._preset_desc_label.setWordWrap(True)
        self._preset_desc_label.setStyleSheet(
            "color: #999; font-size: 11px; padding: 4px 8px; font-style: italic;"
        )
        preset_layout.addWidget(self._preset_desc_label)

        preset_group.setLayout(preset_layout)
        main_layout.addWidget(preset_group)

        # --- 波形预览 ---
        preview_group = QGroupBox("波形预览")
        preview_layout = QVBoxLayout()
        self._preview = WaveformPreview()
        preview_layout.addWidget(self._preview)
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)

        # --- 基础频率 ---
        freq_group = QGroupBox("基础频率")
        freq_layout = QFormLayout()

        freq_row = QHBoxLayout()
        self._freq_slider = QSlider(Qt.Orientation.Horizontal)
        self._freq_slider.setRange(10, 100)
        self._freq_slider.setValue(10)
        self._freq_slider.setToolTip(
            "基础频率 (10-100)\n值越低体感越平滑，值越高颗粒感越强"
        )
        self._freq_label = QLabel("10")
        self._freq_label.setMinimumWidth(30)
        self._freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._freq_slider.valueChanged.connect(
            lambda v: (self._freq_label.setText(str(v)), self._on_editor_changed())
        )
        freq_row.addWidget(self._freq_slider)
        freq_row.addWidget(self._freq_label)
        freq_layout.addRow("频率:", freq_row)

        freq_hint = QLabel("低频 (10) = 平滑持续输出　　高频 (100) = 颗粒感")
        freq_hint.setStyleSheet("color: #888; font-size: 11px;")
        freq_layout.addRow(freq_hint)

        freq_group.setLayout(freq_layout)
        main_layout.addWidget(freq_group)

        # --- 关键帧编辑 ---
        kf_group = QGroupBox("关键帧编辑")
        kf_layout = QVBoxLayout()

        kf_hint = QLabel(
            "每个关键帧定义一个过渡：在指定步数内线性过渡到目标强度。\n"
            "波形从强度 0 开始，依次过渡到各关键帧的目标值。"
        )
        kf_hint.setStyleSheet("color: #888; font-size: 11px; padding: 2px;")
        kf_hint.setWordWrap(True)
        kf_layout.addWidget(kf_hint)

        header = QHBoxLayout()
        h1 = QLabel("步数 (×100ms)")
        h1.setMinimumWidth(90)
        header.addWidget(h1)
        header.addWidget(QLabel("目标强度 (%)"), 1)
        kf_layout.addLayout(header)

        self._keyframes_layout = QVBoxLayout()
        self._keyframes_layout.setSpacing(4)
        kf_layout.addLayout(self._keyframes_layout)

        btn_layout = QHBoxLayout()
        self._add_kf_btn = QPushButton("+ 添加关键帧")
        self._add_kf_btn.clicked.connect(lambda: (self._add_keyframe_row(), self._on_editor_changed()))
        btn_layout.addWidget(self._add_kf_btn)

        self._del_kf_btn = QPushButton("- 删除最后")
        self._del_kf_btn.clicked.connect(self._remove_last_keyframe)
        btn_layout.addWidget(self._del_kf_btn)
        kf_layout.addLayout(btn_layout)

        self._duration_label = QLabel("总时长: —")
        self._duration_label.setStyleSheet("color: #888; font-size: 11px;")
        kf_layout.addWidget(self._duration_label)

        kf_group.setLayout(kf_layout)
        main_layout.addWidget(kf_group)

        # Default keyframes (breathing-like)
        self._add_keyframe_row(20, 80)
        self._add_keyframe_row(20, 1)

        # --- 播放控制 ---
        playback_group = QGroupBox("播放控制")
        playback_form = QFormLayout()

        self._playback_mode_combo = QComboBox()
        self._playback_mode_combo.addItems(["循环", "单次", "往返"])
        self._playback_mode_combo.setToolTip(
            "循环：到末尾后从头重放\n单次：播放一遍后停在末尾\n往返：到末尾后反向播放"
        )
        self._playback_mode_combo.currentIndexChanged.connect(self._on_playback_ui_changed)
        playback_form.addRow("播放模式:", self._playback_mode_combo)

        speed_layout = QHBoxLayout()
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(25, 400)
        self._speed_slider.setValue(100)
        self._speed_slider.setToolTip("播放速度 (0.25x~4.00x)\n<1.0 变慢，>1.0 变快")
        self._speed_label = QLabel("1.00x")
        self._speed_label.setMinimumWidth(50)
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._speed_slider.valueChanged.connect(self._on_speed_slider_changed)
        speed_layout.addWidget(self._speed_slider)
        speed_layout.addWidget(self._speed_label)
        playback_form.addRow("播放速度:", speed_layout)

        playback_group.setLayout(playback_form)
        main_layout.addWidget(playback_group)

        # --- 通道与应用 ---
        apply_group = QGroupBox("应用设置")
        apply_form = QFormLayout()

        self._channel_combo = QComboBox()
        self._channel_combo.addItems(["A 通道", "B 通道", "AB 通道"])
        self._channel_combo.setToolTip("选择波形应用到哪个通道")
        apply_form.addRow("目标通道:", self._channel_combo)

        btn_layout2 = QHBoxLayout()
        self._apply_a_btn = QPushButton("应用波形到 A")
        self._apply_a_btn.clicked.connect(lambda: self._on_apply("A"))
        btn_layout2.addWidget(self._apply_a_btn)

        self._apply_b_btn = QPushButton("应用波形到 B")
        self._apply_b_btn.clicked.connect(lambda: self._on_apply("B"))
        btn_layout2.addWidget(self._apply_b_btn)

        apply_form.addRow(btn_layout2)
        apply_group.setLayout(apply_form)
        main_layout.addWidget(apply_group)

        main_layout.addStretch()

        # Initial preview
        self._update_preview()

    # ──────────────────────────────────────────────
    # Keyframe row management
    # ──────────────────────────────────────────────

    def _add_keyframe_row(self, steps: int = 5, strength: int = 50):
        row = QHBoxLayout()

        spin = QSpinBox()
        spin.setRange(1, 200)
        spin.setValue(steps)
        spin.setMinimumWidth(80)
        spin.setToolTip("到达目标强度需要的步数 (每步 100ms)")
        spin.valueChanged.connect(self._on_editor_changed)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        slider.setValue(strength)
        slider.valueChanged.connect(self._on_editor_changed)

        label = QLabel(str(strength))
        label.setMinimumWidth(30)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        slider.valueChanged.connect(lambda v: label.setText(str(v)))

        row.addWidget(spin)
        row.addWidget(slider, 1)
        row.addWidget(label)

        self._keyframes_layout.addLayout(row)
        self._keyframe_rows.append((spin, slider, label, row))

    def _remove_last_keyframe(self):
        if len(self._keyframe_rows) <= 1:
            return
        spin, slider, label, row = self._keyframe_rows.pop()
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._keyframes_layout.removeItem(row)
        self._on_editor_changed()

    def _clear_keyframe_rows(self):
        while self._keyframe_rows:
            spin, slider, label, row = self._keyframe_rows.pop()
            while row.count():
                item = row.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._keyframes_layout.removeItem(row)

    def _get_keyframes(self) -> list:
        return [(spin.value(), slider.value())
                for spin, slider, _label, _row in self._keyframe_rows]

    def _set_keyframes(self, keyframes: list):
        """Replace all keyframe rows with new data."""
        self._clear_keyframe_rows()
        for steps, strength in keyframes:
            self._add_keyframe_row(steps, strength)

    # ──────────────────────────────────────────────
    # Callbacks
    # ──────────────────────────────────────────────

    def _on_editor_changed(self):
        """Keyframe or frequency changed by user."""
        if not self._updating_preset:
            self._preset_combo.blockSignals(True)
            self._preset_combo.setCurrentText("自定义")
            self._preset_desc_label.setText("")
            self._preset_combo.blockSignals(False)
        self._update_preview()

    def _on_preset_changed(self, name: str):
        if name == "自定义":
            self._preset_desc_label.setText("")
            return

        for preset in PRESET_WAVEFORMS:
            if preset.display_name == name:
                self._preset_desc_label.setText(preset.description)
                self._updating_preset = True
                self._freq_slider.setValue(preset.frequency)
                self._set_keyframes(preset.keyframes)
                self._updating_preset = False
                self._update_preview()
                self.preset_selected.emit(name)
                return

    def _update_preview(self):
        keyframes = self._get_keyframes()
        strengths = interpolate_keyframes(keyframes)
        self._preview.set_data(strengths)

        total_ms = len(strengths) * 100
        if total_ms >= 1000:
            self._duration_label.setText(
                f"总时长: {total_ms / 1000:.1f}s ({len(strengths)} 段)"
            )
        else:
            self._duration_label.setText(
                f"总时长: {total_ms}ms ({len(strengths)} 段)"
            )

    def _on_speed_slider_changed(self, value: int):
        self._speed_label.setText(f"{value / 100:.2f}x")
        self._on_playback_ui_changed()

    def _on_playback_ui_changed(self, _=None):
        mode_map = {"循环": "loop", "单次": "once", "往返": "pingpong"}
        mode_text = self._playback_mode_combo.currentText()
        self.playback_changed.emit({
            "mode": mode_map.get(mode_text, "loop"),
            "speed": self._speed_slider.value() / 100.0,
        })

    def _on_apply(self, channel: str):
        data = self.get_waveform_data()
        self.waveform_changed.emit(channel, data)

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def get_waveform_data(self) -> dict:
        return {
            "frequency": self._freq_slider.value(),
            "keyframes": self._get_keyframes(),
        }

    @property
    def selected_channel(self) -> str:
        text = self._channel_combo.currentText()
        if "A" in text and "B" in text:
            return "AB"
        elif "A" in text:
            return "A"
        return "B"

    def get_config(self) -> dict:
        return {
            "preset": self._preset_combo.currentText(),
            "frequency": self._freq_slider.value(),
            "keyframes": self._get_keyframes(),
            "channel": self._channel_combo.currentText(),
            "playback_mode": self._playback_mode_combo.currentText(),
            "playback_speed": self._speed_slider.value(),
        }

    def set_config(self, config: dict):
        preset = config.get("preset", "自定义")
        self._preset_combo.blockSignals(True)
        idx = self._preset_combo.findText(preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)

        # Frequency
        self._freq_slider.blockSignals(True)
        self._freq_slider.setValue(config.get("frequency", 10))
        self._freq_label.setText(str(self._freq_slider.value()))
        self._freq_slider.blockSignals(False)

        # Keyframes (backward compatible: old configs won't have this)
        if "keyframes" in config:
            self._updating_preset = True
            self._set_keyframes(config["keyframes"])
            self._updating_preset = False

        # Channel
        ch_text = config.get("channel", "A 通道")
        self._channel_combo.blockSignals(True)
        ch_idx = self._channel_combo.findText(ch_text)
        if ch_idx >= 0:
            self._channel_combo.setCurrentIndex(ch_idx)
        self._channel_combo.blockSignals(False)

        # Playback controls
        pb_mode = config.get("playback_mode", "循环")
        self._playback_mode_combo.blockSignals(True)
        pb_idx = self._playback_mode_combo.findText(pb_mode)
        if pb_idx >= 0:
            self._playback_mode_combo.setCurrentIndex(pb_idx)
        self._playback_mode_combo.blockSignals(False)

        pb_speed = config.get("playback_speed", 100)
        self._speed_slider.blockSignals(True)
        self._speed_slider.setValue(pb_speed)
        self._speed_label.setText(f"{pb_speed / 100:.2f}x")
        self._speed_slider.blockSignals(False)

        self._update_preview()
