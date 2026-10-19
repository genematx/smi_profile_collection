# Attenuator A/B commissioning draft

**Calibration update:** v2 uses 20 accepted results from scan 1171324 plus
16–17 keV follow-up thicknesses for 2_3/2_4 and the 16 keV baseline for 2_6:
23 foil thicknesses are corrected in the production physics layer. See
[accepted values and targeted follow-up](CALIBRATION_1171324.md). Previous preview
counts/precision estimates below describe the earlier nominal design; regenerate
tests and preview against the current calibrated model before acquisition.

**MOVE this directory to `SWAXS_user_scripts/commissioning` when complete.** It is
temporarily staged in `profile_collection/docs` because the sister checkout is
not available in this sandbox. This plan is opt-in and is not loaded by startup.

- [attenuator_ab.py](attenuator_ab.py): hardware-free design/preview, Bluesky
  acquisition, ratio analysis, and individual-foil fits.
- [ATTENUATOR_CHARACTERIZATION.md](ATTENUATOR_CHARACTERIZATION.md): experimental
  rationale, energy coverage, precision targets, and photon-statistics estimates.
- [test_attenuator_ab.py](test_attenuator_ab.py): simulated RunEngine and physics tests.

## What the draft does

The current schedule uses **8.8, 16, and 19.5 keV**. The 6 keV point is excluded
because higher-harmonic contributions were observed there; explicit tests below
8.8 keV are also rejected. Beam-size and off-axis diagnostics remain enabled.

**Bank 2 foil 6 (`2_6`, Al 204 µm) is now excluded by default** after repeated
insertion failures. Regenerate `tests` after reloading the script; the previous
8.8 keV reference contained this foil, so simply filtering tests loses that block.
The generator selects new references and designs for the other 23 foils. Explicit
tests still containing `2_6` are rejected before acquisition. The bank requests
keep it retracted and its readback is still checked. The unrestricted automatic
attenuation selection inside initial alignment is bypassed with exclusions;
geometry moves remain shutter-closed and exact stacks precede every exposure.

```python
tests = make_ab_tests(pairs=5, excluded_foils=("2_6",))
preview_ab(tests, exposure_s=10, excluded_foils=("2_6",))
```

This produces **130 tests, 650 pairs, 1,300 frames**, approximately **483 minutes
(8 hours)** at 10 s exposures and 10 s stack changes. All remaining 23 foils retain
independent coverage at two or more energies. `2_6` remains unresolved in fitting.
Pass the same `excluded_foils` to acquisition if changing the exclusion list.

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
   RunEngine messages: set parameters, apply, wait **30 s**, set/apply again, wait
   **30 s**, check energy/threshold/gain and detector idle. A third set/wait is
   available if confirmation fails. Energy and threshold readbacks must confirm.
   If `GainMenu_RBV` is disconnected, the plan checks the `GainMenu` setting
   instead, prints that gain is not independently confirmed, and records
   `sensitivity_gain_readback_confirmed=False` and the source in `detector_settings`.
   A connected gain readback that disagrees still fails after the retries.
6. Updates the direct-beam ROI at each energy. No dark frames are acquired;
   analysis assumes zero background. `dark_frames=0` is required because the
   detector controls the shutter during exposure.
7. For each test, acquires its requested number of pairs, alternating order
    **AB, BA, AB, BA, ...**. Every state exchange is shutter-closed, using the
    aggregate bank devices and checking all 24 actual foil readbacks before exposure.
    The detector opens/closes the shutter during acquisition; the plan sends no
    manual open command and confirms closure after exposure and before moves.
    A completed-but-failed foil move skips that test and proceeds to the next;
    skipped tests and any loss of fit coverage are reported at the end.
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

