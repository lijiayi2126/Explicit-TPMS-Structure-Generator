import sys
import time
import asyncio
import faulthandler
import os
import math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cadquery as cq

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox,
    QGroupBox, QStatusBar, QMessageBox,
    QAction, QFileDialog,
    QFrame, QStyledItemDelegate, QSlider, QCheckBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QColor

from OCP.Aspect import (
    Aspect_DisplayConnection,
    Aspect_TypeOfTriedronPosition,
)
from OCP.OpenGl import OpenGl_GraphicDriver
from OCP.V3d import V3d_Viewer
from OCP.AIS import AIS_InteractiveContext, AIS_DisplayMode, AIS_Shape
from OCP.Quantity import (
    Quantity_Color,
    Quantity_NOC_GOLD as GOLD,
)
from OCP.Graphic3d import Graphic3d_NOM_JADE, Graphic3d_MaterialAspect
from OCP.gp import gp_Trsf, gp_GTrsf, gp_Ax1, gp_Dir
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.StlAPI import StlAPI_Reader
from OCP.TopoDS import TopoDS_Shape

from Lattice_lib.schwarzP import schwarzP_Shell, schwarzP_Solid
from Lattice_lib.IWP import IWP_Shell, IWP_Solid
from Lattice_lib.Gyroid import gyroid_Shell, gyroid_Solid
from Lattice_lib.Diamond import diamond_Shell, diamond_Solid

faulthandler.enable()
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ZOOM_STEP = 0.9

TPMS_TYPES = [
    "SchwarzP-Shell", "SchwarzP-Solid",
    "IWP-Shell",      "IWP-Solid",
    "Gyroid-Shell",   "Gyroid-Solid",
    "Diamond-Shell",  "Diamond-Solid",
]

MODEL_FILTERS = (
    "CAD/Mesh Files (*.step *.stp *.iges *.igs *.brep *.brp *.stl);;"
    "STEP Files (*.step *.stp);;"
    "IGES Files (*.iges *.igs);;"
    "BREP Files (*.brep *.brp);;"
    "STL Files (*.stl);;"
    "All Files (*.*)"
)

#  Offset mapping:  w = param_w(d) = 2.5*d + 0.5
#  Solid:  d_bot = -t/2,  d_top = t/2
#          w_bot = 2.5*(-t/2) + 0.5 = -1.25*t + 0.5
#          w_top = 2.5*( t/2) + 0.5 =  1.25*t + 0.5
def d_to_w(d: float) -> float:
    """Physical offset w from normalised offset d."""
    return 2.5 * d + 0.5

def t_to_w_bot(t: float) -> float:
    return d_to_w(-t / 2)          # = -1.25*t + 0.5

def t_to_w_top(t: float) -> float:
    return d_to_w( t / 2)          # =  1.25*t + 0.5


#  Density <-> t conversion
#  Fitting: rho = a * t^b    t = (rho/a)^(1/b)
DENSITY_PARAMS = {
    "SchwarzP": {"a": 1.022,  "b": 1.092},
    "IWP":      {"a": 0.8070, "b": 1.221},
    "Gyroid":   {"a": 0.8319, "b": 1.154},
    "Diamond":  {"a": 0.5627, "b": 1.053},
}

T_MIN, T_MAX = 0.0, 0.4
SLIDER_STEPS = 1000


def t_to_rho(family: str, t: float) -> float:
    p = DENSITY_PARAMS[family]
    return p["a"] * (t ** p["b"])


def rho_to_t(family: str, rho: float) -> float:
    p = DENSITY_PARAMS[family]
    return (rho / p["a"]) ** (1.0 / p["b"])


def rho_range(family: str):
    lo = t_to_rho(family, max(T_MIN, 1e-9))
    hi = t_to_rho(family, T_MAX)
    return lo, hi


def family_from_type(t_str: str) -> str:
    for k in DENSITY_PARAMS:
        if t_str.startswith(k):
            return k
    return None


def _as_cq_shape(obj) -> cq.Shape:
    if isinstance(obj, cq.Workplane):
        return obj.val()
    if isinstance(obj, cq.Shape):
        return obj
    if hasattr(obj, "wrapped"):
        return cq.Shape(obj.wrapped)
    raise TypeError(f"Unsupported shape object: {type(obj)}")


