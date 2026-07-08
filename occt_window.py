"""Platform-specific Qt window integration for the OCCT viewport."""

import sys


def create_occt_window(widget, display_connection):
    """Wrap a Qt native window in the matching OCCT window class."""
    native_id = widget.winId()

    if sys.platform == "win32":
        from OCP.WNT import WNT_Window

        window = WNT_Window(_as_capsule(native_id))
    elif sys.platform == "darwin":
        from OCP.Cocoa import Cocoa_Window

        window = Cocoa_Window(_as_capsule(native_id))
    elif sys.platform.startswith("linux"):
        from OCP.Xw import Xw_Window

        window = Xw_Window(display_connection, int(native_id))
    else:
        raise RuntimeError(
            f"Unsupported operating system: {sys.platform}. "
            "Supported platforms are Windows, Linux with X11, and macOS."
        )

    if not window.IsMapped():
        window.Map()
    return window


def _as_capsule(native_id):
    """Return the native pointer capsule required by Windows and macOS OCP."""
    if hasattr(native_id, "ascapsule"):
        return native_id.ascapsule()
    raise RuntimeError(
        "PyQt did not expose the native window handle as a capsule. "
        "Check that a supported PyQt5 and cadquery-ocp build is installed."
    )
