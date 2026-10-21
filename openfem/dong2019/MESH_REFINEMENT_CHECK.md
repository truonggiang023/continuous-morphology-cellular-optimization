# Geometry/mesh regression check (Dong 2019)

The original Gmsh GEO contained `Point(id)={x,y,0,1.0}` for every input point.
This overrides the intended variation in `lc` and led all six trials to
produce the same mesh. The generator now sets each point's characteristic
length to the requested `lc` and saves all trial diagnostics to
`mesh_candidate_report.json`. A trial is rejected if:
* Sum of QUAD4 element areas differs by >2% from CAD polygon union area;
* any quad has a nonpositive corner;
* minimum quad scaled Jacobian is below provisional threshold 0.2.

These numerical cutoffs are conservative diagnostics, not publication-grade
proof of mesh convergence. The reported CAD area is about 407.645502 mm2;
the old element area was about 432.434337 mm2.

Run in the Codespace:

```bash
git switch validation/dong2019-physics-audit
git pull origin validation/dong2019-physics-audit
python3 -m py_compile openfem/dong2019/generate_model.py
mkdir -p openfem/dong2019/mesh_probe
python3 openfem/dong2019/generate_model.py --out openfem/dong2019/mesh_probe
```

If the generator raises `No geometrically acceptable mesh`, this is
INTENTIONAL; inspect `mesh_probe/mesh_candidate_report.json`. Do NOT
increase the 2% tolerance or force the solver to run. Confirm that trials
have distinct element counts and investigate geometric errors, thin wall
meshing, quadrilateral recombination, or mesh connectivity as indicated.

The wall thickness is 0.30 mm. Point-size variation alone does NOT prove
sufficient elements across thickness or good element conditioning. A later
structured/transfinite mesh study and deformation-mode comparison are still
required. No full OpenCourant solver execution was performed as part of
this change.
