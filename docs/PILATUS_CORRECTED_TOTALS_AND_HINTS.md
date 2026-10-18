# Pilatus attenuation-corrected totals and stats selection

Status: **IMPLEMENTED — SIMULATION TESTED; BEAMLINE COMMISSIONING PENDING**.
Both live detector instances are wired to the strict attenuation provider at startup.

## Goal

Make `count([pil2M])`, `scan([pil2M], ...)`, and the equivalent WAXS plans record
stats 1–5 consistently, including attenuation-corrected totals. Provide one convenient
operation to select any combination of stats for live tables/plots, using raw or
corrected totals, without accidentally removing other stats from recorded events.

The supported acquisition is a settled step: energy and foil positions are settled
before triggering and remain fixed until all detector reads for that point finish.
The areaDetector stats are fast IOC readbacks. With the state held fixed, correction
can use a single attenuation read during detector readout. No acquisition-time latch
is needed for this workflow. Timing and provenance below describe that guarantee
precisely.

## Background and migration

- `src/smi_beamline/devices/pilatus.py` defines a shared `Pilatus` base for
  `SAXS_Detector` and `WAXS_Detector`. Its five `StatsWCentroid` components explicitly
  now use `read_attrs=["total", "total_corrected"]`.
- Previously, `Pilatus.set_primary_roi(num)` reset the detector's `read_attrs` to the
  chosen stats plugin and TIFF plugin, coupling plotting selection to recording.
  It now delegates to raw `hint_stats()` and retains all stats and other readouts.
- `src/smi_beamline/instances/pilatus.py` now uses `hint_stats(1)` instead of restoring
  raw stats kinds manually after a narrowing selection. All five raw/corrected totals
  are recorded, with raw stats1 hinted by default.
- Ophyd `kind="normal"` means recorded; `kind="hinted"` additionally recommends a
  field for display. A single displayed stats1 column does not mean only stats1 is
  in the event. Callbacks ultimately decide how to use hints.
- `attenuation` is an `AttenuatorSet`. Its `attenuation_factor` is a cached ordinary
  `Signal`, not an ophyd `DerivedSignal`. The parent refreshes it during `compute()`,
  `trigger()`, `read()`, and after a set. Calling the child signal's `.get()` alone
  does not recalculate for changed energy or foil positions.
- `AttenuatorSet.read_state()` calculates current attenuation without updating its
  signals or run metadata. Its factor is `1 / transmission`, so correction multiplies
  the measured total by that factor.
- Its default non-strict mode can substitute a cached/midpoint energy when live energy
  is unavailable and replace a non-finite factor with `_ad_MAX_FACTOR`. The underlying
  attenuation tables also clamp out-of-range energies. Those convenience behaviors
  are bypassed by the strict correction provider.

## Operator interface

Existing raw fields are retained, with read-only corrected components:

```python
pil2M.stats1.total
pil2M.stats1.total_corrected
# ... through stats5, on both pil2M and pil900KW
```

Use the detector method or the short operator-facing wrapper:

```python
# Same behavior through either entry point:
pil2M.hint_stats([1, 3], corrected=True)
hint_pilatus_stats(pil2M, [1, 3], corrected=True)

RE(bp.count([pil2M]))

# Select raw totals from stats2 and stats5 instead.
hint_pilatus_stats(pil2M, [2, 5], corrected=False)

# Convenient single selection, all stats, and no stats hints.
hint_pilatus_stats(pil2M, 1, corrected=False)
hint_pilatus_stats(pil2M, [1, 2, 3, 4, 5], corrected=True)
hint_pilatus_stats(pil2M, [], corrected=False)

# WAXS has the same interface and an independent selection.
hint_pilatus_stats(pil900KW, [1, 4], corrected=True)
```

These are ordinary Python configuration functions, called before starting a run;
they do not acquire data or move hardware. Continue passing the parent detector to
acquisition plans: selecting/reading a child signal does not trigger a Pilatus exposure.

### Named ROI calculations: reflectivity and arbitrary math

Register a Python function between runs. Its `roi` argument is an immutable mapping
from stats indices 1–5 to the **same parent-read snapshot** used for the event.
`corrected=True` supplies attenuation-corrected totals; `False` supplies raw totals.

