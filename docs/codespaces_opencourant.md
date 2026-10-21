# GitHub Codespaces + Gmsh + OpenCourant

This environment is intended to provide an independent open-source FE
workflow for the continuous-morphology cellular-structure project.

## 1. Create the Codespace

From the GitHub repository:

```text
Code -> Codespaces -> Create codespace
```

The devcontainer automatically runs:

```bash
bash scripts/setup_codespace.sh
```

The setup script installs Gmsh and downloads the latest Linux
OpenCourant precompiled binary from the OpenCourant GitHub release API.

## 2. Verify the environment

```bash
bash scripts/check_toolchain.sh
```

Expected tools:

- Python 3
- Gmsh
- OpenCourant Starter
- OpenCourant Engine

## 3. Run an OpenCourant model

Place the two Radioss/OpenCourant input decks in `openfem/model/`.

Example:

```bash
bash scripts/run_opencourant.sh \
  openfem/model/reentrant_0000.rad \
  openfem/model/reentrant_0001.rad \
  4
```

## 4. Validation strategy

The first validation target is the Dong et al. thin-wall re-entrant
specimen. The independent model should reproduce the published
experimental/FE response before it is used for the larger ML design
space.

Primary checks:

1. mesh quality at the re-entrant apex and wall junctions;
2. deformation mode at nominal strain ~0.12 and ~0.35;
3. nominal stress computed from the 76 mm x 25 mm gross area;
4. plateau stress and densification strain;
5. kinetic/internal-energy ratio for quasi-static validity.

## 5. Important distinction

OpenCourant does not use the Abaqus element name C3D8R. Therefore this
workflow is an independent solver validation, not an exact reproduction
of Abaqus's element formulation.
