from paraview.simple import *

data = "openfem/dong2019/visualization/core_lc_1.20.vtu"

reader = OpenDataFile(data)
reader.UpdatePipeline()

view = GetActiveViewOrCreate("RenderView")
Show(reader, view)
ResetCamera(view)

SaveScreenshot("test_render.png", view)

print("RENDER SUCCESS")
