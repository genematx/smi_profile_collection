"""Hardware-free commissioning tests. MOVE with attenuator_ab.py."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from bluesky import RunEngine
import bluesky.plan_stubs as bps
from ophyd import Component as Cpt, Device, Signal
from ophyd.status import DeviceStatus

spec = importlib.util.spec_from_file_location("attenuator_ab", Path(__file__).with_name("attenuator_ab.py"))
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


def simple_test(pairs=3):
    return dict(id="al9", energy_eV=8800, a=["1_1", "1_2", "2_8"],
                b=["1_1", "1_2", "2_8", "2_9"], pairs=pairs)


def test_preview_is_hardware_free_and_counts_exposures():
    plan = ab.attenuator_ab_calibration([simple_test()], dry_run=True, exposure_s=5)
    with pytest.raises(StopIteration) as end:
        next(plan)
    assert end.value.value["frames"] == 6
    assert end.value.value["exposure_seconds"] == 30
    assert end.value.value["estimated_seconds"] > 30
    with pytest.raises(ValueError, match="dark_frames must be 0"):
        ab.preview_ab([simple_test()], dark_frames=3)
    with pytest.raises(ValueError, match="outside"):
        ab.preview_ab([dict(simple_test(), a=[])])
    with pytest.raises(ValueError, match="integer"):
        ab.preview_ab([dict(simple_test(), pairs=0)])
    with pytest.raises(ValueError, match="8800–20000"):
        ab.preview_ab([dict(simple_test(), energy_eV=6000)])
    with pytest.raises(ValueError, match="8800–20000"):
        ab.make_ab_tests(energies_eV=(6000,))


def test_default_design_has_two_energy_coverage_and_identifiable_foils():
    tests = ab.make_ab_tests(pairs=2)
    assert {t["energy_eV"] for t in tests} == {8800, 16000, 19500}
    assert all("2_6" not in t["a"] + t["b"] for t in tests)
    counts = {l: 0 for l in ab.ad.FOIL_LAYOUT if l != "2_6"}
    for energy in {t["energy_eV"] for t in tests}:
        subset = [t for t in tests if t["energy_eV"] == energy]
        x = np.array([[int(l in t["b"])-int(l in t["a"]) for l in counts] for t in subset])
        active = np.any(x, axis=0)
        assert np.linalg.matrix_rank(x) == active.sum()
        for label, present in zip(counts, active):
            counts[label] += int(present)
    assert min(counts.values()) >= 2


def test_synthetic_joint_fit_recovers_non_nominal_thickness():
    tests = ab.make_ab_tests(energies_eV=(19500,), pairs=5, excluded_foils=())
    scales = {l: 1 + .01*np.sin(i) for i,l in enumerate(ab.ad.FOIL_LAYOUT)}
    summaries = []
    for t in tests:
        def counts(state):
            return 5e12*np.exp(-sum(ab.ad.foil_optical_depth(l,19500,calibrated=False)*scales[l] for l in state))
        a, b = counts(t["a"]), counts(t["b"])
        summaries.append(ab.summarize_test(t, [(a+10,b+10)]*5, [10]*3))
    results, diagnostics = ab.fit_foils(tests, summaries)
    assert len(results) == 24
    assert diagnostics[0]["rank"] == 24
    for r in results:
        assert r["thickness_scale"] == pytest.approx(scales[r["foil"]], abs=1e-9)
        assert r["thickness_scale_sigma"] > 0
    # A simple unchanged reference cancels even if its actual thickness is unknown.
    t = simple_test()
    s = ab.summarize_test(t, [(100000,76501)]*3, [0]*3)
    results, diagnostics = ab.fit_foils([t], [s])
    assert [r["foil"] for r in results] == ["2_9"]
    assert "1_2" in diagnostics[0]["unidentifiable"]


def test_repeat_scatter_and_shared_dark_uncertainty():
    t = simple_test()
    quiet = ab.summarize_test(t, [(10000,5000)]*3, [100,100,100])
    noisy = ab.summarize_test(t, [(10000,4900),(10000,5000),(10000,5100)], [100,100,100])
    assert noisy["independent_variance"] > quiet["independent_variance"]
    assert quiet["dark_gradient"] != 0
    assert quiet["delta_optical_depth_sigma"]**2 > quiet["independent_variance"]
    with pytest.raises(RuntimeError, match="above measured dark"):
        ab.summarize_test(t, [(100,50)], [100]*3)


def signal(value=0, name="signal"):
    return Signal(value=value, name=name)


class ShutterButton(Signal):
    """IOC command that resets immediately but acknowledges the put."""

    def put(self, value, *, callback=None, **kwargs):
        super().put(value)
        super().put(0)
        if callback is not None:
            callback()


class Bank(Device):
    def __init__(self, prefix, **kwargs):
        super().__init__("", **kwargs)
        self.bank_prefix = prefix
        for i in range(1,13):
            setattr(self, f"f{i}", SimpleNamespace(status=signal("Not Open", f"{prefix}_{i}"),
                                                 open_val="Open", close_val="Not Open"))

    def set(self, wanted):
        for i in range(1,13):
            getattr(self,f"f{i}").status.put("Open" if f"f{i}" in wanted else "Not Open")
        status = DeviceStatus(self)
        status.set_finished()
        return status


class Camera(Device):
    cam_energy = Cpt(Signal, value=6.)
    threshold_energy = Cpt(Signal, value=3.)
    gain_menu = Cpt(Signal, value=2)
    threshold_apply = Cpt(Signal, value=0)
    energyset = Cpt(Signal, value=6.)
    detector_state = Cpt(Signal, value=0)
    acquire_time = Cpt(Signal, value=1.)
    acquire_period = Cpt(Signal, value=1.01)
    num_images = Cpt(Signal, value=1)
    image_mode = Cpt(Signal, value=0)
    trigger_mode = Cpt(Signal, value=0)
    array_counter = Cpt(Signal, value=0)
    port_name = Cpt(Signal, value="CAM")
    class ArraySize(Device):
        array_size_x = Cpt(Signal,value=1475)
        array_size_y = Cpt(Signal,value=1679)
    array_size = Cpt(ArraySize,"")


class XY(Device):
    x = Cpt(Signal,value=1)
    y = Cpt(Signal,value=1)


class MinXY(Device):
    min_x = Cpt(Signal,value=500)
    min_y = Cpt(Signal,value=500)


class Stats(Device):
    total = Cpt(Signal, value=0.)
    max_value = Cpt(Signal, value=0.)
    unique_id = Cpt(Signal, value=0)
    port_name = Cpt(Signal, value="ROI1")
    nd_array_port = Cpt(Signal, value="CAM")
    enable = Cpt(Signal, value=1)
    compute_statistics = Cpt(Signal, value=1)
    blocking_callbacks = Cpt(Signal, value=1)
    compute_centroid = Cpt(Signal,value=0)
    centroid_threshold = Cpt(Signal,value=0.)
    centroid = Cpt(XY,"")
    sigma_x = Cpt(Signal,value=3.)
    sigma_y = Cpt(Signal,value=2.)
    sigma_xy = Cpt(Signal,value=.1)
    min_xyz = Cpt(MinXY,"")
    size = Cpt(XY,"")
    bin_ = Cpt(XY,"")
    reverse = Cpt(XY,"")
    roi_enable = Cpt(XY,"")
    enable_scale = Cpt(Signal,value=0)


class Detector(Device):
    cam = Cpt(Camera, "")
    stats1 = Cpt(Stats, "")
    stats5 = Cpt(Stats, "")
    stats2 = Cpt(Stats, "")
    stats3 = Cpt(Stats, "")
    roi1 = Cpt(Stats, "")
    roi2 = Cpt(Stats, "")
    roi3 = Cpt(Stats, "")
    energy_read = Cpt(Signal, value=6.)
    threshold_read = Cpt(Signal, value=3.)
    gain_read = Cpt(Signal, value=2)

    @property
    def cam_energy(self):
        return self.cam.cam_energy

    @property
    def threshold(self):
        return self.cam.threshold_energy

    @property
    def gain(self):
        return self.cam.gain_menu

    @property
    def apply(self):
        return self.cam.threshold_apply

    def trigger(self):
        s = DeviceStatus(self)
        assert self.shutter.status_pv.get() == 7
        # Hardware exposure output owns opening/closing; no plan open command.
        self.shutter.status_pv.put(0)
        is_open = self.shutter.status_pv.get() == 0
        if self.fail_trigger and is_open:
            self.shutter.status_pv.put(7)
            s.set_exception(RuntimeError("simulated trigger failure"))
            return s
        inserted = [f"{bank.bank_prefix}_{i}" for bank in self.banks for i in range(1,13)
                    if getattr(bank,f"f{i}").status.get() == "Open"]
        counts = 0.
        if is_open:
            counts += 1e12*self.cam.acquire_time.get()*ab.ad.transmission(inserted,self.energy_read.get()*1000)
        self.stats1.total.put(counts)
        self.stats2.total.put(counts*.002)
        self.stats3.total.put(counts*.003)
        self.stats1.centroid.x.put(self.roi1.size.x.get()/2)
        self.stats1.centroid.y.put(self.roi1.size.y.get()/2)
        self.stats1.sigma_x.put(4. if "2_9" in inserted else 3.)
        self.stats5.max_value.put(self.cam.acquire_time.get()*2e6 if self.saturate and is_open else counts/100)
        uid = self.cam.array_counter.get()+1
        self.cam.array_counter.put(uid)
        if not self.stale:
            self.stats1.unique_id.put(uid)
            self.stats5.unique_id.put(uid)
            if not getattr(self,"stale_side",False):
                self.stats2.unique_id.put(uid)
            self.stats3.unique_id.put(uid)
        self.shutter.status_pv.put(7)
        s.set_finished()
        return s

    def restore_beamstop(self):
        assert self.shutter.status_pv.get() == 7
        self.restored = True
        yield from bps.null()


@pytest.fixture
def hardware():
    shutter = SimpleNamespace(open_cpt=ShutterButton(name="open", value=0),
                              close_cpt=ShutterButton(name="close", value=0),
                              status_pv=signal(7,"shutter_status"))
    shutter.open_cpt.subscribe(lambda **kw: shutter.status_pv.put(0), run=False)
    shutter.close_cpt.subscribe(lambda **kw: shutter.status_pv.put(7), run=False)
    banks = [Bank("1",name="bank1"),Bank("2",name="bank2")]
    detector = Detector("",name="pil2M")
    detector.shutter, detector.banks = shutter,banks
    detector.fail_trigger = detector.saturate = detector.stale = False
    detector.restored = False
    # RunEngine needs a readable energy object, plus the real nested readback API.
    class Energy(Device):
        energy = Cpt(Signal, value=6000)
    energy = Energy("",name="energy")
    energy.energy.readback = energy.energy

    def move(en):
        assert shutter.status_pv.get() == 7
        yield from bps.mv(energy.energy,en)

    def sensitivity_readbacks(**kwargs):
        detector.energy_read.put(detector.cam.cam_energy.get())
        detector.threshold_read.put(detector.cam.threshold_energy.get())
        detector.gain_read.put(detector.cam.gain_menu.get())
    detector.cam.threshold_apply.subscribe(sensitivity_readbacks,run=False)

    def alignment(**kw):
        assert shutter.status_pv.get() == 7
        yield from bps.null()

    smi = SimpleNamespace(modeAlignment=alignment,setDirectBeamROI=alignment)
    detector.roi1.size.x.put(48)
    detector.roi1.size.y.put(12)
    kwargs = dict(detector=detector,energy=energy,attenuators1=banks[0],attenuators2=banks[1],
                  fs=shutter,smi=smi,tracked_energy_move=move,sensitivity_wait_s=0,foil_settle_s=0)
    return detector,shutter,kwargs


def test_run_one_uid_streams_order_results_and_cleanup(hardware, capsys):
    detector, shutter, kwargs = hardware
    docs, messages = [], []
    re = RunEngine({},call_returns_result=True)
    re.subscribe(lambda name,doc: docs.append((name,doc)))
    re.msg_hook = lambda msg: messages.append(msg)
    result = re(ab.attenuator_ab_calibration([simple_test()], **kwargs)).plan_result
    assert len([d for n,d in docs if n=="start"]) == 1
    assert [d for n,d in docs if n=="stop"][0]["exit_status"] == "success"
    assert result["uid"] == [d for n,d in docs if n=="start"][0]["uid"]
    streams = {d["uid"]:d["name"] for n,d in docs if n=="descriptor"}
    events = [d for n,d in docs if n=="event" and streams[d["descriptor"]]=="primary"]
    assert [e["data"]["ab_state"] for e in events] == list("ABBAAB")
    assert len(result["foil_summary"]) == 1
    assert result["foil_summary"][0]["foil"] == "2_9"
    assert result["foil_summary"][0]["thickness_scale"] == pytest.approx(
        ab.ad.effective_thickness_um("2_9")/ab.ad.nominal_thickness_um("2_9"))
    assert shutter.status_pv.get() == 7 and detector.restored
    applies = [m for m in messages if m.command=="set" and m.obj is detector.cam.threshold_apply]
    assert len(applies) == 2
    assert len(result["shape_summary"]) == 1
    assert result["shape_summary"][0]["sigma_x_px_variance_delta"] == pytest.approx(7)
    assert "shape_sigma_x_px" in events[0]["data"]
    assert detector.stats1.compute_centroid.get() == 1
    assert detector.roi1.size.x.get() == 40
    assert detector.roi2.min_xyz.min_x.get()+128 < detector.roi1.min_xyz.min_x.get()
    assert detector.roi3.min_xyz.min_x.get() > detector.roi1.min_xyz.min_x.get()+40
    output = capsys.readouterr().out
    steps = ["opening run; waiting for initial baseline", "initial baseline complete",
             "checking Pilatus idle", "staging Pilatus and file plugins",
             "detector staging complete", "starting alignment geometry",
             "alignment complete", "tracked energy move to 8800",
             "sensitivity 8.8 keV: attempt 1/3", "waiting 0 s for sensitivity",
             "sensitivity 8.8 keV: attempt 2/3", "placing direct-beam ROI",
             "starting test 1/1", "pair 1/3, state A",
             "moving bank 1", "moving bank 2", "requested stack confirmed",
             "triggering with detector-controlled shutter",
             "fitting completed tests", "unstaging Pilatus", "detector unstaging complete",
             "cleanup: closing", "cleanup: restoring", "run closed:"]
    cursor = 0
    for step in steps:
        cursor = output.index(step, cursor) + len(step)


@pytest.mark.parametrize("failure", ["saturate", "fail_trigger"])
def test_failure_closes_shutter_restores_beamstop_and_fails_run(hardware,failure):
    detector,shutter,kwargs = hardware
    setattr(detector,failure,True)
    docs = []
    re = RunEngine({})
    re.subscribe(lambda n,d: docs.append((n,d)))
    with pytest.raises(Exception):
        re(ab.attenuator_ab_calibration([simple_test()],**kwargs))
    assert shutter.status_pv.get() == 7 and detector.restored
    assert [d for n,d in docs if n=="stop"][0]["exit_status"] == "fail"
    if failure == "saturate":
        assert any(d["data"].get("ab_saturated") for n,d in docs if n=="event")


def test_sensitivity_waits_reapplies_and_fails_unconfirmed(hardware):
    detector,_,_ = hardware
    messages = []
    re = RunEngine({})
    re.msg_hook = lambda msg: messages.append(msg)
    # Simulate waits without sleeping; RunEngine still executes and checks writes.
    from bluesky.preprocessors import plan_mutator
    def skip_sleep(msg):
        if msg.command == "sleep":
            messages.append(msg)
            return bps.null(), None
        return None,None
    re(plan_mutator(ab._sensitivity(detector,6000),skip_sleep))
    assert len([m for m in messages if m.command=="sleep" and m.args==(30,)]) == 2
    detector.cam.threshold_apply.unsubscribe_all()
    detector.energy_read.put(12)
    with pytest.raises(RuntimeError,match="failed to confirm"):
        re(ab._sensitivity(detector,6000,0))


def test_multiple_energies_one_run_reapplies_each_time(hardware):
    detector,shutter,kwargs = hardware
    t2 = dict(id="al9_high", energy_eV=19500, a=["1_2", "1_3", "1_6", "2_11"],
              b=["1_2", "1_3", "1_6", "2_11", "2_9"], pairs=2)
    docs, messages = [],[]
    re = RunEngine({},call_returns_result=True)
    re.subscribe(lambda n,d: docs.append((n,d)))
    re.msg_hook = lambda m: messages.append(m)
    result = re(ab.attenuator_ab_calibration([simple_test(2),t2],**kwargs)).plan_result
    assert len([d for n,d in docs if n=="start"]) == 1
    assert len(result["foil_summary"]) == 2
    assert {r["energy_eV"] for r in result["foil_summary"]} == {8800, 19500}
    assert all(r["thickness_scale"] == pytest.approx(
        ab.ad.effective_thickness_um(r["foil"])/ab.ad.nominal_thickness_um(r["foil"]))
        for r in result["foil_summary"])
    assert len([m for m in messages if m.command=="set" and m.obj is detector.cam.threshold_apply]) == 4
    stage_index = next(i for i,m in enumerate(messages) if m.command in ("stage","stage_all"))
    assert any(m.command=="set" and m.obj is detector.cam.num_images for m in messages[:stage_index])
    assert shutter.status_pv.get() == 7 and detector.restored


@pytest.mark.parametrize("stale_channel",["stale","stale_side"])
def test_stale_stats_fail_closed(hardware,monkeypatch,stale_channel):
    detector,shutter,kwargs = hardware
    setattr(detector,stale_channel,True)
    original = ab._poll
    def quick_poll(signal,predicate,**kw):
        return (yield from original(signal,predicate,timeout=.001,interval=.001,
                                     description=kw.get("description","readback")))
    monkeypatch.setattr(ab,"_poll",quick_poll)
    with pytest.raises(RuntimeError,match="fresh statistics"):
        RunEngine({})(ab.attenuator_ab_calibration([simple_test()],**kwargs))
    assert shutter.status_pv.get() == 7 and detector.restored


def test_roi_bounds_and_nonoverlap():
    rects = ab.beam_roi_layout((500,600),(1475,1679))
    assert rects == [(480,580,40,40),(336,536,128,128),(536,536,128,128)]
    with pytest.raises(ValueError,match="bounds"):
        ab.beam_roi_layout((100,100),(1475,1679))


def test_shape_normalization_rejects_flux_change_as_diffuse_signal():
    t = simple_test()
    def frame(core,left,right,sigma=3.):
        return dict(raw_counts=core,left_counts=left,right_counts=right,shape_valid=True,
                    centroid_x_px=500.,centroid_y_px=600.,sigma_x_px=sigma,sigma_y_px=2.,sigma_xy_px2=.1)
    a = frame(100000,1000,2000)
    b = frame(50000,500,1000,4.)
    dark = [frame(0,0,0)]*3
    summary = ab.summarize_shape(t,[(a,b)]*3,dark,dict(left=100,right=100))
    assert summary["left_per_pixel_per_core_delta"] == pytest.approx(0)
    assert summary["right_per_pixel_per_core_delta"] == pytest.approx(0)
    assert summary["left_per_pixel_per_core_delta_sem"] > 0
    assert summary["sigma_x_px_variance_delta"] == pytest.approx(7)
    b["left_counts"] = 1000
    excess = ab.summarize_shape(t,[(a,b)]*3,dark,dict(left=100,right=100))
    assert excess["left_per_pixel_per_core_delta"] > 0
    single = ab.summarize_shape(t,[(a,b)],dark,dict(left=100,right=100))
    assert not single["moment_sem_valid"]
    assert single["sigma_x_px_delta_sem"] == -1


def test_shape_optional_and_geometry_failure_closed(hardware):
    detector,shutter,kwargs = hardware
    re = RunEngine({},call_returns_result=True)
    result = re(ab.attenuator_ab_calibration([simple_test(1)],beam_shape=False,**kwargs)).plan_result
    assert result["shape_summary"] == []
    detector.roi1.min_xyz.min_x.put(0)
    with pytest.raises(ValueError,match="bounds"):
        re(ab.attenuator_ab_calibration([simple_test(1)],**kwargs))
    assert shutter.status_pv.get() == 7


@pytest.mark.parametrize("failure", ["status", "readback"])
def test_stuck_foil_skips_partial_test_and_continues(hardware, monkeypatch, capsys, failure):
    detector, shutter, kwargs = hardware
    bank = kwargs["attenuators2"]
    original = bank.set
    moves = 0

    def stuck(wanted):
        nonlocal moves
        assert shutter.status_pv.get() == 7
        moves += 1
        # One complete pair succeeds; then f9 refuses to retract in BA order.
        if moves >= 4 and bank.f9.status.get() == "Open" and "f9" not in wanted:
            original(list(wanted) + ["f9"])
            status = DeviceStatus(bank)
            if failure == "status":
                status.set_exception(TimeoutError("2_9 refuses to retract"))
            else:
                status.set_finished()  # a lying status must still not allow exposure
            return status
        return original(wanted)

    monkeypatch.setattr(bank, "set", stuck)
    # This next test can run with f9 remaining inserted in both states.
    good = dict(id="al18", energy_eV=8800, a=simple_test()["b"],
                b=simple_test()["b"] + ["2_10"], pairs=2)
    docs = []
    re = RunEngine({}, call_returns_result=True)
    re.subscribe(lambda n, d: docs.append((n, d)))
    result = re(ab.attenuator_ab_calibration([simple_test(), good], **kwargs)).plan_result
    skip, = result["skipped_tests"]
    assert skip["test_id"] == "al9" and skip["completed_pairs"] == 1
    assert skip["pair"] == 1 and skip["state"] == "A"
    assert json.loads(skip["actual_states_json"])["2_9"] == "Open"
    assert [s["test_id"] for s in result["ab_summary"]] == ["al18"]
    assert [s["test_id"] for s in result["shape_summary"]] == ["al18"]
    assert [r["foil"] for r in result["foil_summary"]] == ["2_10"]
    assert "2_9" in result["fit_diagnostics"][0]["unidentifiable"]
    streams = {d["uid"]: d["name"] for n, d in docs if n == "descriptor"}
    events = [d["data"] for n, d in docs if n == "event" and streams[d["descriptor"]] == "primary"]
    assert [d["ab_state"] for d in events if d["ab_test_id"] == "al9"] == list("ABB")
    assert any(n == "event" and d["data"].get("skip_test_id") == "al9" for n, d in docs)
    assert [d for n, d in docs if n == "stop"][0]["exit_status"] == "success"
    assert shutter.status_pv.get() == 7 and detector.restored
    assert "1/2 tests completed; 1 skipped" in capsys.readouterr().out


def test_all_tests_skipped_reports_zero_rank_and_continues_energy(hardware, monkeypatch):
    detector, shutter, kwargs = hardware
    bank = kwargs["attenuators1"]

    def stuck(wanted):
        assert shutter.status_pv.get() == 7
        status = DeviceStatus(bank)
        status.set_exception(TimeoutError("bank 1 stuck"))
        return status

    monkeypatch.setattr(bank, "set", stuck)
    high = dict(id="high", energy_eV=19500, a=["1_2", "1_3", "1_6", "2_11"],
                b=["1_2", "1_3", "1_6", "2_11", "2_9"], pairs=1)
    docs = []
    re = RunEngine({}, call_returns_result=True)
    re.subscribe(lambda n, d: docs.append((n, d)))
    result = re(ab.attenuator_ab_calibration([simple_test(), high], **kwargs)).plan_result
    assert len(result["skipped_tests"]) == 2
    assert result["ab_summary"] == result["foil_summary"] == []
    assert len(result["fit_diagnostics"]) == 2
    assert all(d["rank"] == d["equations"] == 0 and len(d["unidentifiable"]) == 24
               for d in result["fit_diagnostics"])
    assert not any(n == "event" and d["data"].get("ab_state") in ("A", "B") for n, d in docs)
    assert shutter.status_pv.get() == 7 and detector.restored


def test_bank_failure_waits_for_all_children_before_next_move(hardware, monkeypatch):
    import threading
    from ophyd.status import Status

    _, shutter, kwargs = hardware
    bank = kwargs["attenuators1"]
    original = bank.set
    finished = threading.Event()
    calls = 0

    def delayed(wanted):
        nonlocal calls
        calls += 1
        if calls > 1:
            assert finished.is_set()
            return original(wanted)
        failed, pending = Status(), Status()
        combined = failed & pending
        failed.set_exception(TimeoutError("first foil stuck"))

        def finish():
            assert shutter.status_pv.get() == 7
            finished.set()
            pending.set_finished()

        threading.Timer(.05, finish).start()
        return combined

    monkeypatch.setattr(bank, "set", delayed)
    result = RunEngine({}, call_returns_result=True)(ab.attenuator_ab_calibration(
        [simple_test(1), dict(simple_test(1), id="retry")], **kwargs)).plan_result
    assert len(result["skipped_tests"]) == len(result["ab_summary"]) == 1
    assert result["ab_summary"][0]["test_id"] == "retry"


def test_shutter_failure_is_not_treated_as_a_skipped_foil(hardware, monkeypatch):
    _, shutter, kwargs = hardware
    original = ab._fast_shutter

    def fail_open(fs, opened):
        if not opened:
            raise RuntimeError("shutter failed")
        yield from original(fs, opened)

    monkeypatch.setattr(ab, "_fast_shutter", fail_open)
    docs = []
    re = RunEngine({})
    re.subscribe(lambda n, d: docs.append((n, d)))
    with pytest.raises(RuntimeError, match="shutter failed"):
        re(ab.attenuator_ab_calibration([simple_test()], **kwargs))
    assert not any(n == "event" and "skip_test_id" in d["data"] for n, d in docs)
    assert [d for n, d in docs if n == "stop"][0]["exit_status"] == "fail"
    assert shutter.status_pv.get() == 7


def test_unfinished_motion_is_fatal_instead_of_starting_next_test(hardware, monkeypatch):
    from bluesky import FailedStatus
    from ophyd.status import Status

    detector, shutter, kwargs = hardware
    pending = Status()
    calls = []

    def never_finishes(wanted):
        calls.append(wanted)
        return pending

    monkeypatch.setattr(kwargs["attenuators1"], "set", never_finishes)
    monkeypatch.setattr(ab._BankMove, "completion_timeout", .02)
    try:
        with pytest.raises(FailedStatus):
            RunEngine({})(ab.attenuator_ab_calibration(
                [simple_test(1), dict(simple_test(1), id="next")], **kwargs))
        assert len(calls) == 1
        assert shutter.status_pv.get() == 7 and detector.restored
    finally:
        pending.set_finished()


def test_shutter_already_closed_does_not_write_command(hardware, monkeypatch):
    _, shutter, _ = hardware

    def unexpected_put(*args, **kwargs):
        pytest.fail("Already-closed shutter should not receive a command")

    monkeypatch.setattr(shutter.close_cpt, "put", unexpected_put)
    RunEngine({})(ab._fast_shutter(shutter, False))
    assert shutter.status_pv.get() == 7


def test_shutter_self_resetting_buttons_use_put_completion(hardware, monkeypatch):
    _, shutter, _ = hardware

    def forbidden_set(*args, **kwargs):
        pytest.fail("Do not wait for a command button to latch at 1")

    monkeypatch.setattr(shutter.open_cpt, "set", forbidden_set)
    monkeypatch.setattr(shutter.close_cpt, "set", forbidden_set)
    re = RunEngine({})
    re(ab._fast_shutter(shutter, True))
    assert shutter.status_pv.get() == 0 and shutter.open_cpt.get() == 0
    re(ab._fast_shutter(shutter, False))
    assert shutter.status_pv.get() == 7 and shutter.close_cpt.get() == 0


def test_shutter_put_acknowledgement_does_not_replace_state_confirmation(hardware, monkeypatch):
    _, shutter, _ = hardware
    shutter.open_cpt.unsubscribe_all()
    original = ab._poll

    def quick_poll(signal, predicate, **kwargs):
        return (yield from original(signal, predicate, timeout=.001, interval=.001,
                                    description=kwargs["description"]))

    monkeypatch.setattr(ab, "_poll", quick_poll)
    with pytest.raises(RuntimeError, match="fast shutter open did not confirm"):
        RunEngine({})(ab._fast_shutter(shutter, True))


def test_disconnected_gain_readback_falls_back_and_records_source(hardware, monkeypatch):
    from ophyd.utils import DisconnectedError

    detector, _, kwargs = hardware

    def disconnected():
        raise DisconnectedError("gain RBV is not connected")

    monkeypatch.setattr(detector.gain_read, "read", disconnected)
    # Parent detector.read would also read this simulated component, unlike the
    # live profile's curated read_attrs. Exercise the fallback through a whole run.
    detector.read_attrs = [attr for attr in detector.read_attrs if attr != "gain_read"]
    docs = []
    re = RunEngine({}, call_returns_result=True)
    re.subscribe(lambda n, d: docs.append((n, d)))
    result = re(ab.attenuator_ab_calibration([simple_test(1)], **kwargs)).plan_result
    assert len(result["ab_summary"]) == 1
    settings, = [d["data"] for n, d in docs if n == "event" and "sensitivity_gain_readback_confirmed" in d["data"]]
    assert not settings["sensitivity_gain_readback_confirmed"]
    assert settings["sensitivity_gain_confirmation_source"] == detector.gain.name
    assert settings["sensitivity_gain_observed"] == 1
    assert settings["sensitivity_energy_readback_keV"] == 8.8


def test_connected_wrong_gain_still_fails_confirmation(hardware, monkeypatch):
    detector, _, _ = hardware
    monkeypatch.setattr(detector.gain_read, "read", lambda: {
        detector.gain_read.name: {"value": 3, "timestamp": 0}})
    with pytest.raises(RuntimeError, match="sensitivity failed to confirm"):
        RunEngine({})(ab._sensitivity(detector, 8800, wait_s=0))


@pytest.mark.parametrize("side", [-5., 0., float("nan")])
def test_no_signal_side_roi_does_not_abort_and_metadata_not_hinted(hardware, monkeypatch, side):
    detector, shutter, kwargs = hardware
    original = detector.trigger

    def trigger():
        result = original()
        detector.stats2.total.put(side)
        detector.stats1.sigma_x.put(-1.)
        return result

    monkeypatch.setattr(detector, "trigger", trigger)
    def forbidden_open(*args, **kwargs):
        pytest.fail("Exposure shutter belongs to detector")
    monkeypatch.setattr(shutter.open_cpt, "put", forbidden_open)
    docs = []
    re = RunEngine({}, call_returns_result=True)
    re.subscribe(lambda n, d: docs.append((n, d)))
    result = re(ab.attenuator_ab_calibration([simple_test(2)], **kwargs)).plan_result
    assert len(result["ab_summary"]) == 1
    shape, = result["shape_summary"]
    assert not shape["moments_valid"]
    assert shape["left_normalized_valid"] == bool(np.isfinite(side))
    if side < 0:
        assert not shape["left_poisson_valid"]
        assert shape["left_per_pixel_per_core_a"] < 0
        assert shape["left_sem_valid"]
    descriptors = [d for n, d in docs if n == "descriptor"]
    assert "dark" not in [d["name"] for d in descriptors]
    settings = next(d for d in descriptors if d["name"] == "detector_settings")
    assert all(h["fields"] == [] for h in settings["hints"].values())
    primary = next(d for d in descriptors if d["name"] == "primary")
    assert primary["hints"]["ab_raw_counts"]["fields"] == ["ab_raw_counts"]


def test_zero_core_is_saved_and_skipped_not_fitted(hardware, monkeypatch):
    detector, _, kwargs = hardware
    original = detector.trigger
    def trigger():
        result = original()
        detector.stats1.total.put(0)
        return result
    monkeypatch.setattr(detector, "trigger", trigger)
    result = RunEngine({}, call_returns_result=True)(ab.attenuator_ab_calibration(
        [simple_test(2)], **kwargs)).plan_result
    assert result["ab_summary"] == result["foil_summary"] == []
    assert result["skipped_tests"][0]["failure_type"] == "insufficient_signal"
    assert result["skipped_tests"][0]["completed_pairs"] == 2


def test_excluded_foil_rejected_in_old_tests_and_alignment_selector_bypassed(hardware):
    _, _, kwargs = hardware
    old = dict(simple_test(), b=simple_test()["b"] + ["2_6"])
    with pytest.raises(ValueError, match="excluded foils.*regenerate"):
        ab.preview_ab([old])
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        ab.make_ab_tests(excluded_foils=("2f6",))

    class AutomaticAttenuation:
        name = "attenuation"
        def set(self, value):
            pytest.fail("Alignment must not use the unrestricted stack selector")

    def alignment(**kwargs):
        yield from bps.abs_set(AutomaticAttenuation(), 1e6, wait=True)

    kwargs["smi"].modeAlignment = alignment
    docs = []
    re = RunEngine({}, call_returns_result=True)
    re.subscribe(lambda n, d: docs.append((n, d)))
    result = re(ab.attenuator_ab_calibration([simple_test(1)], **kwargs)).plan_result
    assert len(result["ab_summary"]) == 1
    assert next(d for n, d in docs if n == "start")["excluded_foils"] == ["2_6"]


@pytest.mark.parametrize("energies", [(16000, 19500), (16500, 17000)])
def test_targeted_followup_identifies_only_targets_with_reference_cancellation(energies):
    tests = ab.make_followup_tests(energies_eV=energies)
    assert len(tests) == 6
    report = ab.preview_ab(tests, exposure_s=10, excluded_foils=())
    assert report["frames"] == 24
    summaries = []
    for t in tests:
        assert set(t["b"]) - set(t["a"]) in ({"2_3"}, {"2_4"}, {"2_6"})
        assert set(t["a"]) < set(t["b"])
        assert 1e-9 <= t["modeled_b"] <= t["modeled_a"] <= 1e-6
        a, b = t["modeled_a"]*1e13, t["modeled_b"]*1e13
        summaries.append(ab.summarize_test(t, [(a,b)]*2, []))
    fitted, diag = ab.fit_foils(tests, summaries)
    assert len(fitted) == 6
    assert all(d["rank"] == 3 for d in diag)
    assert all(r["foil"] in ("2_3", "2_4", "2_6") for r in fitted)
    assert all(r["thickness_scale"] == pytest.approx(
        ab.ad.effective_thickness_um(r["foil"])/ab.ad.nominal_thickness_um(r["foil"])) for r in fitted)
    with pytest.raises(ValueError, match="reference foil"):
        ab.make_followup_tests(targets=("1_3",))
