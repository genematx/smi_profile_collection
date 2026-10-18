"""Hardware-free commissioning tests. MOVE with attenuator_ab.py."""
import importlib.util
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
    return dict(id="al9", energy_eV=6000, a=["1_2"], b=["1_2", "2_9"], pairs=pairs)


def test_preview_is_hardware_free_and_counts_exposures():
    plan = ab.attenuator_ab_calibration([simple_test()], dry_run=True, exposure_s=5)
    with pytest.raises(StopIteration) as end:
        next(plan)
    assert end.value.value["frames"] == 9
    assert end.value.value["exposure_seconds"] == 45
    assert end.value.value["estimated_seconds"] > 45
    with pytest.raises(ValueError, match="outside"):
        ab.preview_ab([dict(simple_test(), a=[])])
    with pytest.raises(ValueError, match="integer"):
        ab.preview_ab([dict(simple_test(), pairs=0)])


def test_default_design_has_two_energy_coverage_and_identifiable_foils():
    tests = ab.make_ab_tests(pairs=2)
    counts = {l: 0 for l in ab.ad.FOIL_LAYOUT}
    for energy in {t["energy_eV"] for t in tests}:
        subset = [t for t in tests if t["energy_eV"] == energy]
        x = np.array([[int(l in t["b"])-int(l in t["a"]) for l in counts] for t in subset])
        active = np.any(x, axis=0)
        assert np.linalg.matrix_rank(x) == active.sum()
        for label, present in zip(counts, active):
            counts[label] += int(present)
    assert min(counts.values()) >= 2


def test_synthetic_joint_fit_recovers_non_nominal_thickness():
    tests = ab.make_ab_tests(energies_eV=(19500,), pairs=5)
    scales = {l: 1 + .01*np.sin(i) for i,l in enumerate(ab.ad.FOIL_LAYOUT)}
    summaries = []
    for t in tests:
        def counts(state):
            return 5e12*np.exp(-sum(ab.ad.foil_optical_depth(l,19500)*scales[l] for l in state))
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
        is_open = self.shutter.status_pv.get() == 0
        if self.fail_trigger and is_open:
            s.set_exception(RuntimeError("simulated trigger failure"))
            return s
        inserted = [f"{bank.bank_prefix}_{i}" for bank in self.banks for i in range(1,13)
                    if getattr(bank,f"f{i}").status.get() == "Open"]
        counts = 10.
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
        s.set_finished()
        return s

    def restore_beamstop(self):
        assert self.shutter.status_pv.get() == 7
        self.restored = True
        yield from bps.null()


@pytest.fixture
def hardware():
    shutter = SimpleNamespace(open_cpt=signal(name="open"), close_cpt=signal(name="close"),
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


def test_run_one_uid_streams_order_results_and_cleanup(hardware):
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
    assert result["foil_summary"][0]["thickness_scale"] == pytest.approx(1.)
    assert shutter.status_pv.get() == 7 and detector.restored
    applies = [m for m in messages if m.command=="set" and m.obj is detector.cam.threshold_apply]
    assert len(applies) == 2
    assert len(result["shape_summary"]) == 1
    assert result["shape_summary"][0]["sigma_x_px_variance_delta"] == pytest.approx(7)
    assert "shape_sigma_x_px" in events[0]["data"]
    assert detector.stats1.compute_centroid.get() == 1
    assert detector.roi1.size.x.get() == 128
    assert detector.roi2.min_xyz.min_x.get()+128 < detector.roi1.min_xyz.min_x.get()
    assert detector.roi3.min_xyz.min_x.get() > detector.roi1.min_xyz.min_x.get()+128


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
    re(plan_mutator(ab._sensitivity(detector,6000,20),skip_sleep))
    assert len([m for m in messages if m.command=="sleep" and m.args==(20,)]) == 2
    detector.cam.threshold_apply.unsubscribe_all()
    detector.energy_read.put(12)
    with pytest.raises(RuntimeError,match="failed to confirm"):
        re(ab._sensitivity(detector,6000,0))


def test_multiple_energies_one_run_reapplies_each_time(hardware):
    detector,shutter,kwargs = hardware
    t2 = dict(id="al9_high", energy_eV=8800, a=["1_3","1_9","2_10"],
              b=["1_3","1_9","2_10","2_9"],pairs=2)
    docs, messages = [],[]
    re = RunEngine({},call_returns_result=True)
    re.subscribe(lambda n,d: docs.append((n,d)))
    re.msg_hook = lambda m: messages.append(m)
    result = re(ab.attenuator_ab_calibration([simple_test(2),t2],**kwargs)).plan_result
    assert len([d for n,d in docs if n=="start"]) == 1
    assert len(result["foil_summary"]) == 2
    assert all(r["thickness_scale"] == pytest.approx(1.) for r in result["foil_summary"])
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
    assert rects == [(436,568,128,64),(292,536,128,128),(580,536,128,128)]
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
