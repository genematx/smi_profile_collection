# Accepted thickness corrections and targeted follow-up

## Current calibration: v2, incorporating scans 1171325–1171327

Active ID: **`smi-attenuators-1171327-v2`**. On operator request, adopt the
consistent 16–17 keV follow-up measurements for the Mo targets and the available
single-energy Al baseline. This supersedes the v1 decisions below:

| Foil | Applied effective thickness, µm | 1σ, µm | Basis |
|---|---:|---:|---|
| 2_3 | **80.801630** | 0.037232 | 16, 16.5, 17 keV and 17 keV repeat |
| 2_4 | **181.884972** | 0.100291 | 16, 16.5, 17 keV and 17 keV repeat |
| 2_6 | **219.115923** | 0.550377 | Single 16 keV measurement from 1171325 |

The Mo means use inverse-variance weights across the four follow-up results;
reduced chi-square is 0.535 and 0.591, so no extra scatter inflation applies.
Their errors are statistical, assuming independent measurements, and exclude
shared systematics. The 19.5 keV discrepancy remains recorded, but those values
are excluded from these means. Use outside the adopted measurement energies is
a thickness-model extrapolation. **23 foils now use measured thicknesses; only
1_4 retains nominal thickness.** `2_6` remains excluded from the normal
commissioning design due to movement failures; a numerical correction does not
establish mechanical reliability.

At an idle console, reload both modules and refresh the existing device metadata:

```python
import importlib
from smi_beamline.devices import attenuator_calibration, attenuator_data
importlib.reload(attenuator_calibration)
importlib.reload(attenuator_data)
attenuation.state_md()
print(attenuator_data.CALIBRATION_ID)
```

Regenerate stack lists after reloading. The PDF currently records the earlier
v1 decision; this v2 adoption section and the code are the current calculation
record. Historical v1 values and follow-up findings are retained below.

## Historical v1 decision and source measurements

Source: scan **1171324**, UID `7cd58d5e-7f31-4fe4-b64f-aad0bde951db`,
Tiled `smi/raw`, acquired 2026-10-18. Calibration ID:
**`smi-attenuators-1171324-v1`**.

## Follow-up result: scan 1171325

UID **`4348a125-4a82-414e-9c5c-15c1513303e7`**. Completed successfully in
**13.06 minutes**: 5/6 tests, 21 frames (20 from complete tests, one partial
reference frame). Two AB/BA pairs per completed test, 10 s per frame.

| Foil | 16 keV thickness, µm | 19.5 keV thickness, µm | Decision |
|---|---:|---:|---|
| 2_3 (Mo 80 µm) | 80.86487 ± 0.06929 | 80.08146 ± 0.19861 | 3.72σ disagreement; retain nominal |
| 2_4 (Mo 160 µm) | 181.94951 ± 0.20832 | 180.19298 ± 0.34920 | 4.32σ disagreement; retain nominal |
| 2_6 (Al 204 µm) | 219.11592 ± 0.55038 | Insertion failed | Baseline measured; retain nominal pending second energy |

The follow-up independently reproduces the direction of the Mo energy
discrepancies with simple reference-plus-target comparisons. The reference
thickness cancels in each ratio, so these estimates do not rely on treating
the newly corrected reference thicknesses as known calibration truth. The
nominal material energy dependence, detector response, spectral contamination,
background and positioning repeatability still need investigation. Two pairs
provide limited empirical-noise evidence. The fits have **zero residual degrees
of freedom**; their near-zero chi-square is not an independent validation.

No new foil meets the existing two-energy acceptance rule. The active correction
therefore remains the same 20 foils under `smi-attenuators-1171324-v1`; follow-up
values are recorded separately in `attenuator_calibration.py`. The 16 keV Al
measurement is about **7.41% above nominal**, but is not applied across energies.

All five beam-moment summaries were valid. Maximum recorded pixel rate was
9,704 counts/pixel/s, with no saturation flags. Side-ROI totals remained negative
(left -1662 to -1592; right -1663 to -1591), so their quantitative interpretation
still needs image-level masking/background review.

### Next targeted actions

**Intermediate-energy check:** the helper now supports 16.5 and 17 keV for
`2_3`, `2_4`, and `2_6`. References are `1_1 + 1_3` at 16.5 keV and
`1_3 + 1_11 + 2_5` at 17 keV; both A and all three B states are within the
modeled 3e-9–3e-7 margin. The old 16 keV reference must not be reused at 17 keV,
where its predicted transmission exceeds 1e-6.

```python
%run -i docs/commissioning/attenuator_ab.py
intermediate = make_followup_tests(
    targets=("2_3", "2_4", "2_6"), energies_eV=(16500, 17000), pairs=2,
)
preview_ab(intermediate, exposure_s=10, excluded_foils=())
RE(attenuator_ab_calibration(
    intermediate, exposure_s=10, sensitivity_wait_s=30,
    excluded_foils=(), beam_shape=True, beam_roi_size=(40, 40),
    md={"sample_name": "attenuator_followup_16p5_17keV"},
))
```

