import sys
import faulthandler
faulthandler.enable()

from sys import platform
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer

from OCP.Aspect import Aspect_DisplayConnection, Aspect_TypeOfTriedronPosition
from OCP.OpenGl import OpenGl_GraphicDriver
from OCP.V3d import V3d_Viewer
from OCP.AIS import AIS_InteractiveContext, AIS_DisplayMode
from OCP.Quantity import Quantity_Color

class TestWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_NativeWindow)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.resize(800, 600)
        self._initialized = False

        print("Step 1: 创建 display_connection")
        self.display_connection = Aspect_DisplayConnection()

        print("Step 2: 创建 graphics_driver")
        self.graphics_driver = OpenGl_GraphicDriver(self.display_connection)

        print("Step 3: 创建 viewer")
        self.viewer = V3d_Viewer(self.graphics_driver)

        print("Step 4: 创建 view")
        self.view = self.viewer.CreateView()

        print("Step 5: 创建 context")
        self.context = AIS_InteractiveContext(self.viewer)

        print("Step 6: 设置灯光")
        self.viewer.SetDefaultLights()
        self.viewer.SetLightOn()
        self.context.SetDisplayMode(AIS_DisplayMode.AIS_Shaded, True)

        print("Step 7: 构造完成，等待 show()")

    def paintEngine(self):
        return None

    def paintEvent(self, event):
        if not self._initialized:
            self._initialize()
        else:
            self.view.Redraw()

    def _initialize(self):
        try:
            from OCP.WNT import WNT_Window
            win = WNT_Window(self.winId().ascapsule())
            self.view.SetWindow(win)
            self._initialized = True
            self.view.Redraw()
            print("Step 12: 初始化完成 ✅")
        except Exception as e:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("启动...")
    app = QApplication(sys.argv)
    w = TestWidget()
    print("show() 前")
    w.show()
    print("show() 后，进入事件循环")
    sys.exit(app.exec_())
