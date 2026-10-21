import paraview.web.venv

from pathlib import Path
from paraview import simple
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
import plotly.graph_objects as go

folder = Path("openfem/dong2019/results_vtk")
files = sorted(folder.glob("Dong2019_thinA*.vtk"))

if not files:
    raise RuntimeError("No VTK results found")

# Start with the latest completed converted frame
path = files[-1]
print("Loading:", path.name, flush=True)

reader = simple.OpenDataFile(str(path.resolve()))
reader.UpdatePipeline()

data = reader.GetClientSideObject().GetOutputDataObject(0)

surface = vtkGeometryFilter()
surface.SetInputDataObject(data)
surface.Update()

tri = vtkTriangleFilter()
tri.SetInputConnection(surface.GetOutputPort())
tri.Update()

mesh = tri.GetOutput()
points = mesh.GetPoints()

x, y, z = [], [], []

for idx in range(points.GetNumberOfPoints()):
    p = points.GetPoint(idx)
    x.append(p[0])
    y.append(p[1])
    z.append(p[2])

i, j, k = [], [], []

for idx in range(mesh.GetNumberOfCells()):
    cell = mesh.GetCell(idx)
    if cell.GetNumberOfPoints() != 3:
        continue
    i.append(cell.GetPointId(0))
    j.append(cell.GetPointId(1))
    k.append(cell.GetPointId(2))

field = "3DELEM_Von_Mises"
array = mesh.GetCellData().GetArray(field)

kwargs = {}

if array is not None and array.GetNumberOfComponents() == 1:
    kwargs["intensity"] = [
        array.GetTuple1(idx)
        for idx in range(len(i))
    ]
    kwargs["intensitymode"] = "cell"
    kwargs["colorscale"] = "Turbo"
    kwargs["colorbar"] = dict(title="Von Mises")
else:
    print("Stress array unavailable on extracted surface")
    kwargs["color"] = "steelblue"

fig = go.Figure(
    data=[go.Mesh3d(
        x=x, y=y, z=z,
        i=i, j=j, k=k,
        flatshading=True,
        **kwargs
    )]
)

fig.update_layout(
    title=f"Dong2019 — {path.name}",
    scene=dict(
        aspectmode="data",
        xaxis_title="X",
        yaxis_title="Y",
        zaxis_title="Z"
    ),
    margin=dict(l=0, r=0, t=45, b=0)
)

out = Path("dong2019_results.html")
fig.write_html(str(out), include_plotlyjs=True)

print("Viewer created:", out.resolve(), flush=True)
print("Triangles:", len(i), flush=True)