```python
def reflectivity(roi):
    return roi[1] - 0.5 * (roi[4] - roi[1])

refl = pil2M.add_roi_calculation(
    "refl", reflectivity, corrected=True,
    description="ROI1 - 0.5 * (ROI4 - ROI1)",
)
pil2M.hint_calculations("refl")
RE(bp.count([pil2M]))
```

The event field and plot label are exactly **`refl`**, without a detector prefix.
Only `refl` is hinted among stats totals/calculations; all five raw totals, all five
corrected totals, provenance, and registered calculations are still recorded.
Unrelated hints are preserved. This is background-subtracted intensity, not incident-
flux-normalized reflectivity. The factor `0.5` assumes ROI4 contains ROI1 and its
remaining background area is twice ROI1's area.

Use this template for other scalar math:

```python
def my_calculation(roi):
    return (roi[2] + roi[3]) / roi[5]

pil2M.add_roi_calculation("roi_ratio", my_calculation, corrected=False,
                         description="(ROI2 + ROI3) / ROI5")
pil2M.hint_calculations(["refl", "roi_ratio"])

# To display ROI totals alongside the calculations:
pil2M.hint_stats([1, 2, 3], corrected=True)
pil2M.hint_calculations("refl", clear_stats=False)

# Inspect the last successful read, without recalculating/acquiring:
pil2M.calculations["refl"].get()  # also available as refl.get()

# Clear calculation hints, retaining stats hints:
pil2M.hint_calculations([], clear_stats=False)

# Remove or redefine a calculation between runs:
pil2M.remove_roi_calculation("roi_ratio")
```

- Functions must return a finite numeric scalar and use only their supplied inputs
  (no hardware reads or writes). Functions can use ordinary Python/math/NumPy
  operations. Division by zero, missing ROI indices, non-finite results, and other
  exceptions fail the parent read without publishing any partial snapshot. Negative
  background-subtracted intensities are valid.
- `hint_calculations()` replaces calculation hints and by default clears stats-total
  hints; `hint_stats()` preserves calculation hints. Neither removes recorded fields.
- Names must be public Python identifiers and unique within the detector. Use distinct
  names across devices in a stream, e.g. `refl` and `waxs_refl` if both detectors have
  calculations. Duplicate registration is rejected; remove first to redefine.
- Registrations last for the Python session and are not enabled automatically at
  startup. Configure/register/remove between runs; these methods reject staged or
  currently-reading detectors. The returned signals are read-only and available via
  `detector.calculations`, not dynamically added Ophyd Components or `read_attrs`.
- Calculation timestamps use the latest of the five stats timestamps in the snapshot.
  The descriptor records `roi_input` (raw/corrected) and the supplied
  `calculation_description`; provide the formula there for later interpretation.
  Python function code is not automatically serialized into the run.

### Selection contract

- Accept one integer or an iterable of integers in 1–5; allow an empty iterable.
  Reject booleans, invalid indices, and invalid `corrected` values before changing
  any kinds. `corrected` must be a boolean. Materialize and validate the entire
  iterable first; deduplicate and report the selection in numeric order.
- `corrected` defaults to `False`. Initial startup selection remains raw stats1.
- Each call replaces the previous stats-total hint selection for that detector.
  Selected totals of the requested type are hinted. Every other raw/corrected total
  is normal, including the alternate type for selected stats. Do not leave stale
  raw hints active after switching to corrected totals.
- All five stats containers remain readable. Configure container and leaf kinds
  together so the detector's `hints["fields"]` actually exposes the selected leaves.
- Preserve unrelated readouts, configuration, TIFF/image assets, and unrelated hints.
  The helper must not replace the detector's complete `read_attrs` list.
  Empty selection clears only stats-total hints, not every hint on the detector.
- Return a small summary containing selected stats, raw/corrected mode, and resulting
  hinted field names, so callers can confirm the selection without inspecting kinds.
- Selection persists for later runs in that Python session until changed. No new
  cross-session persistence is proposed. Configure hints between runs so descriptor
  hints and data schema remain stable within a run.
- The first version selects one mode for the whole chosen group. Mixed raw/corrected
  hints in one call and a temporary-selection context manager can be added if needed.

## Recorded data contract

By default, reading either parent detector records all five raw and all five
corrected totals, independently of hint selection. Existing raw names retain their
meaning. Example fields:

```text
pil2M_stats1_total
pil2M_stats1_total_corrected
...
pil2M_stats5_total
pil2M_stats5_total_corrected
pil2M_attenuation_factor_used
pil2M_attenuation_energy_eV_used
pil2M_attenuation_foils_used
```