# Default coverage: 8.8, 16, 19.5 keV, with modeled margin inside the hard bounds.
tests = make_ab_tests(pairs=5)
preview = preview_ab(tests, exposure_s=5)
```

The preview is a plain function and reads/writes **no hardware**. The plan also
supports `dry_run=True`; under `RE` it returns the same report without opening a
run or resolving devices:

```python
RE(attenuator_ab_calibration(tests, exposure_s=5, dry_run=True))
```

The current default generates **130 test definitions / 650 pairs / 1,300 frames**.
At 5 s this is **108 minutes of exposure**, approximately **374 minutes total
(6.2 hours)** with **10 seconds per complete stack change**. There are 40 tests
at 8.8 keV, 44 at 16 keV, and 46 at 19.5 keV, with no dark frames.
This is a coverage-first draft with
redundant equations, not a minimum-time experimental design.

Preview assumptions can be adjusted without touching hardware:

```python
preview_ab(tests, exposure_s=5, energy_move_s=240, stack_move_s=10,
           shutter_cycle_s=1, readout_s=0.2, geometry_s=30)
```

`energy_move_s` is an estimate **per visited energy**, including approach to the
first energy. The default is 180 s. `stack_move_s=10` estimates the total time for
both sequential bank moves, not 10 seconds per bank. This is a time-budget input,
not an extra acquisition sleep or a motion timeout. Sensitivity contributes at
least 60 s/energy (two 30 s waits). At 10 s exposures the full schedule takes
approximately 483 minutes with these estimates. Retries, tracking/recentering,
additional sensitivity attempts, analysis, file writing and suspender pauses make
wall time variable. The estimate includes every pair as two state moves even when
AB/BA ordering leaves adjacent frames in the same state.

## Explicit tests and per-test repeat counts

`a` and `b` are **complete inserted-stack lists across both banks**, not incremental
commands. All other foils are retracted. Labels use `bank_position`, e.g. `"2_9"`.

```python
tests = [
    {
        "id": "Al9_8p8keV",
        "energy_eV": 8800,
        "a": ["1_1", "1_2", "2_8"],
        "b": ["1_1", "1_2", "2_8", "2_9"],
        "pairs": 10,
    },
    {
        "id": "Al9_19p5keV",
        "energy_eV": 19500,
        "a": ["1_2", "1_3", "1_6", "2_11"],
        "b": ["1_2", "1_3", "1_6", "2_11", "2_9"],
        "pairs": 25,
    },
]
# Illustrative isolated foil tests, not a replacement for the full 24-foil design.
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

## Current three-energy commissioning sequence

1. Generate and preview the design above. All 23 usable foils remain independently
   identifiable at at least two energies; 19.5 keV covers all 23. `2_6` is excluded.
2. Acquire the three energy blocks with five AB/BA pairs per test, 5 s per frame,
   and `beam_shape=True`. Sensitivity is reapplied and confirmed at each energy;
   beam centroid, RMS widths, and side intensities are collected on the same frames.
3. Inspect paired scatter, width/centroid changes, normalized side intensities,
   and fit residuals before allocating follow-up repeats. Compare inferred
   thickness scales between energies with their uncertainties.
4. Treat the thin-Al cross-energy check as a lower-precision result. Do not claim
   the original 1% at 3-sigma target for 9, 18, or 36 µm Al from this default run.

To acquire the full schedule after preview:

```python
tests = make_ab_tests(pairs=5)
RE(attenuator_ab_calibration(
    tests, exposure_s=5, beam_shape=True,
    md={"sample_name": "attenuator_commissioning_8p8_and_up"},
))
```

Historical counting-only **1-sigma effective-thickness uncertainties (%)** for the
original 24-foil design are below, before excluding `2_6`; the regenerated design
has different references and covariance. They assume 1e12 incident photons/s, unit detection
efficiency/core capture, 5 s exposures and five pairs, with all reference foils
jointly fitted. The last column combines the two strongest energies in quadrature.
Harmonics, drift, dark uncertainty, and detector-response systematics are excluded.

| Foil | Al thickness, µm | 8.8 keV | 16 keV | 19.5 keV | Cross-energy difference |
|---|---:|---:|---:|---:|---:|
| `2_9` | 9 | 0.345 | 1.993 | 5.705 | 2.022 |
| `2_10` | 18 | 0.170 | 0.969 | 2.855 | 0.983 |
| `2_11` | 36 | 0.098 | 0.524 | 1.136 | 0.533 |
| `2_12` | 72 | 0.061 | 0.259 | 0.638 | 0.266 |
| `2_5` | 102 | 0.048 | 0.173 | 0.469 | 0.180 |

