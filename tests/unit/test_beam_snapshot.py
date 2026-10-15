import copy
import json
from types import SimpleNamespace

import pytest
from ophyd import Signal
from bluesky import RunEngine
import bluesky.plan_stubs as bps

from smi_beamline.plans import beam_snapshot


class _Motor:
    def __init__(self, name, value):
        self.name = name
        self.parent = None
        self.prefix = name.upper()
        self.user_readback = Signal(value=value, name=name + "_rb")
        self.user_setpoint = Signal(value=value, name=name + "_sp")
        self.user_offset = Signal(value=0.0, name=name + "_off")
        self.low_limit = Signal(value=-1000.0, name=name + "_llm")
        self.high_limit = Signal(value=1000.0, name=name + "_hlm")
        self.velocity = Signal(value=2.5, name=name + "_velo")
        self.motor_egu = Signal(value="mm", name=name + "_egu")

    def set(self, value):
        return self.user_setpoint.set(value)


class _Device:
    pass


def _slit(prefix, start=0):
    dev = _Device()
    for i, axis in enumerate(("h", "hg", "v", "vg")):
        setattr(dev, axis, _Motor(prefix + "_" + axis, start + i))
    return dev


def _mirror(prefix, start=0):
    dev = _Device()
    for i, axis in enumerate(("x", "y", "th")):
        setattr(dev, axis, _Motor(prefix + "_" + axis, start + i))
    return dev


def _xbpm(prefix, start=0):
    dev = _Device()
    dev.x = _Motor(prefix + "_x", start)
    dev.y = _Motor(prefix + "_y", start + 1)
    return dev


def _crl():
    dev = _Device()
    dev.inserted_tolerance_mm = 3.0
    for axis in ("x", "y", "z", "ph", "th"):
        setattr(dev, axis, _Motor("crl_" + axis, 0.0))
    for i in range(1, 13):
        value = -0.42 if i == 3 else (10.0 if i <= 6 else -10.0)
        setattr(dev, "lens{}".format(i), _Motor("crl_lens{}".format(i), value))
    return dev


def _voltage(prefix):
    dev = _Device()
    dev.name = prefix
    for i in range(beam_snapshot.N_BIMORPH_CH):
        setattr(dev, "ch{}".format(i), Signal(value=float(i), name="{}_ch{}".format(prefix, i)))
        setattr(dev, "ch{}_trg".format(i), Signal(value=float(i), name="{}_trg_write{}".format(prefix, i)))
        setattr(dev, "ch{}_trg_rb".format(i), Signal(value=float(i), name="{}_trg{}".format(prefix, i)))
        setattr(dev, "ch{}_status".format(i), Signal(value="On", name="{}_status{}".format(prefix, i)))

    def read_outputs():
        return [getattr(dev, "ch{}".format(i)).get() for i in range(beam_snapshot.N_BIMORPH_CH)]

    def set_targets(voltages):
        for i, value in enumerate(voltages):
            getattr(dev, "ch{}_trg".format(i)).put(value)
            getattr(dev, "ch{}_trg_rb".format(i)).put(value)
        yield from bps.null()

    def apply_and_wait():
        for i in range(beam_snapshot.N_BIMORPH_CH):
            getattr(dev, "ch{}".format(i)).put(getattr(dev, "ch{}_trg_rb".format(i)).get())
        yield from bps.null()

    dev.read_outputs = read_outputs
    dev.set_targets = set_targets
    dev.apply_and_wait = apply_and_wait
    def move_voltages(voltages, **kwargs):
        yield from dev.set_targets(voltages, **kwargs)
        yield from dev.apply_and_wait(**kwargs)
    dev.move_voltages = move_voltages
    return dev


