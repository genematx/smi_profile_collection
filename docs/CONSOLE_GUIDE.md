# Console guide — staff-preview pilot

The guide is a searchable, documentation-only browser in terminal IPython.
It does not read hardware, execute examples, construct plans or import smi-plans.
The reviewed design and wider inventory are in [the implementation plan](CONSOLE_DISCOVERY_PLAN.md).

## Load and explore

With this repository's `src` on the Python path (as in the beamline profile):

```ipython
%load_ext smi_beamline.discovery.ipython
%guide
```

The pilot is manually loaded; it is not automatically installed by startup.
For a separate Python environment, install the package's `console` extra, or
provide IPython >=9.5 and prompt-toolkit >=3.0.41,<4 alongside the source.

- Type to search. Up/down selects, Enter opens a card, Tab completes its ID.
- There is one numbered choices list. Type a number and Enter to open that
  entry (including multi-digit numbers); invalid numbers leave the card alone.
  To pick from filtered results, append the number to the search, e.g. `exp 2`.
  Numbers are stable across scrolling within the current results.
- Color distinguishes topics (cyan), equipment/parts (blue), related equipment
  (magenta), command/workflow help (green), and scientist assistance (yellow).
  A compact legend replaces bracketed relationship labels. Selected entries
  also have a pointer and reverse highlight. `NO_COLOR` or `%colors nocolor`
  disables the palette and adds short textual labels instead.
- An empty query lists curated choices for the current card.
- Contextual matches are labeled separately from matches elsewhere in the guide.
- Back, Home, Search everything and Exit are always available at the end of the
  suggestion list. Escape clears the query; Alt-Left goes back; Ctrl-C/D exits.
- The browser uses a temporary alternate screen: cards replace one another as
  you navigate. Page Up/Down scrolls long cards; arrows select search results.
  Exiting restores the original console and leaves only the breadcrumb, last
  entry's title/summary, and a direct lookup command. Breadcrumbs represent your
  navigation history, not a unique equipment hierarchy.
- `%guide --plain` opens a numbered menu with text search and pagination.
  This text-only fallback retains its transcript for basic terminal compatibility.
- Terminals declaring `TERM=dumb` use the numbered menu automatically.
- Non-TTY/notebook sessions show help instead of opening a blocking browser.

For updates or removal:

```ipython
%reload_ext smi_beamline.discovery.ipython
%unload_ext smi_beamline.discovery.ipython
```

Python variables are preserved. Use `%guide` explicitly if a variable named
`guide` shadows automagic. Unload restores any previous `guide` magic and removes
only this extension's completer.

## Direct queries

```ipython
%guide devices
%guide show pil2M
%guide show pil2M.motor.z --detail
%guide find saxs distance
%guide find detector --page 2
%guide show command:exp
%guide align
%guide learn runengine
%guide learn pf
```

Direct queries print cards without entering the browser. `show` resolves exact
IDs/aliases; misspellings produce suggestions, never automatic actions. `--detail`
includes source references and aliases. `find` searches titles, identifiers,
synonyms and summaries, not arbitrary Python attributes. Direct-query Tab
completion offers catalog identifiers. Direct queries remain plain text and
include related links; the interactive card omits those links because its one
numbered menu already provides them.

## First-pass content

- SAXS/WAXS detectors, positions, geometry, beamstops and related pin-diode readout.
- Piezo versus Huber/stage, units, exposure/burst settings, snapshots, positions,
  relative scans, photon shutter, status and RunEngine concepts.
- Sample-context alignment: normal grazing-incidence samples are positioned
  roughly by eye, then use `alignment_gisaxs` on piezo or
  `alignement_gisaxs_hex` on stage. A low relevant angle is typically 0.1 or
  0.15 degrees. The “hex” name is historical.
- Transmission: use an appropriate sample X/Y relative scan, inspect the result
  by eye or using `pf`, and decide the position deliberately. `pf` is the modern
  user-facing replacement for `ps`; existing automated plans are not modified.
- Rough samples, vertical/rotated mounts, special setups, problems or uncertainty
  lead to a beamline scientist. Generic grid-scan selection and plan construction
  are outside the pilot; automation stays with smi-plans.

Entering the guide from a detector does not narrow an operation's real scope:
the exposure card explicitly explains that `%exp` configures both Pilatus
detectors. Usage examples that move or acquire are labeled as such. Selecting
them only displays text. The guide does not confirm live availability/readiness;
use established status/operating procedures outside it.

## Staff maintenance

`src/smi_beamline/discovery/catalog.py` contains immutable cards and typed links;
`schema.py` validates IDs/aliases and links without resolving device paths.
`search.py` owns deterministic ranking and navigation, `render.py` renders cards,
`browser.py` owns the temporary-screen interaction, and `ipython.py` registers the
optional magic/completer. None needs a live device to build its documentation.

All current cards are labeled staff preview. This pilot has a single preview
catalog, not an authentication or multi-audience policy system. Review content
before wider publication, and do not place private material in it. The larger
audience/versioned-provider design remains in the plan.

When adding cards, supply purpose, exact aliases, meaningful related links and
source. Operation cards need effects, units, execution context and normal/failure
end-state guidance. Add unknown contexts to the scientist-assistance route rather
than guessing a recommended workflow.

## Offline verification

```sh
pytest tests/unit/test_discovery.py
```

Tests cover isolated imports with live dependencies blocked, sentinel session
objects, catalog identity/relationships, sample-context routes, real IPython
parsing/load/unload, numbered navigation, and prompt-toolkit key input without
hardware. The beamline startup profile and usage examples are not executed.