The default still gives useful single-energy thickness estimates at 8.8 keV.
Cu, Sn, Mo and the thicker Al retain strong counting statistics. Additional
thin-Al exposure should be chosen from observed variance rather than assuming
that nominal counting estimates describe the actual harmonic/background floor.

## Foil-movement failure recovery

### Progress during acquisition

Timestamped, flushed `A/B:` messages announce run opening/baseline, shutter
confirmation, detector timing and staging, individual alignment set/wait messages,
energy moves, sensitivity attempts and settling, ROI setup, each test/pair/state,
bank exchanges, exposure, frame saving, fitting and cleanup. The last message
identifies the operation being attempted if progress stops. Detector staging is
reported as a whole; internal plugin waits may require further diagnosis.

Fast-shutter handling first reads the actual controller status (`0` open, `7`
closed). If already in the requested state, it sends no command. Otherwise it
uses EPICS put-completion with a 5 s timeout, then confirms actual state with a
10 s polling timeout. It does not wait for the open/close command PV to remain
at `1`: these command buttons can reset after processing, so ordinary
`EpicsSignal.set(1)` readback matching can stall despite a completed action.
Progress messages distinguish the initial status read, command acknowledgement,
and actual-state confirmation.

To use edited code, first finish or abort the current run normally, then reload:

```python
%run -i docs/commissioning/attenuator_ab.py
```

Reloading does not change an already-running plan. After requesting a pause with
Ctrl-C, use `RE.abort()` once the prompt returns if abandoning that run; this
executes normal cleanup. Avoid `RE.halt()` when cleanup is needed.

### Skipping failed tests

If a foil exhausts its device-level retries or the finished move's readbacks do
not match the requested stack, the plan **skips the entire current A/B test** and
tries the next test. The fast shutter stays closed during the failed exchange.
All child foil statuses must finish before recovery proceeds: a bank's aggregate
status can fail before its other foils finish moving.

Each subsequent test attempts its own exact stacks and checks all 24 readbacks
before exposing. A foil stuck inserted may still permit tests that include it in
both states; one stuck retracted may permit tests that do not require it. There is
no permanent blacklist: a later request can succeed if the fault is intermittent.
Device retries can therefore extend the time budget when a fault persists.

The `skipped_tests` stream records the test ID, energy, zero-based pair index,
A/B state, number of completed pairs, requested inserted labels, all actual foil
readbacks as JSON, failure type (`foil_movement` or `insufficient_signal`), and
the failure reason. It is also returned as
`result["skipped_tests"]`. Partial frames remain in `primary`, but the skipped
test contributes **no attenuation or beam-shape summary and no fit equations**.
Offline analyses must exclude those test IDs unless explicitly reanalyzing the
partial data.

Cleanup prints completed/skipped counts, the skipped-test list with reasons, and
per-energy fit rank/unresolved foils. If every test at an energy is skipped, a
zero-rank diagnostic marks all 24 foils unresolved and the next energy proceeds.
A run that finishes its schedule with skips has a successful Bluesky stop status;
inspect `skipped_tests` and fit coverage to assess commissioning completeness.
There is no `skipped_tests` stream if nothing was skipped.

This recovery applies to finished foil-movement failures. Shutter, detector,
energy, readout/connection failures and motion that has not finished within the
60 s bank completion limit still terminate acquisition with normal cleanup.
The 60 s completion limit is distinct from the 10 s motion-cost estimate.

## One run, analysis-friendly streams

The plan opens **one Bluesky run**; the profile's normal document subscriptions
store it in Tiled. The plan itself does not create or connect a Tiled client.

