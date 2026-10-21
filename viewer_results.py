import paraview.web.venv

from pathlib import Path
from paraview import simple
from ptc import Viewer

folder = Path("openfem/dong2019/results_vtk")
files = sorted(folder.glob("Dong2019_thinA*.vtk"))

if not files:
    raise RuntimeError("No converted VTK result files found")

reader = simple.OpenDataFile(
    [str(f.resolve()) for f in files]
)
reader.UpdatePipeline()

view = simple.GetActiveViewOrCreate("RenderView")

display = simple.Show(reader, view)
display.Representation = "Surface"
simple.ColorBy(display, None)

simple.ResetCamera(view)
simple.Render(view)

print("Loaded result files:", len(files))
print("Point fields:", list(reader.PointData.keys()))
print("Cell fields:", list(reader.CellData.keys()))

app = Viewer()
app.start()
