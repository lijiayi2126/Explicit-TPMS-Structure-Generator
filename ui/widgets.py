from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QComboBox, QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QSlider, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from .density import SLIDER_STEPS


class BlueSelectedComboBox(QComboBox):
    """Combo box that highlights the selected item in blue."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(_BlueSelectedDelegate(self))
        self.currentIndexChanged.connect(self._update_edit_color)

    def _update_edit_color(self):
        self.setStyleSheet("""
            QComboBox {
                border: 1px solid #c0c8d8;
                border-radius: 4px;
                padding: 2px 6px;
                background: white;
                color: #1565C0;
                font-weight: bold;
                height: 26px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                color: #222;
                font-weight: normal;
                selection-background-color: #ddeeff;
                selection-color: #1565C0;
            }
        """)


class _BlueSelectedDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        combo = self.parent()
        if index.row() == combo.currentIndex():
            option.palette.setColor(option.palette.Text, QColor("#1565C0"))
            from PyQt5.QtGui import QFont
            font = option.font
            font.setBold(True)
            option.font = font


def make_slider_row(color: str, lbl_min: str, lbl_max: str):
    """Return a slider row container and its QSlider instance."""
    container = QWidget()
    h = QHBoxLayout(container)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)

    label_style = "color: #999; font-size: 10px;"

    left = QLabel(lbl_min)
    left.setStyleSheet(label_style)
    left.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    left.setFixedWidth(36)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, SLIDER_STEPS)
    slider.setFixedHeight(18)
    slider.setStyleSheet(f"""
        QSlider::groove:horizontal {{
            height: 4px; background: #dde3ee; border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {color}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            width: 13px; height: 13px; margin: -5px 0;
            border-radius: 6px;
            background: {color}; border: 2px solid white;
        }}
    """)

    right = QLabel(lbl_max)
    right.setStyleSheet(label_style)
    right.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    right.setFixedWidth(36)

    h.addWidget(left)
    h.addWidget(slider, stretch=1)
    h.addWidget(right)
    return container, slider


def form_row(label_text: str, widget, label_width: int = 130):
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    label = QLabel(label_text)
    label.setFixedWidth(label_width)
    h.addWidget(label)
    h.addWidget(widget)
    return row


def divider():
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #d0d8e8; margin: 3px 0;")
    return line


def group_box(title: str) -> QGroupBox:
    box = QGroupBox(title)
    box.setStyleSheet("""
        QGroupBox {
            border: 1px solid #c8d0de;
            border-radius: 6px;
            background: white;
            padding: 8px;
            margin-top: 6px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            color: #444;
            font-weight: bold;
        }
    """)
    box.setLayout(QVBoxLayout())
    box.layout().setSpacing(4)
    return box


def line_edit(default: str) -> QLineEdit:
    edit = QLineEdit(default)
    edit.setFixedHeight(26)
    edit.setStyleSheet("""
        QLineEdit {
            border: 1px solid #c0c8d8;
            border-radius: 4px;
            padding: 2px 6px;
            background: white;
        }
    """)
    return edit


def parameter_row(label: str, edit: QLineEdit, slider_row_widget: QWidget) -> QWidget:
    """Stack an edit row above a matching slider row."""
    container = QWidget()
    v = QVBoxLayout(container)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(2)

    top = QWidget()
    h = QHBoxLayout(top)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)
    label_widget = QLabel(label)
    label_widget.setFixedWidth(100)
    h.addWidget(label_widget)
    h.addWidget(edit)

    v.addWidget(top)
    v.addWidget(slider_row_widget)
    return container
