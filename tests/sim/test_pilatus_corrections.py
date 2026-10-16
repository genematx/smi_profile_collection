"""Snapshot corrections on fake areaDetector plugins, including Bluesky events."""
from collections import Counter
from functools import partial
from itertools import combinations, count
from pathlib import Path
import runpy
import sys
from threading import Event, Thread, Timer
from types import ModuleType
from unittest.mock import Mock
import time

import numpy as np
import pytest
from bluesky import RunEngine
from bluesky import plans as bp
from ophyd import Kind, Signal, Staged
from ophyd.sim import FakeEpicsSignal, make_fake_device
from ophyd.status import DeviceStatus
from ophyd.utils import ReadOnlyError

from smi_beamline.devices import _context
from smi_beamline.devices.attenuators import AttenuatorSet, make_attenuator_bank
from smi_beamline.devices.pilatus import (
    Pilatus, SAXS_Detector, WAXS_Detector, hint_pilatus_stats,
)


def state(factor=2.0, energy=10000.0, labels=()):
    return dict(attenuation_factor=factor, transmission=1 / factor,
                energy_eV=energy, inserted=list(labels))


def seed_detector(det):
    det.cam.port_name.sim_put("CAM")
    det.cam.color_mode.sim_put("Mono")
    det.cam.array_size.array_size_x.sim_put(10)
    det.cam.array_size.array_size_y.sim_put(20)
    det.cam.num_images.sim_put(1)
    for n in range(1, 6):
        plugin = getattr(det, f"stats{n}")
        plugin.nd_array_port.sim_put("CAM")
        plugin.total.sim_put(float(n), timestamp=1000.0 + n)
    det.tiff.nd_array_port.sim_put("CAM")
    det.tiff.array_size.height.sim_put(20)
    det.tiff.array_size.width.sim_put(10)
    det.tiff.data_type.sim_put("Int32")


def snapshot_signals(det):
    return [getattr(det, f"stats{n}").total_corrected for n in range(1, 6)] + [
        det.attenuation_factor_used, det.attenuation_energy_eV_used,
        det.attenuation_foils_used,
    ]


@pytest.fixture(params=[SAXS_Detector, WAXS_Detector])
def detector(request, make_fake):
    det = make_fake(request.param, name="det", asset_path="test",
                    attenuation_provider=Mock(return_value=state()))
    seed_detector(det)
    return det


def test_first_read_describe_readonly_and_timestamps(detector, monkeypatch):
    det = detector
    for signal in snapshot_signals(det):
        with pytest.raises(RuntimeError, match="unavailable"):
            signal.get()
        with pytest.raises(RuntimeError, match="unavailable"):
            signal.read()
        for method in (signal.put, signal.set):
            with pytest.raises(ReadOnlyError):
                method(7)
        assert not signal.write_access
        monkeypatch.setattr(signal, "get", Mock(side_effect=AssertionError("describe called get")))
    description = det.describe()
    assert det.attenuation_provider.call_count == 0
    before = time.time()
    result = det.read()
    after = time.time()
    assert set(result) == set(description)
    assert det.attenuation_provider.call_count == 1
    for n in range(1, 6):
        raw = result[f"det_stats{n}_total"]
        corrected = result[f"det_stats{n}_total_corrected"]
        assert corrected == {"value": 2 * raw["value"], "timestamp": raw["timestamp"]}
        assert description[f"det_stats{n}_total_corrected"]["dtype"] == "number"
    for signal in snapshot_signals(det):
        assert description[signal.name]["shape"] == []
        assert signal.read() == {signal.name: result[signal.name]}
    assert description[det.attenuation_foils_used.name]["dtype"] == "string"
    provenance = [result[s.name] for s in snapshot_signals(det)[5:]]
    assert len({r["timestamp"] for r in provenance}) == 1
    assert before <= provenance[0]["timestamp"] <= after


def test_exact_raw_once_and_no_child_recalculation(detector, monkeypatch):
    det = detector
    calls = Counter()
    for n in range(1, 6):
        signal = getattr(det, f"stats{n}").total

        def read(signal=signal, n=n):
            calls[n] += 1
            return {signal.name: {"value": 100 * calls[n] + n, "timestamp": 2000 + n}}

        monkeypatch.setattr(signal, "read", read)
    first = det.read()
    det.attenuation_provider.return_value = state(3, labels=["2_10", "1_2", "2_1"])
    assert det.stats1.total_corrected.get() == 202
    assert det.stats1.total_corrected.read()[det.stats1.total_corrected.name]["value"] == 202
    assert det.attenuation_provider.call_count == 1
    second = det.read()
    assert calls == Counter({n: 2 for n in range(1, 6)})
    assert det.attenuation_provider.call_count == 2
    for result, factor in ((first, 2), (second, 3)):
        for n in range(1, 6):
            assert result[f"det_stats{n}_total_corrected"]["value"] == (
                result[f"det_stats{n}_total"]["value"] * factor)
    assert second[det.attenuation_foils_used.name]["value"] == "1_2,2_1,2_10"


