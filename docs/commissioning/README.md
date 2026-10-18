# Attenuator A/B commissioning draft

**MOVE this directory to `SWAXS_user_scripts/commissioning` when complete.** It is
temporarily staged in `profile_collection/docs` because the sister checkout is
not available in this sandbox. This plan is opt-in and is not loaded by startup.

- [attenuator_ab.py](attenuator_ab.py): hardware-free design/preview, Bluesky
  acquisition, ratio analysis, and individual-foil fits.
- [ATTENUATOR_CHARACTERIZATION.md](ATTENUATOR_CHARACTERIZATION.md): experimental
  rationale, energy coverage, precision targets, and photon-statistics estimates.
- [test_attenuator_ab.py](test_attenuator_ab.py): simulated RunEngine and physics tests.

## What the draft does

1. Validates both A and B stacks against total transmission `1e-9`–`1e-6`.
2. Closes and confirms the fast shutter, then calls `smi.modeAlignment()` to
   establish direct-beam geometry. The default detector is `pil2M`.
3. Sets **5 s, one image per trigger**, with timing written twice before staging
   so the TIFF resource's frames-per-point metadata matches acquisition.
4. Calls the existing **`energy_walk`** for each energy. This is the tracked,
   feedback-managed energy move, with its usual beamline diagnostics. The upstream
   photon shutter remains in its existing state; the downstream fast shutter is
   closed during moves. Tracking requires upstream beam/BPM feedback to be available.
5. Applies the **same pil2M energy/threshold/gain policy as `set_energy_cam`** using
   RunEngine messages: set parameters, apply, wait **20 s**, set/apply again, wait
   **20 s**, check energy/threshold/gain readbacks and detector idle. A third
   set/wait is available if confirmation fails. Missing/unconfirmed readbacks fail
   the run instead of continuing with uncertain sensitivity.
6. Updates the direct-beam ROI at each energy, and measures three shutter-closed
   dark frames at the same exposure time.
7. For each test, acquires its requested number of pairs, alternating order
   **AB, BA, AB, BA, ...**. Every state exchange is shutter-closed, using the
   aggregate bank devices and checking all 24 actual foil readbacks before exposure.
8. Uses **raw `pil2M.stats1.total`** for analysis. Stats5 is routed directly from
   the camera, with statistics enabled, to obtain the full-frame maximum pixel.
   Camera and stats frame IDs are checked to reject stale readout.
9. Records maximum pixel count / actual exposure time. A rate **>= 1,000,000
   counts/pixel/s** records the flagged frame and terminates the run with the
   shutter closed. This is a post-exposure rate check, not a hardware interlock;
   it cannot recover counts already lost to detector dead time or counter overflow.
10. Records ratios, individual-foil fits with uncertainties, and fit diagnostics.
    On completion/error/abort, closes the fast shutter and restores the SAXS
    beamstop using the detector's restore helper. Leaves the last foil stack in
    place. The plan does not call `modeMeasurement()`, because that retracts foils.

The detector is unstaged on exit. Energy, sensitivity, exposure, ROI/plugin routing,
and any WAXS geometry changes made by alignment remain at their final settings.
Normal RunEngine abort executes cleanup; `RE.halt()` or process termination does
not guarantee finalizers. The saturation signal remains a separate device-level
follow-up; this draft records `ab_saturated` without changing the Pilatus class.

## Load and preview

In the live profile console, from the profile root:

```python
%run -i docs/commissioning/attenuator_ab.py

# Default coverage: 6, 8.8, 16, 19.5 keV, with modeled margin inside the hard bounds.
tests = make_ab_tests(pairs=5)
preview = preview_ab(tests, exposure_s=5)
```

The preview is a plain function and reads/writes **no hardware**. The plan also
supports `dry_run=True`; under `RE` it returns the same report without opening a
run or resolving devices:

```python
RE(attenuator_ab_calibration(tests, exposure_s=5, dry_run=True))
```

The current default generates **160 test definitions / 800 pairs / 1,612 frames**.
At 5 s this is **134 minutes of exposure**, approximately **302 minutes total**
with the default overhead assumptions. This is a coverage-first draft with
redundant equations, not a minimum-time experimental design.

Preview assumptions can be adjusted without touching hardware:

