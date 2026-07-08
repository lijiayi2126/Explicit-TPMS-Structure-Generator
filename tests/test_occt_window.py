import sys
import types
import unittest
from unittest.mock import patch

from occt_window import create_occt_window


class NativeId:
    def __init__(self, value=123):
        self.value = value
        self.capsule = object()

    def __int__(self):
        return self.value

    def ascapsule(self):
        return self.capsule


class Widget:
    def __init__(self):
        self.native_id = NativeId()

    def winId(self):
        return self.native_id


class FakeWindow:
    def __init__(self, *args):
        self.args = args
        self.mapped = False

    def IsMapped(self):
        return self.mapped

    def Map(self):
        self.mapped = True


class OcctWindowTests(unittest.TestCase):
    def _create(self, platform, module_name, class_name):
        module = types.ModuleType(module_name)
        setattr(module, class_name, FakeWindow)
        with patch.object(sys, "platform", platform), patch.dict(
            sys.modules, {module_name: module}
        ):
            return create_occt_window(Widget(), "display")

    def test_windows_uses_pointer_capsule(self):
        window = self._create("win32", "OCP.WNT", "WNT_Window")
        self.assertEqual(len(window.args), 1)
        self.assertTrue(window.mapped)

    def test_linux_uses_display_and_integer_window_id(self):
        window = self._create("linux", "OCP.Xw", "Xw_Window")
        self.assertEqual(window.args, ("display", 123))
        self.assertTrue(window.mapped)

    def test_macos_uses_nsview_capsule(self):
        window = self._create("darwin", "OCP.Cocoa", "Cocoa_Window")
        self.assertEqual(len(window.args), 1)
        self.assertTrue(window.mapped)

    def test_unknown_platform_is_rejected(self):
        with patch.object(sys, "platform", "freebsd"):
            with self.assertRaisesRegex(RuntimeError, "Unsupported operating system"):
                create_occt_window(Widget(), "display")


if __name__ == "__main__":
    unittest.main()
