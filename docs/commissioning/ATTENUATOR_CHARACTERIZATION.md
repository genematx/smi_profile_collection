# Attenuator characterization: thickness and material checks

**Staged here for transfer to `SWAXS_user_scripts/commissioning`.** The executable
draft and instructions are in [attenuator_ab.py](attenuator_ab.py) and
[README.md](README.md). Statistical tables below are planning estimates; use the
executable preview for the actual chosen A/B list and exposure duration.

## Goals

1. Assuming the specified material, determine an independent effective thickness
   for each of the 24 physical foil positions across both banks.
2. Test whether that same thickness explains transmission at other energies.
   Energy-dependent residuals motivate a material/composition investigation after
   accounting for backgrounds, detector response, and harmonic contamination.
3. Collect simultaneous beam-profile and off-axis intensity diagnostics for each
   A/B stack comparison: ROI1 centroid/width, plus left/right ROI2/ROI3 counts.
   The commissioning plan now records these with paired uncertainty summaries;
   see [README.md](README.md#beam-broadening-and-off-axis-background-on-the-same-frames).
   They are roughness/scattering proxies, not a direct roughness calibration.

Transmission measures areal density. Converting it to thickness assumes the
specified material density and beam path geometry. A density change is therefore
indistinguishable from a thickness change using these measurements alone.

## Existing acquisition plans

`src/smi_beamline/plans/attenuator_calibration.py` already contains:

- `attenuator_thickness_calibration`: exposed by `startup/startup.py`; measures
  exact physical foil combinations, defaults to all single foils and adjacent
  pairs within each base-thickness family, and inserts open-beam references.
- `attenuator_two_pass_calibration`: diode pass followed by a high-attenuation
  Pilatus pass, with alignment/measurement geometry transitions. This wrapper is
  defined in the module but is not explicitly imported by startup.

The default energy list is 5, 6.5, 8, 10, 12, 16, 19, 22, and 24 keV. The plans
record measurements for offline analysis; they do not fit thicknesses or perform
the material-consistency test. They are a starting point for acquisition, rather
than a complete implementation of the protocol below.

Nominal specifications and CXRO transmission curves are in
`src/smi_beamline/devices/attenuator_data.py`. The physical inventory is:

| Positions | Specified material | Nominal thicknesses, µm |
|---|---|---|
| `1_1`–`1_4` | Cu | 68, 136, 272, 544 |
| `1_5`–`1_8` | Sn | 60, 120, 240, 480 |
| `1_9`–`1_12` | Sn | 30, 60, 120, 240 |
| `2_1`–`2_4` | Mo | 20, 40, 80, 160 |
| `2_5`–`2_8` | Al | 102, 204, 408, 816 |
| `2_9`–`2_12` | Al | 9, 18, 36, 72 |

Fit each position separately, even where nominal thicknesses match. In particular,
the duplicate Sn thicknesses provide useful independent cross-checks.

## Direct-beam constraint and calculated coverage

The usable direct-beam range is **total transmission `1e-9 <= T <= 1e-6`**,
equivalently attenuation factors `1e6`–`1e9` in the code's reciprocal convention.
The requested energy range is **6–20 keV**. All acquisition and reference states
must satisfy this constraint; an unattenuated direct-beam reference is not part
of this protocol.

**All 24 positions are identifiable in the nominal monochromatic model**, using
stack substitutions and a joint fit. **21 of 24** also have a feasible simple
reference-plus-test measurement somewhere in this energy range.

For a simple pair `R` and `R + foil`, both states must fit into the three-decade
window. This requires `T_foil >= 1e-3` (optical depth at most `ln(1000)`). The
three positions that never satisfy that condition anywhere from 6–20 keV are:

| Position | Nominal foil | Largest modeled transmission in 6–20 keV |
|---|---|---|
| `1_3` | Cu 272 µm | `2.87e-4` at 20 keV |
| `1_4` | Cu 544 µm | `8.26e-8` at 20 keV |
| `1_8` | Sn 480 µm | `9.53e-4` at 20 keV |

These require replacing other foils rather than simply adding the test foil.
The Sn limit is close to the boundary, so actual thickness could change its
simple-pair eligibility; the substitution method does not rely on that.

### Enumeration check

Enumerating all physical subsets with one through four inserted foils using the
current nominal CXRO table gives:

| Energy, keV | Positions appearing in allowed stacks | Rank including unknown incident-flux intercept | Missing positions |
|---|---|---|---|
| 6 | 12 | 13 / 13 | Mostly thick metal foils |
| 8.8 | 21 | 22 / 22 | `1_7`, `1_8`, `1_12` (Sn 240/480/240 µm) |
| 16 | 23 | 24 / 24 | `1_4` (Cu 544 µm) |
| 19.5 | 24 | 25 / 25 | None |

The ranks are for the augmented foil-incidence matrix `[1, X]` over allowed
stacks, not merely counts of foils that appear. Thus individual optical depths
and an unknown flux intercept can be distinguished at each of these energies
without assuming calibrated reference thicknesses. This is an identifiability
check, not a prediction of experimental precision or a proposed exhaustive scan.
The same coverage and full ranks persist for the narrower nominal window
`3e-9 <= T <= 3e-7`, leaving some margin for thickness errors.

### Recommended initial energies

Use **6, 8.8, 16, and 19.5 keV**, selecting a compact, well-conditioned set of
stacks at each energy:

- Thin Al: prioritize 6 and 8.8 keV for meaningful thickness sensitivity.
  For example, 9 µm Al transmits about 0.765 at 6 keV but 0.992 at 19.5 keV.
- Thick Sn: use 16 and 19.5 keV.
- Thickest Cu: use 8.8 and 19.5 keV. Its single-foil transmission is approximately
  `6.13e-9` and `2.48e-8`, respectively, so it is itself an allowed measurement
  state. These energies also straddle the Cu K edge at approximately 8.98 keV.
- Other foils: select at least two of these energies, emphasizing measurable
  optical depth and well-conditioned combinations.

This gives every foil at least two independently identifiable energy points.
If minimizing energy changes is paramount, 19 and 19.5 keV both support all
24 positions, but that close pair is a weak material test and poorly sensitive
to thin Al. The wider four-energy set is preferable.

The 20 keV upper bound does not provide a clean above-edge point for the Mo K
edge near 20.0 keV. The existing 46 eV grid interpolates across that edge, so a
value at exactly 20 keV should not be used as a resolved edge measurement.
Al and Sn also have no accessible diagnostic edges in 6–20 keV. Their energy
dependence tests consistency, without uniquely proving composition.

## Statistical precision and exposure budget

### Assumptions and significance target

The following are **shot-noise planning estimates**, assuming `1e12 photons/s`
incident on the attenuators, 1 s exposures, unit detection efficiency/ROI capture,
linear photon counting, negligible background uncertainty, and perfect correction
of incident-flux drift. Counts per exposure are therefore:

| Total transmission | Detected counts | Single-exposure Poisson noise |
|---|---:|---:|
| `1e-6` | 1,000,000 | 0.100% |
| `1e-7` | 100,000 | 0.316% |
| `1e-8` | 10,000 | 1.00% |
| `1e-9` | 1,000 | 3.16% |

Specify an effect size before choosing repeats. As a worked target, use a **1%
effective-thickness change at nominal 3-sigma significance**. For the material
check, use a **1% difference in the inferred thickness scale between energies**;
this is not equivalent to detecting 1% impurity concentration.

One pair means one 1 s reference exposure and one 1 s test exposure; both remain
attenuated. For `n` independent pairs, expected counts per exposure `N_off` and
`N_on`, and foil optical depth `tau`, near the nominal thickness:

```text
sigma_tau^2 = (1/N_off + 1/N_on) / n
sigma_s = sigma_tau / tau
n >= z^2 * (1/N_off + 1/N_on) / (delta_s^2 * tau^2)
```

Round upward. For two independent energies measured with `n` pairs each, let
`v_E = (1/N_off + 1/N_on) / tau_E^2` and use
`n >= z^2 * (v_E1 + v_E2) / delta_s^2`.

These are expected signal-to-standard-error thresholds. To achieve approximately
90% detection probability at a two-sided 3-sigma threshold, use approximately
`(3 + 1.282)^2` instead of `3^2`, about twice the unrounded exposure budget.
The quoted significance is per test, without a multiple-comparisons correction.

### Simple-pair counts, brightest allowed references

For each foil and each of 6, 8.8, 16, and 19.5 keV, enumerate reference stacks
of at most three other foils, keeping both reference and reference-plus-test
within `1e-9 <= T <= 1e-6`. Choose the brightest allowed reference, then the two
energies with lowest counting variance. This gives the following lower-bound
budget for the 21 simple-pair foils:

| Position | Material/thickness, µm | Best / second energy, keV | Pairs for 1% thickness at best energy | Pairs **at each energy** for 1% energy discrepancy |
|---|---|---|---:|---:|
| `1_1` | Cu 68 | 8.8 / 19.5 | 1 | 1 |
| `1_2` | Cu 136 | 8.8 / 19.5 | 1 | 2 |
| `1_5` | Sn 60 | 16 / 19.5 | 1 | 1 |
| `1_6` | Sn 120 | 19.5 / 16 | 1 | 1 |
| `1_7` | Sn 240 | 19.5 / 16 | 1 | 2 |
| `1_9` | Sn 30 | 8.8 / 16 | 1 | 1 |
| `1_10` | Sn 60 | 16 / 19.5 | 1 | 1 |
| `1_11` | Sn 120 | 19.5 / 16 | 1 | 1 |
| `1_12` | Sn 240 | 19.5 / 16 | 1 | 2 |
| `2_1` | Mo 20 | 8.8 / 16 | 1 | 2 |
| `2_2` | Mo 40 | 16 / 8.8 | 1 | 1 |
| `2_3` | Mo 80 | 16 / 19.5 | 1 | 1 |
| `2_4` | Mo 160 | 19.5 / 16 | 1 | 1 |
| `2_5` | Al 102 | 6 / 8.8 | 1 | 1 |
| `2_6` | Al 204 | 8.8 / 6 | 1 | 2 |
| `2_7` | Al 408 | 8.8 / 16 | 1 | 1 |
| `2_8` | Al 816 | 16 / 19.5 | 1 | 1 |
| `2_9` | Al 9 | 6 / 8.8 | 3 | 28 |
| `2_10` | Al 18 | 6 / 8.8 | 1 | 8 |
| `2_11` | Al 36 | 6 / 8.8 | 1 | 3 |
| `2_12` | Al 72 | 6 / 8.8 | 1 | 1 |

These references can be very close to the upper transmission boundary; they are
precision bounds, not an exposure-ready state list. A nominal reference near
`3e-7` instead of `1e-6` increases count-limited repeat requirements by roughly
3.3 when the same foil ratio is retained. Changing stacks changes the exact
budget, and some high-optical-depth simple pairs no longer fit a narrowed window.

For 9 µm Al, actual enumerated simple pairs give:

- At 6 keV: reference `1_2`, about 974,570 off and 745,560 on counts;
  `tau = 0.26786`, giving 0.574% thickness-scale uncertainty per pair.
- At 8.8 keV: reference `1_3 + 1_9 + 2_10`, about 999,224 off and 915,376 on
  counts; `tau = 0.08764`, giving 1.651% thickness-scale uncertainty per pair.
- Thus 28 pairs at **each** energy take 112 s of exposure, excluding motion and
  settling. Unequal allocation can improve this: for example, 9 pairs at 6 keV
  and 37 at 8.8 keV meet the same ideal 3-sigma target in 92 s of exposure.
- Direct enumeration with both states inside `3e-9`–`3e-7` instead gives 11 pairs
  for the 6 keV thickness test and 94 pairs at each energy for the energy check.

### The three substitution-only foils

There is no independent on/off-pair count for `1_3`, `1_4`, and `1_8`: their
precision includes the uncertainty and covariance of the other fitted foils.
For a proposed joint design with row `a = [1, -X]` and expected counts `N`, use
the Poisson information matrix `F = sum_states N * a.T * a`. Invert `F` and
divide the optical-depth variances by `tau_i^2` for thickness-scale variances.
Include additional nuisance parameters when fitting drift or backgrounds.

An offline illustrative design using only nominal transmissions `3e-9`–`3e-7`
and at most four foils per state was constructed by weighted row-pivot selection,
followed by greedy information-gain selection. With all active optical depths
and an unknown flux intercept free, the resulting 1 s exposure blocks give:

| Energy | Exposures in block | Cu 272 µm uncertainty | Cu 544 µm uncertainty | Sn 480 µm uncertainty |
|---|---:|---:|---:|---:|
| 8.8 keV | 44 | 0.145% | 0.128% | Unavailable |
| 16 keV | 48 | 0.133% | Unavailable | 0.133% |
| 19.5 keV | 50 | 0.154% | 0.144% | 0.151% |

These are one-sigma uncertainties in thickness scale, including joint-reference
uncertainty in the ideal model. Comparing 8.8/19.5 keV for Cu or 16/19.5 keV for
Sn gives approximately 0.19–0.21% uncertainty in the difference. One such block
at each energy therefore suffices statistically for a 1% difference at 3 sigma.
The blocks serve many foils simultaneously; their exposures are not charged
separately to each foil. This illustrates feasibility, not an optimized or
commissioned acquisition sequence.

### Noise floors and practical allocation

- Photon efficiency, ROI capture, and actual incident flux scale the required
  counts: repeat budgets scale inversely with effective detected flux and exposure
  time. Energy-dependent efficiencies affect each energy separately.
- A ratio's residual random log-noise variance adds to `1/N_off + 1/N_on`.
  Background subtraction and incident-monitor noise must be propagated as well.
- A systematic log-ratio floor `f` produces a thickness-scale floor `f/tau` and
  does not disappear by repetition. For 9 µm Al at 8.8 keV, detecting 1% thickness
  at 3 sigma requires ratio uncertainty below about **0.029%**, and still lower
  per-energy uncertainty if both energies contribute equally to a comparison.
- Required repeats scale as `1/delta_s^2`: a 0.5% effect needs four times the
  unrounded budget; a 0.1% effect needs 100 times. A 5-sigma criterion multiplies
  the 3-sigma budget by `25/9`.
- Start with 5–10 independent pairs or repeated selected stacks to measure actual
  variance, insertion repeatability, and drift, then allocate further exposures
  using the measured variance. One mathematically sufficient pair cannot itself
  validate the assumed noise model.

## Measurement sequence

### 1. Establish measurement conditions

- Use a downstream direct-beam detector that sees both banks, with no sample in
  the beam. Keep total transmission within the specified window.
- Measure shutter-closed dark/background at each detector setting, before and
  after a block. Establish linearity throughout the three-decade signal range.
- Prefer fixed gain/threshold within a block. Normalize counts by exposure time;
  if detector ranges change, acquire overlap states to determine relative scale.
- If available, record an incident monitor upstream of both banks. A monitor
  affected by either tested bank cannot serve as an independent incident reference.
- Record actual energy, foil position readbacks, diode range/integration settings,
  timestamps, and relevant optical settings. Allow the beam and electrometer
  averaging to settle after changes.
- For Pilatus measurements use raw ROI counts and exposure time. Do not use the
  attenuation-corrected totals: they already incorporate the model being tested.

### 2. Measure overlapping stacks

At each selected energy, measure a repeatable attenuated reference stack, then
small groups of selected stacks, followed by the reference again. Start with
reference brackets every 3–4 states and shorten if drift requires it. Include
simple reference-plus-foil pairs where possible and substitutions that separate
the three strongly absorbing foils. Select the state list by rank and expected
uncertainty rather than measuring every allowed combination.

Take at least three independent settled readings per state, and repeat an
insert/retract cycle to separate detector noise from positioning repeatability.
Repeated reads must span fresh electrometer integration windows rather than
sample the same cached mean repeatedly. Reverse the foil order in a repeat block
to expose time-dependent bias.

Interpolate the normalized attenuated references in time. For a downstream signal
`S`, dark `D`, and optional upstream signal `U` with dark `D_U`, use:

```text
J = (S - D) / (U - D_U)       # omit the denominator if no upstream monitor
ratio(E) = J_(R+foil)(E) / J_R_interpolated(E)
tau_foil(E) = -ln(ratio(E))   # for unchanged reference stack R
```

Calculate each ratio at the same energy. Absolute flux and detector efficiency
may change between energies without invalidating these within-energy ratios.
Propagate reference, background, range-transfer, and repeatability uncertainty;
shared references produce correlated errors. Treat below-background measurements
as limits, not as positive transmissions manufactured for a logarithm.

For general substitutions, fit all selected states at a given energy jointly:

```text
ln(J_state) = b_E - sum_i X_state,i * tau_i(E)
```

Here `X` records physical insertion (0 or 1), `b_E` is an unknown flux/detector
normalization, and each `tau_i(E)` is an independent foil optical depth. Normalize
drift with an upstream monitor and repeated reference states; do not allow an
independent free intercept for every measurement. Full column rank of `[1, X]`
is required. Fit background-inclusive signals instead when log-space noise is
inappropriate. This jointly calibrates the reference foils as well as test foils;
using nominal reference transmissions as known values would bias the result.

### 3. Validate combinations and difficult foils

After fitting individual optical depths, measure selected same-material and cross-bank combinations
as held-out validation data. Test `tau_AB = tau_A + tau_B`, or `T_AB = T_A*T_B`.
Include the independent equal-thickness Sn pairs (`1_5` vs `1_10`, `1_6` vs
`1_11`, `1_7` vs `1_12`). Choose combinations that remain measurable.

For signals beyond one detector/range's dynamic range, use overlapping reference
states with a measured normalization chain. A fixed reference foil can cancel
in `I(reference + test)/I(reference)` for a monochromatic beam; it cannot be
assumed to cancel for a harmonic-contaminated spectrum. Establish a diode/Pilatus
overlap if combining their data; their energy responses differ.

Include dedicated harmonic/background diagnostic states within the allowed window.
Excess transmission or failure of optical-depth additivity is evidence to
investigate leakage, scatter, fluorescence, foil nonuniformity, or detector
nonlinearity before assigning a different material.

## Analysis: the two requested checks

### Check 1 — specified material, free effective thickness

For each physical foil, obtain its nominal optical depth `tau_nom(E)` from the
table and fit one positive scale factor `s_i`:

```text
tau_meas_i(E) = s_i * tau_nom_i(E)
t_eff_i = s_i * t_nom_i
thickness_difference_percent = 100 * (s_i - 1)
```

First fit the best-conditioned energy, then predict the other energies without
refitting. If consistent, fit all accepted measurements jointly for the final
effective thickness and uncertainty. Do not force the 1x/2x/4x/8x positions to
have exact thickness ratios. Fit in signal/transmission space when the noise or
background makes a log-space Gaussian fit inappropriate.

### Check 2 — energy dependence after thickness is removed

Plot `s_i(E) = tau_meas_i(E)/tau_nom_i(E)` with uncertainties. A constant value
is consistent with the specified material and an effective-thickness correction.
Equivalently, for two usable energies, test:

```text
tau_meas(E1) / tau_meas(E2) = tau_nom(E1) / tau_nom(E2)
```

Thickness cancels in this ratio. Use residual significance and a stated practical
tolerance to flag discrepancies, rather than a universal percentage cut on
transmission. For small optical depth, `sigma_s/s` is approximately
`(sigma_T/T)/tau`, so nearly transparent foils require especially stable references.

A failed consistency test does not identify the contaminant. Check repeatability,
energy calibration, backgrounds, harmonics, and combinations first. With enough
additional independent energies, compare specified-material fits against plausible
alternative elements or mixture areal-density models. Two points cannot generally
separate thickness, composition, and spectral leakage simultaneously.

For explicit harmonic fits, a useful normalized model is
`T_obs(E) = sum_n w_n(E) * exp(-tau(n*E))`, with nonnegative detector-weighted
fractions summing to one, and a separately measured background. Constrain these
fractions with diagnostic data rather than freeing them independently for every
foil. The current tables stop at **25 keV** and clamp out-of-range queries, so
they must be extended before evaluating higher harmonics above that range.

## Acquisition work needed before implementing this protocol

Build on the existing plan with:

1. Energy-specific stack selection within the two-sided transmission window,
   including reference states, a predicted-transmission preview, and full-rank
   substitution designs. Recheck coverage with margins for thickness uncertainty.
2. Explicit dark blocks, repeated fresh integrations, insertion-cycle repeats,
   incident normalization, and detector range/exposure metadata. The current
   `pdcurrent` is a scalar EPICS mean-value signal; triggering it does not itself
   request a new integration. The existing state deduplication also removes
   duplicate combinations, so repetition needs a separate loop.
3. Explicit attenuated direct-beam geometry/reference sequences. The existing
   wrapper removes the SAXS beamstop and its inner plan still visits open states,
   including at each energy's end. `pilatus_min_factor` only gates triggering;
   it does not prevent open-beam exposure or provide a Pilatus normalization.
   Replace open references and open restoration, enforce both transmission bounds,
   and sequence transitions so intermediate states do not expose the detector
   above the allowed transmission (e.g. close the beam during stack exchanges).
   Specify the intended end state as part of that sequence as well.
4. Offline reduction and fitting with uncertainty propagation and the two checks
   above. Save a versioned candidate calibration alongside the nominal model.

## Deliverables and completion criteria

- Per-position table: material, nominal thickness, effective thickness and
  uncertainty, percentage difference, usable energies, fit residuals, and flags.
- Measured/model transmission plots and thickness scale versus energy for every
  foil, plus held-out combination residuals.
- Raw run UIDs, dark/reference associations, actual settings, and model provenance.
- Every position has either a thickness estimate and at least two usable-energy
  checks, or an explicit unresolved measurement requirement. Three energies are
  preferable for suspicious foils.
- A separate candidate correction file, retaining nominal specifications, ready
  for review against the combination validation before production use.
