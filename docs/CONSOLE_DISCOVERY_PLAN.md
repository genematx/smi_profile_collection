# Interactive console discovery and learning — review draft

**Status:** design record; a manually loaded staff-preview pilot is implemented.
See [pilot usage](CONSOLE_GUIDE.md) for its supported commands and subset. The
broader inventory, filters and rollout phases below remain design proposals.
**Audit:** 2026-10-13, profile revision `ea8e8cd`.
**Audience:** SMI staff reviewing the design and initial content before publication.

### Reading map

- [Recommendation](#1-recommendation) and [ownership/model](#3-ownership-what-belongs-to-a-device-an-installation-or-a-workflow)
- [Console experience](#4-proposed-terminal-experience) and [guardrails](#5-guardrails-and-helpful-hints)
- [RunEngine primer](#6-runengine-primer-proposed-user-content)
- [Initial device entries](#7-initial-device-catalog-for-review)
- [Alignment chooser and complete local alignment inventory](#8-alignment-discovery-central-user-journey)
- [Other commands and workflows](#9-command-and-workflow-catalog-beyond-alignment)
- [Implementation phases and checks](#10-implementation-sequence-and-acceptance-criteria)
- [Specific review findings](#11-specific-review-findings-and-publication-blockers) and [open decisions](#12-review-checklist-and-open-decisions)

## 1. Recommendation

Build a **curated, read-only field guide inside IPython**, with one entry point
(`%guide`, proposed). It should help a person answer:

- What is this device called, and what does it do?
- Which equipment belongs to my task or experimental setup?
- Which existing alignment is appropriate, what does it change, and what options
  does it accept?
- What command should I learn next, and does that command read, move, acquire,
  change configuration, or run a plan?
- Why did I get a generator, an unavailable-device message, or a paused run?

Use categories, synonyms, location, and task relationships as independent ways
to find the same entry. Give a short answer first, with explicit detail and
related-topic commands. Execution remains in the existing console commands and
staff-approved workflows; experiment orchestration belongs to **smi-plans**.

The first release should support browsing and learning without a connection to
hardware. Staff can publish useful device descriptions before approving any
associated action examples.

### Decisions proposed for review

1. One `%guide` entry point: a searchable contextual browser by default, with
   direct subcommands for quick lookups. The interactive direction was accepted
   in the design discussion; the detailed keyboard behavior remains a prototype
   specification to validate.
2. A pure-data, version-controlled catalog, with device-type descriptions,
   installation bindings, workflow descriptions, and publication policy owned
   separately as described below.
3. A multi-category relationship model, with a shallow physical component tree
   where useful. Python module boundaries organize maintenance, not navigation.
4. Alignment selection is a deterministic question-and-answer guide; its result
   is a reviewed workflow card, never an executable plan assembled by the guide.
5. Default help/search/completion performs no PV reads or writes. Live status is
   an explicit separate operation using curated readers.
6. Every initial entry in this document is **draft**, including those suggested
   for routine user visibility. Staff still choose the published set.

## 2. Audit scope and existing foundations

This is a static source audit, not a live connectivity or operational validation.
It covers all modules listed by `instances.DEVICE_MODULES`, the devices and
meaningful component groups they construct, startup's additional exposures,
motor magics, status/layout metadata, alignment implementations, and relevant
local documentation. Repeated foil, ROI, and axis families are enumerated below
as groups rather than hundreds of individual EPICS fields.

The external smi-plans implementation was not available in the inspected local
environment. Its interface was audited at the profile wiring boundary only.
`pixi.lock` records smi-plans revision
`7a4cbb46b71a0c26ea71b2a68ad8e7ab33c46ea5`; installed-version verification and a
matching smi-plans workflow audit are an explicit prerequisite for publishing
its command cards. Do not infer that every smi-plans Python API is exposed at
the SMI prompt.

| Existing source | What to reuse / what it establishes |
| --- | --- |
| `src/smi_beamline/motor_magics.py` | Literal-only standalone commands; help tokens bypass execution; session RE; idle checks for normal actions; `%help`, `%status`, position/energy/exposure readouts. |
| `src/smi_beamline/devices/status.py` | Immutable field descriptions and state meaning shared by devices and missing-device placeholders. |
| `src/smi_beamline/instances/layout.py` | 22 named layout entries: hutch, relative beam order, label, status profile; not a complete device inventory. |
| `src/smi_beamline/beamline_status.py` | Curated live readers, duplicate-read caching, 150 ms reads and a 3 s read budget; no generic recursive device dump. |
| `src/smi_beamline/instances/__init__.py` | Startup module order, partial-failure report, public-name collection. Public exports include imported helpers and loop variables as well as devices. |
| `startup/startup.py`, `startup/__init__.py` | Session services, smi-plans `_qserver.__all__` exposure, optional helpers, terminal-only magic registration. |
| `src/smi_beamline/plans/alignment.py`, `_alignment.py` | Actual alignment variants, options, axes, scan/fit recovery, and differing cleanup behavior. |
| `docs/DEVICE_STATUS.md`, `docs/MOTOR_MAGICS.md`, `docs/ALIGNMENT.md` | Starting documentation; review discrepancies noted in section 11 before reusing prose. |

Existing ophyd labels, `kind`, `read_attrs`, Python `dir()`, and public exports
are useful audit inputs, but none define a staff-approved user interface.
`devices/device_factory.py` has a construction registry, but the inspected
instance modules largely construct their devices directly. That registry is
not a complete inventory and its fake-device environment settings must not be
treated as proof that importing startup is hardware-free.

## 3. Ownership: what belongs to a device, an installation, or a workflow?

### Recommended split

| Owner | Owns | Example |
| --- | --- | --- |
| Device type | Intrinsic meaning, curated component descriptions, units, readback semantics, device-level coupling and constraints | A SAXS detector has acquisition, positioning, geometry, and beamstop capabilities. |
| Installation | Stable entry ID, console binding, aliases, physical identity, location, local labels, installed/absent notes | This SAXS detector is `pil2M`, in hutch C; `pil2M_pos` is an alias of its positioning child. |
| Workflow implementation owner | Purpose, supported setup, parameter meaning, effects, normal completion, interruption behavior, supported invocation | A GISAXS alignment uses specific sample axes and detector ROIs. |
| SMI staff publication policy | Audience, recommended routes, permitted examples, setup restrictions, temporary operational notes, review state | Show detector geometry to users, but direct beamstop calibration to staff. |
| UI | Search, filtering, completion, paging, formatting and navigation | “Find sample height” returns both piezo and stage entries with units. |

**Each ophyd object should not need to discover or own all its relationships to
the outside world.** Keep intrinsic facts close to the class, and cross-device
relationships in installation/workflow records. An instance can reference an
immutable description; it should not implement an IPython help system.

Likewise, do not put executable registration in every live instance file and
import those files to build help. Several imports construct devices, read PVs,
change configuration, or access services. A future pure-data catalog can be
split into domain files (`detectors`, `sample`, `optics`, etc.) without imposing
those files as the user's hierarchy.

### Proposed implementation layout (future files)

```text
src/smi_beamline/discovery/
    schema.py             immutable records; standard-library only
    catalog/              pure-data descriptions/bindings by domain
    workflows.py          local workflow cards and external provider references
    policy.py             staff publication/setup policy
    search.py             deterministic search and facet filtering
    alignment.py          decision questions and explanations, no plan logic
    render.py             compact terminal cards/tables
    ipython.py            %guide and catalog-only completion
```

Use typed Python records initially, consistent with `BeamlineLocation` and
`StatusField`, without adding a configuration parser dependency. Catalog modules
may import schema/other pure records only. Retain one authoritative copy of
intrinsic descriptions that live classes can reference; the guide must not import
live classes to obtain them. For example, `Ring` currently creates signals at
class scope, so even “class imports only” is not a sufficient isolation rule.

Reuse `DEFAULT_LAYOUT` for existing location facts, and preserve the existing
status description API. Add reviewed missing locations incrementally; unknown
locations must say “not documented,” not be guessed from a module name or PV.
Layout boundary labels should remain distinct from equipment physical location.

smi-plans should eventually supply a versioned, data-only description of its
supported user workflows/options. Prefer packaged metadata or an explicit
already-loaded provider over importing its orchestration modules for help.
This profile adds local device links and staff policy. Until that provider exists,
keep reviewed, revision-bound descriptions with a drift check. Do not copy plan
bodies or turn queue schemas into unrestricted user-editable plan builders.

### Entry schema

Required fields for a published device/component card:

- Stable `id`, human `title`, one-sentence `summary`, `kind`.
- Canonical `namespace_path`, explicit `aliases`, and search-only `synonyms`.
- `categories` (many), `capabilities` (many), `location_ref` if known.
- Curated children and typed links: `part_of`, `positions`, `protects`,
  `measures`, `used_by`, `same_object_as`, `same_hardware_as`.
- Unit and coordinate semantics for each published axis/field; unknowns explicit.
- Approved command/workflow links; these are documentation references, not callables.
- Optional `status_profile_ref` for a reviewed live reader.
- Source module and symbol, owner role, review state, reviewed revision/date,
  operating restrictions and documentation links.

Workflow/command cards additionally require:

- Invocation kind: magic, RE plan, direct Python helper, plan factory, analysis,
  or documentation topic. Declare this explicitly; signatures alone cannot tell.
- Signature and parameter table: meaning, units, default, required/optional,
  choices, implementation validation, and any narrower staff-approved range.
- Suitable/unsuitable setups; required devices; whether beam or prior alignment
  is required; what the user must already know.
- Effects: motion, exposure/acquisition, shutter/feedback, ROI, attenuation,
  persistent metadata/configuration, files/services.
- Normal end state and failure/interruption behavior, with “not guaranteed”
  where that is what the implementation establishes.
- Staff-reviewed literal usage examples and related learning topics.

Keep **publication**, **audience**, **session presence**, **connectivity**, and
**setup suitability** separate. A present device is not necessarily connected;
a connected device does not establish that a workflow is appropriate.

### Composite example: Pilatus 2M

Proposed record sketch, not an installed configuration:

```text
id: detector.saxs
title: SAXS detector — Pilatus 2M
namespace_path: pil2M
synonyms: [pil2m, SAXS camera, small-angle detector, 2M]
categories: [detectors, saxs, alignment]
capabilities: [acquisition, roi-readout, detector-positioning, beamstop-assembly]
location_ref: pil2M
children:
  detector.saxs.position -> pil2M.motor
  detector.saxs.beamstops -> pil2M.beamstop
  detector.saxs.geometry -> curated beam-center/distance fields
  detector.saxs.roi -> curated roi1..roi4 and stats1..stats5 descriptions
commands: [console.snaps, console.exp, console.e]
review_state: draft
```

`detector.saxs.position` also appears under **positioning** and **geometry**;
its canonical binding is `pil2M.motor`, with true aliases `pil2m_pos` and
`pil2M_pos`. `detector.saxs.beamstops` appears under **beamstops** and **alignment**.
It has a same-hardware link to the separately constructed `saxs_bs`, not a claim
that the two Python objects are identical. `pin_diode` is a related readout
device, not a child motor or an alias of the pin beamstop.

Do not grant access to every child operation because the detector card is public.
The ability to take a reviewed snapshot does not imply permission to remove a
beamstop, alter a calibration, or move the detector carriage.

## 4. Proposed terminal experience

All `%guide` examples in this section are **proposed syntax, not available now**.
Document the explicit `%` form to avoid Python-name shadowing.

```ipython
%guide
%guide devices
%guide devices --category positioning
%guide devices --category detectors --hutch C
%guide find sample height
%guide find beamstop
%guide show pil2M
%guide show pil2M.motor
%guide commands --task acquisition
%guide show command:exp
%guide align
%guide align --stage piezo --goal touch-up
%guide learn runengine
%guide learn units
```

The home screen should fit about 15 lines: Devices, Commands, Alignments,
Learning, and a few task-oriented examples. Existing `%help` stays a quick
command reference and gains a single pointer to `%guide` after implementation.

### Primary interaction: searchable contextual browser

Calling `%guide` without arguments opens a temporary documentation prompt inside
terminal IPython. Bare `guide` may work through normal IPython automagic when
unshadowed; do not replace an existing Python name. Use `prompt_toolkit`, already
used by terminal IPython, for a searchable selection menu below the current
scrollable card in a temporary alternate screen. Navigation replaces the screen
instead of accumulating console output. Exit restores the original console and
prints only the breadcrumb, last entry's title/summary and direct lookup command.
Page Up/Down scrolls long cards. This supersedes the original inline/scrollback
proposal following pilot feedback. The plain numbered fallback retains a text
transcript for terminals without screen control. Verify compatibility with the installed version and declare the
dependency explicitly if the implementation imports it directly.

Further pilot feedback establishes one numbered choices list, rather than links
printed on the card and duplicated in the selector. Number + Enter opens that
entry; a search followed by a number (e.g. `exp 2`) selects a filtered result.
Multi-digit numbers work and invalid numbers do not navigate. Colors replace
bracketed relation labels: cyan topics, blue equipment/parts/parent, magenta
related equipment, green command/workflow help, yellow scientist help, muted
navigation. Include a compact legend and pointer/reverse selection. Honor
`NO_COLOR` and IPython's no-color preference with textual relationship fallbacks.
Direct one-shot lookups retain their plain-text links.

```text
SMI GUIDE — browse and learn
Selecting an entry displays documentation; it does not operate equipment.

  Devices
  Alignment
  Console commands
  Learn Bluesky
  Common tasks

guide › det
  Devices → X-ray detectors
  pil2M — SAXS detector
  pil900KW — WAXS detector
  Detector exposure
  Detector positioning
```

Typing updates the matches immediately; Tab is a convenience, not a prerequisite
for seeing results. Up/down selects a suggestion; Enter opens the selected card;
Tab completes its label. An empty query shows the current card's curated choices.
No match leaves the query in place with an explanation; never interpret it as
Python or silently choose a fuzzy match.

Every screen has visible Back, Home, Search everything and Exit actions.
Proposed shortcuts: Escape clears the query/menu; Alt-Left navigates back;
Ctrl-D or Ctrl-C exits the guide and returns to IPython. Do not bind Backspace
to navigation while editing text. Show a compact keyboard legend. On errors or
interrupts, restore terminal state and return to the ordinary IPython prompt;
exiting the guide does not call any RunEngine control method.

Selecting `pil2M` opens its card and contextual choices:

```text
pil2M — SAXS detector
Records scattering images and intensity statistics.

Explore: Exposure and image count · ROIs and intensity · Positioning
         Beamstops · Detector geometry
Related: Sample alignment · WAXS detector · Pin-diode readout

guide [pil2M] › exp
  Read detector exposure settings
  Set detector exposure settings
  Learn exposure, period and images per trigger
```

The resulting operation card shows purpose, syntax, a clearly labeled action
example, argument meaning, affected equipment, execution context, and related
topics. For example, the exposure card explains `%exp IMAGE_SECONDS
TOTAL_SECONDS`, and that `%exp 0.5 2` changes settings to four 0.5-second images
per trigger. It explicitly says that the existing helper configures **both**
Pilatus detectors, plus Amptek when enabled. Navigating from SAXS must not imply
that this operation affects only SAXS. The card does not execute the command,
prefill an executable IPython cell, or write to the clipboard automatically.

Every operation card distinguishes:

- Standalone terminal magic.
- Existing plan executed through RE.
- Plan helper used by maintained orchestration.
- Ordinary Python function that acts immediately (including Status-returning
  device methods).
- Read-only or analysis helper.

“Works in a script” is too ambiguous: explain the actual execution context.
Routine-user automation guidance points to the approved smi-plans workflow;
deeper staff reference may describe the underlying helper. A script-compatible
API is not an invitation to assemble ad hoc plans through this interface.

### A relationship web, presented as understandable paths

The same canonical card can be reached through multiple routes:

```text
Devices → X-ray detectors → SAXS → Positioning → Distance
Common tasks → Understand detector distance → SAXS distance
Devices → Motors and positioning → Detector positioning → SAXS distance
Search everything → "saxs distance"
```

All reach `pil2M.motor.z` (singular `motor`), with its aliases, units and the
distinction between motor Z and calibrated sample-detector distance. The card
links to its containing detector, related beamstops, geometry quantities and
reviewed workflows. Breadcrumbs show navigation history, not a unique ownership
hierarchy; maintain a back stack and handle relationship cycles naturally.

Search ranks exact identifiers first, then contextual topics/children/related
equipment and broader matches. Label “In this context” and “Elsewhere in the
guide” separately; users are never trapped in a category. For example, searching
`temperature` from `pil2M` can show no documented local matches and then offer
LakeShore, Linkam and motor-temperature topics. Context and search change only
navigation, not device bindings, publication policy or actual beamline setup.

Use searchable cards for equipment/commands, short linked explanations for
learning, and guided questions for alignment choices. Alignment questions remain
deterministic and lead to reviewed cards; “unsure” is a valid answer throughout.

### Terminal integration and fallback

Prototype the handoff between IPython and the nested documentation prompt with
static data first. Do not reuse or modify IPython's active input buffer, nest
incompatible event loops, or register a second global completion system. Scope
guide completion to its own prompt. Test prompt restoration, resize, Ctrl-C/D,
SSH terminals and asynchronous output from the surrounding session.

Retain direct forms such as `%guide show pil2M` for quick use and reproducible
transcripts. A numbered line-menu is the simpler fallback for terminals without
the rich menu. In non-TTY/notebook contexts, display home/help and direct-query
examples without opening a blocking interactive prompt. Keep navigation state
in memory for the guide session; reopening starts at Home. Persistent preferences
or history are not needed for the initial prototype.

### Browsing and searching

- List approximately 10–15 rows per page: name, plain-language role, primary
  categories, and publication/availability annotation where relevant.
- Combine facets by intersection; list available facets with counts. Categories:
  sample positioning, detectors, detector geometry, beamstops, slits/apertures,
  optics/focusing, energy, attenuation, diagnostics/cameras, shutters/vacuum,
  sample environments, session/data, and staff commissioning.
- Use curated everyday synonyms: “height”, “hexapod”, “Huber”, “SAXS distance”,
  “incident angle”, “flux”, “camera”, “temperature”, “beam size”.
- Exact case-sensitive names win; case-insensitive and fuzzy matches are
  suggestions only. Preserve distinctions such as `wbs`/`WBS`, `vfm`/`VFM`,
  and `fs`/`FS`. An ambiguous query shows choices rather than picking silently.
- Search includes unavailable but documented equipment. Explain missing session
  bindings without importing or constructing them.
- No automatic method/PV enumeration. Expanded details show only curated children.
- Tab completion in `%guide` uses catalog strings only, with no device traversal,
  signature execution, network requests, or live state evaluation.
- Provide `--page`, `--detail`, and `--all` within the current published audience;
  `--all` must not reveal unpublished/staff-only internals as a hidden escape hatch.
- Stable one-line forms work in logs and pasted transcripts. Interactive cards
  show their equivalent direct query. Numbered choices are a fallback, not the
  primary interaction. Keep all rich navigation inside one temporary-screen
  application so intermediate cards do not enter normal console scrollback.
- Respect `NO_COLOR`, narrow terminals, and plain text. Sanitize terminal control
  sequences in catalog and external strings. Use words as well as color.

### Example short card

```text
pil2M — SAXS detector                          [documentation; no live read]
Records small-angle scattering images and intensity statistics.
Find under: detectors / SAXS / alignment
Parts: acquisition · ROIs · detector position · beamstops · geometry
Position aliases: pil2m_pos, pil2M_pos -> pil2M.motor
Learn commands: %guide show command:snaps | %guide show command:exp
Related: %guide show pil2M.beamstop | %guide align
Live overview: %status
```

No changing numerical values on the documentation card. A future explicit
`%guide status pil2M` may use the existing status reader; implement it only after
per-device selection and side-effect guarantees are tested. Do not imply that
`%status pil2M` is currently supported.

## 5. Guardrails and helpful hints

### Discovery safety contract

1. Browse, search, card rendering, alignment questions, and completion never call
   RE, create a plan, advance a generator, write EPICS, trigger/stage a device,
   change metadata, or contact Redis/Tiled/SSH.
2. Do not `eval` or `exec` user input, expand IPython expressions, or resolve
   arbitrary dotted paths. Disable magic variable expansion. Paths must match
   catalog identifiers before any optional adapter is considered.
3. Do not run a plan “as a dry run” to discover its effects. Generator iteration
   can execute ordinary Python side effects even without RE; effects must be
   declared and reviewed.
4. Do not use general `read()`, `describe()`, `repr()`, properties, or recursive
   `getattr` as a help mechanism. In this profile, some read-like helpers mutate
   software state or metadata, and some descriptors can create EPICS components.
5. Optional explicit live views use only allowlisted adapters and fields. Reuse
   the status read budget and cache, including connection timeouts; mark stale,
   missing, offline, unknown and budget-exhausted values accurately. Attribute
   resolution itself must also be reviewed; a read timeout does not bound an
   arbitrary property. No continuous polling by default.
6. Documentation remains available when RE is paused, devices are absent, or the
   smi-plans package failed to load. Do not attempt repairs from a help command.
7. Names in the Python namespace and `__all__` do not automatically become
   published actions. Methods containing “get”, “save”, “status”, or “set” are
   classified by behavior, not by spelling.

### What staff can define

- Which entries are public, staff-reference, legacy-reference, or unpublished.
- Which task/setup combinations are supported and recommended; a named owner for
  each group, a reviewed revision, and temporary restrictions with a review date.
- Which parameters are explained to users, which options require staff support,
  and which complete usage examples may be shown.
- Per-operation policy, including explicit consequences of modes and commands.
- An installed/setup profile from trusted configuration. User chooser answers
  filter explanations; they must not change the actual beamline setup.
- When no supported workflow matches, a useful explanation of what information
  or staff assistance is needed, without suggesting a custom scan sequence.

Catalog audience labels are **guidance, not access control** in an unrestricted
Python/IPython process. Actual motion restrictions belong in approved commands,
plans, devices/IOCs and, where used, QueueServer permissions. Future guardrail
changes must be implemented at those execution boundaries; marking an example
“staff” does not enforce it. The guide never offers a generic `%run`, `%move
DEVICE`, sequence editor, arbitrary detector selection, or plan-code export.

### Hints that teach

First release: put helpful hints in cards and local command diagnostics. Examples:

| Situation | Helpful response |
| --- | --- |
| `pil2m` search | “The console name is `pil2M`. It includes position and beamstop components.” |
| “height” | “Piezo height and stage height use different units. Choose your sample stack.” |
| `piezo.ph` | “This axis is not defined in the current profile. The stage phi axis is a different device.” |
| Bad `%exp` arguments | Explain per-image seconds versus total seconds and show help, without choosing values. |
| RE not idle | State the RE state and link to the run-control topic; do not recommend retrying the motion. |
| Alignment failure | Explain rejected fit/retry exhaustion and link to the chosen workflow's recovery notes. |
| “snapshot” | Offer detector acquisition, optical-camera image, and saved beam-position configuration as different tasks. |

Optional later enhancement: an IPython formatter for **known, unstarted plan
generators displayed as a bare expression** can append one concise explanation.
Use explicit identities from reviewed loaded callables and generator code objects;
unrecognized/decorated cases may receive no hint. Never call/advance/close the
generator, inspect its locals for argument values, replace its return type, alter
tracebacks, or automatically wrap it in RE. Preserve normal object display and
make registration reversible/idempotent. Assignment (`p = shclose()`) normally
has no display, so do not promise universal detection. Defer this feature until
ordinary help has proven useful.

## 6. RunEngine primer: proposed user content

### Three things that look similar at the prompt

| Input | Meaning |
| --- | --- |
| `%guide show command:sc` | Proposed documentation lookup; performs no beamline action. |
| `shclose()` | Creates a plan generator. This particular generator function has not run its body, so the shutter has not closed. |
| `RE(shclose())` | Executes the existing photon-shutter closing plan through this session's RunEngine. |
| `%sc` or `%sclose` | Existing standalone console action that calls `RE(shclose())` for you. |

The last two examples **act on the beamline**. Show them in a clearly labeled
usage section, not as commands to try while exploring help.

A plan describes work as a sequence of messages. The RunEngine consumes that
sequence, dispatches actions, waits for completion and coordinates run documents,
callbacks and installed suspenders/preprocessors. A generator's display is not
an error or a report that the work completed. Do not use `next()`/`list()` to
make it work. Prefer the reviewed console action or documented RE invocation.

The distinction must be explicit per command: ordinary helpers may act
immediately. For example, `set_energy(...)`, `feedback(...)`, Linkam setters and
humidity flow helpers perform direct actions; they are not all plans. A helper
returning an ophyd Status has already requested an action. A factory can also do
work before returning a generator: `restore_beam_position_snapshot` reads state
at call time and returns either a report or a plan depending on `dry_run`.

The shutter example also teaches scope: `shclose()` disables pitch/roll feedback,
waits, then commands the **photon shutter**; it is not a universal hardware stop.
`shopen()` defaults to enabling feedback after opening that shutter. FE shutter
status and fast-shutter status describe different equipment.

### Minimal run-control lesson

- `RE.state` reports the local RunEngine state. `idle` alone does not establish
  that nobody else is controlling the beamline.
- Normal action magics require idle RE. A paused plan needs a deliberate resume
  or termination decision, not another scan or move.
- Explain the site's verified Ctrl-C/pause behavior with the installed Bluesky
  version before publishing keystroke instructions. A pause request can wait for
  a checkpoint, and some plans cannot resume at every point.
- From a paused RE, `RE.resume()` continues; `RE.stop()` ends gracefully;
  `RE.abort()` aborts; `RE.halt()` skips normal plan cleanup and belongs in staff
  recovery guidance. `%stop` currently calls `RE.stop()`.
- Pause/stop/abort do not imply rollback to original positions. Finalizers and
  cleanup can themselves command hardware. Document each approved workflow's
  actual behavior and direct unresolved recovery to staff.
- Suspenders can wait for beam or temperature recovery. Explain the displayed
  condition and delay; never recommend disabling suspenders as a routine fix.
  Beam-down startup still installs temperature suspenders in the current code.
- Most acquisitions record runs; a plan that only closes a shutter need not open
  a data run. Avoid claiming every RE action creates an image or scan ID.
- Console magics are standalone actions. Acquisition sequences, repeated samples,
  coordinated scans and automation go through supported smi-plans workflows.

Add short topics for units (um/mm, eV/keV, degrees), relative versus absolute
motion, normal scan endpoints, exposure/burst semantics, detector ROI versus
full image, pseudo axes versus real motors, baseline versus primary data,
sample/proposal/project naming, and console versus QueueServer sessions.

## 7. Initial device catalog for review

**Legend:** U = candidate routine-user description; S = staff-oriented detail;
R = unresolved/legacy/experimental entry requiring explicit review. These are
proposed audiences, not existing permissions or claims of readiness. Every row
is draft. Names are exact namespace bindings unless explicitly labeled a child
path. Source paths below are relative to `src/smi_beamline/`.

For U entries, “user description” can be approved independently of motion or
configuration examples. A grouped row should become individual records wherever
users need distinct search results; family members remain individually searchable.

### 7.1 Sample positioning and sample environment

| Proposed entry / exact bindings | Description and meaningful parts | Categories / initial policy / review |
| --- | --- | --- |
| `piezo` | SmarAct sample stack: `x`, `y`, `z` in um; `th`, `ch` in degrees. `ph` is absent. | Sample positioning, alignment; U. Link existing axis magics; staff confirm physical directions/setup meanings. |
| `stage` | Huber laboratory-frame pseudo-positioner: `x/y/z` mm; `theta/phi/chi` degrees, also `th/ph/ch`. Rotations compensate real translations using configured centers. | Sample positioning, alignment; U. Search synonym “hexapod” reflects historical routine names. Real axes and rotation-center changes are S. |
| `stage_temps` | Huber temperature readouts `x/y/z/th/phi/chi`, used by motor-temperature suspenders. Object name is `Huber`. | Diagnostics, positioning; U readout explanation; verify units per channel. |
| `bdm` | Bounce-down-mirror alignment stage; `x/y/th` SmarAct positioners. Class docstring also says “beam-diagnostic-module”: naming needs staff confirmation. | Optics, alignment, positioning; S. Controller units and signs need an explicit card; alignment source says positive height/theta bend downward. |
| `ls` | LakeShore inputs A–D, explicit `input_A_celsius`; four control outputs with range/PID/temperature setpoints. Input C participates in WAXS-motor temperature protection. | Temperature, diagnostics, sample environments; U selected readouts, S output controls. Do not label all channels as sample temperature or assume Celsius for all inputs. |
| `LThermal` | Linkam temperature/ramp readbacks, heater and controller status; direct setters exist. | Sample environments, temperature; U descriptive, S setup-specific actions. |
| `LTensile` | Linkam thermal plus tensile position, force, strain, stress, mode and motion controls. | Sample environments, mechanics, temperature; U descriptive, R action examples. Prefix differs from `LThermal`; confirm installed mapping and units. |
| `sorensen_ps1` | Sorensen supply: current A, output voltage V, current limit, output and lock status/commands. `current_limit` aliases `max_current`. | Sample environments, power; U descriptive/readbacks, S outputs and limits. |
| `bc_smaract` | Blade-coater motors `x1/x2`. | Sample environments, coating, positioning; setup-specific U description; S actions. |
| `syringe_pu` | Syringe pump: `vol/rate/dia/dir` and `go/stop_flow`. | Sample environments, coating, flow; U description, S actions; volume/rate units and syringe setup need confirmation. |
| `MDrive` | Auxiliary motor controller, `m1` through `m8`. | Auxiliary positioning; R. Channel-to-equipment mapping is not established by this file. |
| `thorlabs_su` | Standalone Thorlabs positioner. | Auxiliary positioning; R. Shares record base with `bc_smaract.x1`, but different wrappers/completion semantics; staff verify physical mapping. |
| Humidity cell (conceptual entry) | Read/flow helpers backed by `moxa_in`/`moxa_out`; no single humidity-cell ophyd root. | Sample environments, humidity, flow; U concept, R recipes/calibration and controls. |

Sources: `instances/manipulators.py`, `devices/manipulators.py`,
`instances/electrometers.py`, `devices/electrometers.py`,
`instances/linkam.py`, `devices/linkam.py`, `instances/power_supply.py`,
`devices/power_supply.py`, `instances/bladecoater.py`, `devices/bladecoater.py`,
`instances/motors.py`, `devices/motors.py`, `plans/humidity_cell.py`.

### 7.2 Detectors, geometry and beamstops

| Proposed entry / exact bindings | Description and meaningful parts | Categories / initial policy / review |
| --- | --- | --- |
| `pil2M` | SAXS Pilatus detector: camera, TIFF acquisition, ROI1–4, statistics1–5; includes the groups below. | Detectors, SAXS, alignment; U. Snapshot/exposure/energy command links. |
| `pil2M.motor` | Detector `x/y/z` positions in mm; Z contributes to sample-detector distance. True aliases `pil2m_pos`, `pil2M_pos`. | Detector geometry, positioning; U description, S/reviewed workflow motion. Explain motor Z versus calibrated `sample_distance_mm`. |
| `pil2M.beamstop` | `x_rod/y_rod/x_pin/y_pin`; rod and pin assemblies. | Beamstops, SAXS, alignment; U description, S motion/calibration. |
| `pil2M` geometry/selection fields | `active_beamstop`, beam center in pixels/mm, sample distance, pixel size, calibration offsets. Software/calculated values must be distinguished from independent hardware readbacks. | Geometry, calibration, beamstops; U explanation, S persistence/calibration. `_removed` selection is meaningful. |
| `saxs_bs` | Separate `SAXSBeamStops` instance addressing the same four motors as `pil2M.beamstop`; object name `saxs_beamstop`. | Beamstops; related compatibility view, not a second assembly or true object alias. |
| `pil900KW` | WAXS Pilatus detector, camera/TIFF/ROI/statistics, geometry and motor group. | Detectors, WAXS, alignment; U. |
| `pil900KW.motors` / `waxs` | Same object: `arc`, `bs_x`, `bs_y`; arc degrees. Composite `set()` includes a temporary arc restriction. | Geometry, positioning, beamstops; U description, S/reviewed workflow motion. Direct `.arc` moves do not pass through the composite `set()` restriction. |
| `waxs_bs` | Separate motor object on the same PV as `waxs.bs_x`. | Beamstops; R compatibility view. Source documents X motor temporarily unplugged. |
| `pil2mroi1`, `pil2mroi2`, `pil2mroi3`, `pil2mroi4` | Scalar views of SAXS statistics totals, separate from configuring a ROI window. | Diagnostics, detectors, alignment; U linked readout family. |
| `pil900kwroi1`, `pil900kwroi2`, `pil900kwroi3`, `pil900kwroi4` | Scalar views of WAXS statistics totals. | Diagnostics, detectors, alignment; U linked readout family. |
| `amptek` | Amptek MCA/spectrum detector with exposure and energy-channel information. | Detectors, spectroscopy; U description. `amptek_det` is currently `None`, so exposure helper participation is not implied by `amptek` existing. |
| `amptek_pos` | Amptek `x/y/z` detector positioning. | Detector geometry, positioning; U description, setup-specific actions. |
| `fd` | In-memory fake detector with acquisition delay, no physical image detector. | Simulation; R/staff reference, excluded from normal hardware choices. |
| `smi_saxs_detector`, `smi_waxs_detector` | Software metadata devices for detector geometry, not additional acquisition detectors. | Session/data, geometry; S reference. |

Sources: `instances/pilatus.py`, `devices/pilatus.py`, `instances/beamstop.py`,
`devices/beamstop.py`, `instances/amptek.py`, `devices/amptek.py`,
`instances/beam.py`.

### 7.3 Source, energy, optics and attenuation

| Proposed entry / exact bindings | Description and meaningful parts | Categories / initial policy / review |
| --- | --- | --- |
| `ring` | Storage-ring current, lifetime, energy, operating mode and fill target. | Source, diagnostics; U explanation/readbacks. Ring energy is not photon energy. |
| `mstr_shutter_enable`, `smi_shutter_enable`, `ivu_permit` | Permit/status signals; distinct from shutter-position readbacks. | Source, diagnostics, shutters; U explanation. |
| `energy` / `dcm` | Same pseudo-positioner object coordinating photon energy in eV with Bragg/DCM gap/IVU and feedback logic. | Energy, optics; U. Link `%e`; harmonic/configuration controls S. |
| `ivugap`, `bragg`, `dcm_gap` | True aliases to `energy.ivugap`, `.bragg`, `.dcmgap`. | Energy components; S direct controls, U relationship explanation. |
| `dcm_pitch`, `dcm_config` | Separate DCM motor views; `dcm_config.height/pitch/roll/theta`. Height/theta/pitch overlap other DCM motor records. | Optics, energy, commissioning; S. |
| `manual_PID_disable_pitch`, `manual_PID_disable_roll` | Aliases of `energy.pitch_feedback_disabled` and `.roll_feedback_disabled`; disable-bit polarity. | Feedback, energy; S. |
| `hfm`, `vfm`, `vdm` | Mirror positioning groups, `x/y/th`; names and location from installation. | Optics, focusing, positioning; U descriptions, S alignment/actions. Units per field must be verified, especially mirror pitch. |
| `hfm_voltage`, `vfm_voltage` | Bimorph outputs, 16 channels per mirror, V; targets, output readbacks, apply/shift behavior. | Optics, focusing, power; U explanation, S controls and saved states. |
| `attenuation` | Energy-aware aggregate of 24 foils: attenuation factor, transmission, inserted foils. | Attenuation, beam conditioning, alignment; U. Factor and transmission are different quantities; calculations are energy-dependent estimates. |
| `attenuators1`, `attenuators2` | Settled aggregate foil banks, each with `f1`–`f12`. | Attenuation; U relationship, S low-level operations. |
| `att1_1`–`att1_12`, `att2_1`–`att2_12` | 24 separately constructed foil objects addressing the same physical foils as bank children. | Attenuation components; expandable reference, not 24 default top-level menu rows. |
| `crl` | Compound refractive lenses: `lens1`–`lens12`, `x/y/z/ph/th`, immutable inventory and pure focus calculations. | Optics, focusing, positioning; U inventory/model explanation, S actuation. Model helpers use keV, unlike `%e`. |

Sources: `instances/machine.py`, `devices/machine.py`, `instances/energy.py`,
`devices/energy.py`, `instances/mirrors.py`, `devices/mirrors.py`,
`devices/bimorph.py`, `instances/attenuators.py`, `devices/attenuators.py`,
`instances/crls.py`, `devices/crls.py`, `devices/crl_optics.py`.

### 7.4 Slits, apertures, shutters and vacuum

| Proposed entry / exact bindings | Description and meaningful parts | Categories / initial policy / review |
| --- | --- | --- |
| `wbs` | White-beam slit group, `h/hg/v/vg`: horizontal/vertical center and gap. | Slits, optics; U description, S moves. Distinct from camera `WBS`. |
| `ssa` | Secondary-source aperture, same center/gap vocabulary. | Slits, optics, focusing; U description, S moves. |
| `eslit`, `cslit` | C-hutch entrance/downstream slit groups, same center/gap vocabulary. | Slits, beam conditioning; U description, staff-defined moves. |
| `hfmslit`, `vfmslit` | Two-axis FOE mono-beam slit groups: `h/hg` and `v/vg`, respectively. | Slits, optics; S. |
| `dsa` | CRL-area downstream aperture, `x/y`. | Apertures, optics, focusing; U description, S positioning. |
| `fe_shutter` | Read-only front-end shutter status. | Shutters, diagnostics; U. No open/close example implied. |
| `ph_shutter` | Photon shutter with command/status interface; `shopen/shclose` provide feedback-related sequencing. | Shutters, beam availability; U. Cross-link commands; no raw command-PV recipe. |
| `fs` | Fast shutter, distinct from photon shutter and fluorescence-screen camera `FS`. | Shutters, acquisition; U description/status. |
| `fs_motor` | Separate fast-shutter positioning motor; object name `fshutter_motor`. | Shutters, positioning; S, not a synonym for opening `ph_shutter`. |
| `chamber_pressure` | `Sample_Chamber` object (ophyd name `chamber`); `waxs/maxs` pressure channels plus vacuum/power controls. | Vacuum, sample environments, diagnostics; U readout explanation. `chamber` is not established as a namespace alias by this file. |
| Chamber isolation components | `upstream_valve`, `waxs_saxs_valve`; `GV7` is a true alias of the latter. | Vacuum, valves; U explanation, S actions. |
| Chamber pumping/venting components | `svent_valve/fvent_valve/air_valve/N2_valve/turbo_valve/turbo_cooling_valve`, `turbo_enable/det_power/vent_safe`. | Vacuum, utilities; S. Command values are not proof of pump or power state. |

Sources: `instances/slits.py`, `devices/slits.py`, `instances/shutter.py`,
`devices/shutter.py`, `instances/waxschamber.py`, `devices/waxschamber.py`.

### 7.5 Diagnostics, electrometers, cameras and I/O

| Proposed entry / exact bindings | Description and meaningful parts | Categories / initial policy / review |
| --- | --- | --- |
| `xbpm1`, `xbpm2`, `xbpm3` | Electrometer/beam-position measurements: currents, `sumX/sumY`, `posX/posY`, range. | Diagnostics, beam position/flux; U readings, S gain/range. |
| `xbpm1_pos`, `xbpm2_pos`, `xbpm3_pos` | Physical monitor positioning motors `x/y`, not measured beam-centroid signals. | Diagnostics, positioning; U explanation, S movement. |
| `xbpm3y` | Separate scalar view of BPM3 vertical beam-position PV, overlapping `xbpm3.posY`. | Diagnostics; linked compatibility readout. |
| `ssacurrent` | Secondary-source slit electrometer sum. | Diagnostics, slits; U description, verify units. |
| `pin_diode` | TetrAMM acquisition/readout device; current channel 2 is hinted. | Diagnostics, detectors, beamstops; U explanation, reviewed acquisition route only. |
| `pin_diode_ext` | Experimental alternate TetrAMM view, same hardware, many configuration/calibration controls. | Diagnostics, commissioning; R. |
| `pdcurrent`, `pdcurrent1`, `pdcurrent2` | Scalar TetrAMM current2 mean, current2 average, and sum average views. | Diagnostics; U descriptions, distinguish averaging and units. |
| `keithly2450`, `hfmcurrent` | Keithley device and separate HFM current readout. Preserve actual `keithly2450` spelling; “Keithley” is a search synonym. | Diagnostics, optics; U readout explanation, S device controls. |
| `OAV`, `OAV2` | On-axis sample camera and top/hex camera. | Cameras, sample positioning, alignment; U. |
| `FS`, `WBS`, `VFM` | Fluorescent-screen, white-beam-stop and VFM diagnostic cameras. | Cameras, diagnostics, optics; U descriptions. Case-sensitive distinctions are essential. |
| `OAV_writing`, `OAV2_writing`, `FS_writing`, `WBS_writing`, `VFM_writing` | Separate TIFF-writing views of the corresponding cameras, not additional cameras. Some share ophyd `.name` values with their non-writing view. | Cameras, acquisition; U relationship, reviewed image-capture workflows. |
| `WBScamroi1`–`WBScamroi4`, `FScamroi1`–`FScamroi4`, `VFMcamroi1`–`VFMcamroi4`, `HEXcamroi1`–`HEXcamroi4` | Sixteen scalar camera-statistics readouts. | Diagnostics, cameras; expandable U family. |
| `FScamera`, `WBScamera`, `VFMcamera` | TIFF **WriteFile command signals**, despite camera-like names. | Camera control; S, not passive image/readout devices. |
| `diagA_pos`, `diagB_pos` | Diagnostic insertion modules: screen/photodiode/out status and valve commands. | Diagnostics, positioning; U description, S insertion. Object names differ from namespace names. |
| `moxa_in` | Analog-output interface: `ch1`–`ch4` readbacks/setpoints; used for humidity dry/wet flows. | I/O, humidity, flow; S hardware view, U conceptual links. Name does not mean analog input. |
| `moxa_out` | Analog-input interface: `ch1_read`–`ch8_read`; humidity sensing. | I/O, humidity, diagnostics; S hardware view, U selected readings. Name does not mean analog output. |

Sources: `instances/xbpms.py`, `devices/xbpms.py`,
`instances/electrometers.py`, `devices/electrometers.py`,
`instances/prosilica.py`, `devices/prosilica.py`,
`instances/ioLogik.py`, `devices/ioLogik.py`.

### 7.6 Non-device session objects and exclusions

- `RE`, `bec`, `sd`: RunEngine, live analysis/plotting, supplemental baseline data.
  Publish learning topics, not a generic attribute browser.
- `db`, Tiled reading clients: data access services, not detectors. Publish a
  version-specific data-finding topic after the preferred user route is agreed.
- `mdsave`, `samplestore`, status store: persistent configuration/sample/service
  stores; staff reference, not editable dictionaries in novice recipes.
- `SMI` and `smi`: the beamline coordination object and its imported alias from
  `plans/alignment.py`; `beam`: legacy beam helper. Explain through workflow
  cards, not as ophyd hardware or automatically published callable methods.
- Suspenders and RE preprocessors: topics about behavior, not “available devices”.
- Imported classes, modules, libraries, SSH clients, credentials, temporary loop
  names (`camera`, `detpos`, `hp`, `pz`, etc.) are excluded from catalog scraping.
- Commented legacy equipment (`pil1M`, `pil300KW`, `rayonix`, `prs`, `SAXS`,
  `SBS`, aperture/mask examples) is not advertised as installed. A legacy search
  explanation can be approved separately when useful.

### 7.7 Identity and overlap rules to validate

| Relation | Audited examples |
| --- | --- |
| Same object / true alias | `dcm = energy`; `pil2m_pos = pil2M_pos = pil2M.motor`; `waxs = pil900KW.motors`; `GV7 = chamber_pressure.waxs_saxs_valve`; `stage.th/ph/ch = stage.theta/phi/chi`; `SMI` and alignment's `smi`. |
| Different objects, same hardware | `saxs_bs` / `pil2M.beamstop`; `waxs_bs` / `waxs.bs_x`; individual attenuators / bank children; cameras / writing views; `pin_diode` / `pin_diode_ext`; DCM motor views. |
| Related, not identical | Detector and its pin-diode readout; `xbpm3` readings and `xbpm3_pos` motors; `fs` and `fs_motor`; `crl` and `dsa`; `stage` and `stage_temps`. |
| Needs mapping review | `thorlabs_su` / `bc_smaract.x1`; Linkam prefixes; auxiliary MDrive channels. |

Use explicit physical IDs and relations. Runtime object identity can confirm
declared aliases but cannot discover all physical duplicates. Do not merge by
`.name`, class name, PV prefix, or case-folded text alone. Aliases that resolve
to unexpected objects should show a binding conflict, not silently redirect.

## 8. Alignment discovery: central user journey

### Approved first-pass sample context

The beamline-scientist guidance supplied during design is:

- **Grazing incidence:** get the sample close by eye first. For a normal piezo
  setup use `alignment_gisaxs` with a low incident angle relevant to the intended
  data, typically 0.1 or 0.15 degrees. These are typical choices, not enforced
  bounds or a guarantee of suitability for every sample.
- **Grazing incidence on the stage:** use `alignement_gisaxs_hex`; “hex” is the
  historical name and this routine moves `stage`, not `piezo`.
- **Rough samples, vertical mounts, double stacks, other special circumstances
  or problems:** explain why specialized routines exist and refer to a beamline
  scientist. Do not automatically map “vertical” to a particular rotation axis
  or recommend an experimental routine from its name.
- **Transmission:** a relative scan of the relevant sample X or Y motor is
  normally enough. The user examines the result and chooses the position by
  hand or with `pf` analysis. `pf` is the modern user-facing replacement for
  `ps`; local alignment implementations still use `ps` internally. Analysis
  does not itself authorize or command a move to the fitted result.
- Explain built-in `bp.rel_scan` conceptually and link existing fixed-axis
  console scans. Choosing arbitrary detectors, assembling scans, and a generic
  `rel_grid_scan` builder are outside the pilot. Refer unknown contexts and
  multi-axis needs to a beamline scientist and supported smi-plans workflows.

These rules lead the pilot chooser: sample geometry, special circumstances,
then the moving stack. They supersede the earlier suggestion to start with a
generic goal selector. All paths include an “unsure / ask a beamline scientist”
exit. Source-code findings below remain relevant to documented effects/recovery.

### Questions the chooser should ask

1. **Goal:** initial sample alignment, touch-up, beam-size/knife-edge measurement,
   or bounce-down-mirror/setup alignment?
2. **Technique/geometry:** grazing incidence (GISAXS/GIWAXS), transmission,
   XRR/vertical geometry, or unsure?
3. **Moving assembly:** piezo sample stack, Huber/stage, BDM, or unsure?
4. **Mount/orientation:** normal mount, rotated 90 degrees, double stack/top row,
   or another staff-defined setup?
5. **Starting knowledge:** roughly centered? usable reflected beam? previously
   aligned? rough/weakly reflecting surface? Ask only relevant follow-ups.

Return a small comparison of eligible reviewed workflows: “why it matches”,
“what must already be true”, devices/axes, changes, parameters, and end state.
Offer “unsure” throughout. Ambiguous or unsupported combinations end in an
explanation and staff contact, not a guess. “GIWAXS” does not automatically mean
using `pil900KW` to align: local sample alignments generally use `pil2M`.

Chooser rules are explicit staff-authored predicates, with tested examples;
no LLM-generated recommendation, runtime interpretation of docstrings, or
ranking by a reassuring function name such as “fast” or “short”. The chooser
does not infer the sample geometry from arbitrary metadata or a camera image.

### Initial top-level alignment entries

Source for every row: `plans/alignment.py`. All are drafts; “candidate” means a
candidate for staff approval, not operational certification. Preserve the
existing misspelled Python names in invocation metadata; use clear human titles
and search synonyms without renaming APIs as part of documentation work.

| Exact function and current options | Actual distinguishing behavior | Proposed publication / review |
| --- | --- | --- |
| `alignment_gisaxs(angle=0.15)` | Piezo Y/theta; direct-beam height/theta then reflected-beam refinement; exposure 0.3 s; requests measurement mode at normal end. | Candidate standard piezo GISAXS/GIWAXS card. Confirm mount, angle range and failure recovery. |
| `alignment_gisaxs_90deg(angle=0.15)` | Uses piezo Y/chi instead of theta; exposure 0.3 s; requests measurement mode at normal end. | Candidate special-orientation card; staff must define exactly which mounting orientation qualifies. |
| `alignement_gisaxs_doblestack(angle=0.15)` | Direct-beam height, then theta using a reflected ROI at 0.1 degrees before refinement; exposure 0.3 s. | Candidate double-stack card. Explain off-center rotation assumption and final center statistic. |
| `alignement_gisaxs_rough(angle=0.15)` | Direct-beam height and broad theta scans; exposure 0.3 s. `angle` is unused. | Hold action example until purpose, unused option and copied docstring are resolved. |
| `alignement_gisaxs_multisample(angle=0.15)` | Piezo direct/reflected refinement, 0.5 s; mode entry/exit are deliberately omitted. | Orchestration component; staff/reference only. Route multi-sample work to smi-plans. |
| `alignement_gisaxs_hex(angle=0.1, rough_y=0.5)` | Stage Y/theta; initial height then reflected-angle stages; exposure 0.5 s. `rough_y` is a half-width in mm. | Candidate standard stage alignment; confirm implementation versus “direct theta” docstring. |
| `alignement_gisaxs_hex_roughsample(angle=0.1)` | Stage direct-beam height/theta repeats, 0.5 s; `angle` unused. | Hold action example pending rough-sample applicability and parameter cleanup. |
| `alignement_gisaxs_hex_short(angle=0.12)` | Stage height then relative theta offset and reflected refinement; 0.3 s. | Candidate touch-up/known-start card after starting-angle assumptions are approved. |
| `quickalign_gisaxs(angle=0.15)` | Piezo reflected-only height/theta refinement after relative angle offset; 0.3 s. | Candidate already-aligned touch-up card; no promise of finding an arbitrary sample. |
| `alignement_gisaxs_short(angle=0.15)` | Repeats piezo height/theta, then calls `align_gisaxs_th_hex` on the stage; `angle` unused. | Hold; mixed moving assemblies must be reviewed before recommendation. |
| `fast_align(angle=0.1)` | Calls fast procedure, falls back to double-stack routine on false result; measurement-mode finalizer. | Staff/experimental until fast-path assumptions, fallback and failure handling are verified. Docstring mentions nonexistent `step` option. |
| `alignment_bdm(angle=0.1, sample_z_offset_mm=185)` | BDM Y/theta, downward reflected ROI, fine refinement; 0.3 s; final measurement-mode call is commented out. | Staff BDM setup card; explicitly state remaining alignment configuration. |
| `alignment_gisaxs_finer_for_bdm(angle=0.1, sample_z_offset_mm=-50)` | Piezo alignment with offset geometry and finer reflected scans; 0.3 s; measurement-mode exit commented out. | Staff BDM-related sample card; end state and offset sign require review. |
| `knife_edge_x(distance=1.0, steps=51, position=None, **kwargs)` | `piezo.x`, delegates to knife-edge scan; distance is total width in motor units (um here). | Candidate beam-size task with staff-approved range; do not imply default 1.0 is suitable for every beam. |
| `knife_edge_y(distance=1.0, steps=51, position=None, **kwargs)` | Same on `piezo.y`. | Same; distinguish beam characterization from sample alignment. |
| `knife_edge_scan(motor, distance=1.0, steps=51, position=None, exposure_time=0.3, move_to_edge=False, plot=True, show=True)` | Generic motor, alignment mode/direct ROI, relative scan and smi-plans `pf(model='erf')`; optional move to fitted center; measurement-mode finalizer. | Staff generic entry. User selector offers reviewed X/Y variants only; optional fitted-center motion needs separate validation review. |

#### Helper-level audit (reference, not a menu of building blocks)

All following scan/fit helpers default to `rang=0.3`, `point=31`,
`max_retries=3`; height helpers also accept `der=False`. `rang` means **half
width**, in the selected motor's units. `_alignment.scan_and_center` requires a
positive finite range, at least four points, and nonnegative integer retries.

| Functions | Axis | Target statistic |
| --- | --- | --- |
| `align_gisaxs_height`, `align_gisaxs_height_rb` | `piezo.y` (um) | `cen`, `peak`, respectively |
| `align_gisaxs_th`, `align_gisaxs_ch` | `piezo.th`, `piezo.ch` (deg) | `peak` |
| `align_gisaxs_height_hex`, `align_gisaxs_th_hex` | `stage.y` (mm), `stage.th` (deg) | `cen`, `peak` |
| `align_bdm_height`, `align_bdm_height_rb`, `align_bdm_th` | `bdm.y`, `bdm.y`, `bdm.th` | `cen`, `peak`, `cen` |
| `align_xrr_height`, `align_xrr_height_motx` | `piezo.z`, `piezo.x` (um) | `peak` |

`fast_align_procedure(angle=0.1, detector=None, intensity_threshold=40)` and
`bisection_search_plan(motor=None, step_size=1.0, min_step=0.05,
intensity=None, target=0.5, detector=None, polarity=1,
detector_suffix='_stats1_total')` are staff/internal references. Their generic
arguments do not become a user plan-building interface. Fast-path code mixes a
parameterized detector with hard-coded `pil2M` references; the bisection helper
does not have the bounded retry contract of `_scan_and_center`.

The complete XRR routines and `align_xrr_prs` in this module are commented out.
Do not recommend them based on text search hits. A query for XRR should refer to
a beamline scientist. Transmission has the relative-scan/manual-or-pf guidance
above, rather than a dedicated automated local alignment routine.

### What every alignment card must explain

- Named sample axes and units; detector and intensity statistic; initial setup
  and whether a reflected beam is needed.
- `angle` is an angle used during alignment, not a blanket promise that the
  sample finishes at that measurement incidence. Describe the actual final move.
- Exposure changes, ROI changes, sample-name tagging, plotting changes, and
  beamline-mode effects. Typical mode entry inserts attenuation, removes the
  active SAXS beamstop, changes WAXS beamstop Y/possibly arc and sets ROIs.
- `modeMeasurement()` restores the SAXS beamstop and requests attenuation factor
  1; it does not restore every pre-alignment setting or the previous WAXS arc.
- Bounded scan/fit helpers reject invalid centers, check motor endpoints, and can
  recenter/rescan up to three extra times **per helper**. They can travel outside
  the first scan interval; this is not a single full-workflow retry budget.
- Most full alignment routines call mode cleanup only on normal completion;
  they do not share a universal finalizer restoring mode, exposure and BEC state.
  `fast_align` and knife-edge have measurement-mode finalizers, which themselves
  can fail. Do not label all alignments “returns to original state”.
- Typical duration should be a measured range for a reviewed setup, including
  possible retries, not a fabricated estimate from point count alone.

### Example option presentation

For the proposed **Stage grazing-incidence alignment** card:

| Option | Current default | Meaning | Review requirement |
| --- | --- | --- | --- |
| `angle` | 0.1 deg | Reflected-beam alignment angle; final theta is calculated separately. | Staff-approved range and geometry. |
| `rough_y` | 0.5 mm | First stage-height scan spans current Y ± this amount; full width 1.0 mm by default. | Mount clearance and appropriate initial centering. |

Show the exact current function name `alignement_gisaxs_hex`. Add a complete RE
usage example only when staff approves it. Do not expose `max_retries` as a
top-level option: it exists on the scan helpers, not on this function.

## 9. Command and workflow catalog beyond alignment

### Existing magic families to document from one shared specification

| Commands | Card must say |
| --- | --- |
| `%help`, `COMMAND ?`, `%COMMAND?` | Documentation forms; current help tokens prevent action. Preserve Python `help(object)`. |
| `%status` | Explicit bounded live overview, no action. `%status ?` is documentation without reads. |
| `%x/%y/%z/%th/%ph/%ch`; `%sx/%sy/%sz/%sth/%sph/%sch` | No argument reads; one number is relative motion; `a VALUE` is absolute. Piezo translations um, stage mm, rotations deg. Piezo phi unavailable. |
| Axis `scan`/`rscan` families | `pil2M` only, current exposure; absolute endpoints versus symmetric half-width; point count includes endpoints; normal final position. Include stage suffix aliases (`xsscan`, `xsrscan`, etc.) as aliases rather than duplicate cards. |
| `%wh` | Two-stack position readout; missing axes do not make all readings unavailable. |
| `%exp` | No argument reads. `N` is single-image seconds; `N M` uses total seconds `M`, `int(M/N)` images and helper period delay. Amptek conditional participation. |
| `%e` | No argument compares beamline and detector energy in eV. A value moves energy through RE then calls direct `set_energy`, which moves energy again before camera updates. Document real behavior. |
| `%snaps/%snapw/%snapsw` | One trigger on SAXS/WAXS/both using current settings; burst settings can mean multiple images; creates acquisition data with snapshot naming. |
| `%so/%sopen`, `%sc/%sclose` | Photon shutter plus feedback sequencing, executed by RE. |
| `%stop` | Graceful stop of paused RE; not emergency hardware stop or rollback. |

Keep command syntax, help strings, and generated reference pages tied to the
same reviewed specification when implementing. Existing magics remain an
execution surface with their current semantics; the discovery project should
not quietly add new scan capabilities.

### Other task cards worth publishing

| Task | Audited surface | Proposed treatment |
| --- | --- | --- |
| “Take data / repeat across samples” | smi-plans curated `_qserver` exports, technique presets and `*_from_spec` wrappers at wiring boundary | smi-plans owns recipes and orchestration. Audit exact version/surface before cards; no free-form spec editor in guide. |
| “Understand peak/edge results” | `ps`, interactive `pf`, `plot_1d`, `get_incident_angle` | Explain center/peak/COM/FWHM and which recorded run/fields were analyzed. `pf` is optional and external; verify signature. Analysis may access data and update analysis results, so not run during browsing. |
| “Understand ROI and alignment/measurement mode” | `SMI.modeAlignment`, `.modeMeasurement`, `.setDirectBeamROI`, `.setReflectedBeamROI` | Conceptual U cards; staff/reviewed workflow actions. `avoid_gaps=True` can move detector Y; mode switching changes attenuation/beamstop/geometry. |
| “Change/understand energy” | `%e`, `move_energy`, `energy_walk`, `with_harmonic_lock`, `feedback`, managed-move enable/disable, `dcm_diag` | U units/readout/concept; staff diagnostics, harmonic control and bypasses. Never suggest raw Bragg/IVU moves as an error workaround. |
| “Focus the beam” | CRL inventory/model, mirror positioning, bimorph named states | U explanation/selection model; S motion/calibration. A computed CRL candidate is not an approved live setup. |
| “Save or compare beam configuration” | `beam_snapshot_devices`, `save_beam_position_snapshot`, `list_beam_position_snapshots`, `compare_beam_position_snapshot`, `restore_beam_position_snapshot` | Distinguish persistence from reading, comparison from restoration, and default dry-run from execution. Restore source says NEEDS TESTING; staff only. |
| “Recall mirror voltages” | `save_bimorph`, `list_bimorph_states`, `delete_bimorph_state`, `stage_bimorph`, `apply_bimorph`, `load_bimorph` | Staff. Save also writes staged targets; stage writes targets even without mirror motion; apply/load move outputs; delete changes persistent state. |
| “Pump or vent” | `pump_waxs`, `vent_waxs`, chamber plans, `startWAXS`, `restartWAXS` | U explanation of system/state, S controlled procedure. Pump includes detector startup; restart uses remote service access. Guide does not initiate recovery. |
| “Name data / select proposal or project” | `project_set`, `proposal_swap`, `sample_id`, `proposal_id`, scan-naming preprocessor and `show_scan_naming` | Explain proposal/project/sample distinctions and recorded-field templates. Mark deprecated `sample_id/proposal_id/get_scan_md/get_more_md`; use verified smi-plans naming route. Proposal changes are staff-controlled policy candidates. |
| “Capture optical images” | `oav_snapshot`, `with_oav_snapshots`, writing camera views | Distinguish camera acquisition from Pilatus snapshot and beam-position snapshots. Approved named capture route; wrapper composition remains smi-plans/staff. |
| “Why is the run waiting?” | Suspenders, RE state, RE-busy Redis flag, GUI lock, beam-down configuration | U explanation; staff-only disabling/changing controls. Local RE state and GUI heartbeat are not global hardware ownership guarantees. |
| “What is connected?” | `%status`, `hardware_check` | Prefer bounded overview. Hardware check traverses more device components and waits; explicit diagnostic only, never automatic on help/search. |
| “Temperature, humidity, power, coating” | Linkam/LakeShore/Sorensen devices; humidity helpers; blade coater/syringe devices | Setup-specific learning cards plus staff-approved smi-plans workflows. No arbitrary controller command explorer. |
| “Commissioning and maintenance” | `calibrate_epu_lookup`, `attenuator_thickness_calibration`, beamstop calibration, `det_next_file`, `clean_re_md`, `purge_cryo`, `stop_turbo` | Staff-only references; flag persistent edits, direct writes and service operations. `attenuator_two_pass_calibration` is defined in its module but not explicitly exposed by startup. |

Useful mini-lessons also include “why a readback differs from a target”, “why a
detector can acquire with an unrelated motor disconnected”, “why two names refer
to the same hardware”, “which settings persist across sessions”, and “why an
image filename contains recorded motor/energy fields”.

## 10. Implementation sequence and acceptance criteria

### Phase 0 — approve this record and initial content

The complete inventory review is a publication milestone, not a prerequisite
for a small staff-preview prototype. Start with the vertical slice in section 12
and mark its content as preview; finish the following review for each subset
before wider distribution.

- Staff choose audience and owner for each family; resolve the publication
  blockers in section 11 for entries they want to release.
- Confirm categories, human titles, synonyms, setup questions, and preferred
  alignment workflows. Review exact aliases and overlapping physical identities.
- Audit the matching smi-plans revision and agree its data-only provider contract.
- Agree which existing commands may be linked publicly, and whether alignment
  usage is shown as existing RE calls or a supported smi-plans entry point.

Deliverable: reviewed subset with signatures, parameter meaning, examples and
effects. Unresolved entries remain in this review record, not silently published.

### Phase 1 — hardware-independent catalog

- Add schema and pure-data domain records for the approved subset.
- Reuse status/layout references; represent missing bindings explicitly.
- Add validation for unique IDs, valid references, alias collisions, units,
  required workflow effect/end-state fields, and review metadata.
- Add a staff audit report for expected bindings, unclassified source definitions,
  and changed signatures. Inventory generation suggests drafts; it never publishes.

Acceptance: loading/validating the catalog offline imports no instance/startup
modules, creates no devices, contacts no services and writes no metadata.

### Phase 2 — compact console discovery

- First prove IPython/prompt_toolkit handoff with a small static menu and reliable
  exit/restoration. Then connect searchable contextual cards, navigation history,
  local/global results, and numbered/noninteractive fallbacks.
- Add `%guide` home, devices, commands, find, show, learn; explicit help and
  catalog-only completion in both the browser and direct-query interface.
  Generate a Markdown reference from the same data.
- Register terminal-only, after startup has its namespace; preserve built-in
  help, user variables, and existing magics. Do not expose guide callables to QS.
- Make load/reload/unload idempotent; registration failure should leave the
  existing console usable. Load report/session binding checks use cached data.

Acceptance: a novice can find sample height, the SAXS detector, its beamstops,
exposure usage and the generator explanation without opening source code.
Search results remain useful with an empty namespace and no smi-plans package.

### Phase 3 — alignment selection and reviewed workflow cards

- Implement deterministic questions/filters and explained alternatives for the
  approved setup matrix. Provide an equivalent one-line query for transcripts.
- Show validated option tables and complete reviewed usage; selecting a workflow
  displays documentation only. “Unsure” and unsupported setups have useful exits.
- Link related device/effects cards and smi-plans workflows by stable ID/version.

Acceptance: normal grazing-incidence piezo/stage setups reach the approved
routine cards; transmission reaches relative-scan and manual/pf guidance.
Rotated/rough/double-stack/unknown setups and specialized goals refer to staff
without invented recommendations. Staff/internal helpers
never appear as a customizable plan-building menu.

### Phase 4 — optional explicit live views and contextual hints

- Add per-entry status only where a reviewed adapter exists, with read budgets,
  timestamps and no writes. No default live reads in discovery.
- Add selected local UsageError hints and, if warranted, the narrowly scoped
  displayed-generator hint described above.
- Pilot with staff and a few novice users; verify short outputs and terminology.

Acceptance: discovery never changes beamline state; explicit status is bounded;
generator display cannot run or consume a plan. Unload restores normal display.

### Verification planned for implementation

1. **Pure catalog tests:** schema, relation resolution, case-sensitive collisions,
   exact-name preference, synonym ambiguity, stable order, pagination, missing
   providers, audience filtering and generated-reference consistency.
2. **Side-effect sentinel tests:** objects whose `getattr`, `repr`, `get`, `read`,
   `describe`, `set`, `put`, `stage`, `trigger`, or iteration raise if accessed;
   all static guide/completion routes must work without touching them. Assert
   RE, config stores, network clients and live imports are unused.
3. **IPython integration:** help tokens with malformed input, disabled expansion,
   shadowed names, syntax rejection, paused/absent RE, repeated load/unload,
   terminal-only registration, no-color/narrow output, KeyboardInterrupt at a
   chooser prompt, no auto-execution and no modified Python help semantics.
   Test search-as-you-type, Enter/Tab semantics, back-stack cycles, local/global
   ranking, Ctrl-C/D restoration, resize, asynchronous output, fallback menus and
   non-TTY behavior. Confirm guide input never enters an executable shell buffer.
4. **Alignment decision matrix:** approved setups, ambiguous/unknown answers,
   ineligible workflows, mode/end-state warnings, parameter-unit boundaries and
   missing device/provider explanations. No motion-based tests needed for a
   documentation selector.
5. **Signature drift:** source/AST or isolated fake-environment checks for approved
   local callables and matching external provider metadata. Account explicitly
   for decorators, `**kwargs` forwarding and ordinary plan factories. Never call
   a function to determine whether it returns a plan.
6. **Optional status tests:** fake readbacks, timeouts/budget exhaustion, duplicate
   hardware views, unknown state, partial connectivity, software-cache distinction,
   and write sentinels around every reader. Unknown units remain unknown.
7. **Optional generator formatter:** inspect only known unstarted generators;
   preserve display for unknown/started/exhausted generators, avoid argument
   disclosure, confirm no body execution or iteration and reversible registration.

Use the repository's hardware-free test tiers for implementation checks. A
documentation-only draft needs source/link review and diff checks, not live
startup, hardware tests or running the usage examples.

### Maintenance and rollout

- Any device/workflow API change affecting public entries updates its metadata
  and review record in the same change. CI reports missing/changed coverage.
- Pin catalog provenance to released source/provider revisions. On mismatch,
  retain descriptive help but mark affected usage unavailable pending review;
  do not import a missing provider or guess a changed signature.
- Preserve IDs across API renames, retain explicit deprecated search aliases,
  and keep physical-identity relationships separate from namespace aliases.
- New equipment starts as an unpublished draft. Staff own temporary restrictions
  and decide when they can be removed; dates do not automatically clear them.
- Later notebook/GUI views can consume the same catalog. Keep the first release
  terminal-focused and independent of optional web/GUI packages.

## 11. Specific review findings and publication blockers

These are source-audit findings to track, not fixes included in this proposal.
They block the affected recommendation/example, not the entire read-only guide.

| Finding | Evidence / required decision |
| --- | --- |
| Piezo phi is registered in magic families but absent from the device | `SMARACT` defines X/Y/Z/chi/theta only. Document unavailable; do not suggest a substitute axis automatically. |
| Physical setup matters more than function name | `stage` is `STG_pseudo`, although several functions say “hex”; BDM's class and alignment terminology differ. Approve user-facing names/directions. |
| Short/rough alignment names overstate their descriptions | Mixed piezo/stage move in `alignement_gisaxs_short`; unused `angle` in rough/hex-rough/short variants; fast-align docstring's `step` is not a parameter. Resolve before recommendation. |
| End states differ substantially | Multi-sample omits mode entry/exit; BDM and finer-for-BDM omit measurement-mode exit; most full routines lack finally-based mode/BEC restoration. |
| Knife-edge optional fitted move has a different validation path | `knife_edge_scan` uses `pf.cen` directly for `move_to_edge=True`, not `_scan_and_center`'s bounded fit validation. Staff review before publishing this option. |
| Fast alignment is not covered by generic bounded-fit guarantees | `fast_align_procedure` has independent loops/intensity assumptions and mixed detector references; bisection lacks an explicit total-step/travel budget. |
| Current WAXS restriction is object-path dependent | `WAXS_Motors.set()` allows approximately 0 ± 0.1 deg or >=14.5 deg while X beamstop is unplugged. Raw `.arc` moves bypass this method; do not advertise arbitrary arc moves based on its checks. |
| SAXS calibration has temporary behavior | `devices/pilatus.py` contains a temporary beamstop restore over-correction block. Review current calibration/motion recommendations rather than deriving recipes from geometry fields alone. |
| Read-like operations are not all passive | Attenuation legacy reads can refresh metadata; `SMI.SAXS.getPositions()` writes software signals; catalog/static help must not call them. |
| `%e` is a mixed execution path | RE move followed by direct `set_energy`, which moves again and sets camera settings. Show effects accurately; any change is a separate execution-code review. |
| Status documentation has a threshold discrepancy | `docs/MOTOR_MAGICS.md` says vented above `7e3`; `Sample_Chamber.vented_above` is `7e2`. Resolve before copying thresholds into new help. Diagnostic pressure labels are not pump completion/interlock conditions. |
| Chamber pumping condition is not an enforced rejection | `Sample_Chamber.pump()` prints a warning and constructs `Exception()` without raising when pressure is below 500. Do not represent this as a guard that prevents pumping. |
| Humidity controls need review | `readHumidity2/3` both use input channel 3; flow helpers print invalid-input messages but continue toward writes. Verify channels, calibration, units and execution validation before user recipes. |
| Camera configuration needs review | `OAV2.stage_sigs` initially references `OAV.cam.trigger_mode`; later configuration also sets each camera's own signal. Validate the intended writing/non-writing view and staging behavior before recommending acquisition routes. |
| Linkam mapping/legacy helpers need review | Thermal/tensile PV prefixes differ; some status helpers reference apparently mismatched attribute names. Publish selected verified fields, not every method. |
| “Saved state” can write or move | Bimorph save synchronizes targets; beam-position restore has mixed return types and explicit NEEDS TESTING notes. Classify per operation. |
| External workflow coverage is incomplete in this audit | Verify installed smi-plans revision, curated exports, signatures, execution ownership and setup recommendations before publishing cards. |
| Source knowledge is not live availability | Imports can fail individually; aliases/optional services may be absent; current wiring does not make every module-local name a console name. Guide must preserve this distinction. |

## 12. Review checklist and open decisions

### First-pass scope: recommended defaults awaiting confirmation

Only a few scope/content choices need agreement before implementation. The
accepted interaction direction is a searchable contextual browser, with direct
queries and a numbered fallback. Keyboard details and visual layout can be
refined through the prototype rather than decided in advance.

| Decision | Recommended first pass | Why it matters |
| --- | --- | --- |
| Initial scope | A complete small slice: `pil2M`, `pil900KW`, their positioning/beamstop relationships, `piezo`, `stage`, exposure/snapshot/position commands, and RunEngine/units topics. | Demonstrates multiple paths, contextual search, useful command help and cross-device effects without waiting for the whole inventory. |
| Alignment content | Implement the sample-context rules in section 8: normal grazing incidence on piezo/stage, transmission relative scans and pf, specialized/unknown cases to a beamline scientist. | The initial contextual guidance has now been supplied; broader specialist recommendations still need review. |
| Script/API detail | Routine cards show terminal usage and the supported smi-plans automation route. Staff reference can explain the underlying plan/helper and exact execution context. | Establishes the educational depth while preserving smi-plans as the orchestration owner. Unknown external routes are labeled pending verification. |
| Pilot loading and audience | Manually loaded IPython extension, visibly marked staff preview, with draft content isolated from the future published catalog view. | Allows evaluation at the beamline before startup automatically exposes it to all users. |
| Content reviewer | Name one initial staff reviewer for the pilot subset; domain owners can be added as coverage grows. | Someone must confirm terminology, recommended alignments, effect descriptions and examples before publication. |

**Proposed prototype completion criteria:** enter/exit the guide cleanly; find
SAXS distance by at least three routes; search exposure from a detector and learn
that the command affects both detectors; distinguish piezo um from stage mm;
read the generator explanation; navigate related equipment and back; and use
direct-query/noninteractive fallbacks. All of these must work offline, without
hardware access or smi-plans imports.

The prototype can proceed with draft alignment cards while recommendation rules
remain unavailable. Full device approval, live per-device status, generator
display hints, permanent startup registration, external workflow-provider
integration, final category wording and notebook/GUI presentation can follow
after the interaction is evaluated. Initial read-only behavior, explicit action
documentation and the pure-data import boundary remain required from the start.

### Publication review checklist

- [x] Choose searchable contextual navigation through one `%guide` entry point,
  with direct queries and a numbered fallback (accepted in design discussion).
- [ ] Approve hybrid ownership and the pure-data import boundary.
- [ ] Identify staff owners for detectors/geometry, sample alignment, optics,
  environments, and session/data guidance.
- [ ] Mark each initial device family U/S/R or remove it from the proposed release.
- [ ] Confirm axis directions/units, auxiliary device mappings and physical aliases.
- [ ] Pick the recommended alignment subset and precise supported setup matrix.
- [ ] Review effects, normal end states, failure recovery and example parameters
  for each published workflow; record unresolved cases as unavailable.
- [ ] Decide the preferred user-facing smi-plans acquisition/alignment entry points
  and the external metadata/version contract.
- [ ] Agree whether explicit live per-device status belongs in the first rollout
  or follows the metadata-only guide (recommended: follows).
- [ ] Decide whether a passive generator-display hint adds enough value after the
  primer and ordinary command help are in use.

The intended outcome is a compact, learnable console guide with a thorough
staff-owned record behind it: **find the equipment, understand the supported
operation, and use the established workflow with its consequences made clear.**