Use detector-prefixed provenance names so reading `[pil2M, pil900KW, attenuation]`
does not create duplicate keys. Record foil labels as a string with fixed scalar
shape, consistent with `AttenuatorSet.inserted`. Factor, energy, and foil provenance
are normal, not hinted. Record these per point, rather than relying on baseline or
start metadata, because attenuation and energy may change during a scan.

Here, `*_used` means **used in the numerical correction**, not hardware-latched at
exposure time. The values are sampled during parent `read()` and represent the
exposure state under the settled-step contract above. Reading the parent at the
console after changing foils or energy without taking another exposure can recompute
an old raw frame with the new state; that is not an exposure-associated measurement.
Child corrected reads, in contrast, return only the last published snapshot.

The timestamps on the three provenance readings are the application wall-clock time
immediately after the provider returns. This is a read-completion observation time,
not an IOC source timestamp or a simultaneous sampling time for all foils and energy.
No extra time-valued data field is needed: the normal reading `timestamp` carries it.

These are modeled attenuation-corrected counts. They do not normalize exposure time,
incident flux, or detector nonlinearity. They preserve whatever frame/ROI meaning
the existing stats total has; no new burst summation is implied.

### Readout hierarchy and defaults

Declare `total_corrected` under each stats plugin and the three provenance components
directly under the detector. Each stats plugin initially reads `total` and
`total_corrected`; both have scalar numeric descriptors. The parent always includes
stats1–5, TIFF, and provenance under the supported default/helper configuration.

Establish the initial readout once at construction/startup, separately from hint
selection. The intended immediate readable children after live-instance setup are:

- `pil2M`: `stats1`–`stats5`, `tiff`, `motor`, and the three provenance components.
- `pil900KW`: `stats1`–`stats5`, `tiff`, `cam`, `motors`, and the three provenance
  components. Preserve its existing readable camera children, including `file_number`.

These describe immediate children; Ophyd's flattened `read_attrs` also includes their
readable descendants. Retain the existing SAXS/WAXS configuration-only geometry,
beamstop, and camera settings. Do not accidentally enable every inherited plugin by
merely removing the old startup `set_primary_roi(1)` calls. Later helper calls only
adjust the stats containers/leaves and preserve any additional user readouts.

Direct manual narrowing of `read_attrs` is outside this contract; the helper restores
all ten stats totals. The parent snapshot path must report missing required raw keys
as an error rather than returning a partial correction. TIFF reads, staging, datum
generation, and asset-document collection retain their existing behavior.

## Implementation: one detector readout snapshot

The shared behavior lives in `devices/pilatus.py`, with the live attenuation source
injected from `instances/pilatus.py`. Device classes remain importable without live
hardware instances. The constructor's `attenuation_provider` argument takes a
zero-argument callable; live instances use `partial(attenuation.read_state, strict=True)`.
Tests can replace `detector.attenuation_provider` with an offline callable.

### Strict attenuation provider

The callable returns a mapping with `attenuation_factor`, `transmission`, `energy_eV`,
and `inserted` (a sequence of known foil labels). Additional descriptive fields are
allowed. It takes one state reading and does not update attenuation signals or run
metadata. The detector converts labels to a deterministic comma-separated string.

In strict mode, `AttenuatorSet.read_state()` enforces the following:

- Require a successfully read live energy when no explicit energy is supplied. Never
  use the cached `energy_eV` signal or midpoint fallback. The production wrapper must
  not supply a constant or previously cached explicit energy.
- Require finite positive energy within the inclusive tabulated energy range; reject
  values outside it before interpolation instead of accepting table endpoint clamping.
- Require each foil state to be known, propagating disconnected/read failures.
- Return the actual computed finite factor `>= 1` and transmission `0 < T <= 1`,
  consistent with `factor = 1 / T` within floating-point tolerance. Raise on underflow
  to zero or overflow; never substitute `_ad_MAX_FACTOR` or a transmission floor.

Keep existing non-strict behavior for other callers. Strictness must be implemented
before the fallback/clamping operations: downstream finite-value checks cannot tell
a fabricated finite result from a valid one. Do not reject a genuinely computed
finite factor solely because it equals the old sentinel; there is no arbitrary upper
factor cutoff beyond representability. The detector also validates the provider
mapping, finite scalar raw totals, and every product, rejecting non-finite products
even if the raw value and factor are separately finite. Zero raw totals are valid;
do not impose a new nonnegative-total rule on existing stats semantics.

