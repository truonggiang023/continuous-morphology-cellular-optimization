"""Export OpenCourant VTK animation to a standalone static Plotly web viewer.
Run from any working directory with: PV_VENV=... pvpython -u scripts/result.py
No ParaView render window, trame or WebSocket required.
"""
import json
import math
import re
from pathlib import Path

import paraview.web.venv  # Activate PV_VENV for ParaView 5.11
from paraview import simple
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkFiltersCore import vtkTriangleFilter
from vtkmodules.util.numpy_support import vtk_to_numpy
import plotly.offline

HERE = Path(__file__).resolve().parent
ROOT = next((p for p in (HERE, *HERE.parents) if (p / 'openfem/dong2019/results_vtk').is_dir()), None)
if ROOT is None:
    raise SystemExit('Cannot find openfem/dong2019/results_vtk in script directory or its parents')
INPUT = ROOT / 'openfem/dong2019/results_vtk'
OUTPUT = ROOT / 'dong2019_animation'
FRAME_DIR = OUTPUT / 'frames'
FRAME_DIR.mkdir(parents=True, exist_ok=True)
FILES = sorted(INPUT.glob('Dong2019_thinA*.vtk'), key=lambda p: int(re.search(r'A(\d+)\.vtk$', p.name).group(1)) if re.search(r'A(\d+)\.vtk$', p.name) else -1)
if not FILES:
    raise SystemExit(f'No animation VTK files in {INPUT}')
FIELDS = ('3DELEM_Von_Mises', '3DELEM_Plastic_Strain', '2DELEM_Von_Mises')
limits = {}
manifest = []

for count, file in enumerate(FILES, 1):
    print(f'[{count}/{len(FILES)}] {file.name}', flush=True)
    reader = simple.OpenDataFile(str(file.resolve()))
    try:
        reader.UpdatePipeline()
        dataset = reader.GetClientSideObject().GetOutputDataObject(0)
        if dataset is None:
            raise RuntimeError(f'No VTK output: {file.name}')
        surf = vtkGeometryFilter()
        surf.SetInputDataObject(dataset)
        surf.Update()
        tri = vtkTriangleFilter()
        tri.SetInputConnection(surf.GetOutputPort())
        tri.Update()
        poly = tri.GetOutput()
        if poly.GetPoints() is None:
            raise RuntimeError(f'No surface points: {file.name}')
        coords = vtk_to_numpy(poly.GetPoints().GetData())
        # Get polygons via GetCell rather than relying on VTK's legacy connectivity layout.
        # More robust to VTK version changes and mixed geometry.
        faces = []
        for cell_id in range(poly.GetNumberOfCells()):
            cell = poly.GetCell(cell_id)
            if cell.GetNumberOfPoints() == 3:
                faces.append((cell.GetPointId(0), cell.GetPointId(1), cell.GetPointId(2)))
        if not faces:
            raise RuntimeError(f'No triangles in {file.name}')
        # TriangleFilter should produce triangles only for this surface. Check mapping.
        if len(faces) != poly.GetNumberOfCells():
            raise RuntimeError(f'Nontriangle cells found in {file.name}; cannot safely map cell arrays')
        frame = {
            'name': file.stem,
            'x': coords[:, 0].tolist(), 'y': coords[:, 1].tolist(), 'z': coords[:, 2].tolist(),
            'i': [f[0] for f in faces], 'j': [f[1] for f in faces], 'k': [f[2] for f in faces],
            'fields': {}
        }
        for field in FIELDS:
            array = poly.GetCellData().GetArray(field)
            if array is None or array.GetNumberOfComponents() != 1:
                continue
            raw = vtk_to_numpy(array)
            if len(raw) != len(faces):
                raise RuntimeError(f'{file.name} {field}: {len(raw)} values vs {len(faces)} triangles')
            clean = [float(v) if math.isfinite(float(v)) else None for v in raw]
            finite = [v for v in clean if v is not None]
            if not finite:
                continue
            frame['fields'][field] = clean
            mn, mx = min(finite), max(finite)
            if field in limits:
                limits[field] = [min(limits[field][0], mn), max(limits[field][1], mx)]
            else:
                limits[field] = [mn, mx]
            print(f'    {field}: {len(finite)}/{len(clean)} finite, range {mn:.6g} .. {mx:.6g}', flush=True)
        filename = f'frame_{count:03d}.json'
        (FRAME_DIR / filename).write_text(json.dumps(frame, separators=(',', ':'), allow_nan=False), encoding='utf-8')
        manifest.append({'name': file.stem, 'path': f'frames/{filename}', 'fields': list(frame['fields'])})
    finally:
        simple.Delete(reader)

# Manifest relative paths are resolved relative to index.html itself.
(OUTPUT / 'manifest.json').write_text(json.dumps({'frames': manifest, 'limits': limits}, separators=(',', ':'), allow_nan=False), encoding='utf-8')
(OUTPUT / 'plotly.min.js').write_text(plotly.offline.get_plotlyjs(), encoding='utf-8')

