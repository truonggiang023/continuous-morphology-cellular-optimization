import paraview.web.venv
from paraview import simple
from ptc import Viewer
from pathlib import Path

base = Path("openfem/dong2019")

result = base / "results_vtk/Dong2019_thinA033.vtk"
mesh = base / "visualization/core_lc_1.20.vtu"

path = result if result.is_file() and result.stat().st_size > 0 else mesh

reader = simple.OpenDataFile(str(path.resolve()))
reader.UpdatePipeline()

view = simple.GetActiveViewOrCreate("RenderView")
display = simple.Show(reader, view)
display.Representation = "Surface With Edges"

simple.ResetCamera(view)
simple.Render(view)

print("Viewing:", path)
print("Point fields:", list(reader.PointData.keys()))
print("Cell fields:", list(reader.CellData.keys()))

app = Viewer()
app.start()