### Parent read and component publication

For each detector `read()`:

1. Traverse the configured readable tree once, excluding only the new snapshot-backed
   corrected/provenance leaves. Read each raw total exactly once and retain its value
   and timestamp, along with the existing TIFF and other readouts. Do not temporarily
   change kinds or `read_attrs` to do this.
2. Obtain one fresh attenuation state with one provider call and capture the
   application read-completion timestamp immediately afterward.
3. Compute all five corrected totals from those exact returned raw values and that
   single factor. Validate and assemble the complete result locally before publication.
4. Publish the successful corrected/provenance snapshot and return the locally built
   read dictionary. Corrected timestamps follow their corresponding raw totals;
   provenance uses the application timestamp from step 2. Never reread the raw totals
   or call a second recursive superclass `read()` to construct the result.

Use declared components so `describe()`, hints, device discovery, and field names
agree with `read()`. An unmodified recursive superclass `read()` is insufficient: it
would read unavailable or previous-snapshot corrected leaves on the first pass.
Implement the filtered traversal explicitly, preserving existing child `read()`
behavior where no filtering is needed. `describe()` must work before the first valid
snapshot. Describe the new snapshot leaves using declared scalar numeric/string types
and shapes without calling their `get()` or refreshing attenuation. Preserve existing
descriptor behavior for raw signals and other children; describing must not acquire
a new image or generate a correction snapshot.

Standalone component semantics: `total_corrected.get()` / `.read()` exposes
the last successful parent-read snapshot. It does not acquire or silently combine
an old frame with a newly changed attenuation. Before any valid snapshot, report a
clear unavailable-state error rather than a plausible zero. If prompt-time live
calculation is later needed, provide an explicitly named operation. Provenance
components have the same last-successful-snapshot semantics.

Use a private, replace-as-a-whole snapshot mapping shared by these components, rather
than sequential public `Signal.put()` updates. The component class must reject public
`.put()` and `.set()` for both corrected totals and provenance; `kind` alone provides
no write protection. Only the parent publication path replaces the snapshot. A failed
parent read raises, publishes nothing, and leaves the previous successful snapshot
and its timestamps intact for child inspection; it never returns that old snapshot
as a substitute for a new event.

The returned parent dictionary is the coherent multi-field readout boundary. Separate
child reads can span successive parent reads and are not a multi-field transaction.
This implementation does not emit corrected/provenance value subscriptions. Live
tables and plots receive updates from Bluesky events. Parent reads/publication are
serialized per detector, and recursive parent reads raise rather than deadlocking.
Consumers requiring a consistent set of fields should use the returned parent read
or the recorded event.

### Acquisition ordering

Standard step scans wait for detector trigger completion before reading. Stats are
computed by areaDetector and are expected to be fast. The current camera stages
`WaitForPlugins="Yes"`, and the custom trigger completes via the acquisition put
callback with a detector-state alarm check. Confirm once during commissioning that
the enabled stats/plugin chain participates in that completion behavior and returns
the completed acquisition's values. Do not add arbitrary sleeps or per-ROI polling
to the correction path solely as a precaution.
Read-time correction avoids the early-calculation problem of a separately triggered
`SynSignal`, but cannot repair stale underlying stats.

For the supported plans, the ordering is: settle energy/foils, trigger, wait for
completion, read all detectors, then permit the next energy/foil change. With that
ordering, each detector's read-time state represents its exposure state even though
the detectors read it separately. This is a software readout snapshot, not an atomic
hardware latch. Fly scans, concurrent manual changes, or a custom plan that changes
energy/foils before all reads finish require a different frame-association design.

## Alternatives considered

1. **Read-time computed signal for each ROI:** simple standalone `.get()` behavior,
   but can repeat attenuation calculations and reread raw totals, losing exact
   raw/corrected event correspondence. Prefer the shared snapshot for recorded data.
2. **`DerivedSignal` based on `total`:** compact transformation, but the attenuation
   source is a second dependency. Stock single-source subscriptions do not refresh
   when only energy/attenuation changes; the current cached factor needs explicit
   refresh handling as well.
3. **Separate `SynSignal` detector:** convenient prototype, but standard plans trigger
   detectors together, so calculation can precede Pilatus acquisition completion.
   It also requires changes to detector lists instead of integrating with `[pil2M]`.

