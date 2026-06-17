import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino.Geometry as rg

objs = rs.GetObjects(
    "Select STEP surfaces or polysurfaces",
    rs.filter.surface | rs.filter.polysurface
)

if not objs:
    print("No objects selected.")
else:
    tol = rs.GetReal("Planarity tolerance", 1e-6)
    if tol is None:
        tol = 1e-6

    total_faces = 0
    planar_faces = 0

    total_area = 0.0
    planar_area = 0.0

    for obj_id in objs:
        brep = rs.coercebrep(obj_id)
        if brep is None:
            continue

        for face in brep.Faces:
            total_faces += 1

            amp = rg.AreaMassProperties.Compute(face)
            if amp:
                area = amp.Area
            else:
                area = 0.0

            total_area += area

            if face.IsPlanar(tol):
                planar_faces += 1
                planar_area += area

    if total_faces > 0:
        count_ratio = 100.0 * planar_faces / float(total_faces)
    else:
        count_ratio = 0.0

    if total_area > 0:
        area_ratio = 100.0 * planar_area / total_area
    else:
        area_ratio = 0.0

    print("Total faces:", total_faces)
    print("Planar faces:", planar_faces)
    print("Planar face ratio by count: %.4f %%" % count_ratio)
    print("Total area:", total_area)
    print("Planar area:", planar_area)
    print("Planar face ratio by area: %.4f %%" % area_ratio)