```python
preview_ab(tests, exposure_s=5, energy_move_s=240, stack_move_s=6,
           shutter_cycle_s=1, readout_s=0.2, geometry_s=30)
```

`energy_move_s` is an estimate **per visited energy**, including approach to the
first energy. The default is 180 s. `stack_move_s=4` estimates two sequential bank
moves. Sensitivity contributes at least 40 s/energy. Retries, tracking/recentering,
additional sensitivity attempts, analysis, file writing and suspender pauses make
wall time variable. The estimate includes every pair as two state moves even when
AB/BA ordering leaves adjacent frames in the same state.

## Explicit tests and per-test repeat counts

`a` and `b` are **complete inserted-stack lists across both banks**, not incremental
commands. All other foils are retracted. Labels use `bank_position`, e.g. `"2_9"`.

```python
tests = [
    {
        "id": "Al9_6keV",
        "energy_eV": 6000,
        "a": ["1_9", "2_5", "2_10"],
        "b": ["1_9", "2_5", "2_10", "2_9"],
        "pairs": 10,
    },
    {
        "id": "Al9_8p8keV",
        "energy_eV": 8800,
        "a": ["1_1", "1_2", "2_8"],
        "b": ["1_1", "1_2", "2_8", "2_9"],
        "pairs": 25,
    },
]
preview_ab(tests, exposure_s=5)
RE(attenuator_ab_calibration(tests, exposure_s=5,
                            md={"sample_name": "attenuator_commissioning"}))
```

The top-level `pairs=5` supplies the default for explicit test dictionaries that
omit `pairs`. A dictionary's own value takes precedence. To change generated tests:

```python
tests = make_ab_tests(pairs=5)
for test in tests:
    if test["energy_eV"] == 8800:
        test["pairs"] = 10
```

Grouping is by energy in first-appearance order, then test order within that energy.
AB/BA ordering refers to acquisition sequence only: the reported ratio is always
**B/A**. A may be a different reference stack for every test.

Generated designs select independent foil equations at each energy and add
redundant equations for residual checks. They include substitutions required for
Cu 272 µm, Cu 544 µm and Sn 480 µm. Simple one-foil pairs can measure that foil
independently; arbitrary isolated substitutions generally cannot determine the
individual foils without the rest of the design. Rank and unresolved labels are
reported, rather than filling in nominal thicknesses.

## One run, analysis-friendly streams

The plan opens **one Bluesky run**; the profile's normal document subscriptions
store it in Tiled. The plan itself does not create or connect a Tiled client.

| Stream | Contents |
|---|---|
| `primary` | Every A/B frame, detector readout and TIFF reference, raw counts, state, test ID, pair, actual/requested energy, labels, exposure and pixel-rate flag |
| `dark` | Shutter-closed frames, same exposure/detector data schema |
| `detector_settings` | Confirmed sensitivity settings and attempt count at each energy |
| `ab_summary` | B/A ratio, log attenuation difference and uncertainty for each completed test |
| `foil_summary` | Individual transmission, reciprocal attenuation factor, effective thickness and uncertainties at each fitted energy |
| `fit_diagnostics` | Fit rank, residual chi-square, degrees of freedom, unresolved labels and full optical-depth covariance as JSON |
| `roi_settings` | Full-camera rectangle for each of ROI1/2/3 at each energy; centroid threshold |
| `shape_summary` | Paired centroid/width/variance differences and dark-subtracted left/right intensity normalized by transmitted core counts |

Start metadata contains the complete test definitions, per-test repeats, nominal
foil layout, transmission bounds and calculation model. Partial runs retain raw
events and all completed test/energy summaries. The plan's return value is a dict
with `uid`, `ab_summary`, `foil_summary`, `fit_diagnostics`, and `shape_summary`; whether `RE(...)`
exposes this directly depends on the RunEngine's `call_returns_result` setting.

For an existing Tiled BlueskyRun object `run`, the relevant datasets are:

```python
raw = run["primary"]["data"].read()
ratios = run["ab_summary"]["data"].read()
foils = run["foil_summary"]["data"].read()

# Fields include:
# raw:    ab_test_id, ab_pair, ab_state, ab_labels, ab_raw_counts, ab_saturated
# ratios: ratio_transmission_ratio, ratio_transmission_ratio_sigma
# foils:  foil_foil, foil_energy_eV, foil_transmission, foil_transmission_sigma,
#         foil_attenuation_factor, foil_attenuation_factor_sigma,
#         foil_effective_thickness_um, foil_thickness_sigma_um,
#         foil_thickness_scale, foil_thickness_scale_sigma, foil_valid
```