def test_all_selections_preserve_schema_and_unrelated_hints(detector):
    det = detector
    det.stats3.centroid_total.kind = "hinted"
    det.threshold.kind = "hinted"
    unrelated = [det.stats3.centroid_total.name, det.threshold.name]
    configuration = list(det.configuration_attrs)
    keys = set(det.read())
    assert det.hints["fields"] == [det.stats1.total.name, *unrelated]
    for length in range(6):
        for selection in combinations(range(1, 6), length):
            for corrected in (False, True):
                result = hint_pilatus_stats(det, selection, corrected=corrected)
                suffix = "total_corrected" if corrected else "total"
                expected = {getattr(getattr(det, f"stats{n}"), suffix).name for n in selection}
                assert set(result["fields"]) == expected | set(unrelated)
                assert result["stats"] == list(selection)
                assert result["corrected"] is corrected
                assert det.hint_stats(selection, corrected=corrected) == result
                assert set(det.read()) == set(det.describe()) == keys
                assert list(det.configuration_attrs) == configuration
                assert det.tiff.kind & Kind.normal
    assert det.hint_stats([np.int64(5), 1, 5])["stats"] == [1, 5]
    det.set_primary_roi(2)
    assert set(det.hints["fields"]) == {det.stats2.total.name, *unrelated}
    assert set(det.read()) == keys


@pytest.mark.parametrize("selection,corrected", [
    (True, False), ([1, False], True), ([0], False), ([6], False),
    ([1, 2.0], False), ("12", False), (None, False), ([1], 1), ([1], "yes"),
])
def test_invalid_selection_is_transactional(detector, selection, corrected):
    det = detector
    det.hint_stats([2, 4], corrected=True)
    before = [(s.item, s.item.kind) for s in det.walk_signals()]
    with pytest.raises(ValueError):
        det.hint_stats(selection, corrected=corrected)
    assert all(signal.kind == kind for signal, kind in before)
    with pytest.raises(ValueError):
        det.set_primary_roi([1, 2])


def test_iterable_failure_does_not_change_selection(detector):
    def bad_iterable():
        yield 2
        raise RuntimeError("broken selection iterator")

    before = detector.hints
    with pytest.raises(RuntimeError, match="broken selection"):
        detector.hint_stats(bad_iterable())
    assert detector.hints == before


@pytest.mark.parametrize("bad_state", [
    None, {}, {**state(), "attenuation_factor": float("inf")},
    {**state(), "attenuation_factor": 0.5}, {**state(), "transmission": 0},
    {**state(), "transmission": 0.75}, {**state(), "energy_eV": float("nan")},
    {**state(), "energy_eV": 1}, {**state(), "inserted": "1_1"},
    {**state(), "inserted": ["unknown"]}, {**state(), "inserted": ["1_1", "1_1"]},
    {**state(), "attenuation_factor": True},
])
def test_invalid_provider_preserves_last_success(detector, bad_state):
    det = detector
    previous = det.read()
    det.stats1.total.sim_put(99)
    det.attenuation_provider.return_value = bad_state
    with pytest.raises(ValueError):
        det.read()
    for signal in snapshot_signals(det):
        assert signal.read()[signal.name] == previous[signal.name]


def test_failure_before_first_publication_and_recovery(detector):
    det = detector
    det.attenuation_provider = None
    with pytest.raises(RuntimeError, match="no attenuation provider"):
        det.read()
    with pytest.raises(RuntimeError, match="unavailable"):
        det.stats1.total_corrected.read()
    det.attenuation_provider = Mock(side_effect=TimeoutError("source disconnected"))
    with pytest.raises(TimeoutError):
        det.read()
    det.attenuation_provider = lambda: state()
    assert det.read()[det.stats1.total_corrected.name]["value"] == 2


@pytest.mark.parametrize("raw,factor", [(float("nan"), 2), (float("inf"), 2), (1e200, 1e200)])
def test_invalid_raw_or_product_publishes_nothing(detector, raw, factor):
    det = detector
    det.stats5.total.sim_put(raw)
    det.attenuation_provider = lambda: state(factor)
    with pytest.raises(ValueError, match="finite"):
        det.read()
    assert det._correction_snapshot is None