def import_model_shape(path: str) -> cq.Shape:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".step", ".stp"):
        return _as_cq_shape(cq.importers.importStep(path))
    if ext in (".iges", ".igs"):
        if hasattr(cq.importers, "importShape"):
            return _as_cq_shape(cq.importers.importShape("IGES", path))
        raise ValueError("This CadQuery version does not expose IGES import.")
    if ext in (".brep", ".brp"):
        if hasattr(cq.importers, "importShape"):
            return _as_cq_shape(cq.importers.importShape("BREP", path))
        raise ValueError("This CadQuery version does not expose BREP import.")
    if ext == ".stl":
        if hasattr(cq.importers, "importStl"):
            return _as_cq_shape(cq.importers.importStl(path))
        shape = TopoDS_Shape()
        ok = StlAPI_Reader().Read(shape, path)
        if not ok or shape.IsNull():
            raise ValueError("Failed to read STL file.")
        return cq.Shape(shape)
    raise ValueError(f"Unsupported model format: {ext}")


def scale_shape_xyz(shape: cq.Shape, sx: float, sy: float, sz: float) -> cq.Shape:
    trsf = gp_GTrsf()
    trsf.SetValue(1, 1, sx)
    trsf.SetValue(2, 2, sy)
    trsf.SetValue(3, 3, sz)
    return cq.Shape(BRepBuilderAPI_GTransform(shape.wrapped, trsf, True).Shape())


def translate_shape_to_bbox(shape: cq.Shape, bbox) -> cq.Shape:
    bb = shape.BoundingBox()
    return shape.translate((
        bbox.xmin - bb.xmin,
        bbox.ymin - bb.ymin,
        bbox.zmin - bb.zmin,
    ))


def t_to_slider(t: float) -> int:
    return int(round((t - T_MIN) / (T_MAX - T_MIN) * SLIDER_STEPS))


def slider_to_t(v: int) -> float:
    return T_MIN + v / SLIDER_STEPS * (T_MAX - T_MIN)


def rho_to_slider(family: str, rho: float) -> int:
    lo, hi = rho_range(family)
    v = (rho - lo) / (hi - lo) * SLIDER_STEPS
    return max(0, min(SLIDER_STEPS, int(round(v))))


def slider_to_rho(family: str, v: int) -> float:
    lo, hi = rho_range(family)
    return lo + v / SLIDER_STEPS * (hi - lo)


#  Custom ComboBox: selected item in blue
class BlueSelectedComboBox(QComboBox):
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
            f = option.font
            f.setBold(True)
            option.font = f


#  Slider with min/max labels on both sides
def _make_slider_row(color: str, lbl_min: str, lbl_max: str):
    """Returns (container_widget, QSlider)."""
    container = QWidget()
    h = QHBoxLayout(container)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(6)

    _lbl_style = "color: #999; font-size: 10px;"

    left = QLabel(lbl_min)
    left.setStyleSheet(_lbl_style)
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
    right.setStyleSheet(_lbl_style)
    right.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    right.setFixedWidth(36)

    h.addWidget(left)
    h.addWidget(slider, stretch=1)
    h.addWidget(right)

    return container, slider


