"""极简置顶小窗 - 实时显示 A/B 通道强度及来源"""

from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QLinearGradient, QFont, QPen,
    QMouseEvent, QPaintEvent,
)

_NAME_MAP = {
    "system": "系统",
    "input": "输入",
    "timer": "定时",
    "idle": "闲置",
    "app": "应用",
    "rhythm": "节奏",
    "dice": "骰子",
}


class MiniMonitor(QWidget):
    """无边框置顶小窗，实时显示两通道强度条、数值和来源"""

    _BAR_AREA_H = 70    # 两个强度条区域高度
    _SRC_LINE_H = 16    # 每行来源高度
    _SRC_HEADER_H = 16  # "── 来源 ──" 行高度

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setFixedSize(220, self._BAR_AREA_H)
        self.setWindowOpacity(0.9)

        self._a = 0
        self._b = 0
        self._max_a = 30
        self._max_b = 30
        self._sources: dict[str, tuple[int, int]] = {}
        self._show_sources = True
        self._drag_pos: QPoint | None = None

        # 初始位置：屏幕右上角
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.width() - 20, geo.top() + 20)

    # ── 公开接口 ──

    def update_strength(self, a: int, b: int, max_a: int, max_b: int):
        self._a = a
        self._b = b
        self._max_a = max(1, max_a)
        self._max_b = max(1, max_b)
        self.update()

    def update_sources(self, sources: dict[str, tuple[int, int]]):
        self._sources = sources
        self._recalc_height()
        self.update()

    @property
    def show_sources(self) -> bool:
        return self._show_sources

    @show_sources.setter
    def show_sources(self, v: bool):
        self._show_sources = v
        self._recalc_height()
        self.update()

    def _recalc_height(self):
        n = len(self._sources) if self._show_sources else 0
        new_h = self._BAR_AREA_H + (self._SRC_HEADER_H + self._SRC_LINE_H * n if n else 0)
        if self.height() != new_h:
            self.setFixedHeight(new_h)

    # ── 绘制 ──

    @staticmethod
    def _bar_color(pct: float) -> QColor:
        """复用 StrengthBar 的粉色渐变逻辑"""
        if pct < 0.5:
            t = pct / 0.5
            r = 255
            g = int(182 + (105 - 182) * t)
            b = int(193 + (180 - 193) * t)
        else:
            t = (pct - 0.5) / 0.5
            r = int(255 + (199 - 255) * t)
            g = int(105 + (21 - 105) * t)
            b = int(180 + (133 - 180) * t)
        return QColor(r, g, b)

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 圆角粉色背景
        p.setPen(QPen(QColor(255, 182, 193), 1))
        p.setBrush(QColor(255, 240, 245, 230))
        p.drawRoundedRect(1, 1, w - 2, h - 2, 10, 10)

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        p.setFont(font)

        # ── 两个强度条 ──
        for i, (label, val, mx) in enumerate([
            ("A", self._a, self._max_a),
            ("B", self._b, self._max_b),
        ]):
            y = 10 + i * 28
            bar_x = 10
            bar_w = w - 20
            bar_h = 20

            # 条背景
            p.setPen(QPen(QColor(255, 182, 193), 1))
            p.setBrush(QColor(255, 250, 252))
            p.drawRoundedRect(bar_x, y, bar_w, bar_h, 4, 4)

            # 填充
            pct = min(val / mx, 1.0) if mx > 0 else 0.0
            if val > 0:
                fill_w = int((bar_w - 2) * pct)
                fill_rect = QRect(bar_x + 1, y + 1, fill_w, bar_h - 2)
                color = self._bar_color(pct)
                grad = QLinearGradient(0, y, 0, y + bar_h)
                grad.setColorAt(0.0, color.lighter(120))
                grad.setColorAt(1.0, color)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                p.drawRoundedRect(fill_rect, 3, 3)

            # 文字
            p.setPen(QColor(30, 30, 30))
            text = f"{label}: {val}/{mx}"
            p.drawText(
                QRect(bar_x + 6, y, bar_w - 12, bar_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                text,
            )

        # ── 来源列表 ──
        if self._show_sources and self._sources:
            src_y = self._BAR_AREA_H

            # 分隔标题
            font.setPointSize(8)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor(200, 150, 160))
            p.drawText(
                QRect(10, src_y, w - 20, self._SRC_HEADER_H),
                Qt.AlignmentFlag.AlignCenter,
                "── 来源 ──",
            )
            src_y += self._SRC_HEADER_H

            # 各模块输出（显示实际强度数值）
            p.setPen(QColor(80, 50, 60))
            for name, (va, vb) in self._sources.items():
                display = _NAME_MAP.get(name, name)
                line = f"{display}  A:{va}  B:{vb}"
                p.drawText(
                    QRect(14, src_y, w - 28, self._SRC_LINE_H),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    line,
                )
                src_y += self._SRC_LINE_H

        p.end()

    # ── 拖动 ──

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None

    # ── 关闭方式 ──

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.hide()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("关闭小窗", self.hide)
        menu.exec(event.globalPos())
