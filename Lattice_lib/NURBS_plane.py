import cadquery as cq
from OCP.Geom import Geom_BSplineSurface
from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal, TColStd_Array1OfInteger
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

# 控制点
poles = TColgp_Array2OfPnt(1, 2, 1, 2)
poles.SetValue(1,1,gp_Pnt(0,0,0))
poles.SetValue(2,1,gp_Pnt(10,0,0))
poles.SetValue(1,2,gp_Pnt(0,10,0))
poles.SetValue(2,2,gp_Pnt(10,10,0))

# 节点矢量
u_knots = TColStd_Array1OfReal(1,2); u_knots.SetValue(1,0.0); u_knots.SetValue(2,1.0)
v_knots = TColStd_Array1OfReal(1,2); v_knots.SetValue(1,0.0); v_knots.SetValue(2,1.0)

# 重复度
u_mults = TColStd_Array1OfInteger(1,2); u_mults.SetValue(1,2); u_mults.SetValue(2,2)
v_mults = TColStd_Array1OfInteger(1,2); v_mults.SetValue(1,2); v_mults.SetValue(2,2)

# B-spline Surface
surface = Geom_BSplineSurface(poles, u_knots, v_knots, u_mults, v_mults, 1, 1, False, False)

# TopoDS Face
face = BRepBuilderAPI_MakeFace(surface,1e-6).Face()

# CQ-Editor 中直接显示
show_object(face)