#  OCCT Viewport
class OCCTWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)

        self._initialized   = False
        self._previous_pos  = QPoint(0, 0)
        self._rotate_step   = 0.008
        self._orbit_method  = "Turntable"
        self.pending_select = False
        self.left_press     = QPoint(0, 0)

        self.display_connection = Aspect_DisplayConnection()
        self.graphics_driver    = OpenGl_GraphicDriver(self.display_connection)
        self.viewer  = V3d_Viewer(self.graphics_driver)
        self.view    = self.viewer.CreateView()
        self.context = AIS_InteractiveContext(self.viewer)
        self._prepare_display()

    def _prepare_display(self):
        params = self.view.ChangeRenderingParams()
        params.NbMsaaSamples         = 8
        params.IsAntialiasingEnabled = True
        self.view.TriedronDisplay(
            Aspect_TypeOfTriedronPosition.Aspect_TOTP_RIGHT_LOWER,
            Quantity_Color(), 0.1
        )
        self.viewer.SetDefaultLights()
        self.viewer.SetLightOn()
        ctx = self.context
        ctx.SetDisplayMode(AIS_DisplayMode.AIS_Shaded, True)
        ctx.DefaultDrawer().SetFaceBoundaryDraw(True)
        material = Graphic3d_MaterialAspect(Graphic3d_NOM_JADE)
        ctx.DefaultDrawer().ShadingAspect().SetMaterial(material)
        ctx.DefaultDrawer().ShadingAspect().SetColor(Quantity_Color(GOLD))

    def display_shape(self, cq_shape, clear=True):
        if not self._initialized:
            return
        if clear:
            self.context.RemoveAll(True)
        if isinstance(cq_shape, cq.Workplane):
            topo = cq_shape.val().wrapped
        elif isinstance(cq_shape, cq.Shape):
            topo = cq_shape.wrapped
        else:
            raise TypeError(f"Unsupported type: {type(cq_shape)}")
        ais = AIS_Shape(topo)
        self.context.Display(ais, True)
        self.view.FitAll()

    def fit_all(self):
        if self._initialized:
            self.context.UpdateCurrentViewer()
            self.view.FitAll()

    def clear(self):
        if self._initialized:
            self.context.RemoveAll(True)

    def paintEngine(self):
        return None

    def paintEvent(self, event):
        if not self._initialized:
            self._initialize()
        else:
            self.view.Redraw()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._initialized:
            self.view.MustBeResized()

    def wheelEvent(self, event):
        delta  = event.angleDelta().y()
        factor = ZOOM_STEP if delta < 0 else 1 / ZOOM_STEP
        self.view.SetZoom(factor)

    def mousePressEvent(self, event):
        pos = event.pos()
        if event.button() == Qt.LeftButton:
            self.pending_select = True
            self.left_press     = pos
            if self._orbit_method == "Trackball":
                self.view.StartRotation(pos.x(), pos.y())
        elif event.button() == Qt.RightButton:
            self.view.StartZoomAtPoint(pos.x(), pos.y())
        self._previous_pos = pos

    def mouseMoveEvent(self, event):
        pos  = event.pos()
        x, y = pos.x(), pos.y()
        if event.buttons() == Qt.LeftButton:
            if self._orbit_method == "Trackball":
                self.view.Rotation(x, y)
            else:
                dx = x - self._previous_pos.x()
                dy = y - self._previous_pos.y()
                cam = self.view.Camera()
                rot = gp_Trsf()
                rot.SetRotation(
                    gp_Ax1(cam.Center(), gp_Dir(0, 0, 1)),
                    -dx * self._rotate_step
                )
                cam.Transform(rot)
                self.view.Rotate(0, -dy * self._rotate_step, 0)
            if abs(x - self.left_press.x()) > 2 or abs(y - self.left_press.y()) > 2:
                self.pending_select = False
        elif event.buttons() == Qt.MiddleButton:
            self.view.Pan(
                x - self._previous_pos.x(),
                self._previous_pos.y() - y,
                theToStart=True
            )
        elif event.buttons() == Qt.RightButton:
            self.view.ZoomAtPoint(
                self._previous_pos.x(), y, x, self._previous_pos.y()
            )
        self._previous_pos = pos

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.pending_select:
            pos = event.pos()
            self.context.MoveTo(pos.x(), pos.y(), self.view, True)

    def _initialize(self):
        try:
            from OCP.WNT import WNT_Window
            win = WNT_Window(self.winId().ascapsule())
            self.view.SetWindow(win)
            self._initialized = True
            self.context.SetDeviationCoefficient(1e-5)
            self.context.SetDeviationAngle(0.1)
            self.view.Redraw()
        except Exception:
            import traceback
            traceback.print_exc()