HTML = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dong2019 | OpenCourant FEA Animation</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f7f9fc;color:#17212f;font-family:system-ui,Arial,sans-serif}
header{padding:13px 22px;background:#fff;border-bottom:1px solid #dce3eb}header h2{margin:0;font-size:18px}
header small{color:#64748b}.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:12px 22px;background:white}
button,select{padding:8px 12px;border:1px solid #ccd5e0;border-radius:7px;background:white;cursor:pointer}
button{background:#1e40af;color:white;border:0}input[type=range]{width:min(390px,42vw)}
#plot{height:calc(100vh - 165px);min-height:460px}#status{padding:3px 22px;color:#475569;font-size:12px;min-height:20px}
</style><script src="plotly.min.js"></script></head>
<body><header><h2>Dong2019 · OpenCourant FEA Animation</h2><small>Surface visualization from converted VTK results — field values are per surface triangle</small></header>
<div class="controls"><button id="play">▶ Play</button><label>Frame <input id="slider" type="range" min="0" max="0" value="0"></label>
<strong id="counter">—</strong><label>Field <select id="field"><option value="none">Geometry only</option></select></label>
<label>Speed <select id="speed"><option value="1200">Slow</option><option value="600" selected>Normal</option><option value="300">Fast</option></select></label></div>
<div id="status">Loading…</div><div id="plot"></div>
<script>
'use strict';
let manifest=null,idx=0,playing=false,requestId=0,plotReady=false;
const slider=document.querySelector('#slider'),counter=document.querySelector('#counter'),selector=document.querySelector('#field');
const button=document.querySelector('#play'),status=document.querySelector('#status'),cache=new Map();
async function getJSON(path){
  // Resolve relative to this HTML page, never the project root.
  const url=new URL(path,document.baseURI);
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok)throw Error(url.pathname+' returned HTTP '+response.status);
  const body=await response.text();
  try{return JSON.parse(body);}catch(e){throw Error(url.pathname+' returned non-JSON content: '+body.slice(0,70));}
}
async function readFrame(n){
  if(cache.has(n))return cache.get(n);
  const f=await getJSON(manifest.frames[n].path);
  if(!Array.isArray(f.i)||!Array.isArray(f.j)||!Array.isArray(f.k)||!f.fields)throw Error('Malformed frame '+n);
  cache.set(n,f);if(cache.size>4)cache.delete(cache.keys().next().value);
  return f;
}
function meshTrace(f,indices,values,range){
  const t={type:'mesh3d',x:f.x,y:f.y,z:f.z,
    i:indices.map(n=>f.i[n]),j:indices.map(n=>f.j[n]),k:indices.map(n=>f.k[n]),
    flatshading:true,opacity:1,hoverinfo:'skip',name:'Dong2019'};
  if(values){Object.assign(t,{intensity:values,intensitymode:'cell',colorscale:'Turbo',
    cmin:range[0],cmax:range[0]===range[1]?range[1]+1:range[1],
    showscale:true,colorbar:{title:selector.value,thickness:18}});
  }else{t.color='#a8b4c2';t.showscale=false;}
  return t;
}
async function render(n){
  const token=++requestId;idx=n;slider.value=n;
  counter.textContent=`${n+1} / ${manifest.frames.length} · ${manifest.frames[n].name}`;
  status.textContent='Loading '+manifest.frames[n].name+'…';
  try{
    const f=await readFrame(n);if(token!==requestId)return;
    const field=selector.value,all=Array.from({length:f.i.length},(_,i)=>i),traces=[];
    let validCount=0;
    if(field!=='none'&&Array.isArray(f.fields[field])){
      const values=f.fields[field];
      if(values.length!==f.i.length)throw Error(field+': '+values.length+' values for '+f.i.length+' triangles');
      const valid=all.filter(i=>typeof values[i]==='number'&&Number.isFinite(values[i]));
      const missing=all.filter(i=>typeof values[i]!=='number'||!Number.isFinite(values[i]));
      validCount=valid.length;
      // Separate triangles lacking this result. Avoid mapping null values to a grey surface.
      if(missing.length)traces.push(meshTrace(f,missing,null,null));
      if(valid.length)traces.push(meshTrace(f,valid,valid.map(i=>values[i]),manifest.limits[field]));
    }else{traces.push(meshTrace(f,all,null,null));}
    if(!traces.length)traces.push(meshTrace(f,all,null,null));
    if(token!==requestId)return;
    await Plotly.react('plot',traces,{
      margin:{l:0,r:0,b:0,t:0},uirevision:'keep-camera',
      scene:{aspectmode:'data',xaxis:{title:'X'},yaxis:{title:'Y'},zaxis:{title:'Z'}},paper_bgcolor:'#f7f9fc'
    },{responsive:true,displaylogo:false});
    status.textContent=`Showing ${f.name} · ${f.i.length.toLocaleString()} triangles · ${field==='none'?'Geometry only':`${validCount.toLocaleString()} triangles with ${field} (${(100*validCount/f.i.length).toFixed(1)}%)`}`;
  }catch(e){status.textContent='Error: '+e.message;playing=false;button.textContent='▶ Play';console.error(e);}
}
async function playLoop(){
  while(playing){
    const start=Date.now();
    await render((idx+1)%manifest.frames.length);
    if(!playing)break;
    await new Promise(resolve=>setTimeout(resolve,Math.max(20,(+document.querySelector('#speed').value)-(Date.now()-start))));
  }
}
button.onclick=()=>{playing=!playing;button.textContent=playing?'❚❚ Pause':'▶ Play';if(playing)playLoop();};
slider.oninput=e=>render(+e.target.value);selector.onchange=()=>render(idx);
(async()=>{
  try{
    manifest=await getJSON('manifest.json');slider.max=manifest.frames.length-1;
    for(const name of Object.keys(manifest.limits)){const o=document.createElement('option');o.value=name;o.textContent=name;selector.appendChild(o);}
    if(manifest.limits['3DELEM_Von_Mises'])selector.value='3DELEM_Von_Mises';
    await render(0);
  }catch(e){status.textContent='Error: '+e.message;console.error(e);}
})();
</script></body></html>'''
(OUTPUT / 'index.html').write_text(HTML, encoding='utf-8')
print(f'Created {len(manifest)} frames: {OUTPUT / "index.html"}', flush=True)
print('Fields:', limits, flush=True)
print('Serve project root with: python3 -m http.server 1234 --bind 0.0.0.0', flush=True)
