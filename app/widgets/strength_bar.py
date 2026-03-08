"""强度实时显示条组件"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont, QPen


class StrengthBar(QWidget):
    """水平强度显示条，使用绿/黄/红渐变并叠加数值文字"""

    def __init__(self, parent=None, label: str = "", max_value: int = 200):
        super().__init__(parent)
        self._value = 0
        self._max_value = max_value
        self._label = label
        self._color = None  # None = 自动渐变色
        self.setMinimumHeight(28)
        self.setMaximumHeight(36)

    @property
    def value(self) -> int:
        return self._value

    @value.setter
    def value(self, v: int):
        v = max(0, min(v, self._max_value))
        if v != self._value:
            self._value = v
            self.update()

    @property
    def max_value(self) -> int:
        return self._max_value

    @max_value.setter
    def max_value(self, v: int):
        self._max_value = max(1, v)
        self.update()

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, text: str):
        self._label = text
        self.update()

    @property
    def color(self) -> QColor | None:
        return self._color

    @color.setter
    def color(self, c: QColor | None):
        self._color = c
        self.update()

    def _get_bar_color(self, percentage: float) -> QColor:
        """根据百分比返回浅粉/热粉/深紫红渐变色"""
        if self._color is not None:
            return self._color
        if percentage < 0.5:
            # 浅粉(255,182,193) -> 热粉(255,105,180)
            t = percentage / 0.5
            r = 255
            g = int(182 + (105 - 182) * t)
            b = int(193 + (180 - 193) * t)
        else:
            # 热粉(255,105,180) -> 深紫红(199,21,133)
            t = (percentage - 0.5) / 0.5
            r = int(255 + (199 - 255) * t)
            g = int(105 + (21 - 105) * t)
            b = int(180 + (133 - 180) * t)
        return QColor(r, g, b)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin = 2

        # 背景
        painter.setPen(QPen(QColor(255, 182, 193), 1))
        painter.setBrush(QColor(255, 240, 245))
        painter.drawRoundedRect(margin, margin, w - 2 * margin, h - 2 * margin, 4, 4)

        # 填充条
        if self._max_value > 0 and self._value > 0:
            pct = self._value / self._max_value
            bar_w = int((w - 2 * margin - 2) * pct)
            bar_rect = QRect(margin + 1, margin + 1, bar_w, h - 2 * margin - 2)

            bar_color = self._get_bar_color(pct)
            gradient = QLinearGradient(0, 0, 0, h)
            gradient.setColorAt(0.0, bar_color.lighter(120))
            gradient.setColorAt(1.0, bar_color)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(bar_rect, 3, 3)

        # 文字
        painter.setPen(QColor(30, 30, 30))
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        text = f"{self._label}  {self._value} / {self._max_value}" if self._label else f"{self._value} / {self._max_value}"
        painter.drawText(
            QRect(margin + 6, 0, w - 2 * margin - 12, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            text,
        )

        painter.end()