This is six tests / 24 frames, about 17 minutes including estimated overhead.
It deliberately retries 2_6; ordinary failed-movement skipping remains active.

1. **2_6:** repair/check insertion, then repeat only its 19.5 keV simple-pair test;
   retain the new 16 keV baseline. Repeat 16 keV too if mechanical intervention
   could alter the foil or its illuminated position.
2. **2_3 and 2_4:** repeat with an alternate reference stack and a controlled
   detector-threshold comparison at fixed energy; check energy/readbacks and
   images before assigning the persistent difference to foil composition.
3. **1_4:** still needs the separate high-energy substitution cross-check.
4. Thin-Al precision, other intermittent foil failures, negative side ROIs,
   and the original 8.8 keV lack of fit remain open.

The combined [PDF report](../ATTENUATOR_COMMISSIONING_1171324.pdf) includes both
runs and the active-correction decision. The sections below preserve the
original acceptance calculation and follow-up design.

## Acceptance and combination

Use only the 16 and **19.5** keV estimates. Accept a foil when both estimates
exist, are positive, and differ by no more than three combined standard errors:
`z = abs(t16 - t19.5) / sqrt(s16² + s19.5²) <= 3`.
The errors from `foil_summary` already include each energy fit's residual
inflation (reduced chi-square 3.15 and 5.92).

For each accepted foil independently, use an inverse-variance weighted mean:

```
t = (t16/s16² + t19.5/s19.5²) / (1/s16² + 1/s19.5²)
sigma = sqrt(max(1, z²) / (1/s16² + 1/s19.5²))
```

The second expression includes two-point scatter inflation. This is a marginal
per-foil combination; errors among different foils remain correlated through
their joint fits. No independent-foil uncertainty propagation is claimed for
stack transmission. The archived `fit_covariance_json` contains those covariance
matrices. The 8.8 keV fit is excluded because of its severe lack of fit.

Statistical agreement is not a precision threshold or proof of composition.
In particular, thin Al has weak second-energy sensitivity. These are effective
thicknesses assuming the nominal composition and density. The corrections scale
the nominal optical depth at all tabulated energies; outside 16–19.5 keV this
is an extrapolation of the material/thickness model, not a measured validation.

## Values now used by the attenuation calculation

All values below are micrometres; errors are 1 sigma. Nominal specifications and
CXRO base curves remain intact. Four unaccepted positions retain nominal values.

| Foil | Material | Nominal | Applied effective thickness | Sigma |
|---|---|---:|---:|---:|
| 1_1 | Cu | 68 | 62.20276 | 0.11279 |
| 1_2 | Cu | 136 | 125.18089 | 0.21826 |
| 1_3 | Cu | 272 | 250.30152 | 0.42238 |
| 1_4 | Cu | 544 | **544 (nominal)** | — |
| 1_5 | Sn | 60 | 67.99583 | 0.11517 |
| 1_6 | Sn | 120 | 138.36407 | 0.22866 |
| 1_7 | Sn | 240 | 271.59666 | 0.39645 |
| 1_8 | Sn | 480 | 580.27712 | 0.77256 |
| 1_9 | Sn | 30 | 32.38423 | 0.15007 |
| 1_10 | Sn | 60 | 68.52314 | 0.10626 |
| 1_11 | Sn | 120 | 135.31775 | 0.20071 |
| 1_12 | Sn | 240 | 272.36662 | 0.39206 |
| 2_1 | Mo | 20 | 20.15130 | 0.05898 |
| 2_2 | Mo | 40 | 40.58803 | 0.22384 |
| 2_3 | Mo | 80 | **80 (nominal)** | — |
| 2_4 | Mo | 160 | **160 (nominal)** | — |
| 2_5 | Al | 102 | 111.95125 | 1.01778 |
| 2_6 | Al | 204 | **204 (nominal)** | — |
| 2_7 | Al | 408 | 438.02879 | 1.31146 |
| 2_8 | Al | 816 | 880.90299 | 1.45469 |
| 2_9 | Al | 9 | 9.56114 | 1.39957 |
| 2_10 | Al | 18 | 19.07682 | 1.11069 |
| 2_11 | Al | 36 | 41.28775 | 0.76056 |
| 2_12 | Al | 72 | 56.47252 | 1.22999 |

Implementation: `src/smi_beamline/devices/attenuator_calibration.py` records the
source estimates, agreement rule, and combined values. `attenuator_data.py`
applies `effective/nominal` to each physical foil's optical depth. Combination
transmission, reciprocal factor, automatic stack selection, and Pilatus totals
using the attenuation provider therefore share the corrected model. Start metadata
includes the calibration ID and per-inserted-foil nominal/effective thicknesses.
Commissioning fits still divide by **nominal** optical depth so that a later
calibration cannot accidentally be applied twice.

For historical reproduction, use `calibrated=False` with `foil_optical_depth`,
`combination_optical_depth`, `transmission`, or `attenuation_factor`. The original
PDF summarizes the original measurements, not this later adoption decision.