def test_zero_and_negative_raw_totals(detector):
    detector.stats1.total.sim_put(0)
    detector.stats2.total.sim_put(-3)
    reading = detector.read()
    assert reading[detector.stats1.total_corrected.name]["value"] == 0
    assert reading[detector.stats2.total_corrected.name]["value"] == -6


def test_missing_raw_fails_and_helper_restores_it(detector):
    detector.stats4.kind = "omitted"
    with pytest.raises(RuntimeError, match="Missing required raw total"):
        detector.read()
    detector.hint_stats([])
    assert detector.stats4.total.name in detector.read()


def test_recursive_read_rejected_and_lock_recovers(detector):
    detector.attenuation_provider = lambda: detector.read()
    with pytest.raises(RuntimeError, match="recursive detector read"):
        detector.read()
    detector.attenuation_provider = lambda: state()
    detector.read()


def test_concurrent_reads_serialize_publication(detector):
    entered, release = Event(), Event()
    values, errors = [], []

    def provider():
        entered.set()
        assert release.wait(3)
        return state()

    detector.attenuation_provider = Mock(side_effect=provider)

    def read():
        try:
            values.append(detector.read())
        except Exception as exc:
            errors.append(exc)

    first, second = Thread(target=read), Thread(target=read)
    first.start()
    assert entered.wait(3)
    second.start()
    try:
        assert detector.attenuation_provider.call_count == 1
        assert detector._correction_snapshot is None
    finally:
        release.set()
        first.join(3)
        second.join(3)
    assert not errors
    assert len(values) == 2
    assert detector.attenuation_provider.call_count == 2


def test_real_strict_provider_tracks_energy_and_foils(make_fake):
    bank_cls = make_attenuator_bank("CorrectionBank", "FAKE:Fltr:{}", [1, 2])
    bank = make_fake_device(bank_cls)("", name="bank")
    bank.f1.status.sim_put("Open")
    bank.f2.status.sim_put("Not Open")
    energy = [10000.0]
    _context.configure(energy_source=lambda: energy[0])
    att = AttenuatorSet("", name="attenuation", banks=[bank])
    det = make_fake(Pilatus, name="det", asset_path="test",
                    attenuation_provider=partial(att.read_state, strict=True))
    seed_detector(det)
    first = det.read()
    energy[0] = 18000.0
    second = det.read()
    assert second[det.attenuation_factor_used.name]["value"] < first[det.attenuation_factor_used.name]["value"]
    bank.f1.status.sim_put("Not Open")
    third = det.read()
    assert third[det.attenuation_factor_used.name]["value"] == 1
    assert third[det.attenuation_foils_used.name]["value"] == ""
    assert att.attenuation_factor.get() == 1  # provider never refreshed this cache
    assert att.energy_eV.get() == 0
    bank.f2.status.sim_put("Moving")
    with pytest.raises(ValueError, match="Unknown state"):
        det.read()
    assert det.attenuation_factor_used.get() == 1


