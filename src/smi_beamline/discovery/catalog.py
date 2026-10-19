"""Pilot content. All examples are text; no live imports or callable bindings.

Alignment applicability follows beamline-scientist guidance recorded in section 8
of CONSOLE_DISCOVERY_PLAN.md. Effects/signatures are audited against the profile.
"""

from .schema import Card, Catalog, Link


def link(target, label, relation="explore"):
    return Link(target, label, relation)


STAFF = link("staff", "Special circumstances / unsure: ask a beamline scientist")
UNITS = link("units", "Learn units and coordinate systems", "learn")
ALIGN = link("alignment", "Choose alignment by sample type", "task")
EXPOSURE = link("command:exp", "Set detector exposure settings", "command")
SCAN = link("transmission", "Locate a transmission sample", "task")
PLAN_CONTEXT = (
    "Execution context",
    "At the interactive prompt, execute the documented plan with RE. Do not put "
    "terminal magics or nested RE calls inside a plan. For experiment scripts and "
    "repeated samples, use the supported smi-plans workflow with staff assistance.",
)
GI_EFFECTS = (
    "Effects and end state",
    "Changes exposure, ROIs, sample position, attenuation and beamstop configuration; "
    "alignment mode can also move WAXS arc/beamstop Y. Uses pil2M even for GIWAXS "
    "samples. Normal completion requests measurement mode (restores SAXS beamstop "
    "and removes attenuation), but does not restore all prior settings. The final "
    "sample angle is calculated by the routine, not necessarily the supplied angle. "
    "Failure does not guarantee mode or plotting-state restoration: ask a beamline "
    "scientist before continuing. Fit retries can extend beyond the initial interval.",
)


