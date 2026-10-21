# OpenFEM model workspace

This directory is reserved for the independent Dong et al. re-entrant
compression validation model.

Target baseline:

- 5 columns x 6 rows
- wall thickness: 0.30 mm
- specimen depth: 25 mm
- nominal specimen dimensions: 76 x 48 x 25 mm
- horizontal edge resolution: 19 divisions
- inclined/bevel edge resolution: 10 divisions
- friction coefficient: 0.35
- compression direction: global Y
- target compression strain: 0.80

The intended workflow is:

```text
Python geometry
    -> Gmsh structured 2D quad mesh
    -> extrusion to 3D hexahedral mesh
    -> OpenCourant explicit compression
    -> Python post-processing
```

Do not commit the OpenCourant solver binaries to this repository.
Codespaces installs the solver under `$HOME/.local/OpenCourant`.
