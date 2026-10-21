"""Patch Dong2019 Plotly viewer to switch between frame-local and global color scales.
Run with python3 fix_dong2019_scale.py from repository root.
Patches existing HTML and the HTML template inside result.py when found.
"""
from pathlib import Path

root = Path.cwd()
paths = [root / 'dong2019_animation/index.html', root / 'result.py', root / 'scripts/result.py']
old = """      if(field!=='none' && f.fields[field]){
        const [lo,hi]=manifest.limits[field];
        Object.assign(data,{intensity:f.fields[field],intensitymode:'cell',colorscale:'Turbo',
          cmin:lo,cmax:hi===lo?lo+1:hi,colorbar:{title:field,thickness:18}});
      }else{ data.color='#4c8bbb'; }"""
# Normalize line indent via find/replace of internal substring, independent of outer indentation.
old_fragment = """if(field!=='none' && f.fields[field]){
      const [lo,hi]=manifest.limits[field];
      Object.assign(data,{intensity:f.fields[field],intensitymode:'cell',colorscale:'Turbo',
        cmin:lo,cmax:hi===lo?lo+1:hi,colorbar:{title:field,thickness:18}});
    }else{ data.color='#4c8bbb'; }"""
new_fragment = """if(field!=='none' && f.fields[field]){
      const values=f.fields[field];
      if(values.length!==f.i.length)throw Error('Cell count does not match surface triangles: '+field);
      const valid=values.filter(v=>typeof v==='number' && Number.isFinite(v));
      if(!valid.length){data.color='#9299a2';}
      else{
        let localMin=Infinity,localMax=-Infinity;
        for(const v of valid){if(v<localMin)localMin=v;if(v>localMax)localMax=v;}
        const globalLimits=manifest.limits[field] || [localMin,localMax];
        const localScale=document.querySelector('#scaleMode').value==='frame';
        const lo=localScale?localMin:globalLimits[0];
        const hi=localScale?localMax:globalLimits[1];
        const eps=Math.max(Math.abs(lo)*1e-9,1e-12);
        const colorLo=hi===lo?lo-eps:lo, colorHi=hi===lo?hi+eps:hi;
        Object.assign(data,{
          intensity:values,intensitymode:'cell',colorscale:'Turbo',
          cauto:false,cmin:colorLo,cmax:colorHi,showscale:true,
          colorbar:{title:{text:field},thickness:18,tickformat:'.4g'}
        });
        document.querySelector('#rangeInfo').textContent=
          'Frame min: '+localMin.toPrecision(5)+' | max: '+localMax.toPrecision(5)+
          ' | scale: '+(localScale?'Per-frame':'Global')+
          ' | valid: '+valid.length.toLocaleString()+'/'+values.length.toLocaleString();
      }
    }else{ data.color='#4c8bbb'; document.querySelector('#rangeInfo').textContent='Geometry only'; }"""
control_anchor = '<label>Speed <select id="speed">'
control_prefix = '<label>Color scale <select id="scaleMode"><option value="frame" selected>Per-frame (auto)</option><option value="global">Global (fixed)</option></select></label>\n'
status_anchor = '<div id="status">Loading manifest…</div>'
status_extension = '<div id="rangeInfo" style="padding:2px 22px;color:#334155;font-size:12px">—</div>'
listener_anchor = 'selector.onchange=()=>render(idx);'
listener_extension = "\ndocument.querySelector('#scaleMode').onchange=()=>render(idx);"
changed = []
for path in paths:
    if not path.exists():
        continue
    src = path.read_text(encoding='utf-8')
    if "id=\"scaleMode\"" in src:
        print('Already patched:', path)
        continue
    if old_fragment not in src:
        print('Skipping (different template):', path)
        continue
    dst = src.replace(old_fragment,new_fragment,1)
    for anchor in (control_anchor,status_anchor,listener_anchor):
        if anchor not in dst:
            raise RuntimeError(f'Missing expected anchor {anchor!r} in {path}; no file written')
    dst=dst.replace(control_anchor,control_prefix+control_anchor,1)
    dst=dst.replace(status_anchor,status_anchor+status_extension,1)
    dst=dst.replace(listener_anchor,listener_anchor+listener_extension,1)
    backup=path.with_suffix(path.suffix+'.bak')
    backup.write_text(src,encoding='utf-8')
    path.write_text(dst,encoding='utf-8')
    changed.append(str(path))
print('Updated:',changed if changed else 'none')
