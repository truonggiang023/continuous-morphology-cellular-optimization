#!/usr/bin/env python3
"""Generate the Dong et al. (2019) thin-wall re-entrant validation model.

Workflow
--------
1. Rebuild the same sharp/mitered 2-D solid geometry used in the prior Abaqus model.
2. Mesh the 2-D union with Gmsh as an all-quadrilateral mesh.
3. Extrude the quad mesh programmatically to 8-node bricks through 25 mm depth.
4. Write OpenCourant starter/engine decks for accelerated quasi-static compression.

The first solver baseline intentionally omits fracture/damage. Dong et al. reported only
one exact ductile-damage point (fracture strain 0.047 at triaxiality 0.333) plus a range
for other estimated points, not the complete locus. Inventing the missing locus would
not be a faithful validation. Geometry, plasticity, self-contact, platen friction,
out-of-plane restraint, nominal dimensions, and mesh target are reproduced first.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
from typing import Dict, Iterable, List, Sequence, Tuple

Point2 = Tuple[float, float]

L1 = 12.0
L2 = 12.0
L_BEVEL = 5.66
T = 0.30
N_ROWS = 6
N_COLS = 5
CORE_HEIGHT_CENTERLINE = 8.0 * N_ROWS - T
DEPTH = 25.0
LAMBDA_M = 1.0
N_Z = 2
TARGET_HEX = 10068
PAPER_AREA = 76.0 * 25.0
COMPRESSION_STRAIN = 0.80
STEP_TIME_MS = 1000.0
DT_TARGET_MS = None  # natural timestep is default; mass scaling requires opt-in
FRICTION_PLATEN = 0.35
FRICTION_SELF = 0.0

# kg-mm-ms units => stress is kN/mm^2 = GPa.
RHO_AL = 2.67e-6
E_AL = 69.0
NU_AL = 0.30

# True stress [MPa], true plastic strain from the user's tensile-data baseline.
PLASTIC_DATA = [
(224.667594,0.0),(226.1780406,0.000219336),(227.78992,0.000438623),(229.4632006,0.000658854),
(230.9756288,0.000878045),(232.1861226,0.001097189),(233.4173009,0.001316284),(234.8308537,0.001536322),
(236.3759741,0.001755321),(237.8006123,0.001974272),(239.2460455,0.002193175),(240.5812366,0.00241302),
(241.9066508,0.002631827),(243.2831397,0.002850586),(244.478304,0.003069297),(245.6840758,0.003287961),
(246.9815872,0.003507566),(248.2389497,0.003726133),(249.577755,0.003944653),(250.7451359,0.004163125),
(252.0852754,0.004382538),(253.3751222,0.004600915),(254.6958786,0.004819243),(255.8045486,0.005037525),
(256.8835483,0.005256746),(258.1450835,0.005474931),(259.4071446,0.005693069),(260.5481176,0.00591116),
(261.679685,0.00613019),(262.8824363,0.006348185),(264.1870987,0.006566133),(265.7154586,0.006784033),
(267.1534126,0.007002871),(268.2974198,0.007220676),(269.4013,0.007438434),(270.5665487,0.007656144),
(271.6002717,0.007873807),(272.563591,0.008092407),(273.5168774,0.008309975),(274.5518412,0.008527496),
(275.688862,0.008744969),(276.9587751,0.008963379),(278.1476012,0.009180758),(279.2860684,0.009398089),
(280.3639714,0.009615373),(281.4629418,0.009833593),(282.3382032,0.010050783),(283.0916731,0.010267925),
(283.9879772,0.01048502),(284.8849234,0.01070305),(285.8430656,0.010920051),(286.8321596,0.011137005),
(287.8522252,0.011353911),(288.9137579,0.011571752),(290.0366068,0.011788564),(291.1497188,0.01200533),
(292.0695115,0.012222048),(293.0100771,0.01243872),(294.0839513,0.012656324),(295.1579758,0.012872902),
(296.252853,0.013089432),(297.3481765,0.013305916),(298.3421193,0.013523332),(299.2953163,0.013739722),
(300.2284652,0.013956064),(301.2028641,0.014172361),(302.1370688,0.014389588),(303.0202394,0.014605791),
(303.8219619,0.014821946),(304.6137751,0.015038055),(305.3345932,0.015255095),(306.1167875,0.01547111),
(306.7969505,0.015687079),(307.4876149,0.015903001),(308.1481345,0.016119853),(308.880295,0.016335682),
(309.5512853,0.016551464),(310.2122913,0.016767199),(310.7816308,0.016983864),(311.3918824,0.017199506),
(312.0228717,0.017415102),(312.74639,0.017630652),(313.6137778,0.017846154),(314.4510417,0.018062586),
(315.1857252,0.018277995),(316.0027985,0.018493359),(316.8304596,0.018708676),(317.6176881,0.01892492),
(318.3227616,0.019140145),(319.0281091,0.019355322),(319.7542785,0.019570454),(320.5324231,0.019786512),
(321.2488916,0.020001551),(321.8114306,0.020216544),(322.4667264,0.02043149),(323.1740131,0.020647363),
(323.8503988,0.020862216),(324.3624151,0.021077024),(324.8334552,0.021291785),(325.4079217,0.021507472),
(326.0852494,0.021722141),(326.6804521,0.021936764),(327.0698713,0.022151341),(327.418217,0.022365872),
(327.8185244,0.022581328),(328.1671201,0.022795766),(328.5364537,0.023010159),(328.833735,0.023224506),
(329.1108052,0.023439776),(329.521752,0.023654031),(330.0463442,0.02386824),(330.6536937,0.024082403),
(331.1686907,0.024297489),(331.6732327,0.02451156),(332.2605763,0.024725585),(332.85847,0.024939564),
(333.4465805,0.025154466),(333.9415871,0.025368354),(334.3230806,0.025582196),(334.6840307,0.025795992),
(335.1178104,0.02601071),(335.5824486,0.026224414),(335.9748418,0.026438073),(336.3156376,0.026651687),
(336.7086192,0.026866221),(337.1221154,0.027079743),(337.5461111,0.027293219),(337.9599013,0.02750665),
(338.3427634,0.027720035),(338.7157249,0.02793434),(339.1092128,0.028147634),(339.5132022,0.028360882),
(339.865499,0.028574085),(340.093815,0.028788207),(340.2907556,0.029001319),(340.5188697,0.029214386),
(340.7470501,0.029427407),(340.9756253,0.029641347),(341.2143185,0.029854277),(341.4530824,0.030067162),
(341.7438396,0.030280001),(342.0454056,0.030493759),(342.4402403,0.030706507),(342.8456031,0.030919211),
(343.2511074,0.031131869),(343.6051057,0.031345444),(343.9069043,0.031558012),(344.1464,0.031770535),
(344.3547598,0.031983012),(344.5215595,0.032195444),(344.6887301,0.032408793),(344.8764271,0.032621134),
(345.1058169,0.032833431),(345.3456863,0.033045683),(345.5547117,0.03325885),(345.7738807,0.033471011),
(346.0139514,0.033683128),(346.2436706,0.033895199),(346.4529399,0.034108185),(346.6827875,0.034320166),
(346.8501288,0.034532103),(347.007079,0.034743994),(347.1539641,0.034956799),(347.290112,0.035168601),
(347.4158489,0.035380358),(347.6042467,0.03559207),(347.7721422,0.035804694),(347.9710773,0.036016316),
(348.1491724,0.036227894),(348.3168631,0.036439426),(348.4218883,0.036650914),(348.5690726,0.036863314),
(348.6845885,0.037074712),(348.7896646,0.037286065),(348.8738344,0.037497374),(348.9583423,0.037709594),
(349.0215926,0.037920814),(351.151075,0.038144409),
]

def signed_area(poly: Sequence[Point2]) -> float:
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
                     poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))

def orient(poly: Sequence[Point2], ccw: bool) -> List[Point2]:
    out = list(poly)
    if (signed_area(out) > 0) != ccw:
        out.reverse()
    return out

def line_intersection(q1: Point2, d1: Point2, q2: Point2, d2: Point2) -> Point2 | None:
    det = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(det) < 1e-12:
        return None
    rx, ry = q2[0] - q1[0], q2[1] - q1[1]
    u = (rx * d2[1] - ry * d2[0]) / det
    return q1[0] + u * d1[0], q1[1] + u * d1[1]

def offset_closed_loop(points: Sequence[Point2], offset: float) -> List[Point2]:
    result: List[Point2] = []
    n = len(points)
    for i in range(n):
        p_prev, p_cur, p_next = points[(i - 1) % n], points[i], points[(i + 1) % n]
        d1 = (p_cur[0] - p_prev[0], p_cur[1] - p_prev[1])
        d2 = (p_next[0] - p_cur[0], p_next[1] - p_cur[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        if min(l1, l2) < 1e-12:
            raise ValueError("zero-length centerline segment")
        n1, n2 = (-d1[1] / l1, d1[0] / l1), (-d2[1] / l2, d2[0] / l2)
        q1 = (p_cur[0] + offset * n1[0], p_cur[1] + offset * n1[1])
        q2 = (p_cur[0] + offset * n2[0], p_cur[1] + offset * n2[1])
        inter = line_intersection(q1, d1, q2, d2)
        if inter is None:
            inter = (p_cur[0] + 0.5 * offset * (n1[0] + n2[0]),
                     p_cur[1] + 0.5 * offset * (n1[1] + n2[1]))
        result.append(inter)
    return result

def geometry_primitives():
    cell_h = CORE_HEIGHT_CENTERLINE / N_ROWS
    half_h = 0.5 * cell_h
    dx_ref = math.sqrt(L_BEVEL ** 2 - half_h ** 2)
    waist = LAMBDA_M * dx_ref
    pitch = L1 + L2 - 2.0 * waist
    surfaces = []
    all_pts = []

    def column_centerline(x0: float):
        x1 = x0 + L1
        pts = [(x0, 0.0)]
        for r in range(N_ROWS):
            z0 = r * cell_h
            pts += [(x0 + waist, z0 + half_h), (x0, z0 + cell_h)]
        pts.append((x1, CORE_HEIGHT_CENTERLINE))
        for r in reversed(range(N_ROWS)):
            z0 = r * cell_h
            pts += [(x1 - waist, z0 + half_h), (x1, z0)]
        return pts

    for c in range(N_COLS):
        cl = column_centerline(c * pitch)
        a = offset_closed_loop(cl, +0.5 * T)
        b = offset_closed_loop(cl, -0.5 * T)
        outer, inner = (a, b) if abs(signed_area(a)) >= abs(signed_area(b)) else (b, a)
        outer = orient(outer, True)
        inner = orient(inner, False)
        surfaces.append((outer, inner))
        all_pts.extend(outer); all_pts.extend(inner)

    for c in range(N_COLS):
        x0, x1 = c * pitch, c * pitch + L1
        for level in range(1, N_ROWS):
            y = level * cell_h
            rect = orient([(x0, y - T/2), (x1, y - T/2), (x1, y + T/2), (x0, y + T/2)], True)
            surfaces.append((rect, None)); all_pts.extend(rect)

    for c in range(N_COLS - 1):
        x1 = c * pitch + L1
        nx0 = (c + 1) * pitch
        for r in range(N_ROWS):
            y = r * cell_h + half_h
            xa, xb = x1 - waist, nx0 + waist
            rect = orient([(xa, y - T/2), (xb, y - T/2), (xb, y + T/2), (xa, y + T/2)], True)
            surfaces.append((rect, None)); all_pts.extend(rect)

    xmin = min(p[0] for p in all_pts); xmax = max(p[0] for p in all_pts)
    ymin = min(p[1] for p in all_pts); ymax = max(p[1] for p in all_pts)
    meta = dict(cell_h=cell_h, half_h=half_h, dx_ref=dx_ref, waist_shift=waist,
                pitch_x=pitch, actual_inclined=math.hypot(half_h, waist))
    return surfaces, (xmin, ymin, xmax, ymax), meta

def add_polygon_geo(lines, pts, pid, lid, loopid):
    point_ids = []
    for x, y in pts:
        lines.append(f"Point({pid}) = {{{x:.12g}, {y:.12g}, 0, 1.0}};")
        point_ids.append(pid); pid += 1
    curve_ids = []
    for i in range(len(point_ids)):
        lines.append(f"Line({lid}) = {{{point_ids[i]}, {point_ids[(i+1)%len(point_ids)]}}};")
        curve_ids.append(lid); lid += 1
    lines.append(f"Curve Loop({loopid}) = {{{','.join(map(str,curve_ids))}}};")
    return pid, lid, loopid + 1

def write_geo(path: Path, lc: float):
    """Write the already-unioned exact Dong section to Gmsh.

    The original version asked OpenCASCADE to Boolean-union 54 overlapping
    thin surfaces. Gmsh/OpenCASCADE can segfault on those coincident sharp
    junctions. The committed JSON is the exact polygonal union of that same
    geometry (area = 407.645502 mm^2), so meshing starts from a single clean
    surface with 50 holes and does not alter the physical geometry.
    """
    section_file = Path(__file__).with_name("dong2019_section.json")
    data = json.loads(section_file.read_text())
    loops = [data["exterior"]] + data["holes"]

    lines = []
    pid = lid = loopid = 1
    loop_ids = []
    for j, raw in enumerate(loops):
        pts = orient([(float(x), float(y)) for x, y in raw], ccw=(j == 0))
        this_loop = loopid
        pid, lid, loopid = add_polygon_geo(lines, pts, pid, lid, loopid)
        loop_ids.append(this_loop)

    lines.append(f"Plane Surface(1) = {{{','.join(map(str, loop_ids))}}};")
    lines += [
        f"Mesh.CharacteristicLengthMin = {min(0.30,lc):.12g};",
        f"Mesh.CharacteristicLengthMax = {lc:.12g};",
        "Mesh.CharacteristicLengthFromCurvature = 0;",
        "Mesh.CharacteristicLengthExtendFromBoundary = 1;",
        "Mesh.Algorithm = 6;",
        "Mesh.RecombineAll = 1;",
        "Mesh.RecombinationAlgorithm = 3;",
        "Mesh.SubdivisionAlgorithm = 1;",
        "Mesh.Smoothing = 20;",
        "Mesh.SaveAll = 1;",
        'Physical Surface("CORE") = {1};',
    ]
    path.write_text("\n".join(lines) + "\n")

    bounds = tuple(float(v) for v in data["bounds_mm"])
    cell_h = CORE_HEIGHT_CENTERLINE / N_ROWS
    half_h = 0.5 * cell_h
    dx_ref = math.sqrt(L_BEVEL ** 2 - half_h ** 2)
    waist = LAMBDA_M * dx_ref
    meta = dict(cell_h=cell_h, half_h=half_h, dx_ref=dx_ref,
                waist_shift=waist, pitch_x=L1 + L2 - 2.0 * waist,
                actual_inclined=math.hypot(half_h, waist),
                exact_section_area_mm2=float(data["area_mm2"]))
    return bounds, meta

def run_gmsh(geo: Path, msh: Path):
    cmd = ["gmsh", "-2", str(geo), "-format", "msh2", "-o", str(msh), "-v", "2"]
    p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f"Gmsh failed ({p.returncode})\n{p.stdout}")

def read_msh2(path: Path):
    lines = path.read_text().splitlines()
    nodes = {}
    quads = []
    types = {}
    i = 0
    while i < len(lines):
        if lines[i] == "$Nodes":
            n = int(lines[i+1]); i += 2
            for _ in range(n):
                a = lines[i].split(); nodes[int(a[0])] = tuple(map(float,a[1:4])); i += 1
        elif lines[i] == "$Elements":
            n = int(lines[i+1]); i += 2
            for _ in range(n):
                a = lines[i].split(); et = int(a[1]); nt = int(a[2]); conn = list(map(int,a[3+nt:]))
                types[et] = types.get(et,0)+1
                if et == 3: quads.append(conn)
                i += 1
        else:
            i += 1
    if not nodes or not quads:
        raise RuntimeError(f"No nodes/quads found in {path}")
    if types.get(2,0):
        raise RuntimeError(f"Mesh is not all-quad: {types.get(2)} TRI3 elements remain. Types={types}")
    return nodes, quads, types

def quad_quality(nodes, quads):
    min_sj = 1.0; max_aspect = 0.0; inverted = 0
    for q in quads:
        pts = [(nodes[n][0],nodes[n][1]) for n in q]
        if signed_area(pts) < 0:
            pts = [pts[0],pts[3],pts[2],pts[1]]
        edges = [math.dist(pts[i],pts[(i+1)%4]) for i in range(4)]
        max_aspect = max(max_aspect, max(edges)/max(min(edges),1e-15))
        for i in range(4):
            p0=pts[i]; p1=pts[(i+1)%4]; pm=pts[(i-1)%4]
            a=(p1[0]-p0[0],p1[1]-p0[1]); b=(pm[0]-p0[0],pm[1]-p0[1])
            cross=a[0]*b[1]-a[1]*b[0]
            sj=cross/max(math.hypot(*a)*math.hypot(*b),1e-15)
            min_sj=min(min_sj,sj)
            if sj <= 0: inverted += 1
    return {"min_scaled_jacobian_2d":min_sj,"max_edge_aspect_2d":max_aspect,"nonpositive_corners":inverted}

def choose_mesh(work: Path, requested_lc):
    # Mesh.SubdivisionAlgorithm=1 halves the characteristic edge length
    # in the final all-quad mesh. Parent lc ~1.1-1.3 mm therefore gives
    # final in-plane resolution ~0.55-0.65 mm, close to Dong's reported
    # 12/19=0.632 mm horizontal and 5.66/10=0.566 mm bevel resolutions.
    candidates = [requested_lc] if requested_lc else [1.05,1.10,1.15,1.20,1.25,1.30]
    trials=[]; best=None
    for lc in candidates:
        geo=work/f"core_lc_{lc:.2f}.geo"; msh=work/f"core_lc_{lc:.2f}.msh"
        try:
            bounds,meta=write_geo(geo,lc)
            run_gmsh(geo,msh)
            nodes,quads,types=read_msh2(msh)
            nhex=len(quads)*N_Z
            q=quad_quality(nodes,quads)
            trial={"parent_lc":lc,"estimated_final_h":0.5*lc,
                   "quads":len(quads),"hex_estimate":nhex,"types":types,**q}
            trials.append(trial)
            final_h = 0.5 * lc
            target_h = 0.5 * (L1 / 19.0 + L_BEVEL / 10.0)
            score=abs(nhex-TARGET_HEX)/TARGET_HEX + 0.15*abs(final_h-target_h)/target_h
            if q["nonpositive_corners"]: score += 100
            if best is None or score<best[0]: best=(score,msh,trial,bounds,meta)
        except Exception as exc:
            trials.append({"lc":lc,"status":"rejected","reason":str(exc)})
    if best is None:
        raise RuntimeError("No all-quad mesh candidate was produced: " + json.dumps(trials))
    return best[1], {"trials":trials,"selected":best[2]}, best[3], best[4]

def extrude_hex(nodes2d, quads):
    old_ids=sorted(nodes2d); idx={old:i for i,old in enumerate(old_ids)}
    base=[nodes2d[old] for old in old_ids]; nn=len(base)
    nodes3={}
    for k in range(N_Z+1):
        z=DEPTH*k/N_Z
        for j,(x,y,_) in enumerate(base):
            nodes3[k*nn+j+1]=(x,y,z)
    hexes=[]
    for q in quads:
        qq=[idx[n] for n in q]
        pts=[(base[j][0],base[j][1]) for j in qq]
        if signed_area(pts)<0: qq=[qq[0],qq[3],qq[2],qq[1]]
        for k in range(N_Z):
            lo=[k*nn+j+1 for j in qq]; hi=[(k+1)*nn+j+1 for j in qq]
            hexes.append(lo+hi)
    front=list(range(1,nn+1)); back=list(range(N_Z*nn+1,(N_Z+1)*nn+1))
    return nodes3,hexes,front,back

def chunks(seq, n=10):
    for i in range(0,len(seq),n): yield seq[i:i+n]

def smoothstep_function(n=20):
    out=[]
    for i in range(n+1):
        r=i/n; out.append((STEP_TIME_MS*r,3*r*r-2*r*r*r))
    return out

def fmt_ints(vals): return ''.join(f"{v:10d}" for v in vals)
def fmt_floats(vals): return ''.join(f"{v:20.10g}" for v in vals)

def write_starter(path, nodes, hexes, front, back, bounds):
    xmin,ymin,xmax,ymax=bounds
    master_bottom=max(nodes)+1; master_top=master_bottom+1
    xmid=0.5*(xmin+xmax); zmid=0.5*DEPTH
    all_nodes=dict(nodes)
    all_nodes[master_bottom]=(xmid,ymin,zmid)
    all_nodes[master_top]=(xmid,ymax,zmid)
    disp=COMPRESSION_STRAIN*48.0
    out=["#RADIOSS STARTER","/BEGIN","Dong2019_thin_reentrant_OpenCourant","      2026         0",
         "                  kg                  mm                  ms",
         "                  kg                  mm                  ms"]

    out += ["/MAT/LAW36/1","AlSi10Mg_Dong_tensile_curve",fmt_floats([RHO_AL]),
            fmt_floats([E_AL,NU_AL,0.0,0.0,0.0]),
            f"{1:10d}{0:10d}{0.0:20.10g}{0.0:20.10g}{0.0:20.10g}{0:20d}",
            f"{0:10d}{0.0:20.10g}{0:10d}{0.0:20.10g}{0.0:20.10g}",
            f"{100:10d}",fmt_floats([1.0]),fmt_floats([0.0])]
    out += ["/FUNCT/100","AlSi10Mg_true_stress_vs_true_plastic_strain"]
    out += [fmt_floats([eps,sig/1000.0]) for sig,eps in PLASTIC_DATA]

    out += ["/NODE"]
    for nid,(x,y,z) in sorted(all_nodes.items()):
        out.append(f"{nid:10d}{x:20.10g}{y:20.10g}{z:20.10g}")

    out += ["/PART/1","Core_AlSi10Mg",fmt_ints([1,1,0]),"/BRICK/1"]
    for eid,h in enumerate(hexes,1): out.append(fmt_ints([eid]+h))

    out += ["/PROP/SOLID/1","Core_C3D8R_analogue",
            f"{1:10d}{4:10d}{0:10d}{0:10d}{0:10d}{0:10d}{0:10d}{2:10d}{0.0:20.10g}",
            fmt_floats([1.1,0.05,0.10,0.0,0.0]),fmt_floats([0.0,0.0,0.0,0.0,0.0]),fmt_ints([0,0,0])]

    oop=front+back
    out += ["/BCS/1","Core_out_of_plane_U3_0",f"   001 000{0:10d}{10:10d}","/GRNOD/NODE/10","Core_front_back_z_faces"]
    out += [fmt_ints(c) for c in chunks(oop)]
    out += ["/BCS/2","Bottom_wall_master_fixed",f"   111 000{0:10d}{11:10d}","/GRNOD/NODE/11","Bottom_wall_master",fmt_ints([master_bottom])]
    out += ["/BCS/3","Top_wall_master_XZ_fixed",f"   101 000{0:10d}{12:10d}","/GRNOD/NODE/12","Top_wall_master",fmt_ints([master_top])]

    out += ["/FUNCT/200","SmoothStep_0_to_1"]
    out += [fmt_floats(v) for v in smoothstep_function()]
    out += ["/IMPDISP/1","Top_wall_compression",
            f"{200:10d}{'Y':>10s}{'':>10s}{0:10d}{12:10d}{'':>10s}{0:10d}",
            fmt_floats([1.0,-disp,0.0,STEP_TIME_MS])]

    search=2.0
    out += ["/RWALL/PLANE/1","Bottom_pedestal",
            f"{master_bottom:10d}{2:10d}{0:10d}{0:10d}{0:10d}",
            f"{search:20.10g}{FRICTION_PLATEN:20.10g}{0.0:20.10g}{0.0:20.10g}{0:10d}",
            fmt_floats([0.0,0.0,0.0,0.0]),fmt_floats([xmid,ymin+1.0,zmid])]
    out += ["/RWALL/PLANE/2","Top_indenter",
            f"{master_top:10d}{2:10d}{0:10d}{0:10d}{0:10d}",
            f"{search:20.10g}{FRICTION_PLATEN:20.10g}{0.0:20.10g}{0.0:20.10g}{0:10d}",
            fmt_floats([0.0,0.0,0.0,0.0]),fmt_floats([xmid,ymax-1.0,zmid])]

    out += ["/INTER/TYPE25/1","Core_self_contact",
            f"{1:10d}{0:10d}{5:10d}{0:10d}{0:10d}{0:10d}{1:20d}{1000:10d}",
            f"{0:10d}{0.0:30.10g}{0.0:20.10g}{0.0:20.10g}{0.0:20.10g}",
            f"{0.0:20.10g}{0.0:20.10g}{1:10d}{1:10d}{0.0:20.10g}",
            f"{0.0:20.10g}{FRICTION_SELF:20.10g}{0.0:20.10g}{0.0:20.10g}{0.0:20.10g}",
            f"{'000':>10s}{0:20d}{5:10d}{0.0:20.10g}{0:10d}{0.0:30.10g}",
            f"{0:10d}{0:10d}{0.0:20.10g}{0:10d}{0:40d}",
            "/SURF/PART/ALL/1","Core_external_surface",fmt_ints([1])]

    out += ["/TH/RWALL/1","Rigid_wall_forces","DEF",fmt_ints([1,2]),
            "/TH/NODE/2","Top_wall_motion","DEF",f"{master_top:10d}{0:10d}",
            "/TH/PART/3","Core_energies","DEF",fmt_ints([1]),"/END"]
    path.write_text("\n".join(out)+"\n")
    return {"master_bottom":master_bottom,"master_top":master_top,"compression_displacement_mm":disp}

def write_engine(path, target_dt_ms=None):
    out=["#RADIOSS ENGINE","/RUN/Dong2019_thin/1/",f"{STEP_TIME_MS:.10g}",
         "/PRINT/-1000","/TFILE",f"{STEP_TIME_MS/200:.10g}",
         "/ANIM/DT",f"0 {STEP_TIME_MS/50:.10g}",
         "/ANIM/VECT/DISP","/ANIM/VECT/VEL","/ANIM/ELEM/VONM","/ANIM/BRICK/EPSP","/ANIM/BRICK/HOURG",
          ]
    if target_dt_ms is not None:
        if target_dt_ms <= 0:
            raise ValueError("Mass scaling target timestep must be positive")
        out += ["/DT/NODA/CST", f"0.67 {target_dt_ms:.10g}"]
    path.write_text("\n".join(out)+"\n")

def main():
    global STEP_TIME_MS
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="openfem/dong2019/generated")
    ap.add_argument("--lc",type=float,default=None)
    ap.add_argument("--step-time-ms",type=float,default=STEP_TIME_MS,
                    help="Compression time in ms; physical 2 mm/min corresponds to 1152000 ms at 80 percent strain.")
    ap.add_argument("--target-dt-ms",type=float,default=None,
                    help="Opt-in nodal timestep / mass scaling. Check added mass and energy balance.")
    args=ap.parse_args()
    if args.step_time_ms <= 0:
        ap.error("--step-time-ms must be positive")
    STEP_TIME_MS = args.step_time_ms
    outdir=Path(args.out); outdir.mkdir(parents=True,exist_ok=True)
    msh,mesh_report,bounds,meta=choose_mesh(outdir,args.lc)
    nodes2d,quads,types=read_msh2(msh)
    nodes3d,hexes,front,back=extrude_hex(nodes2d,quads)
    starter=outdir/"Dong2019_thin_0000.rad"; engine=outdir/"Dong2019_thin_0001.rad"
    deckmeta=write_starter(starter,nodes3d,hexes,front,back,bounds)
    write_engine(engine, args.target_dt_ms)

    xmin,ymin,xmax,ymax=bounds
    area=sum(abs(signed_area([(nodes2d[n][0],nodes2d[n][1]) for n in q])) for q in quads)
    volume=area*DEPTH
    report={
      "paper":{"thin_relative_density":0.109,"target_c3d8r_elements":10068,"horizontal_divisions":19,"bevel_divisions":10,
               "experimental_plateau_MPa":0.28,"experimental_densification_strain":0.58,"fe_plateau_5x6_MPa":0.31},
      "geometry":{"bounds_mm":[xmin,ymin,xmax,ymax],"nominal_height_mm":48.0,"depth_mm":DEPTH,
                  "mesh_area_mm2":area,"mesh_volume_mm3":volume,"relative_density_vs_76x48":area/(76.0*48.0),**meta},
      "mesh":{**mesh_report,"selected_2d_quads":len(quads),"selected_3d_hex8":len(hexes),"z_layers":N_Z,"gmsh_types":types},
      "loading":{"step_time_ms":STEP_TIME_MS,"target_dt_ms":DT_TARGET_MS,"compression_strain":COMPRESSION_STRAIN,"target_dt_ms":args.target_dt_ms,
                 "nominal_stress_area_mm2":PAPER_AREA,"platen_friction":FRICTION_PLATEN,"self_friction":FRICTION_SELF},
      "model_scope":{"damage":"OFF in Stage-1 baseline; full Dong triaxiality locus is not published",
                     "platens":"rigid walls for Stage-1; paper used elastic steel plates"},
      **deckmeta,
    }
    (outdir/"model_report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