#  Background thread: lattice generation
class GenerateThread(QThread):
    finished = pyqtSignal(float)
    error    = pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params
        self.result = None

    def run(self):
        try:
            t0 = time.perf_counter()
            self.result = self._build(self.params)
            self.finished.emit(time.perf_counter() - t0)
        except Exception:
            import traceback
            self.error.emit(traceback.format_exc())

    def _build(self, p):
        t  = p['type']
        if p.get('bool_enabled'):
            target = import_model_shape(p['model_path'])
            bbox = target.BoundingBox()
            if min(bbox.xlen, bbox.ylen, bbox.zlen) <= 0:
                raise ValueError("Imported model has an invalid bounding box.")
            s1 = float(p['cell_size'])
            if s1 <= 0:
                raise ValueError("Unit cell size must be positive.")
            nx = max(1, math.ceil(bbox.xlen / s1))
            ny = max(1, math.ceil(bbox.ylen / s1))
            nz = max(1, math.ceil(bbox.zlen / s1))
            lattice = self._build_lattice(t, s1, nx, ny, nz, p)
            lattice = _as_cq_shape(lattice)
            lattice = translate_shape_to_bbox(lattice, bbox)
            return lattice.intersect(target)

        nx, ny, nz = int(p['nx']), int(p['ny']), int(p['nz'])
        s1 = float(p['cell_size'])
        return self._build_lattice(t, s1, nx, ny, nz, p)

    def _build_lattice(self, t, s1, nx, ny, nz, p):
        if t == "SchwarzP-Shell":
            return schwarzP_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "SchwarzP-Solid":
            return schwarzP_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "IWP-Shell":
            return IWP_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "IWP-Solid":
            return IWP_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "Gyroid-Shell":
            return gyroid_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "Gyroid-Solid":
            return gyroid_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        elif t == "Diamond-Shell":
            return diamond_Shell(s1, float(p['t']), nx, ny, nz)
        elif t == "Diamond-Solid":
            return diamond_Solid(s1, float(p['w_bot']), float(p['w_top']), nx, ny, nz)
        else:
            raise ValueError(f"Unknown lattice type: {t}")