The running console retains imported code. At an **idle** prompt, this reload
updates the physics module referenced by existing attenuation devices without
moving hardware:

```python
import importlib
from smi_beamline.devices import attenuator_data
importlib.reload(attenuator_data)
print(attenuator_data.CALIBRATION_ID)
attenuation.state_md()  # refresh calculated metadata using the current foil state
```

A fresh profile session also loads the correction. Existing saved runs are not
rewritten. Regenerate any commissioning `tests` after changing the model.

## Foils still needing attention

### Missing or inconsistent thickness calibration

- **2_6, Al 204 µm:** initially unmeasured; follow-up now provides the 16 keV baseline above. Fix/check insertion first. Keep excluded
  from the normal commissioning design. The targeted follow-up explicitly opts in.
- **2_3, Mo 80 µm:** original 81.075 ± 0.160 versus 79.531 ± 0.374 µm; 3.79-sigma disagreement, confirmed by follow-up at 3.72 sigma.
- **2_4, Mo 160 µm:** original 182.633 ± 0.286 versus 179.809 ± 0.639 µm; 4.04-sigma disagreement, confirmed by follow-up at 4.32 sigma.
- **1_4, Cu 544 µm:** good single-energy candidate 563.065 ± 1.609 µm at 19.5 keV,
  but unavailable at 16 keV. No accepted two-energy correction yet.

### Precision and mechanical follow-up

- **2_9, Al 9 µm:** combined uncertainty about 15%; also five failure mentions.
- **2_10, Al 18 µm:** combined uncertainty about 6%; optional precision follow-up.
- **2_2, Mo 40 µm:** borderline 2.61-sigma agreement; correction accepted with
  enlarged uncertainty, but include in the Mo follow-up if practical.
- **1_9, Sn 30 µm** and **1_8, Sn 480 µm:** nine and six failure mentions,
  respectively, despite good final thickness estimates. Their priority is
  repeatability, not another unconstrained full-stack fit.
- Other failure mentions: 2_7 (2), 2_2 (2), 1_2 (2), 1_5 (2), 2_12 (1),
  1_10 (1), 1_7 (1), 1_6 (1). These counts are not per-move failure rates.

## Minimal-movement baseline follow-up

Use fixed reference stacks, adding just the target foil. Reference thickness
cancels from `B/A`; the online fit identifies each target independently. Two
10 s pairs in AB/BA order give **A B B A**: one insertion and one retraction per
test. Consecutive B frames check counting repeatability without another foil
cycle. This is a baseline, not a precise motion-reliability measurement.

| Energy | Fixed reference A | B |
|---|---|---|
| 16 keV | 1_3 + 2_8 | A + target |
| 19.5 keV | 1_3 + 1_11 + 1_12 + 2_8 | A + target |

Reference transmissions under the corrected model are about 1.98e-7 and 2.49e-7.
Both states for the default targets 2_3, 2_4, 2_6 lie inside the 1e-9–1e-6 bounds.
The 19.5 keV reference uses four fixed foils to avoid repeatedly moving 1_8/1_9
and to maintain brightness; B uses five foils. Explicit stack lists support this.

```python
%run -i docs/commissioning/attenuator_ab.py
followup = make_followup_tests()  # 2_3, 2_4, 2_6; two pairs at each energy
preview_ab(followup, exposure_s=10, excluded_foils=())
# Once 2_6 is ready for an insertion attempt:
RE(attenuator_ab_calibration(
    followup, exposure_s=10, excluded_foils=(), beam_roi_size=(40, 40),
    md={"sample_name": "attenuator_targeted_followup"},
))
```

This is **6 tests / 12 pairs / 24 frames**, 4 minutes exposure and approximately
17 minutes including nominal energy/sensitivity/motion overhead. Failure still
skips a whole test. Add 2_2, 2_9, 2_10 or 1_9 to `targets` for specific checks;
thin-Al precision will remain limited in such a short baseline. Do not infer
successful insertion just from a command acknowledgment; all readbacks are checked.

### Cu 1_4 and thick Sn 1_8: substitution checks

These cannot be added to the above references while keeping both states within
the measurement window. Use targeted substitutions, not the simple-pair helper:

- **1_4 at 19 and 19.5 keV:** measure the foil alone as B; references can be
  `1_1 + 1_3 + 1_7` at 19 keV and `1_3 + 1_7 + 1_12` at 19.5 keV. Two AB/BA
  pairs per energy give a short high-energy repeatability check. The close energy
  spacing provides only a weak material test.
- **1_8 at 16 keV:** B = `1_8` alone, A = `1_3 + 2_8`. Two pairs provide a
  minimal insertion/retraction check without loading it into many stacks.

These isolated substitutions do **not** identify the target in the unconstrained
online foil fit. Reduce offline as `tau_target = tau_reference + ln(A/B)` using
the accepted reference calibration and its archived covariance. Retain that
reference uncertainty; do not silently substitute nominal reference thicknesses
or treat an unresolved online fit as a measured thickness. Run these separately
from the simple-pair schedule and retain all raw frames for this reduction.
