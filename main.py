"""DG-LAB 电脑互动控制器 - 入口"""
import sys
import asyncio
import logging

from PyQt6.QtWidgets import QApplication
from qasync import QEventLoop

from app.main_window import MainWindow


def main():
    # 日志配置：控制台 INFO，文件 DEBUG
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 控制台：INFO 级别
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # 文件：DEBUG 级别，保留完整日志
    # file_handler = logging.FileHandler("dg-lab-debug.log", encoding="utf-8", mode="w")
    # file_handler.setLevel(logging.DEBUG)
    # file_handler.setFormatter(fmt)
    # root_logger.addHandler(file_handler)

    logging.getLogger(__name__).info("========== DG-LAB 电脑互动控制器启动 ==========")

    app = QApplication(sys.argv)
    app.setApplicationName("DG-LAB 电脑互动控制器")
    app.setStyle("Fusion")

    # ── 粉色现代化主题 ──
    app.setStyleSheet("""
        /* 主背景 */
        QWidget {
            background-color: #FFF0F5;
            color: #333333;
            font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
        }

        /* 分组框 */
        QGroupBox {
            border: 1px solid #FFB6C1;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
            background-color: #FFFAFC;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: #C71585;
            font-weight: bold;
        }

        /* 按钮 */
        QPushButton {
            background-color: #FF69B4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #FF85C2;
        }
        QPushButton:pressed {
            background-color: #DB4C9A;
        }
        QPushButton:disabled {
            background-color: #FFCCE0;
            color: #FFFFFF99;
        }

        /* 滑块 */
        QSlider::groove:horizontal {
            border: 1px solid #FFB6C1;
            height: 6px;
            background: #FFD1E8;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #FF69B4;
            border: 1px solid #FF69B4;
            width: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }
        QSlider::handle:horizontal:hover {
            background: #FF85C2;
        }
        QSlider::sub-page:horizontal {
            background: #FF69B4;
            border-radius: 3px;
        }

        /* 输入框 */
        QLineEdit, QSpinBox {
            border: 1px solid #FFB6C1;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: white;
        }
        QLineEdit:focus, QSpinBox:focus {
            border: 2px solid #FF69B4;
        }

        /* 下拉框 */
        QComboBox {
            border: 1px solid #FFB6C1;
            border-radius: 4px;
            padding: 4px 8px;
            background-color: white;
        }
        QComboBox:focus {
            border: 2px solid #FF69B4;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        QComboBox QAbstractItemView {
            border: 1px solid #FFB6C1;
            background-color: white;
            selection-background-color: #FF69B4;
            selection-color: white;
        }

        /* 列表 */
        QListWidget {
            border: 1px solid #FFB6C1;
            border-radius: 4px;
            background-color: white;
            outline: none;
        }
        QListWidget::item {
            padding: 6px 10px;
            border-bottom: 1px solid #FFF0F5;
        }
        QListWidget::item:selected {
            background-color: #FF69B4;
            color: white;
        }
        QListWidget::item:hover:!selected {
            background-color: #FFE4EF;
        }

        /* 表格 */
        QTableWidget {
            border: 1px solid #FFB6C1;
            gridline-color: #FFD1E8;
            background-color: white;
        }
        QTableWidget::item:selected {
            background-color: #FF69B4;
            color: white;
        }
        QHeaderView::section {
            background-color: #FFE4EF;
            border: 1px solid #FFB6C1;
            padding: 4px;
            color: #C71585;
            font-weight: bold;
        }

        /* 复选框 */
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border: 2px solid #FFB6C1;
            border-radius: 3px;
            background-color: white;
        }
        QCheckBox::indicator:checked {
            background-color: #FF69B4;
            border-color: #FF69B4;
        }

        /* 单选按钮 */
        QRadioButton::indicator {
            width: 16px;
            height: 16px;
            border: 2px solid #FFB6C1;
            border-radius: 9px;
            background-color: white;
        }
        QRadioButton::indicator:checked {
            background-color: #FF69B4;
            border-color: #FF69B4;
        }

        /* 进度条 */
        QProgressBar {
            border: 1px solid #FFB6C1;
            border-radius: 4px;
            text-align: center;
            background-color: #FFD1E8;
        }
        QProgressBar::chunk {
            background-color: #FF69B4;
            border-radius: 3px;
        }

        /* 状态栏 */
        QStatusBar {
            background-color: #FFE4EF;
            border-top: 1px solid #FFB6C1;
            color: #C71585;
        }

        /* 滚动区域 */
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QScrollBar:vertical {
            border: none;
            background: #FFF0F5;
            width: 8px;
        }
        QScrollBar::handle:vertical {
            background: #FFB6C1;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background: #FF69B4;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        /* Tab 描述标签 */
        QLabel#tabDescription {
            border-left: 3px solid #FF69B4;
            background-color: #FFF5F8;
            padding: 8px 12px;
            color: #888888;
            font-size: 12px;
        }
    """)

    # Replace the default event loop with qasync's loop
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