def _namespace():
    energy = _Device()
    energy.energy = _Device()
    energy.energy.readback = Signal(name="energy_readback", value=10000.0)
    energy.pitch_feedback_disabled = Signal(name="pitch_feedback_disabled", value="0")
    energy.roll_feedback_disabled = Signal(name="roll_feedback_disabled", value="0")
    energy.bragg = _Motor("bragg", 1.0)
    energy.dcmgap = _Motor("dcmgap", 2.0)
    energy.ivugap = _Motor("ivugap", 3.0)
    dcm_config = _Device()
    dcm_config.pitch = _Motor("dcm_pitch", 4.0)
    dcm_config.roll = _Motor("dcm_roll", 5.0)
    xbpm3 = _Device()
    xbpm3.range = Signal(name="xbpm3_range", value=3)
    return {
        "mdsave": {},
        "crl": _crl(),
        "wbs": _slit("wbs"),
        "ssa": _slit("ssa"),
        "eslit": _slit("eslit"),
        "cslit": _slit("cslit"),
        "energy": energy,
        "dcm_config": dcm_config,
        "xbpm3": xbpm3,
        "ph_shutter": Signal(name="ph_shutter", value="Open"),
        "xbpm2_pos": _xbpm("xbpm2"),
        "xbpm3_pos": _xbpm("xbpm3"),
        "hfm": _mirror("hfm"),
        "vfm": _mirror("vfm"),
        "vdm": _mirror("vdm"),
        "hfm_voltage": _voltage("hfm_voltage"),
        "vfm_voltage": _voltage("vfm_voltage"),
    }


def test_beam_snapshot_saves_to_mdsave_and_indexes():
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot(
        "test", note="unit", namespace=ns, store=ns["mdsave"])

    assert snapshot["snapshot_name"] == "test"
    assert len(snapshot["items"]) == 85
    assert "beam_position_snapshots:test" in ns["mdsave"]
    assert ns["mdsave"]["beam_position_snapshots:index"]["test"]["count"] == 85

    names = {item["name"] for item in snapshot["items"]}
    assert "energy.bragg" in names
    assert "xbpm2_pos.x" in names
    assert "hfm_voltage.ch15" in names
    assert "hfmslit.h" not in names
    assert "energy.dcmx" not in names
    assert next(item for item in snapshot["items"] if item["name"] == "wbs.h")["speed"] == 2.5


def test_beam_snapshot_compare_is_dry_run_and_reports_diff():
    ns = _namespace()
    beam_snapshot.save_beam_position_snapshot("test", namespace=ns, store=ns["mdsave"])
    ns["wbs"].h.user_readback.put(10.0)

    rows = beam_snapshot.compare_beam_position_snapshot(
        "test", namespace=ns, store=ns["mdsave"], print_table=False)

    row = next(row for row in rows if row["name"] == "wbs.h")
    assert row["status"] == "would move"
    assert row["current"] == 10.0
    assert row["snapshot"] == 0


def test_beam_snapshot_voltage_diff_is_restorable():
    ns = _namespace()
    beam_snapshot.save_beam_position_snapshot("test", namespace=ns, store=ns["mdsave"])
    ns["vfm_voltage"].ch0.put(99.0)

    rows = beam_snapshot.compare_beam_position_snapshot(
        "test", namespace=ns, store=ns["mdsave"], print_table=False)

    row = next(row for row in rows if row["name"] == "vfm_voltage.ch0")
    assert row["status"] == "would move"


def test_beam_snapshot_restore_defaults_to_dry_run():
    ns = _namespace()
    beam_snapshot.save_beam_position_snapshot("test", namespace=ns, store=ns["mdsave"])
    ns["wbs"].h.user_readback.put(10.0)

    rows = beam_snapshot.restore_beam_position_snapshot(
        "test", namespace=ns, store=ns["mdsave"], names=["wbs.h"], print_table=False)

    assert rows == [
        {
            "name": "wbs.h",
            "group": "slits",
            "target": 0,
            "current": 10.0,
            "units": "mm",
            "status": "would move",
            "delta": -10.0,
        }
    ]


def test_beam_snapshot_restore_moves_selected_motor_when_enabled():
    ns = _namespace()
    RE = RunEngine({})
    beam_snapshot.save_beam_position_snapshot("test", namespace=ns, store=ns["mdsave"])
    ns["wbs"].h.user_readback.put(10.0)
    ns["wbs"].v.user_readback.put(20.0)

    RE(beam_snapshot.restore_beam_position_snapshot(
        "test", namespace=ns, store=ns["mdsave"], names=["wbs.h"], dry_run=False,
        print_table=False))

    assert ns["wbs"].h.user_setpoint.get() == 0
    assert ns["wbs"].v.user_setpoint.get() == 2


