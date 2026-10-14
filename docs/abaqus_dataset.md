# Abaqus and dataset contract

The supplied `ContinuousMorphology_Dataset_A_B_v2.xlsx` has been inspected. Its A sheet contains 21 controlled cases; B contains 300 candidates (3 anchors at r_L=0.5, t=0.30 mm and lambda_m=-1/0/+1, plus 297 LHS). All FEM targets and job-status cells in the supplied file are empty. The generic 315-point DOE described below is an alternative plan, not the uploaded workbook; preserve the existing B IDs/designs for ongoing FEM.

Use `cmco-import-workbook` for v2. Mapping: DOE_ID→design_id, t_mm→t, SEA_60_J_g→SEA_60_J_kg and SEA_d_J_g→SEA_d_J_kg (multiply by 1000), PCF_preD_N retained, FirstPeak_N→first_peak_force_N. Design_Space selectors currently choose SEA_d and PCF_preD; generated workbook_config.json honors these. Reference t is 0.30 mm, H0=47.7 mm, depth=50 mm, target width=108 mm. Baseline core volume and Dataset A target relative density remain blank.

Importer recomputes known mass/SEA and QC expressions rather than executing arbitrary spreadsheet formulas or trusting stale target caches. Eligibility requires the workbook job/nominal-geometry/width/kinetic-energy checks plus complete selected positive responses and mass, and a finite 0<epsilon_d<1 for densification-based objectives. Literal manual FALSE flags remain exclusions. Densification quality cannot be established from these summary columns; it is explicitly reported as unavailable. The generated workbook config therefore uses its summary-QC flag without the raw-curve `densification_status=ok` filter; users must inspect FEM histories separately. No source workbook is rewritten.

## Two separate scientific datasets

| Dataset | Sampling | Purpose | Controls |
| --- | --- | --- | --- |
| A | 21 lambda_m states from -1 to +1 | Mechanisms, load paths, instability, collapse, densification | Same connectivity, envelope, and material amount/relative density as practical |
| B | 300 LHS + 15 anchors | Surrogate learning and SEA–PCF optimization | Fixed material; variable r_L, t and lambda_m; record actual dimensions, mass, density |

Horizontal normalization alone does not ensure the same H0, D0, mass or relative density. For A, compute the geometry and thickness needed to satisfy declared controls, check t remains feasible and document deviations. If envelope and material density are fixed, matching mass also matches relative density; verify actual CAD/mesh volume instead of assuming it from lambda_m. No geometry transformation is implemented without the connectivity and node-coordinate law.

Reference transition: lambda_m=0, L1=L2=12 mm, r_L=0.5. L1+L2=24 mm belongs to the supplied reference and is not assumed valid for every normalized morphed cell. DOE files leave A thickness unresolved and use a provisional reference thickness, not a solved constant-density series.

## Manifest

| Column | Meaning |
| --- | --- |
| design_id | Unique design/group key; preserve across mesh/solver repeats in ML tables |
| dataset | A or B |
| r_L, t, lambda_m | Inputs; t in mm |
| H0_mm, W0_mm, D0_mm | Actual initial core envelope dimensions |
| mass_tonne | Core mass only, exclude platens |
| relative_density | Actual core material volume / envelope volume |
| curve_csv | CSV path relative to the manifest, or absolute |
| qa_accepted | 0 initially; 1 only after independently approving physical/numerical FEM quality |
| material, E_MPa, nu, rho_tonne_mm3 | Material identity and baseline values |
| mesh_id, odb_path, deformation_mode, notes | Provenance and physical interpretation |

The postprocessor expects one row per design in a manifest. For replicates, postprocess separate manifests and retain the same design_id when combining the response tables for grouped ML. Identical feature vectors may not be assigned distinct groups. Train data filters do not validate convergence or infer QA approval.

## Abaqus acquisition

Use a core-only model; ensure loading-platen U2 and its total RF2 represent the intended axial compression and do not double-count reactions from both platens. Request synchronized history output at adequate frequency. The provided ODB exporter accepts explicit region names and a single step. It does not merge steps, sum nodal forces or correct compliance. Verify signs and reaction balance in Abaqus before using absolute magnitudes downstream.

Model unit system: mm, N, s, tonne, MPa. Material density is 2.67e-9 tonne/mm³ = 2670 kg/m³. Supply actual mass from the core geometry/model, not nominal density alone. Plastic material response, anisotropy/damage assumptions, contacts, friction, element formulation, mesh, loading velocity/time and imperfections must be specified separately.

Before setting qa_accepted=1, document solver completion, mesh/temporal convergence and physically acceptable collapse. For Explicit, examine kinetic/internal energy histories, artificial/hourglass energy, mass scaling and sensitivity to loading rate using justified study-specific criteria. The software does not invent universal numeric acceptance thresholds. Keep energy histories and deformed shapes for scientific audit.

Abaqus execution/ODB integration has not been validated in this cloud, which has no Abaqus executable. The standard-library exporter targets Abaqus 2024+ Python 3; its synchronization logic is covered by a mock test, not a real ODB test.

## Response definitions

For monotonic displacement u=|U2| and force F=|RF2|:

- epsilon = u/H0; sigma = F/(W0 D0), MPa.
- EA(epsilon) = integral F du, converted from N mm to J.
- SEA = EA / core mass in kg, J/kg.
- eta(epsilon) = integral_0^epsilon sigma(e) de / sigma(epsilon), evaluated only where sigma > 0.
- epsilon_d is the sampled maximum of eta over epsilon >= 0.05 by default (CLI override available).
- PCF_preD is max force from zero to epsilon_d, inclusive.
- MCF_preD = EA_Nmm(epsilon_d) / displacement(epsilon_d).
- CFE_preD = MCF_preD / PCF_preD.
- plateau stress follows the supplied full-interval definition: integral_0^epsilon_d sigma de / epsilon_d. It is not the average over an independently chosen plateau-only interval.
- first_peak_force is the first sampled local maximum before epsilon_d (SciPy find_peaks defaults), null if absent. It is not an automatically validated physical buckling peak.

Trapezoidal integration is used with no smoothing; SEA_60 adds a linearly interpolated endpoint if necessary, and is null when 60% strain was not reached. Densification maxima at either search boundary receive review-required flags. Raw noise or force drops can move the eta maximum; an interior maximum alone does not establish physically correct densification. Inspect curves and record a consistent smoothing/search policy before freezing research outputs. The current version intentionally does not silently smooth, truncate or override epsilon_d.

The lower search bound 0.05 is a configurable numerical convention, not an established material constant. Stored postprocessing provenance records it, curve hashes and manifest hash. Preserve exported ODB provenance sidecars and original files; response SHA records identify data, not Abaqus convergence.

## Validation loop

First use A to examine mechanism changes under quantified controls. Fit/tune B models on train groups, preserve final holdout and investigate sensitivity to split and data coverage. Interpret morphology–geometry interactions jointly with deformation images and force–displacement histories. Run selected Pareto inputs in the same verified Abaqus model, recompute responses with the same definitions, compare measured FEM responses to predictions, and record feasibility/errors before claiming a validated Pareto trade-off. Never use verification results to repeatedly tune against the original holdout while calling that holdout untouched.