CARDS = [
    Card("home", "SMI guide", "Find equipment, learn commands, and choose a supported task.",
         kind="menu", links=(
             link("devices", "Devices"), ALIGN, link("commands", "Console commands"),
             link("learn", "Learn Bluesky"), link("tasks", "Common tasks"))),
    Card("devices", "Devices", "Browse by role; equipment may appear in several categories.",
         kind="menu", links=(link("detectors", "X-ray detectors"),
             link("positioning", "Motors and positioning"), link("sample", "Sample manipulators"),
             link("beamstops", "Beamstops"), STAFF)),
    Card("detectors", "X-ray detectors", "SAXS and WAXS image detectors.", kind="menu",
         keywords=("camera", "detector types"), links=(
             link("pil2M", "pil2M — SAXS detector"), link("pil900KW", "pil900KW — WAXS detector"))),
    Card("positioning", "Motors and positioning", "Sample and detector coordinates serve different purposes.",
         kind="menu", links=(link("sample", "Sample manipulators"),
             link("detector-positioning", "Detector positioning"), UNITS)),
    Card("detector-positioning", "Detector positioning", "Find detector position and geometry information.",
         kind="menu", links=(link("pil2M.motor", "SAXS detector positioning"),
             link("pil2M.motor.z", "SAXS distance axis"), link("pil900KW.motors", "WAXS positioning"))),
    Card("sample", "Sample manipulators", "Choose the stack that actually carries your sample.",
         kind="menu", keywords=("height", "sample stage", "motors"), links=(
             link("piezo", "Piezo sample stack — um"), link("stage", "Huber / stage — mm"),
             ALIGN, UNITS)),
    Card("beamstops", "Beamstops", "Learn which beamstop assembly belongs to each detector.",
         kind="menu", links=(link("pil2M.beamstop", "SAXS rod and pin beamstops"),
             link("pil900KW.motors", "WAXS beamstop and arc"), STAFF)),
    Card("tasks", "Common tasks", "Start with what you want to understand.", kind="menu", links=(
         ALIGN, SCAN, link("pil2M.motor.z", "Understand SAXS detector distance"),
         EXPOSURE, link("command:snaps", "Take a detector snapshot"), STAFF)),
    Card("commands", "Console commands", "These cards explain existing commands; selecting one never runs it.",
         kind="menu", links=(link("command:positions", "Read or move sample axes"),
             link("command:relscan", "Relative sample-axis scans"), EXPOSURE,
              link("command:snaps", "Detector snapshots"), link("command:shutter", "Photon shutter"),
              link("command:attenuation", "Read or set attenuation"),
              link("command:waxs-vacuum", "Vent or pump WAXS"),
             link("command:status", "Read beamline status"), link("runengine", "RunEngine and run control"))),
    Card("learn", "Learn Bluesky", "Short explanations connected to equipment and tasks.",
         kind="menu", links=(link("runengine", "Why did I get a generator?"), UNITS,
             link("exposure", "Exposure, period and images per trigger"),
             link("pf", "Analyze a scan with pf"), link("automation", "Terminal versus scripts"))),
    Card("pil2M", "pil2M — SAXS detector", "Records small-angle scattering images and intensity statistics.",
         kind="device", keywords=("saxs detector", "small angle", "camera", "2m"),
         sections=(("Equipment", "Hutch C. Camera and TIFF acquisition, ROI1–4, statistics1–5, "
                    "detector positioning, geometry and beamstops are parts of this device."),),
         links=(link("exposure", "Exposure and image count"), EXPOSURE,
             link("command:exp-read", "Read detector exposure settings"),
             link("roi", "Regions of interest and intensity"),
             link("pil2M.motor", "Detector positioning", "child"),
             link("pil2M.beamstop", "Beamstops", "child"),
             link("saxs-geometry", "Detector geometry", "child"), ALIGN,
             link("pil900KW", "WAXS detector", "related"),
             link("pin_diode", "Pin-diode readout", "related"),
             link("command:snaps", "Take a detector snapshot", "command")),
         source="src/smi_beamline/instances/pilatus.py; devices/pilatus.py"),
    Card("pil900KW", "pil900KW — WAXS detector", "Records wide-angle scattering images and intensity statistics.",
         kind="device", keywords=("waxs detector", "wide angle", "camera", "900kw"),
         sections=(("Equipment", "Hutch C. Camera/TIFF acquisition and ROI/statistics plugins, "
                    "with an arc and beamstop motor assembly."),),
         links=(link("exposure", "Exposure and image count"), EXPOSURE,
             link("command:exp-read", "Read detector exposure settings"),
             link("pil900KW.motors", "WAXS arc and beamstop", "child"),
             link("roi", "Regions of interest"), link("pil2M", "SAXS detector", "related"),
             link("command:snaps", "Take a detector snapshot", "command")),
         source="src/smi_beamline/instances/pilatus.py; devices/pilatus.py"),
    Card("pil2M.motor", "SAXS detector positioning", "Detector X/Y/Z motors in mm; this is not the sample stack.",
         kind="component", aliases=("pil2m_pos", "pil2M_pos"), keywords=("saxs position", "carriage"),
         sections=(("Names", "pil2M.motor, pil2m_pos and pil2M_pos are the same object. "
                    "X/Y affect beam-center geometry; Z contributes to sample-detector distance. "
                    "Detector moves and beamstop coordination need an approved setup workflow."),),
         links=(link("pil2M.motor.z", "SAXS distance axis", "child"),
             link("saxs-geometry", "Calibrated geometry"), link("pil2M", "SAXS detector", "part of"),
             link("pil2M.beamstop", "Related beamstops", "related"), STAFF),
         source="src/smi_beamline/instances/pilatus.py"),
    Card("pil2M.motor.z", "SAXS distance axis — pil2M.motor.z", "Detector Z motor position in mm; related to sample-detector distance.",
         kind="component", aliases=("pil2m_pos.z", "pil2M_pos.z"),
         keywords=("saxs distance", "sdd", "sample detector distance", "detector z"),
         sections=(("Position versus distance", "The motor coordinate is not automatically the calibrated "
                    "sample-detector distance. pil2M.sample_distance_mm includes a calibration offset; "
                    "geometry/beamstop calibration also depends on detector position. Ask a beamline "
                    "scientist for the supported geometry-changing workflow."),),
         links=(link("pil2M.motor", "Detector positioning", "part of"),
             link("saxs-geometry", "Calibrated SAXS geometry", "related"),
             link("pil2M.beamstop", "SAXS beamstops", "related"), UNITS, STAFF),
         source="src/smi_beamline/devices/pilatus.py"),
    Card("saxs-geometry", "SAXS detector geometry", "Beam center, pixel size and calibrated distance are software geometry values.",
         aliases=("pil2M.sample_distance_mm",), keywords=("calibration", "pixels", "sdd"),
         sections=(("Meaning", "Beam-center fields in pixels/mm and sample_distance_mm are calculated "
                    "using positions and calibration. They are not independent hardware measurements. "
                    "Calibration changes belong to staff."),), links=(
             link("pil2M.motor.z", "Distance motor", "related"), link("pil2M", "SAXS detector", "part of"), STAFF),
         source="src/smi_beamline/devices/pilatus.py"),
    Card("pil2M.beamstop", "SAXS rod and pin beamstops", "The detector's beamstop assembly has x_rod/y_rod/x_pin/y_pin motors.",
         kind="component", keywords=("saxs_bs", "pin", "rod", "protection"),
         sections=(("Related names", "saxs_bs is a separate Python object addressing the same hardware, "
                    "not a second beamstop assembly or a true object alias. active_beamstop is a software "
                    "selection; values ending in _removed have a specific meaning."),
                   ("Operation", "Alignment and measurement modes coordinate attenuation and beamstop "
                    "movement. Learn these effects before using a reviewed alignment routine. "
                    "Beamstop positioning/calibration needs a beamline scientist.")),
         links=(link("pil2M", "SAXS detector", "part of"), link("pin_diode", "Pin-diode readout", "related"),
             link("modes", "Alignment and measurement modes", "learn"), STAFF),
         source="src/smi_beamline/devices/pilatus.py; instances/beamstop.py"),
    Card("pil900KW.motors", "WAXS arc and beamstop", "Arc angle (degrees), beamstop X and beamstop Y form a coupled setup.",
         kind="component", aliases=("waxs",), keywords=("waxs_bs", "waxs position", "arc", "beamstop"),
         sections=(("Current source restriction", "WAXS_Motors.set restricts the arc while the X beamstop "
                    "is documented as unplugged. Direct arc moves bypass that composite method. "
                    "This guide does not recommend arbitrary arc/beamstop moves; ask a beamline scientist."),
                   ("Identity", "waxs is the same object as pil900KW.motors. waxs_bs is a separate "
                    "motor object on the same hardware as waxs.bs_x.")),
         links=(link("pil900KW", "WAXS detector", "part of"), STAFF),
         source="src/smi_beamline/devices/pilatus.py; instances/beamstop.py"),
    Card("pin_diode", "Pin-diode readout", "TetrAMM intensity readout related to the SAXS pin beamstop.",
         kind="device", keywords=("flux", "current", "pdcurrent"),
         sections=(("Distinction", "The readout device is not a beamstop motor. Scalar current views "
                    "and the experimental pin_diode_ext view address related readout hardware."),),
         links=(link("pil2M.beamstop", "SAXS beamstop assembly", "related"), STAFF),
         source="src/smi_beamline/instances/electrometers.py"),
    Card("piezo", "Piezo sample stack", "Sample translations X/Y/Z use um; theta/chi use degrees.",
         kind="device", keywords=("height", "smaract", "sample position", "incident angle"),
         sections=(("Axes", "piezo.x/y/z and piezo.th/ch are defined. piezo.ph is currently absent. "
                    "Confirm the mount and physical direction before selecting a motor."),),
         links=(link("command:positions", "Read or move sample axes"), ALIGN, SCAN, UNITS,
             link("stage", "Other sample stack: Huber / stage", "related")),
         source="src/smi_beamline/devices/manipulators.py"),
    Card("stage", "Huber / stage sample stack", "Laboratory-frame pseudo axes: X/Y/Z in mm; rotations in degrees.",
         kind="device", keywords=("hex", "hexapod", "height", "sample position", "incident angle"),
         sections=(("Axes and old names", "stage.th/ph/ch alias stage.theta/phi/chi. Rotations can "
                    "compensate real translations using configured rotation centers. 'hex' in alignment "
                    "routine names is historical: those routines use stage, not piezo."),),
         links=(link("command:positions", "Read or move sample axes"), ALIGN, SCAN, UNITS,
             link("piezo", "Other sample stack: piezo", "related")),
         source="src/smi_beamline/devices/manipulators.py"),
    Card("exposure", "Exposure, period and images per trigger", "One trigger can produce several images with current burst settings.",
         keywords=("exposure time", "acquire time", "image count", "burst"),
         sections=(("Meaning", "Exposure is time per image. Period is the interval configured between "
                    "image starts; the current helper adds 0.001 s to exposure by default. "
                    "Images per trigger = int(total measurement seconds / image seconds). "
                    "The total argument is not an image count; a remainder is truncated."),),
         links=(EXPOSURE, link("command:exp-read", "Read current settings"),
             link("command:snaps", "Snapshot acquisition")), source="src/smi_beamline/motor_magics.py"),
    Card("command:exp-read", "Read detector exposure settings", "The existing %exp command without arguments reads settings.",
         kind="command", sections=(("Terminal usage — live read", "%exp"),
             ("Scope", "Reads SAXS/WAXS exposure, period and images per trigger; Amptek when enabled. "
              "Does not call RE. The guide itself does not perform these reads.")),
         links=(EXPOSURE, link("exposure", "Understand the settings")), source="src/smi_beamline/motor_magics.py"),
    Card("command:exp", "Set detector exposure settings", "Configure both Pilatus detectors; Amptek participates when enabled.",
         kind="command", aliases=("exp",), keywords=("exposure time", "setting exposure", "burst"),
         sections=(("Terminal syntax", "%exp IMAGE_SECONDS TOTAL_SECONDS"),
             ("Example — changes detector settings", "%exp 0.5 2"),
             ("Arguments", "0.5 s per image; int(2 / 0.5) = 4 images per trigger. Require "
              "IMAGE_SECONDS > 0 and TOTAL_SECONDS >= IMAGE_SECONDS. %exp N alone sets one N-second image."),
             ("Execution context", "Standalone IPython magic, using this session's idle RE. The "
              "underlying det_exposure_time(exp_t, meas_t, period_delay=0.001) is a plan helper, "
              "not an immediate setter. Experiment automation belongs to smi-plans; do not call "
              "the magic inside functions/plans."),
             ("Scope and end state", "Changes both pil2M and pil900KW, even when reached from one "
              "detector's card; optionally Amptek. Settings remain changed and are read back after success.")),
         links=(link("command:exp-read", "Read exposure settings"), link("exposure", "Learn exposure semantics"),
             link("automation", "Terminal versus scripts")), source="src/smi_beamline/motor_magics.py; instances/pilatus.py"),
    Card("command:snaps", "Detector snapshots", "One trigger on SAXS, WAXS or both, using current exposure settings.",
         kind="command", aliases=("snaps", "snapw", "snapsw"), keywords=("image", "acquisition", "count"),
         sections=(("Terminal usage — acquires data", "%snaps   (SAXS)\n%snapw   (WAXS)\n%snapsw  (both)"),
             ("Effects", "Calls RE on a count plan and records data with snapshot naming. One trigger "
              "may produce multiple images. Requires the correct measurement setup; it does not "
              "perform sample alignment or establish beamstop safety."),
             ("Execution context", "Standalone terminal commands; current exposure remains in effect. "
              "For scripted acquisition and repeated samples use the supported smi-plans workflow.")),
         links=(link("exposure", "Check exposure semantics"), link("modes", "Measurement setup"),
             link("automation", "Acquisition automation")), source="src/smi_beamline/motor_magics.py"),
    Card("command:positions", "Read or move sample axes", "Bare axis commands read; a number jogs; 'a' selects an absolute target.",
         kind="command", keywords=("x", "y", "z", "sx", "sy", "wh", "move", "height", "position"),
         sections=(("Read at the terminal", "%wh\n%x   (piezo X)\n%sx  (stage X)"),
             ("Motion syntax — changes sample position", "%x VALUE       relative piezo X, um\n"
              "%x a VALUE     absolute piezo X, um\n%sx VALUE      relative stage X, mm\n"
              "%sx a VALUE    absolute stage X, mm"),
             ("Other axes", "Piezo: x y z th ch (ph unavailable). Stage: sx sy sz sth sph sch. "
              "Rotations are degrees. Use finite numeric literals, no units or expressions in input. "
              "Select distances appropriate to the actual mount; limits do not establish collision clearance."),
             ("Execution context", "Standalone magics: movement uses an idle RE, reading does not. "
              "Do not use these magics inside scripts/functions/plans. No automatic position rollback.")),
         links=(link("piezo", "Piezo axes"), link("stage", "Stage axes"), UNITS, SCAN),
         source="src/smi_beamline/motor_magics.py"),
    Card("command:relscan", "Relative sample-axis scans", "Existing fixed-axis console scans use pil2M and current exposure.",
         kind="command", keywords=("rel_scan", "xrscan", "yrscan", "sxrscan", "syrscan", "scan"),
         sections=(("Terminal syntax — moves and acquires", "%xrscan SPAN POINTS    piezo.x, um\n"
              "%yrscan SPAN POINTS    piezo.y, um\n%sxrscan SPAN POINTS   stage.x, mm\n"
              "%syrscan SPAN POINTS   stage.y, mm"),
             ("Arguments", "SPAN is a positive half-width about the starting position; POINTS is an "
              "integer >= 2 including both endpoints. Choose the axis and span appropriate to the "
              "sample and setup. Current detector exposure is used."),
             ("End state", "The relative scan returns to its starting position on normal completion; "
              "it does not move to a fitted result. Check the actual state after interruption."),
             ("Execution context", "Standalone terminal magics wrap RE(bp.rel_scan(...)). For "
              "automation use smi-plans. General multi-axis/grid-scan selection is outside this guide; "
              "ask a beamline scientist.")), links=(SCAN, link("pf", "Analyze the result with pf"),
             link("exposure", "Exposure settings"), UNITS, STAFF), source="src/smi_beamline/motor_magics.py"),
    Card("command:shutter", "Photon shutter and feedback", "Open/close commands coordinate the photon shutter and DCM feedback.",
         kind="command", aliases=("sc", "sclose", "so", "sopen", "shclose", "shopen"),
         sections=(("Terminal usage — acts on the beamline", "%sc  or %sclose   close\n%so  or %sopen    open"),
             ("Meaning", "Close runs RE(shclose()): disables feedback, waits, then commands the "
              "photon shutter. Open runs RE(shopen()), enabling feedback by default. These are not "
              "fast-shutter or front-end-shutter commands, and not emergency stops."),
             ("Execution context", "Magics run the plan for you. shclose() alone returns a generator; "
              "RE(shclose()) executes it. Use only when intending this hardware action.")),
         links=(link("runengine", "Why a generator?"), link("command:status", "Shutter status")),
         source="src/smi_beamline/instances/shutter.py; motor_magics.py"),
    Card("command:attenuation", "Read or set attenuation", "Report current attenuation or request a factor at the current energy.",
         kind="command", aliases=("a", "attenuation"), keywords=("attenuator", "transmission", "foils"),
         sections=(("Terminal syntax", "%a       read current attenuation\n%a 1234  request attenuation factor 1234"),
             ("Meaning", "Factor is 1/transmission; use a finite value >= 1. A factor of 1 removes "
              "attenuation. Foil selection can approximate the requested value; the achieved factor, "
              "transmission, energy and inserted foils are read back after success."),
             ("Execution context", "Standalone magic. Setting uses RE(bps.mv(attenuation, VALUE)) "
              "with an idle RE; reading uses current foil states without calling RE.")),
         links=(link("command:status", "Beamline status"), link("automation", "Terminal versus scripts")),
         source="src/smi_beamline/motor_magics.py; devices/attenuators.py"),
    Card("command:waxs-vacuum", "Vent or pump WAXS", "Run the existing WAXS chamber plans from the console.",
         kind="command", aliases=("vent", "pump", "vent_waxs", "pump_waxs"), keywords=("vacuum", "chamber"),
         sections=(("Terminal syntax", "%vent   RE(vent_waxs())\n%pump   RE(pump_waxs())"),
             ("Meaning", "Venting runs the chamber vent routine. Pumping runs the chamber autopumping "
              "routine, waits, then starts the WAXS detector. These operations take several minutes."),
             ("Execution context", "Standalone magics taking no arguments and using this session's idle RE.")),
         links=(link("pil900KW", "WAXS detector"), link("runengine", "RunEngine and run control")),
         source="src/smi_beamline/motor_magics.py; instances/pilatus.py"),
    Card("command:status", "Read beamline status", "The existing %status displays a bounded live overview.",
         kind="command", aliases=("status",), keywords=("offline", "connected", "readout"),
         sections=(("Terminal usage — live read", "%status\n%status ?   (help only)"),
             ("Meaning", "Curated upstream-to-downstream readbacks, with 150 ms read timeouts and "
              "a 3 s read budget. Missing/offline/unknown values stay visible. No RE or device writes. "
              "It is a sequential snapshot, not proof that a workflow is ready. Guide cards never read hardware.")),
         links=(link("runengine", "RunEngine states"), STAFF), source="src/smi_beamline/beamline_status.py"),
    Card("roi", "Regions of interest and intensity", "An ROI selects image pixels; statistics summarize their intensity.",
         keywords=("roi", "stats", "peak", "direct beam", "reflected beam"),
         sections=(("Alignment", "Alignment routines configure direct/reflected-beam ROIs and use "
                    "intensity to locate the sample. ROI settings are not the same thing as moving "
                    "the sample or acquiring an image. Use staff-reviewed setup procedures."),),
         links=(ALIGN, link("pf", "Peak/edge analysis"), link("pil2M", "SAXS detector")),
         source="src/smi_beamline/instances/beam.py"),
    Card("modes", "Alignment and measurement modes", "Mode changes coordinate attenuation, beamstops and detector geometry.",
         keywords=("modeAlignment", "modeMeasurement", "attenuation"),
         sections=(("Alignment mode", "Inserts attenuation, removes the active SAXS beamstop, sets ROIs, "
                    "and can move WAXS arc/beamstop Y. These are hardware actions, not display modes."),
                   ("Measurement mode", "Restores SAXS beamstop and requests attenuation factor 1. "
                    "Does not restore every previous setting or WAXS arc. An interrupted alignment "
                    "may need staff-assisted recovery.")), links=(ALIGN, STAFF),
         source="src/smi_beamline/instances/beam.py"),
    Card("units", "Units and coordinate systems", "Piezo translations use um; stage translations use mm; rotations use degrees.",
         keywords=("microns", "millimeters", "relative", "absolute", "energy", "ev", "kev"),
         sections=(("Scale", "1000 um = 1 mm. Detector positioning is mm. Beamline %e uses eV; "
                    "some optics helpers use keV. Read each command's units; magics do not convert units."),
                   ("Coordinates", "Relative motion adds an offset to the current coordinate; absolute "
                    "motion selects a coordinate. Stage pseudo axes can move multiple real motors. "
                    "Motor limits do not describe all mount clearances.")),
         links=(link("piezo", "Piezo"), link("stage", "Stage"), link("command:positions", "Axis commands"))),
    Card("runengine", "RunEngine and generators", "A plan generator describes work; RE executes it.",
         aliases=("generators",), keywords=("shclose()", "generator object", "pause", "stop", "resume", "suspenders"),
         sections=(("Why shclose() gives a generator", "shclose() creates the plan without running its "
                    "body: the shutter has not closed. RE(shclose()) executes that plan; %sc is the "
                    "existing terminal shortcut. Those latter forms act on hardware. Do not use next() "
                    "or list() to make a plan work."),
                   ("Other Python calls", "Ordinary helpers and device setters may act immediately, "
                    "even when they return a Status. Not every function is a plan; check its context."),
                   ("Paused or waiting", "RE.state describes the local engine, not global beamline "
                    "ownership. A paused plan needs a deliberate resume or termination decision. "
                    "RE.resume() continues; RE.stop() (or %stop) ends gracefully; RE.abort() aborts. "
                    "These are actions, not rollback or emergency hardware stops. Cleanup can move "
                    "hardware. For uncertainty or interruption recovery, ask a beamline scientist."),
                   ("Suspenders and data", "Suspenders can wait for beam or temperature recovery; "
                    "do not disable them as a routine workaround. Acquisition plans record runs, "
                    "but a shutter-only plan need not create a data run.")),
         links=(link("command:shutter", "Shutter usage"), link("automation", "Terminal versus scripts"), STAFF)),
    Card("automation", "Terminal versus scripts", "Use supported smi-plans workflows for experiment orchestration.",
         keywords=("script", "plan", "queue", "functions", "repeat", "scan builder"),
         sections=(("Execution contexts", "Terminal magics perform complete standalone actions. "
                    "Plan helpers are consumed by RE as part of maintained workflows; ordinary helpers "
                    "may act immediately. This guide does not compose plans or offer an arbitrary "
                    "command runner. Ask a beamline scientist for the appropriate smi-plans entry point."),
                   ("External API", "smi-plans is optional at startup. Its installed command surface "
                    "and parameter signatures require separate verification; the guide does not import "
                    "it to inspect or invent script recipes.")), links=(link("runengine", "RE basics"), STAFF)),
    Card("pf", "Analyze a scan with pf", "pf is the modern user-facing peak/edge analysis helper, replacing ps.",
         aliases=("ps",), keywords=("fit", "center", "peak", "fwhm", "analysis", "transmission"),
         sections=(("User workflow", "Inspect the recorded scan and decide which position is appropriate "
                    "by eye or using pf analysis. A fitted center/peak is evidence for your decision, "
                    "not an automatic instruction to move. Confirm the run and fields being analyzed."),
                   ("Installed help — documentation only", "pf?"),
                   ("Availability and context", "Interactive startup exposes pf from smi-plans when "
                    "available. Consult its installed signature/options; this preview does not guess "
                    "them. Analysis can read stored data and create plots. Existing local automated "
                    "alignment routines still use ps internally; this guide does not change them.")),
         links=(SCAN, link("command:positions", "Deliberate positioning"), STAFF),
         source="startup/startup.py; src/smi_beamline/plans/alignment.py; scientist guidance"),
    Card("staff", "Ask a beamline scientist", "For special samples, unknown setups or problems, get assistance before choosing a procedure.",
         keywords=("rough", "vertical", "rotated", "double stack", "xrr", "bdm", "knife edge", "rel_grid_scan", "problem", "unsure"),
         sections=(("Useful information to bring", "Your sample geometry, mounting orientation, moving "
                    "stack, intended incidence/measurement, and what you observed. Specialized "
                    "rough-sample, rotated-mount, double-stack and BDM routines exist, but their "
                    "names alone do not establish suitability."),
                   ("Beyond this guide", "Multi-axis/grid scans, beam-size characterization, XRR, "
                    "unusual mounts and failed alignment need a staff-selected procedure. "
                    "Do not substitute axes or chain together helpers to compensate.")), links=(ALIGN, SCAN)),
]