@pytest.mark.parametrize("debug", [False, True])
def test_beam_snapshot_restore_moves_selected_bimorph_channel_when_enabled(debug):
    ns = _namespace()
    RE = RunEngine({})
    beam_snapshot.save_beam_position_snapshot("test", namespace=ns, store=ns["mdsave"])
    ns["hfm_voltage"].ch0.put(99.0)
    ns["hfm_voltage"].ch1.put(88.0)
    calls = []
    dev = ns["hfm_voltage"]
    original_stage = dev.set_targets
    original_apply = dev.apply_and_wait

    def stage(targets, **kwargs):
        calls.append(("stage", kwargs))
        yield from original_stage(targets)

    def apply(**kwargs):
        calls.append(("apply", kwargs))
        yield from original_apply()

    dev.set_targets = stage
    dev.apply_and_wait = apply

    RE(beam_snapshot.restore_beam_position_snapshot(
        "test", namespace=ns, store=ns["mdsave"], names=["hfm_voltage.ch0"],
        dry_run=False, print_table=False, bimorph_debug=debug))

    assert ns["hfm_voltage"].ch0.get() == 0.0
    assert ns["hfm_voltage"].ch1.get() == 88.0
    assert ns["hfm_voltage"].ch1_trg_rb.get() == 88.0
    options = {"debug": True} if debug else {}
    assert calls == [("stage", options), ("apply", options)]


@pytest.mark.parametrize("legacy", [False, True])
def test_xbpm_positions_restore_and_compare_including_old_snapshots(legacy):
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot("test", namespace=ns)
    names = ["xbpm2_pos.x", "xbpm2_pos.y", "xbpm3_pos.x", "xbpm3_pos.y"]
    for item in snapshot["items"]:
        if item["name"] in names:
            assert item["restore"] is True
            if legacy:
                item["restore"] = False
            dev, axis = item["name"].split(".")
            motor = getattr(ns[dev], axis)
            motor.user_readback.put(20.0)
            motor.user_setpoint.put(20.0)
    original = copy.deepcopy(snapshot)

    compared = beam_snapshot.compare_beam_position_snapshot(
        snapshot, namespace=ns, print_table=False)
    assert all(row["status"] == "would move" for row in compared if row["name"] in names)
    dry_rows = beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, names=names, groups=["diagnostics"], print_table=False)
    assert {row["name"] for row in dry_rows} == set(names)
    assert all(row["status"] == "would move" for row in dry_rows)

    RE = RunEngine({}, call_returns_result=True)
    result = RE(beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, names=names, groups=["diagnostics"], dry_run=False, print_table=False))
    assert all(row["status"] == "moved" for row in result.plan_result)
    for dev in ("xbpm2_pos", "xbpm3_pos"):
        assert ns[dev].x.user_setpoint.get() == 0
        assert ns[dev].y.user_setpoint.get() == 1
    assert snapshot == original


def test_restore_starts_each_motor_batch_before_waiting_and_keeps_read_only_axes():
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot("test", namespace=ns)
    for item in snapshot["items"]:
        if item["kind"] == "motor":
            dev, axis = item["name"].split(".")
            motor = getattr(ns[dev], axis)
            motor.user_readback.put(50.0)
            motor.user_setpoint.put(50.0)

    messages = []
    RE = RunEngine({}, call_returns_result=True)
    RE.msg_hook = messages.append
    result = RE(beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, dry_run=False, print_table=False))

    # All sets in a batch must precede its wait, and share that wait's group.
    batches = []
    pending = []
    for msg in messages:
        if msg.command == "set":
            pending.append(msg)
        elif msg.command == "wait":
            assert pending
            assert all(move.kwargs["group"] == msg.kwargs["group"] for move in pending)
            batches.append({move.obj.name for move in pending})
            pending = []
    assert not pending
    assert batches == [
        {"pitch_feedback_disabled", "roll_feedback_disabled"},
        {"ph_shutter"},
        {"dcm_pitch", "dcm_roll"},
        {dev + "_" + axis for dev in ("wbs", "ssa", "eslit", "cslit") for axis in ("h", "v")},
        {dev + "_" + axis for dev in ("wbs", "ssa", "eslit", "cslit") for axis in ("hg", "vg")},
        {dev + "_" + axis for dev in ("hfm", "vfm", "vdm") for axis in ("x", "y")},
        {dev + "_th" for dev in ("hfm", "vfm", "vdm")},
        {dev + "_" + axis for dev in ("xbpm2", "xbpm3") for axis in ("x", "y")},
        {"crl_" + axis for axis in ("x", "y", "z", "ph", "th")},
        {"crl_lens{}".format(i) for i in range(1, 13)},
    ]
    rows = {row["name"]: row for row in result.plan_result}
    for item in snapshot["items"]:
        if item["kind"] != "motor":
            continue
        dev, axis = item["name"].split(".")
        if item["restore"]:
            assert getattr(ns[dev], axis).user_setpoint.get() == item["readback"]
            assert rows[item["name"]]["status"] == "moved"
        else:
            assert getattr(ns[dev], axis).user_setpoint.get() == 50.0
            assert rows[item["name"]]["status"] == "skipped read-only"


