# Dong 2019: current run is NOT validated

Source: Dong et al., Materials & Design 182 (2019) 108036.

Run `python3 openfem/dong2019/physics_audit.py --case openfem/dong2019/generated` before comparing figures. Exit 2 signals failed physics checks.

## Findings in the committed baseline

- `mesh_area_mm2=432.434337` vs `exact_section_area_mm2=407.645502` (~6.08% mismatch). These should agree independently of published relative density. Check Gmsh recombination, quad area, boundary integrity and mesh topology.
- 26,336 HEX8 vs reference 10,068 C3D8R. Different counts alone do not imply invalidity, but use a mesh-convergence study. Minimum 2-D scaled Jacobian is 0.0532.
- `STEP_TIME_MS=1000`, `COMPRESSION_STRAIN=0.8`, `H=48 mm`: commanded 38.4 mm/s = **2304 mm/min**, whereas the paper's FE platen speed was **2 mm/min** (experiments **1 mm/min**). The current speed is an accelerated numerical surrogate, not a 1:1 test.
- `/DT/NODA/CST 0.67 0.01` forces a target timestep. Solver `DM/M` values in the engine log are enormous (starting at 1.5383e6), and `ERR` is about -99.9%: investigate exact log conventions, added mass and energy balance, rather than trusting a fitted stress curve.
- Failure is OFF. Published fracture data do not fully define the locus; do not invent triaxiality coordinates to force agreement.
- Friction/self-contact: contact formulation should be verified against sliding, interpenetration, and force transmission. Rigid platens differ from the paper's elastic steel platens.

## Remediation order

1. Establish exact geometry in a converged mesh: independent CAD area versus summed element area to within a chosen tolerance, no inverted elements, robust aspect ratios, and proper thickness representation.
2. Confirm units and solve one elastic element to check force, mass and stable timestep. Run at *natural timestep without mass scaling* for a shortened diagnostic test. For faster full compression, use a documented acceleration/mass-scaling convergence series; require small kinetic/internal energy ratio and small added-mass ratio.
3. Check contact reactions at both platens, friction, shell/solid contact surface, displacement sign and nominal stress = absolute top reaction force / (76 x 25 mm²). Nominal strain = platen relative approach / 48 mm.
4. Validate stress–strain against **digitized** experimental and FE curves, with shape-based comparisons at nominal strains 0.12, 0.35 and 0.65. Plateau approximate experiment 0.28 MPa; paper 5x6 FE about 0.31 MPa.
5. Only then study ductile damage initiation/evolution as a documented material-calibration sensitivity. Validate final results against energy balance, failure modes and mesh convergence.

The audit is deliberately a diagnostic check: it does not change solver physics and DOES NOT establish agreement with the paper. A passing audit is necessary, not sufficient, for publication-grade validation.