Parent Pilatus reads may also include the usual modeled attenuation-corrected
totals. Those are retained with normal detector metadata, but **not used** by this
analysis. `ab_raw_counts` is a snapshot of the raw Stats1 total used by the fit.

## What the uncertainty means

Each pair contributes `ln(A-dark) - ln(B-dark)`. A test summary uses the mean of
these differences, with independent variance given by the **larger** of the
propagated Poisson variance and the observed between-pair variance of the mean.
One shared dark estimate per energy introduces covariance between tests, which
is retained in the generalized least-squares foil fit:

```text
delta_tau_test = sum_i (inserted_B_i - inserted_A_i) * tau_foil_i
```

All reference foils are unknowns in this fit; their nominal attenuation is not
used as calibration truth. Singular-value analysis identifies independently
determined foils. Fit covariance is inflated when residual reduced chi-square
exceeds one. Uncertainties are **one standard error**, not 3-sigma intervals.
`fit_reduced_chi_squared=-1` means there are no residual degrees of freedom.
`valid=False` and transmission/factor values of `-1` flag nonphysical fits.

The online estimates assume monoenergetic, linear photon counting and stable
background. AB/BA alternation reduces simple order bias, and 5 s frames average
fast beam fluctuations, but neither removes arbitrary slow drift. Correlated
drift, detector efficiency/systematics, harmonics, scatter and calibration-model
uncertainty are not included in the statistical error bars. Diagnose these with
the raw data, repeated reference tests, residuals and energy comparisons. No
automatic production-table update is made.

For the material check, compare `foil_thickness_scale` between energies using
their combined uncertainty. Constant scale is consistent with effective thickness;
energy-dependent scale motivates further investigation. It does not identify
composition on its own. A backend re-fit can use the retained raw data and
covariance without rerunning acquisition.

## Beam broadening and off-axis background on the same frames

`beam_shape=True` (default) collects additional diagnostics without extra frames.
After the usual direct-beam ROI placement at each energy, the plan keeps that
center but enlarges ROI1 to **128 × 64 pixels**. ROI2 and ROI3 are **128 × 128
pixels**, left and right of ROI1 with a **16-pixel edge-to-edge gap**. These are
starting dimensions, not a measured optimum; inspect the images to choose sizes
appropriate for the actual beam and module layout.

```python
RE(attenuator_ab_calibration(
    tests, exposure_s=10,
    beam_shape=True,
    beam_roi_size=(128, 64),
    side_roi_size=(128, 128),
    side_gap_px=16,
    centroid_threshold=0.,
))
```

ROI1/2/3 are routed from the full camera frame with unit binning, no reversal or
intensity scaling. Stats1/2/3 are routed from their matching ROIs. Stats1 centroid
calculation is explicitly enabled. All these statistics must refer to the same
fresh frame as Stats5. ROI bounds are checked and readbacks verified before beam
exposure; out-of-bounds rectangles fail rather than being silently clipped.
ROIs are fixed across all A/B tests at an energy, then rebuilt at the next energy.
`beam_shape=False` retains the previous attenuation-only behavior.

### Recorded observables

Every primary and dark event includes:

- `shape_centroid_x_px`, `shape_centroid_y_px`: centroid transformed from ROI-local
  coordinates to full-camera coordinates.
- `shape_sigma_x_px`, `shape_sigma_y_px`: Stats1 RMS widths; for a Gaussian only,
  multiply by 2.355 to express FWHM. `shape_sigma_xy_px2` records the plugin's
  cross moment for later inspection.
- `shape_left_counts`, `shape_right_counts`: raw Stats2/Stats3 totals.
- `shape_left_counts_per_s_per_pixel`, `shape_right_counts_per_s_per_pixel`:
  raw side-region intensities normalized by exposure and rectangular pixel area.
- `shape_shape_valid`: moment validity flag. Dark/no-signal moment values should
  not be interpreted; nonfinite values use a sentinel of -1 and clear the flag.