#  Main Window
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Explicit TPMS Structure Generator")
        self.resize(1100, 760)
        self._shape = None
        self._thread = None
        self._last_params = None
        self._model_path = ""
        self._model_shape = None
        self._model_bbox = None
        self._syncing = False
        # Internal w values (converted from t via param_w)
        self._w_bot = t_to_w_bot(0.20)
        self._w_top = t_to_w_top(0.20)
        self._build_ui()

    #  Helpers 
    def _row(self, label_text: str, widget, label_width: int = 130):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        h.addWidget(lbl)
        h.addWidget(widget)
        return w

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #d0d8e8; margin: 3px 0;")
        return line

    def _group_box(self, title: str) -> QGroupBox:
        gb = QGroupBox(title)
        gb.setStyleSheet("""
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
        gb.setLayout(QVBoxLayout())
        gb.layout().setSpacing(4)
        return gb

    def _line_edit(self, default: str) -> QLineEdit:
        e = QLineEdit(default)
        e.setFixedHeight(26)
        e.setStyleSheet("""
            QLineEdit {
                border: 1px solid #c0c8d8;
                border-radius: 4px;
                padding: 2px 6px;
                background: white;
            }
        """)
        return e

    def _param_row(self, label: str, edit: QLineEdit,
                   slider_row_widget: QWidget) -> QWidget:
        """Stacked: [label + edit]  /  [minslidermax]"""
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        top = QWidget()
        h = QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lbl = QLabel(label)
        lbl.setFixedWidth(100)
        h.addWidget(lbl)
        h.addWidget(edit)

        v.addWidget(top)
        v.addWidget(slider_row_widget)
        return container

    #  Build UI 
    def _build_ui(self):

        menubar = self.menuBar()
        menu_file = menubar.addMenu("File")
        act_exp = QAction("Export", self)
        act_exp.triggered.connect(self._on_export)
        menu_file.addAction(act_exp)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        panel = QWidget()
        panel.setFixedWidth(300)
        panel.setStyleSheet("background: #f5f6fa;")
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(8)
        pv.setAlignment(Qt.AlignTop)

        #   Lattice type 
        g_type = self._group_box("Lattice type")
        self.combo_subtype = BlueSelectedComboBox()
        self.combo_subtype.addItems(TPMS_TYPES)
        self.combo_subtype.currentTextChanged.connect(self._on_type_changed)
        self.combo_subtype._update_edit_color()
        g_type.layout().addWidget(self.combo_subtype)
        pv.addWidget(g_type)

        #   Array parameters 
        g_array = self._group_box("Array parameters")
        self.e_cell = self._line_edit("10")
        self.e_nx   = self._line_edit("1")
        self.e_ny   = self._line_edit("1")
        self.e_nz   = self._line_edit("1")
        self.row_cell = self._row("Unit cell size (mm):", self.e_cell)
        self.row_nx = self._row("X array number:", self.e_nx)
        self.row_ny = self._row("Y array number:", self.e_ny)
        self.row_nz = self._row("Z array number:", self.e_nz)
        g_array.layout().addWidget(self.row_cell)
        g_array.layout().addWidget(self._divider())
        g_array.layout().addWidget(self.row_nx)
        g_array.layout().addWidget(self.row_ny)
        g_array.layout().addWidget(self.row_nz)
        pv.addWidget(g_array)

        g_bool = self._group_box("Model filling")
        self.chk_bool = QCheckBox("Enable model clipping")
        self.chk_bool.stateChanged.connect(self._on_bool_changed)
        self.btn_import_model = QPushButton("Import model")
        self.btn_import_model.setFixedHeight(28)
        self.btn_import_model.clicked.connect(self._on_import_model)
        self.lbl_model_name = QLabel("No model imported")
        self.lbl_model_name.setWordWrap(True)
        self.lbl_model_name.setStyleSheet("color:#666; font-size:11px;")
        self.lbl_bbox = QLabel("BBox: -")
        self.lbl_bbox.setWordWrap(True)
        self.lbl_bbox.setStyleSheet("color:#1565C0; font-size:11px;")
        g_bool.layout().addWidget(self.chk_bool)
        g_bool.layout().addWidget(self.btn_import_model)
        g_bool.layout().addWidget(self.lbl_model_name)
        g_bool.layout().addWidget(self.lbl_bbox)
        self.lbl_fill_counts = QLabel("Auto cells: -")
        self.lbl_fill_counts.setWordWrap(True)
        self.lbl_fill_counts.setStyleSheet("color:#444; font-size:11px;")
        g_bool.layout().addWidget(self.lbl_fill_counts)
        pv.addWidget(g_bool)

        #   Design parameters 
        self.g_design = self._group_box("Design parameters")

        #  Shell 
        self.w_shell = QWidget()
        vs = QVBoxLayout(self.w_shell)
        vs.setContentsMargins(0, 0, 0, 0)
        vs.setSpacing(4)
        self.e_t = self._line_edit("0.5")
        vs.addWidget(self._row("Offset value:", self.e_t))
        self.g_design.layout().addWidget(self.w_shell)

        #  Solid 
        self.w_solid = QWidget()
        vso = QVBoxLayout(self.w_solid)
        vso.setContentsMargins(0, 0, 0, 0)
        vso.setSpacing(6)

        #  t 
        lbl_t_sec = QLabel("Thickness  t")
        lbl_t_sec.setStyleSheet(
            "color:#1565C0; font-size:11px; font-weight:bold; margin-top:2px;"
        )
        vso.addWidget(lbl_t_sec)

        self.e_thick = self._line_edit("0.20")
        t_slider_row, self.slider_t = _make_slider_row(
            "#4A90D9",
            f"{T_MIN:.2f}",
            f"{T_MAX:.2f}",
        )
        vso.addWidget(self._param_row("t :", self.e_thick, t_slider_row))

        vso.addWidget(self._divider())

        #  * 
        self.lbl_rho_sec = QLabel("Relative density rho*")
        self.lbl_rho_sec.setStyleSheet(
            "color:#c07000; font-size:11px; font-weight:bold; margin-top:2px;"
        )
        vso.addWidget(self.lbl_rho_sec)

        self.e_rho = self._line_edit("0.20")

        # rho slider row with dynamic labels
        self._rho_lbl_min = QLabel("0.000")
        self._rho_lbl_max = QLabel("0.000")
        _lbl_style = "color: #999; font-size: 10px;"
        self._rho_lbl_min.setStyleSheet(_lbl_style)
        self._rho_lbl_max.setStyleSheet(_lbl_style)
        self._rho_lbl_min.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._rho_lbl_max.setAlignment(Qt.AlignLeft  | Qt.AlignVCenter)
        self._rho_lbl_min.setFixedWidth(36)
        self._rho_lbl_max.setFixedWidth(36)

        self.slider_rho = QSlider(Qt.Horizontal)
        self.slider_rho.setRange(0, SLIDER_STEPS)
        self.slider_rho.setFixedHeight(18)
        self.slider_rho.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 4px; background: #dde3ee; border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #e8a020; border-radius: 2px;
            }
            QSlider::handle:horizontal {
                width: 13px; height: 13px; margin: -5px 0;
                border-radius: 6px;
                background: #e8a020; border: 2px solid white;
            }
        """)

        rho_slider_row = QWidget()
        rho_h = QHBoxLayout(rho_slider_row)
        rho_h.setContentsMargins(0, 0, 0, 0)
        rho_h.setSpacing(6)
        rho_h.addWidget(self._rho_lbl_min)
        rho_h.addWidget(self.slider_rho, stretch=1)
        rho_h.addWidget(self._rho_lbl_max)

        vso.addWidget(self._param_row("rho* :", self.e_rho, rho_slider_row))

        self.g_design.layout().addWidget(self.w_solid)
        pv.addWidget(self.g_design)
        pv.removeWidget(g_bool)
        pv.insertWidget(pv.indexOf(self.g_design) + 1, g_bool)

        #   Buttons 
        self.btn_gen = QPushButton("Generate")
        self.btn_gen.setFixedHeight(40)
        self.btn_gen.setStyleSheet("""
            QPushButton {
                background: #4A90D9; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover    { background: #357abd; }
            QPushButton:disabled { background: #aac4e0; }
        """)
        self.btn_gen.clicked.connect(self._on_generate)

        self.btn_exp = QPushButton("Export")
        self.btn_exp.setFixedHeight(40)
        self.btn_exp.setEnabled(False)
        self.btn_exp.setStyleSheet("""
            QPushButton {
                background: #6c757d; color: white;
                border-radius: 6px; font-weight: bold; font-size: 13px;
            }
            QPushButton:hover    { background: #545b62; }
            QPushButton:disabled { background: #c0c4c8; }
        """)
        self.btn_exp.clicked.connect(self._on_export)

        pv.addWidget(self.btn_gen)
        pv.addWidget(self.btn_exp)
        pv.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #d0d8e8;")
        self.canvas = OCCTWidget()

        root.addWidget(panel)
        root.addWidget(sep)
        root.addWidget(self.canvas, stretch=1)

        self.status = QStatusBar()
        self.status.setStyleSheet(
            "QStatusBar { background: #f0f2f7; border-top: 1px solid #d0d8e8; }"
        )
        self.setStatusBar(self.status)
        self.status.showMessage(
            "Ready. Select the TPMS type, set parameters, then click Generate."
        )

        # Connect signals
        self.slider_t.valueChanged.connect(self._on_slider_t)
        self.e_thick.editingFinished.connect(self._on_edit_t)
        self.slider_rho.valueChanged.connect(self._on_slider_rho)
        self.e_rho.editingFinished.connect(self._on_edit_rho)
        self.e_nx.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_ny.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_nz.editingFinished.connect(self._sync_bool_cell_size_hint)
        self.e_cell.editingFinished.connect(self._sync_bool_cell_size_hint)

        self._on_type_changed(self.combo_subtype.currentText())

    def _on_bool_changed(self):
        enabled = self.chk_bool.isChecked()
        self.row_nx.setVisible(True)
        self.row_ny.setVisible(True)
        self.row_nz.setVisible(True)
        self.e_nx.setReadOnly(enabled)
        self.e_ny.setReadOnly(enabled)
        self.e_nz.setReadOnly(enabled)
        self._sync_bool_cell_size_hint()

    def _sync_bool_cell_size_hint(self):
        if not hasattr(self, "lbl_fill_counts") or self._model_bbox is None:
            return
        try:
            a = float(self.e_cell.text())
            if a <= 0:
                raise ValueError
        except ValueError:
            self.lbl_fill_counts.setText("Auto cells: invalid unit cell size")
            return
        bx, by, bz = self._model_bbox.xlen, self._model_bbox.ylen, self._model_bbox.zlen
        nx = max(1, math.ceil(bx / a))
        ny = max(1, math.ceil(by / a))
        nz = max(1, math.ceil(bz / a))
        if self.chk_bool.isChecked():
            self.e_nx.setText(str(nx))
            self.e_ny.setText(str(ny))
            self.e_nz.setText(str(nz))
        self.lbl_fill_counts.setText(
            f"Auto cells: {nx} x {ny} x {nz}  (a = {a:.3f} mm)"
        )

    def _on_import_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import fill model", "", MODEL_FILTERS)
        if not path:
            return
        try:
            shape = import_model_shape(path)
            bbox = shape.BoundingBox()
            self._model_path = path
            self._model_shape = shape
            self._model_bbox = bbox
            self.lbl_model_name.setText(os.path.basename(path))
            self.lbl_bbox.setText(
                f"BBox: {bbox.xlen:.3f} x {bbox.ylen:.3f} x {bbox.zlen:.3f} mm"
            )
            self.chk_bool.setChecked(True)
            self._sync_bool_cell_size_hint()
            self.canvas.display_shape(shape)
            self.status.showMessage(f"Imported model: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            self.status.showMessage("Model import failed")

    #  Type combo  show/hide
    def _on_type_changed(self, t: str):
        if not t:
            return
        self.w_shell.setVisible(t.endswith("-Shell"))
        self.w_solid.setVisible(t.endswith("-Solid"))
        if t.endswith("-Solid"):
            self._refresh_rho_range()
            self._sync_t_to_rho()

    def _current_family(self) -> str:
        return family_from_type(self.combo_subtype.currentText())

    def _refresh_rho_range(self):
        fam = self._current_family()
        if fam is None:
            return
        lo, hi = rho_range(fam)
        self._rho_lbl_min.setText(f"{lo:.3f}")
        self._rho_lbl_max.setText(f"{hi:.3f}")

    #  t <-> rho* two-way sync
    #  w = param_w(d) = 2.5*d + 0.5
    #  d_bot = -t/2    w_bot = -1.25*t + 0.5
    #  d_top =  t/2    w_top =  1.25*t + 0.5
    def _sync_t_to_rho(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            t = float(self.e_thick.text())
            t = max(T_MIN, min(T_MAX, t))

            # Apply param_w mapping: w = 2.5*d + 0.5
            self._w_bot = t_to_w_bot(t)   # d = -t/2
            self._w_top = t_to_w_top(t)   # d =  t/2

            fam = self._current_family()
            if fam:
                rho = t_to_rho(fam, t) if t > 1e-9 else 0.0
                self.e_rho.setText(f"{rho:.4f}")
                self.slider_rho.setValue(rho_to_slider(fam, rho))
            self.slider_t.setValue(t_to_slider(t))
        except ValueError:
            pass
        finally:
            self._syncing = False

    def _sync_rho_to_t(self):
        if self._syncing:
            return
        self._syncing = True
        try:
            fam = self._current_family()
            if fam is None:
                return
            rho = float(self.e_rho.text())
            lo, hi = rho_range(fam)
            rho = max(lo, min(hi, rho))
            t   = rho_to_t(fam, rho)
            t   = max(T_MIN, min(T_MAX, t))

            self.e_thick.setText(f"{t:.4f}")

            # Apply param_w mapping: w = 2.5*d + 0.5
            self._w_bot = t_to_w_bot(t)   # d = -t/2
            self._w_top = t_to_w_top(t)   # d =  t/2

            self.slider_t.setValue(t_to_slider(t))
            self.slider_rho.setValue(rho_to_slider(fam, rho))
        except ValueError:
            pass
        finally:
            self._syncing = False

    def _on_slider_t(self, v: int):
        if self._syncing:
            return
        self.e_thick.setText(f"{slider_to_t(v):.4f}")
        self._sync_t_to_rho()

    def _on_edit_t(self):
        self._sync_t_to_rho()

    def _on_slider_rho(self, v: int):
        if self._syncing:
            return
        fam = self._current_family()
        if fam is None:
            return
        self.e_rho.setText(f"{slider_to_rho(fam, v):.4f}")
        self._sync_rho_to_t()

    def _on_edit_rho(self):
        self._sync_rho_to_t()

    #  Generate
    def _current_params(self) -> dict:
        t = self.combo_subtype.currentText()
        is_solid = t.endswith("-Solid")
        return {
            'type':      t,
            'cell_size': self.e_cell.text(),
            'nx':        self.e_nx.text(),
            'ny':        self.e_ny.text(),
            'nz':        self.e_nz.text(),
            't':         self.e_t.text(),
            'w_bot': f"{self._w_bot:.6f}" if is_solid else "0",
            'w_top': f"{self._w_top:.6f}" if is_solid else "0",
            'bool_enabled': self.chk_bool.isChecked(),
            'model_path': self._model_path,
        }

    def _on_generate(self):
        t = self.combo_subtype.currentText()
        is_solid = t.endswith("-Solid")
        if self.chk_bool.isChecked() and not self._model_path:
            QMessageBox.warning(self, "Missing model", "Please import a model before Bool generation.")
            return
        if self.chk_bool.isChecked():
            self._sync_bool_cell_size_hint()
        params = {
            'type':      t,
            'cell_size': self.e_cell.text(),
            'nx':        self.e_nx.text(),
            'ny':        self.e_ny.text(),
            'nz':        self.e_nz.text(),
            't':         self.e_t.text(),
            'w_bot': f"{self._w_bot:.6f}" if is_solid else "0",
            'w_top': f"{self._w_top:.6f}" if is_solid else "0",
            'bool_enabled': self.chk_bool.isChecked(),
            'model_path': self._model_path,
        }
        self.btn_gen.setEnabled(False)
        self.btn_exp.setEnabled(False)
        self.status.showMessage(f"Generating {t}, please wait...")
        self._thread = GenerateThread(params)
        self._thread.finished.connect(self._on_gen_done)
        self._thread.error.connect(self._on_gen_error)
        self._last_params = dict(params)   # Cache the generated parameter set.
        self._thread.start()

    def _on_gen_done(self, elapsed: float):
        self._shape = self._thread.result
        self.canvas.display_shape(self._shape)
        self.btn_gen.setEnabled(True)
        self.btn_exp.setEnabled(True)
        self.status.showMessage(f"Done. Elapsed: {elapsed:.8f} s")

    def _on_gen_error(self, msg: str):
        self.btn_gen.setEnabled(True)
        self.status.showMessage("Generation failed")
        QMessageBox.critical(self, "Error", msg)

    #  Export
    def _on_export(self):
        from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
        from OCP.IGESControl import IGESControl_Writer
        from OCP.BRepMesh import BRepMesh_IncrementalMesh

        if self._shape is None:
            QMessageBox.warning(self, "Notice", "Please generate the lattice structure first!")
            return

        # Parameter-change guard.
        if self._last_params is not None and self._current_params() != self._last_params:
            QMessageBox.warning(
                self, "Parameters Changed",
                "The parameters have been modified since the last generation.\n"
                "Please click Generate again before exporting."
            )
            return

        filters = "STEP Files (*.step);;IGES Files (*.igs);;STL Files (*.stl)"
        path, sel = QFileDialog.getSaveFileName(self, "Export", "lattice", filters)
        if not path:
            return

        try:
            wp = (
                self._shape.val().wrapped
                if isinstance(self._shape, cq.Workplane)
                else self._shape.wrapped
            )

            if "step" in sel.lower():
                if not path.lower().endswith(".step"):
                    path += ".step"

                writer = STEPControl_Writer()
                writer.Transfer(wp, STEPControl_AsIs)
                status = writer.Write(path)

                if not os.path.exists(path):
                    raise RuntimeError(f"STEP export failed, file was not created: {path}")

                file_size_mb = os.path.getsize(path) / 1024 / 1024
                print('The STEP file size is:  %s MB' % file_size_mb)

            elif "iges" in sel.lower():
                if not path.lower().endswith(".igs"):
                    path += ".igs"
                writer = IGESControl_Writer()
                writer.AddShape(wp)
                writer.Write(path)

            else:
                if not path.lower().endswith(".stl"):
                    path += ".stl"
                BRepMesh_IncrementalMesh(wp, 0.05, False, 0.3, True).Perform()
                if isinstance(self._shape, cq.Workplane):
                    self._shape.val().exportStl(path)
                else:
                    self._shape.exportStl(path)

            self.status.showMessage(f"Exported to: {path}")

        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))
            self.status.showMessage("Export failed")
def main() -> int:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