def test_batched_restore_respects_selection_exclusions_and_tolerance():
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot("test", namespace=ns)
    names = ["wbs.h", "wbs.hg", "ssa.h", "ssa.v", "hfm.x", "xbpm2_pos.x"]
    for name in names:
        dev, axis = name.split(".")
        motor = getattr(ns[dev], axis)
        motor.user_readback.put(50.0)
        motor.user_setpoint.put(50.0)
    ns["ssa"].v.user_readback.put(2.01)
    messages = []
    RE = RunEngine({}, call_returns_result=True)
    RE.msg_hook = messages.append
    result = RE(beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, names=names, groups=["slits", "diagnostics"],
        exclude=["ssa.h"], tolerance=0.1, dry_run=False, print_table=False))

    assert [msg.obj.name for msg in messages if msg.command == "set"] == [
        "pitch_feedback_disabled", "roll_feedback_disabled", "ph_shutter",
        "wbs_h", "wbs_hg", "xbpm2_x"]
    assert sum(msg.command == "wait" for msg in messages) == 5
    rows = {row["name"]: row for row in result.plan_result}
    assert set(rows) == {"wbs.h", "wbs.hg", "ssa.v", "xbpm2_pos.x"}
    assert rows["ssa.v"]["status"] == "already there"


def test_energy_restore_records_harmonic_with_feedback_off_before_gain():
    ns = _namespace()
    en = ns["energy"]
    en.enabledcmgap = Signal(name="enabledcmgap", value=True)
    en.enableivu = Signal(name="enableivu", value=True)
    en.harmonic = Signal(name="harmonic", value=7)
    en.PseudoPosition = SimpleNamespace
    en._harmonic_and_gap = lambda value: (5, 8000.0)
    def forward(pos):
        assert pos.energy == 10000
        assert en.pitch_feedback_disabled.get() == "1"
        assert en.roll_feedback_disabled.get() == "1"
        assert ns["ph_shutter"].get() == "Close"
        return SimpleNamespace(bragg=11.0, dcmgap=12.0, ivugap=8000.0)
    en.forward = forward
    snapshot = beam_snapshot.save_beam_position_snapshot("test", namespace=ns)
    en.energy.readback.put(9000)
    ns["xbpm3"].range.put(4)
    engine = RunEngine({})
    messages = []
    engine.msg_hook = messages.append
    engine(beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, dry_run=False, print_table=False,
        names=["energy.energy", "xbpm3.range"], tolerance=2))
    assert [msg.obj.name for msg in messages if msg.command == "set"] == [
        "pitch_feedback_disabled", "roll_feedback_disabled", "ph_shutter",
        "bragg", "dcmgap", "ivugap", "harmonic", "xbpm3_range"]
    assert en.harmonic.get() == 5
    assert en.ivugap.user_setpoint.get() == 8000
    assert ns["xbpm3"].range.get() == 3  # enum change is not swallowed by tolerance
    assert en.pitch_feedback_disabled.get() == "1"
    assert en.roll_feedback_disabled.get() == "1"
    assert ns["ph_shutter"].get() == "Close"


def test_crl_alignment_is_part_of_full_persisted_beam_snapshot():
    ns = _namespace()
    # An explicitly aligned holder can lie outside the automatic IN tolerance.
    ns["crl"].lens3.user_readback.put(-3.2)
    snapshot = beam_snapshot.save_beam_position_snapshot(
        "good_focus_16keV", crl_inserted=[3], note="best focus", namespace=ns)
    saved = json.loads(json.dumps(ns["mdsave"]["beam_position_snapshots:good_focus_16keV"]))
    assert saved == snapshot
    assert saved["created"] and saved["operator"]
    assert saved["schema_version"] == 3
    items = {item["name"]: item for item in saved["items"]}
    assert {"crl." + axis for axis in ("x", "y", "z", "ph", "th")} <= items.keys()
    assert {"crl.lens{}".format(i) for i in range(1, 13)} <= items.keys()
    assert {"hfm.x", "vfm.th", "vdm.y", "hfm_voltage.ch15", "vfm_voltage.ch15",
            "ssa.h", "ssa.v", "ssa.hg", "ssa.vg", "energy.energy"} <= items.keys()
    alignment = saved["crl_alignment"]
    assert alignment["state_source"] == "operator"
    assert alignment["declared_inserted"] == [3]
    assert alignment["holders"][2] == {"number": 3, "state": "IN", "in_mm": -3.2}
    assert all(h["state"] == "OUT" and h["in_mm"] is None
               for h in alignment["holders"] if h["number"] != 3)
    registry = {item["name"]: item for item in beam_snapshot.beam_snapshot_devices(ns)}
    assert registry["crl.lens3"]["restore"] is True