@pytest.mark.parametrize("plan", ["count", "scan"])
def test_runengine_delayed_acquisition_preserves_tiff_assets_and_hints(make_fake, monkeypatch, plan):
    """Simulate camera completion; exercise real parent read and filestore documents."""
    detectors = []
    energy = Signal(name="scan_energy", value=15000.0)
    for name, cls in (("pil2M", SAXS_Detector), ("pil900KW", WAXS_Detector)):
        det = make_fake(cls, name=name, asset_path="test",
                        attenuation_provider=lambda: state(energy.get() / 5000, energy.get()))
        seed_detector(det)
        det.hint_stats([1, 3], corrected=True)
        # IOC/file setup is simulated; real TIFF generate/read/describe/collect are used.
        def stage(det=det):
            det._staged = Staged.yes
            det.tiff._staged = Staged.yes
            det.tiff._fn = str(det.tiff.reg_root / "simulated")
            det.tiff._generate_resource({"template": "%s%s_%06d.tiff", "filename": "sim",
                                         "frame_per_point": 1})
            det.tiff._point_counter = count()
            return [det]

        def unstage(det=det):
            det._staged = Staged.no
            det.tiff._staged = Staged.no
            return [det]

        frames = count(1)

        def trigger(det=det, frames=frames):
            status = DeviceStatus(det)
            frame = next(frames)

            def done():
                try:
                    for n in range(1, 6):
                        getattr(det, f"stats{n}").total.sim_put(float(10 * frame + n))
                    det.tiff.generate_datum(det._image_name, time.time(), {})
                except Exception as exc:
                    status.set_exception(exc)
                else:
                    status.set_finished()

            Timer(0.02, done).start()
            return status

        monkeypatch.setattr(det, "stage", stage)
        monkeypatch.setattr(det, "unstage", unstage)
        monkeypatch.setattr(det, "trigger", trigger)
        detectors.append(det)
    _context.configure(energy_source=lambda: 10000)
    att = AttenuatorSet("", name="attenuation", banks=[])
    docs = []
    RE = RunEngine({})
    RE.subscribe(lambda name, doc: docs.append((name, doc)))
    if plan == "count":
        RE(bp.count([*detectors, att], num=2))
    else:
        RE(bp.scan([*detectors, att], energy, 10000, 20000, 2))
    descriptor = next(doc for name, doc in docs if name == "descriptor")
    events = [doc for name, doc in docs if name == "event"]
    resources = {doc["uid"] for name, doc in docs if name == "resource"}
    datums = {doc["datum_id"]: doc for name, doc in docs if name == "datum"}
    assert len(events) == 2
    assert len(resources) == 2
    assert len(datums) == 4
    for frame, event in enumerate(events, 1):
        assert set(event["data"]) == set(descriptor["data_keys"])
        for det in detectors:
            factor = 3 if plan == "count" else 2 * frame
            assert event["data"][det.attenuation_factor_used.name] == factor
            assert event["data"][det.attenuation_energy_eV_used.name] == factor * 5000
            for n in range(1, 6):
                assert event["data"][f"{det.name}_stats{n}_total"] == 10 * frame + n
                assert event["data"][f"{det.name}_stats{n}_total_corrected"] == factor * (10 * frame + n)
            assert descriptor["hints"][det.name]["fields"] == [
                det.stats1.total_corrected.name, det.stats3.total_corrected.name]
            datum = datums[event["data"][det._image_name]]
            assert datum["resource"] in resources
            assert datum["datum_kwargs"]["point_number"] == frame - 1
            assert descriptor["data_keys"][det._image_name]["external"] == "FILESTORE:"
    assert "attenuation_attenuation_factor" in events[0]["data"]


def test_actual_instance_setup_and_namespace_export(monkeypatch):
    """Execute startup tuning with fake constructors, not a duplicated configuration."""
    import ophyd
    import paramiko
    from smi_beamline.devices import pilatus
    from smi_beamline.instances import _public_names

    _context.configure(energy_source=lambda: 10000)
    att = AttenuatorSet("", name="attenuation", banks=[])
    provider = Mock(wraps=att.read_state)
    monkeypatch.setattr(att, "read_state", provider)
    dependencies = {
        "waxschamber": {"chamber_pressure": Mock()},
        "shutter": {"shopen": Mock(), "shclose": Mock()},
        "amptek": {"amptek": Mock()},
        "energy": {"energy": Mock()},
        "attenuators": {"attenuation": att},
    }
    for module_name, attributes in dependencies.items():
        full_name = f"smi_beamline.instances.{module_name}"
        module = ModuleType(full_name)
        vars(module).update(attributes)
        monkeypatch.setitem(sys.modules, full_name, module)
    for cls in (SAXS_Detector, WAXS_Detector):
        monkeypatch.setattr(pilatus, cls.__name__, make_fake_device(cls))
    monkeypatch.setattr(ophyd, "EpicsSignal", FakeEpicsSignal)
    monkeypatch.setattr(paramiko, "SSHClient", Mock())
    path = Path(__file__).parents[2] / "src/smi_beamline/instances/pilatus.py"
    namespace = runpy.run_path(str(path))
    module = ModuleType("fake_pilatus_instances")
    vars(module).update(namespace)
    assert "hint_pilatus_stats" in _public_names(module)
    for name, extras in (("pil2M", {"motor"}), ("pil900KW", {"cam", "motors"})):
        det = namespace[name]
        seed_detector(det)
        immediate = {name for name, _ in det._get_components_of_kind(Kind.normal)}
        assert immediate == {"stats1", "stats2", "stats3", "stats4", "stats5", "tiff",
                             "attenuation_factor_used", "attenuation_energy_eV_used",
                             "attenuation_foils_used"} | extras
        assert det.hints["fields"] == [det.stats1.total.name]
        initial = det.read()
        configuration = list(det.configuration_attrs)
        namespace["hint_pilatus_stats"](det, [2, 5], corrected=True)
        assert set(det.read()) == set(initial) == set(det.describe())
        assert list(det.configuration_attrs) == configuration
        assert det.cam.wait_for_plugins in det.cam.stage_sigs or "wait_for_plugins" in det.cam.stage_sigs
    assert all(call.kwargs == {"strict": True} for call in provider.call_args_list)