def _alignment_cards():
    cards = [
        Card("alignment", "Alignment: what type of sample?", "Start with sample geometry, then mounting and the moving stack.",
             kind="question", aliases=("align",), keywords=("sample alignment",), links=(
                 link("gi-mount", "Grazing incidence — GISAXS / GIWAXS"),
                 link("transmission", "Transmission sample"), STAFF)),
        Card("gi-mount", "Grazing incidence: mounting and surface", "Is this a normal mount, or are there special circumstances?",
             kind="question", links=(link("gi-stack", "Normal mount and surface"),
                 link("staff", "Rough sample / weak reflection"),
                 link("staff", "Vertical or rotated mount"),
                 link("staff", "Double stack / other special setup"), STAFF)),
        Card("gi-stack", "Grazing incidence: which sample stack?", "Get the sample close by eye before running the automated routine.",
             kind="question", sections=(("Angle choice", "Use a low incident angle relevant to your "
                 "intended data, typically 0.1 or 0.15 degrees. Ask a scientist if unsure."),), links=(
                 link("alignment:piezo", "Sample on piezo"), link("alignment:stage", "Sample on stage / Huber (old 'hex')"), STAFF)),
        Card("transmission", "Locate a transmission sample", "Scan the relevant sample X or Y axis, then choose the position from the result.",
             kind="workflow", keywords=("transmission alignment", "rel_scan", "horizontal", "vertical", "sample location"),
             sections=(("Workflow", "A relative scan of the relevant X or Y sample motor is normally "
                 "enough. Choose the motor based on the actual sample/mount and choose a suitable "
                 "span and detector setup. Inspect the scan by eye or use pf analysis, then decide "
                 "where to position the sample."),
                 ("Bluesky concept", "bp.rel_scan scans offsets around the starting coordinate; RE "
                  "executes the plan. Normal completion returns to the starting coordinate, not the "
                  "feature you found. Existing fixed-axis console commands below use pil2M."),
                 ("Scope", "This is user-directed localization, not an automatic grazing-incidence "
                  "alignment. Grid/multi-axis scan selection and arbitrary plan construction are "
                  "outside the pilot. Ask a beamline scientist for other detectors or unknown setups.")),
             links=(link("transmission:piezo", "Sample on piezo"),
                 link("transmission:stage", "Sample on stage / Huber"), link("pf", "Analyze with pf"), STAFF),
             source="Scientist guidance; src/smi_beamline/motor_magics.py"),
    ]
    for stack, routine, default, exposure in (
        ("piezo", "alignment_gisaxs", "0.15", "0.3"),
        ("stage", "alignement_gisaxs_hex", "0.1", "0.5"),
    ):
        options = f"angle={default} degrees; typical choices are 0.1 or 0.15 degrees, relevant to your data."
        if stack == "stage":
            options += " rough_y=0.5 mm is the initial height scan half-width, not full width."
        cards.append(Card(
            f"alignment:{stack}", f"Grazing-incidence alignment on {stack}",
            f"For a normal grazing-incidence sample carried by {stack}, after getting close by eye.",
            kind="workflow", aliases=(routine,), keywords=("gisaxs", "giwaxs", "incident angle", stack),
            sections=(("Applicability", "Normal mount/surface only. Rough samples, vertical mounts, "
                       "special setups, uncertainty or problems: ask a beamline scientist. "
                       "This search result does not establish your setup is suitable."),
                      ("Terminal example — moves hardware and acquires", f"RE({routine}(angle={default}))"),
                      ("Options", options + f" The routine sets exposure to {exposure} s. "
                       "Typical angles are not enforced bounds. " +
                       ("'hex' is the old name: this routine moves stage.y and stage.th."
                        if stack == "stage" else "Moves piezo.y and piezo.th.")),
                      GI_EFFECTS, PLAN_CONTEXT),
            links=(link(stack, "Moving sample stack", "uses"), link("pil2M", "Alignment detector", "uses"),
                   link("modes", "Mode changes explained"), ALIGN, STAFF),
            source=f"src/smi_beamline/plans/alignment.py:{routine}; scientist guidance"))
        prefix, unit = ("", "um") if stack == "piezo" else ("s", "mm")
        cards.append(Card(
            f"transmission:{stack}", f"Transmission positioning on {stack}",
            f"Choose the relevant {stack}.x or {stack}.y axis; translations use {unit}.", kind="workflow",
            sections=(("Existing terminal scans — moves and acquires", f"%{prefix}xrscan SPAN POINTS\n%{prefix}yrscan SPAN POINTS"),
                      ("Choose settings deliberately", f"SPAN is a half-width in {unit}; POINTS >= 2. "
                       "These commands use pil2M and its current exposure settings. Confirm the correct "
                       "measurement setup first; no universal scan width is appropriate to every mount."),
                      ("Decide after the scan", "Inspect the data by eye or with pf, then deliberately "
                       "choose a position. The scan returns to start on normal completion; pf analysis "
                       "does not automatically move the sample. Ask staff about other setups.")),
            links=(link("command:relscan", "Scan syntax and execution context"), link("pf", "Analyze with pf"),
                   link("command:positions", "Read / deliberately move axes"), UNITS, STAFF),
            source="Scientist guidance; src/smi_beamline/motor_magics.py"))
    return cards


CATALOG = Catalog((*CARDS, *_alignment_cards()))