@pytest.mark.parametrize("inserted, source, state", [
    (None, "readback_zero_tolerance", "IN"), ([], "operator", "OUT"),
])
def test_crl_state_inference_and_explicit_all_out(inserted, source, state):
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot(namespace=ns, crl_inserted=inserted)
    alignment = snapshot["crl_alignment"]
    assert alignment["state_source"] == source
    assert alignment["holders"][2]["state"] == state
    assert alignment["holders"][2]["in_mm"] == (-0.42 if state == "IN" else None)


@pytest.mark.parametrize("inserted", [[0], [13], [3.0], [True], ["3"]])
def test_crl_invalid_holder_numbers_do_not_save(inserted):
    ns = _namespace()
    with pytest.raises(ValueError, match="holder numbers"):
        beam_snapshot.save_beam_position_snapshot(namespace=ns, crl_inserted=inserted)
    assert ns["mdsave"] == {}


def test_crl_failed_readback_is_unknown_and_not_a_restore_target():
    ns = _namespace()
    def fail():
        raise TimeoutError("disconnected")
    ns["crl"].lens3.user_readback.get = fail
    snapshot = beam_snapshot.save_beam_position_snapshot(namespace=ns, crl_inserted=[3])
    assert snapshot["crl_alignment"]["holders"][2] == {
        "number": 3, "state": "UNKNOWN", "in_mm": None}
    assert snapshot["crl_alignment"]["declared_inserted"] == [3]
    rows = beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, names=["crl.lens3"], print_table=False)
    assert rows[0]["status"] == "skipped non-numeric target"


def test_crl_compare_and_filtered_restore_use_measured_in_and_out_positions():
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot(namespace=ns, crl_inserted=[3])
    for axis in ("x", "lens3", "lens7", "lens8"):
        getattr(ns["crl"], axis).user_readback.put(5.0)
        getattr(ns["crl"], axis).user_setpoint.put(5.0)
    ns["hfm"].x.user_readback.put(50.0)
    compared = beam_snapshot.compare_beam_position_snapshot(snapshot, namespace=ns, print_table=False)
    assert next(row for row in compared if row["name"] == "crl.lens3")["snapshot"] == -0.42
    options = dict(namespace=ns, groups=["crl"], exclude=["crl.lens8"], print_table=False)
    preview = beam_snapshot.restore_beam_position_snapshot(snapshot, **options)
    assert ns["crl"].lens3.user_setpoint.get() == 5.0
    assert ns["ph_shutter"].get() == "Open"
    assert {row["name"] for row in preview if row["status"] == "would move"} == {
        "crl.x", "crl.lens3", "crl.lens7"}
    engine = RunEngine({})
    engine(beam_snapshot.restore_beam_position_snapshot(snapshot, dry_run=False, **options))
    assert ns["crl"].x.user_setpoint.get() == 0.0
    assert ns["crl"].lens3.user_setpoint.get() == -0.42
    assert ns["crl"].lens7.user_setpoint.get() == -10.0
    assert ns["crl"].lens8.user_setpoint.get() == 5.0


def test_legacy_snapshot_does_not_generate_crl_moves():
    ns = _namespace()
    snapshot = beam_snapshot.save_beam_position_snapshot(namespace=ns)
    snapshot["schema_version"] = 2
    snapshot.pop("crl_alignment")
    snapshot["items"] = [item for item in snapshot["items"] if item["group"] != "crl"]
    rows = beam_snapshot.compare_beam_position_snapshot(snapshot, namespace=ns, print_table=False)
    assert all(row["status"] == "missing saved" for row in rows if row["group"] == "crl")
    engine = RunEngine({})
    messages = []
    engine.msg_hook = messages.append
    engine(beam_snapshot.restore_beam_position_snapshot(
        snapshot, namespace=ns, dry_run=False, print_table=False))
    assert not any(msg.command == "set" for msg in messages)
