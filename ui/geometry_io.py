import os

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
from OCP.gp import gp_GTrsf
from OCP.StlAPI import StlAPI_Reader
from OCP.TopoDS import TopoDS_Shape


def as_cq_shape(obj) -> cq.Shape:
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
        return as_cq_shape(cq.importers.importStep(path))
    if ext in (".iges", ".igs"):
        if hasattr(cq.importers, "importShape"):
            return as_cq_shape(cq.importers.importShape("IGES", path))
        raise ValueError("This CadQuery version does not expose IGES import.")
    if ext in (".brep", ".brp"):
        if hasattr(cq.importers, "importShape"):
            return as_cq_shape(cq.importers.importShape("BREP", path))
        raise ValueError("This CadQuery version does not expose BREP import.")
    if ext == ".stl":
        if hasattr(cq.importers, "importStl"):
            return as_cq_shape(cq.importers.importStl(path))
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