`roi_settings` records the exact rectangle and threshold used at each energy, so
the reduced values can be reconstructed from the saved TIFF frames.

### Paired analysis and error bars

`shape_summary` records each test's A and B averages, **B-minus-A** changes, and
standard errors of changes for centroid, sigma, and cross moment. It also records
`sigma_x_px_variance_delta` and `sigma_y_px_variance_delta`, the mean differences
in **squared widths**. Independent convolution kernels add in variance, not width,
making these useful broadening proxies. Negative differences are retained.

Moment standard errors are empirical, from variation among paired measurements;
they are **not** a pixel-level statistical fit or a guaranteed counting-noise
floor. With one pair their standard error is unavailable (`-1`, with
`moment_sem_valid=False`). Constant simulated/plugin values can yield zero
empirical scatter; this does not establish zero physical uncertainty. The moment
calculation itself is not dark-subtracted by this plan. Background and the chosen
centroid threshold can strongly bias widths, especially at low signal.

For each side, the plan also computes

```text
side_per_pixel_per_core = (side_counts - side_dark)
                          / (core_counts - core_dark) / side_ROI_pixel_area
```

The A/B change in this quantity removes the leading effect of different total
transmissions. Its uncertainty uses the larger of counting variance and observed
pair scatter, plus shared side/core dark uncertainty. Negative dark-subtracted
side values are retained. Left and right uncertainties share the core denominator;
a later asymmetry fit must account for that correlation. Area normalization uses
the geometric rectangle, not the number of active/unmasked detector pixels.

### Interpretation and follow-up

These are **beam broadening and off-axis intensity diagnostics**, not direct
surface-roughness measurements. A simple `reference` / `reference + foil` pair
provides a useful foil-associated change under stable illumination. A general
stack substitution includes changes from multiple foils and propagation distances.
The attenuation fit's log-additivity must not be reused for diffuse intensity.
A per-foil scattering or width model requires validating the optical assumptions
and fitting stack dependencies separately.

Practical interpretation considerations:

- Track centroid shifts alongside width. Five- or ten-second exposures include
  within-exposure pointing motion in the measured width; centroid averages alone
  cannot remove it.
- A larger ROI1 can capture beam wings, but also includes more diffuse background.
  This can change both measured width and the definition of transmission. Keep its
  geometry and threshold fixed within an energy and compare image-based, locally
  background-subtracted core fits offline.
- The side ROIs deliberately avoid the immediate beam wings. They sample broad
  background in two directions, not a complete angular scattering distribution.
  Beam wings entering them, module gaps/dead pixels, masks and detector shadows
  must be assessed in the images. Bounds checks do not check module gaps.
- Fluorescence, parasitic scattering and roughness-related scattering can all
  contribute to side counts. Left/right symmetry, energy dependence, and a
  dedicated threshold comparison can help diagnose them, but these ROIs alone
  cannot distinguish the mechanisms. Sensitivity/gain changes between energies
  change the spectral response to fluorescence.
- A surface-roughness value would additionally require foil-to-detector geometry,
  angular calibration and an appropriate scattering model. The saved frames and
  per-test diagnostics preserve those options for the backend analysis.

Example dataset access:

```python
shape = run["shape_summary"]["data"].read()
geometry = run["roi_settings"]["data"].read()
# e.g. shape_test_sigma_x_px_variance_delta,
#      shape_test_left_per_pixel_per_core_delta,
#      shape_test_left_per_pixel_per_core_delta_sem
```

## Verification

From `profile_collection`, using the existing pixi test environment:

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 .pixi/envs/test/bin/python -B -m pytest docs/commissioning/test_attenuator_ab.py -q
```

Simulation covers hardware-free preview, full-rank two-energy coverage, recovery
of deliberately changed foil thicknesses, uncertainty propagation, one-run
multi-energy acquisition, sensitivity reapply and failure, fresh-statistics
checks, saturation, trigger failure and closed-shutter/beamstop cleanup.
Additional tests cover ROI bounds/nonoverlap, shape capture, optional diagnostics,
and distinguishing flux attenuation from a normalized side-intensity change. Live
detector readiness, fast-shutter readback mapping (0 open, 7 closed), direct-beam
ROI placement and real TIFF/Tiled ingestion still need commissioning verification.
