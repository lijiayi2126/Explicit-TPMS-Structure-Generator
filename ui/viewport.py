import cadquery as cq
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QWidget

from OCP.Aspect import Aspect_DisplayConnection, Aspect_TypeOfTriedronPosition
from OCP.OpenGl import OpenGl_GraphicDriver
from OCP.V3d import V3d_Viewer
from OCP.AIS import AIS_InteractiveContext, AIS_DisplayMode, AIS_Shape
from OCP.Quantity import Quantity_Color, Quantity_NOC_GOLD as GOLD
from OCP.Graphic3d import Graphic3d_NOM_JADE, Graphic3d_MaterialAspect
from OCP.gp import gp_Trsf, gp_Ax1, gp_Dir

from .constants import ZOOM_STEP


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