| Stream | Contents |
|---|---|
| `primary` | Every A/B frame, detector readout and TIFF reference, raw counts, state, test ID, pair, actual/requested energy, labels, exposure and pixel-rate flag |
| `detector_settings` | Requested sensitivity, observed energy/threshold/gain, gain confirmation flag/source, and attempt count at each energy |
| `ab_summary` | B/A ratio, log attenuation difference and uncertainty for each completed test |
| `foil_summary` | Individual transmission, reciprocal attenuation factor, effective thickness and uncertainties at each fitted energy |
| `fit_diagnostics` | Fit rank, residual chi-square, degrees of freedom, unresolved labels and full optical-depth covariance as JSON |
| `roi_settings` | Full-camera rectangle for each of ROI1/2/3 at each energy; centroid threshold |
| `shape_summary` | Paired centroid/width/variance differences and left/right intensity normalized by core counts, with validity flags |
| `skipped_tests` | Failed test ID, energy, pair/state, completed pairs, requested stack, actual foil readbacks and reason; only emitted on a skip |

Start metadata contains the complete test definitions, per-test repeats, nominal
foil layout, transmission bounds and calculation model. Partial runs retain raw
events and all completed test/energy summaries. The plan's return value is a dict
with `uid`, `ab_summary`, `foil_summary`, `fit_diagnostics`, `shape_summary`, and
`skipped_tests`; whether `RE(...)`
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

Each pair contributes `ln(A) - ln(B)` with zero background assumed. A test summary uses the mean of
these differences, with independent variance given by the **larger** of the
propagated Poisson variance and the observed between-pair variance of the mean.
The generalized least-squares foil fit also supports a shared dark estimate in
offline reduction, but the current acquisition supplies none:

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
center and sets ROI1 to **40 × 40 pixels**. ROI2 and ROI3 are **128 × 128
pixels**, left and right of ROI1 with a **16-pixel edge-to-edge gap**. These are
starting dimensions, not a measured optimum; inspect the images to choose sizes
appropriate for the actual beam and module layout.

```python
RE(attenuator_ab_calibration(
    tests, exposure_s=10,
    beam_shape=True,
    beam_roi_size=(40, 40),
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

Every primary event includes:

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
side_per_pixel_per_core = side_counts / core_counts / side_ROI_pixel_area
```

The A/B change in this quantity removes the leading effect of different total
transmissions. Its uncertainty uses the larger of counting variance and observed
pair scatter for nonnegative counts. Finite zero/negative side values are retained;
negative totals use empirical paired scatter rather than a Poisson variance and
set `<side>_poisson_valid=False`. Nonfinite side totals are represented by `-1`
with `shape_<side>_counts_valid=False`; their normalized summaries are invalid.
The original detector fields remain in the saved readout. `<side>_normalized_valid`
and `<side>_sem_valid` distinguish available ratios and error estimates. Left and
right uncertainties share the core denominator;
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

No-signal centroid/width values are flagged invalid and do not abort acquisition.
Finite core counts at or below the assumed background are saved, but the test is
excluded from log-ratio fitting and recorded in `skipped_tests` with
`skip_failure_type="insufficient_signal"`. Negative side counts alone do not
invalidate the core transmission fit; inspect raw images to distinguish signed
totals from hardware sentinel values. The full-frame maximum must remain finite
and nonnegative for the pixel-rate check.

Commissioning metadata fields have explicit empty plotting hints; strings such
as the gain confirmation source are recorded without being offered to BEC plots.
Raw core/max-pixel-rate and beam widths are hinted, as are the main ratio/fit
summary values. Hints affect display only, not plugin calculations or acquisition.

From `profile_collection`, using the existing pixi test environment:

```bash
PYTHONPATH=src OPENBLAS_NUM_THREADS=1 .pixi/envs/test/bin/python -B -m pytest docs/commissioning/test_attenuator_ab.py -q
```

Simulation covers hardware-free preview, full-rank two-energy coverage, recovery
of deliberately changed foil thicknesses, uncertainty propagation, one-run
multi-energy acquisition, sensitivity reapply and failure, fresh-statistics
checks, saturation, trigger failure and closed-shutter/beamstop cleanup.
Additional tests cover ROI bounds/nonoverlap, shape capture, optional diagnostics,
distinguishing flux attenuation from a normalized side-intensity change, stuck
foil/status mismatch recovery, partial-test exclusion, all-skipped energy blocks,
and waiting for outstanding child moves after an aggregate failure. Live
detector readiness, fast-shutter readback mapping (0 open, 7 closed), direct-beam
ROI placement and real TIFF/Tiled ingestion still need commissioning verification.
