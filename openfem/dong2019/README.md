# Dong et al. 2019 thin-wall re-entrant validation

This folder builds an independent OpenCourant validation model for the
thin-wall re-entrant honeycomb reported by Dong et al. (Materials & Design,
2019, 182, 108036).

## Paper-reported baseline

- AlSi10Mg
- wall thickness: 0.30 mm
- cell height: 8 mm
- horizontal length: 12 mm
- bevel length: 5.66 mm
- cell-wall angle: 45 deg
- specimen: 5 horizontal x 6 transverse cells
- nominal envelope: 76 x 48 x 25 mm
- thin-wall relative density: 0.109
- Abaqus FE mesh: 10,068 C3D8R
- horizontal / bevel discretization: 19 / 10 elements
- FE indenter speed: 2 mm/min
- self-contact
- out-of-plane displacement constrained
- platen/core friction: 0.35
- experimental thin-wall plateau stress: about 0.28 MPa
- experimental densification strain: about 0.58
- paper 5x6 FE plateau stress: about 0.31 MPa

## Stage 1

Stage 1 is a solver/mesh/contact baseline:

1. rebuild the same sharp/mitered solid geometry used in the earlier Abaqus model;
2. generate an all-quad 2-D Gmsh mesh;
3. extrude it to 8-node reduced-integration bricks;
4. constrain both z-end faces in U3;
5. compress between frictional rigid planes;
6. use the supplied tabulated AlSi10Mg tensile plastic curve;
7. target about 10,068 bricks;
8. check deformation, stress-strain response, added mass, kinetic/internal energy,
   and hourglass energy.

Damage is deliberately OFF in Stage 1. The Dong paper does not publish the full
fracture-strain/triaxiality locus; it only gives 0.047 at triaxiality 0.333 and
states that other points were estimated in the range 0.08-0.018. Those missing
coordinates must not be invented for a claimed 1:1 validation.

Rigid walls are used in Stage 1 for robust contact-force extraction. Dong used
elastic steel plates. Elastic platens will be a follow-up sensitivity if the
Stage-1 response is otherwise consistent.

## Run

From the repository root inside Codespaces:

```bash
git switch codespaces-opencourant
git pull
bash openfem/dong2019/run_validation.sh
```

Generated files are placed in `openfem/dong2019/generated/`.

The first comparison targets are:

- mesh count near 10,068 hexes;
- no inverted mesh corners;
- relative density close to the prior exact geometry (~0.1117) and the paper
  analytical value 0.109;
- Bi-V/inward contraction around nominal strain 0.12;
- Z-like localization around nominal strain 0.35;
- plateau stress near 0.28 MPa experiment / 0.31 MPa paper FE;
- densification near 0.58 experiment;
- quasi-static energy balance and acceptable hourglass energy.