## Compatibility and rollout

The convenience wrapper is exported through the existing instance-module loading
pattern. Restart the collection session to load the new device classes and provider
wiring. Ordinary `count`/`scan` calls continue to use parent detectors without plan
changes. Configure display hints between runs.

`set_primary_roi(num)` accepts a single index under the new validation rules and calls
`hint_stats(num, corrected=False)`. This preserves the call spelling, **not the old
readout-narrowing behavior**. The two in-repository startup callers have been migrated;
check external operator/user scripts for assumptions that it records only one ROI.
The similarly named Prosilica method remains a separate interface.

Relative to the previous live defaults, this adds five corrected numbers and three
provenance values per detector per event (plus their timestamps/descriptors). The
five raw totals already belong in the current default readout. Users who previously
narrowed the detector will see more fields. Check downstream exact-schema assumptions
and compare representative event payload/read latency during commissioning; do not
assume compatibility merely because existing field names are preserved. Automatic
correction also makes valid attenuation state a prerequisite for a successful parent
read, even with raw-only display hints. An unavailable strict provider aborts that
read rather than silently switching to raw-only acquisition.

## Automated verification

Run the focused hardware-free tests with:

```sh
pixi run -e test pytest tests/sim/test_pilatus_corrections.py tests/sim/test_attenuator_set.py
```

The tests use fake areaDetector devices and an injected provider, plus real strict
attenuation calculations against simulated foil/energy sources. Coverage includes:

- All five raw and corrected totals appear in both `read()` and `describe()`, with
  matching names and scalar shapes. `describe()` works before the first snapshot
  without invoking snapshot-component `get()` or the provider. Corrected/provenance
  `.put()` and `.set()` both fail; their initial `.get()`/`.read()` report unavailable
  state.
- Instrument raw readers to count calls and change value on every call: each raw
  total is read exactly once and corrections use that returned value. There is one
  provider call per successful parent read. Changing energy/foil state between points
  changes the next correction even if the cached attenuation signal is unchanged.
- Corrected timestamps equal the corresponding raw timestamps. All provenance
  timestamps use the application time captured just after the one provider call.
- Provenance matches the factor actually used; invalid state fails without publishing
  a partially updated snapshot or fabricating a valid initial corrected value. Test
  missing live energy, unknown/disconnected foil state, out-of-table energy, factor
  overflow/transmission underflow, and finite inputs whose product overflows. Exercise
  the real strict provider with simulated sources, not only a well-behaved stub.
  Confirm default non-strict callers retain their existing behavior.
- After a failed read, child values/timestamps still describe the last successful
  snapshot, while the parent raises. Concurrent reads serialize publication and
  recursive parent reads are rejected without deadlock.
- Every combination of stats 1–5 (including empty) has the expected raw/corrected
  hints. Switching modes clears old hints while leaving all ten totals recorded.
- Invalid helper arguments leave existing kinds unchanged; repeat calls are idempotent.
- TIFF assets, motor/configuration readouts, and unrelated hints survive helper calls.
  Verify the initial live-instance readout hierarchy as well as repeated helper calls.
  `set_primary_roi()` follows the documented behavior change without narrowing reads.
- Simulated RunEngine counts and energy scans with delayed acquisition produce
  current-point corrected values, consistent descriptors/events, and expected hints.
  Reading both detectors and attenuation produces unique keys. Real TIFF filestore
  methods generate resource/datum documents whose IDs match the recorded image fields.

### Beamline commissioning (pending)

Before rollout, commission both detectors with single-image acquisition and the
supported multi-image/burst settings. Deliberately vary the signal between points
(for example, exposure at fixed beam conditions) and use IOC frame/counter information
or saved-image ROI comparisons to establish that each raw stats total belongs to the
just-completed acquisition. Confirm stats1–5 enablement and document whether the burst
total represents the last frame or other configured processing; correction preserves
that behavior. Fast readback alone is not the frame-association check.

Confirm event keys, TIFF resource/datum linkage, and live display selection while
switching between multiple raw/corrected ROIs. Check two settled attenuation states
and a settled energy scan: at each point, corrected total must equal that event's raw
total times its recorded factor, with energy/foils held until all reads finish.
Record representative event size and read latency. Simulation validates the software
contracts; this remaining commissioning checks the actual IOC/plugin frame ordering,
burst semantics, and live displays.
