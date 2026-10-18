from ophyd import (
    Component as Cpt,
    ADComponent,
    Signal,
    Device,
    EpicsSignal,
    EpicsSignalRO,
    EpicsMotor,
    ROIPlugin,
    TransformPlugin,
    PilatusDetector,
    OverlayPlugin,
    TIFFPlugin,
    Staged,
    DeviceStatus,
    Kind,
)
from ophyd.signal import SignalRO
from collections import OrderedDict
from collections.abc import Callable, Mapping
from numbers import Integral, Real
from threading import RLock
from types import MappingProxyType
from dataclasses import dataclass
import math

from ophyd.areadetector.cam import PilatusDetectorCam
from ophyd.areadetector.detectors import PilatusDetector
from ophyd.areadetector.base import EpicsSignalWithRBV as SignalWithRBV
from ophyd.areadetector.filestore_mixins import FileStoreTIFFIterativeWrite
import bluesky.plans as bp
import time
from nslsii.ad33 import StatsPluginV33, SingleTriggerV33
import bluesky.plan_stubs as bps

from ophyd.utils.epics_pvs import AlarmStatus

import uuid
import numpy as np
import time as ttime
from warnings import warn

from .beamstop import SAXSBeamStops
from . import _context
from . import _config
from . import attenuator_data as _attenuator_data
from .status import WAXS_STATUS, SAXS_STATUS, compare_energy, finite_number, read_signal as _read_signal

# Persistent-config dict (Redis ``mdsave`` on the live beamline; ``{}`` fallback under bare
# import / tests so the class-body ``Cpt(Signal, value=mdsave.get(...))`` seeding still works
# with no hardware).  The profile bootstrap configures the seam before this module is imported.
mdsave = _context.get_config()


class _SnapshotSignal(SignalRO):
    """Read-only leaf of the last successful parent detector read (no monitors)."""

    def __init__(self, *args, snapshot_dtype="number", **kwargs):
        self._snapshot_dtype = snapshot_dtype
        super().__init__(*args, **kwargs)

    def _reading(self):
        owner = self.parent
        while owner is not None and not hasattr(owner, "_correction_snapshot"):
            owner = owner.parent
        snapshot = None if owner is None else owner._correction_snapshot
        if snapshot is None or self not in snapshot:
            raise RuntimeError(f"{self.name}: unavailable until a successful parent detector read")
        return snapshot[self]

    def get(self, **kwargs):
        return self._reading()["value"]

    @property
    def timestamp(self):
        return self._reading()["timestamp"]

    def read(self):
        # Capture the value and timestamp from the same snapshot, even if another
        # thread publishes a new one between accesses.
        return {self.name: dict(self._reading())}

    def describe(self):
        return {self.name: {"source": f"computed:{self.name}",
                           "dtype": self._snapshot_dtype, "shape": []}}


class StatsWCentroid(StatsPluginV33):
    centroid_total = Cpt(EpicsSignalRO,'CentroidTotal_RBV')
    total_corrected = Cpt(_SnapshotSignal, kind="normal")

    def _read_without_correction(self):
        result = OrderedDict()
        for _, component in self._get_components_of_kind(Kind.normal):
            if not isinstance(component, _SnapshotSignal):
                result.update(component.read())
        return result


@dataclass(frozen=True)
class _ROICalculation:
    signal: _SnapshotSignal
    function: Callable
    corrected: bool
    description: str


def hint_pilatus_stats(detector, stats, *, corrected=False):
    """Select stats display hints between runs, retaining all raw/corrected totals."""
    return detector.hint_stats(stats, corrected=corrected)


class PilatusDetectorCamV33(PilatusDetectorCam):
    """This is used to update the Pilatus to AD33."""

    wait_for_plugins = Cpt(EpicsSignal, "WaitForPlugins", string=True, kind="config")
    file_path = Cpt(SignalWithRBV, "FilePath", string=True)
    file_name = Cpt(SignalWithRBV, "FileName", string=True)
    file_template = Cpt(SignalWithRBV, "FileTemplate", string=True)
    file_number = Cpt(SignalWithRBV, "FileNumber")
    auto_increment = Cpt(SignalWithRBV, "AutoIncrement")
    cam_energy = Cpt(SignalWithRBV, "Energy")
    # Remembers the beamline energy (used to reset the camera threshold after a camserver
    # restart).  Seeded in __init__ from the live energy via the context seam -- NOT read from
    # EPICS at class-definition time (which would break off-beamline import / unit tests).
    energyset = Cpt(Signal, name="Beamline Energy", value=0.0)


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs["wait_for_plugins"] = "Yes"
        self.stage_sigs["file_template"] = "%s%s_%6.6d_SAXS.tif"
        self.stage_sigs["auto_increment"] = 1
        self.stage_sigs["file_number"] = 0
        # Seed the remembered beamline energy from the live source if available (no-op when
        # the seam is unconfigured, e.g. under test).
        _e = _context.current_energy_eV()
        if _e is not None:
            self.energyset.put(_e)


    def ensure_nonblocking(self):
        self.stage_sigs["wait_for_plugins"] = "Yes"
        for c in self.parent.component_names:
            cpt = getattr(self.parent, c)
            if cpt is self:
                continue
            if hasattr(cpt, "ensure_nonblocking"):
                cpt.ensure_nonblocking()
    # file_path = Cpt(SignalWithRBV, "FilePath", string=True)
    # file_name = Cpt(SignalWithRBV, "FileName", string=True)
    # file_template = Cpt(SignalWithRBV, "FileName", string=True)
    # file_number = Cpt(SignalWithRBV, "FileNumber")

    def stage(self):
        self.file_name.set(str(uuid.uuid4()))
        super().stage()

class PilatusDetector(PilatusDetector):
    cam = Cpt(PilatusDetectorCamV33, "cam1:")


class TIFFPluginWithFileStore(TIFFPlugin, FileStoreTIFFIterativeWrite):
    # def __init__(self, *args, md=None, root_path="/nsls2/data/smi/proposals", **kwargs):
    def __init__(self, *args, root_str="/nsls2/data/smi/proposals", md=None, **kwargs):
        super().__init__(*args, **kwargs)
        # ``md`` carries proposal/data-session info (RE.md) used to build the raw-data path at
        # stage() time.  Resolve it lazily from the context seam when not explicitly given, so
        # the class can be defined/imported with no live RE (off-beamline / unit tests).  On the
        # beamline the seam is configured before staging, so RE.md is used exactly as before.
        self._md = md if md is not None else _context.get_md()
        self.__stage_cache = {}
        self._asset_path = ''
        self.root_str = root_str

    def describe(self):
        ret = super().describe()
        key = self.parent._image_name
        if key not in ret:
            # Before the first datum, filestore has no image field to describe.
            return ret
        color_mode = self.parent.cam.color_mode.get(as_string=True)
        if color_mode == 'Mono':
            ret[key]['shape'] = [
                self.parent.cam.num_images.get(),
                self.array_size.height.get(),
                self.array_size.width.get()
                ]

        elif color_mode in ['RGB1', 'Bayer']:
            ret[key]['shape'] = [self.parent.cam.num_images.get(), *self.array_size.get()]
        else:
            raise RuntimeError("SHould never be here")

        cam_dtype = self.data_type.get(as_string=True)
        type_map = {'UInt8': '|u1', 'UInt16': '<u2', 'Float32':'<f4', "Float64":'<f8', 'Int32':'<i4'}
        if cam_dtype in type_map:
            ret[key].setdefault('dtype_str', type_map[cam_dtype])

        return ret

    def get_frames_per_point(self):
        # added for debugging - removing the print March 2026
        ret = super().get_frames_per_point()
        #print('get_frames_per_point returns', ret)
        return ret

    def _update_paths(self):
        self.write_path_template = self.root_path_str + "%Y/%m/%d/"
        self.read_path_template = self.root_path_str + "%Y/%m/%d/"
        self.reg_root = self.root_path_str

    @property
    def root_path_str(self):
        return f"{self.root_str}/{self._md['cycle']}/{self._md['data_session']}/assets/{self._asset_path}/"

    def stage(self):

        self._update_paths()
        return super().stage()



class Pilatus(SingleTriggerV33, PilatusDetector):
    energy_match_tolerance_eV = 100.0

    def energy_difference(self, beamline_energy_eV, *, read_signal=_read_signal):
        """Return detector energy offset and agreement in eV, without changes."""
        detector_energy = finite_number(read_signal(self.cam.cam_energy)) * 1000
        return compare_energy(detector_energy, beamline_energy_eV, self.energy_match_tolerance_eV)

    tiff = Cpt(
        TIFFPluginWithFileStore,
        suffix="TIFF1:",
        write_path_template="/ramdisk/PLACEHOLDER",
        root_str="/nsls2/data/smi/proposals",
        root="/nsls2/data/smi/proposals",
    )

    attenuation_factor_used = Cpt(_SnapshotSignal, kind="normal")
    attenuation_energy_eV_used = Cpt(_SnapshotSignal, kind="normal")
    attenuation_foils_used = Cpt(_SnapshotSignal, snapshot_dtype="string", kind="normal")

    def __init__(self, *args, asset_path, attenuation_provider=None, **kwargs):
        self.asset_path = asset_path
        self.attenuation_provider = attenuation_provider
        self._correction_snapshot = None
        self._snapshot_lock = RLock()
        self._snapshot_reading = False
        self._roi_calculations = OrderedDict()
        # Establish the minimal parent readout once, not on every hint selection.
        # Instance setup adds the existing SAXS/WAXS motor/camera readouts.
        kwargs.setdefault("read_attrs", [
            "stats1", "stats2", "stats3", "stats4", "stats5", "tiff",
            "attenuation_factor_used", "attenuation_energy_eV_used", "attenuation_foils_used",
        ])
        super().__init__(*args, **kwargs)
        self.tiff._asset_path = self.asset_path
        self.hint_stats(1)

    roi1 = Cpt(ROIPlugin, "ROI1:")
    roi2 = Cpt(ROIPlugin, "ROI2:")
    roi3 = Cpt(ROIPlugin, "ROI3:")
    roi4 = Cpt(ROIPlugin, "ROI4:")

    stats1 = Cpt(StatsWCentroid, "Stats1:", read_attrs=["total", "total_corrected"])
    stats2 = Cpt(StatsWCentroid, "Stats2:", read_attrs=["total", "total_corrected"])
    stats3 = Cpt(StatsWCentroid, "Stats3:", read_attrs=["total", "total_corrected"])
    stats4 = Cpt(StatsWCentroid, "Stats4:", read_attrs=["total", "total_corrected"])
    stats5 = Cpt(StatsWCentroid, "Stats5:", read_attrs=["total", "total_corrected"])

    over1 = Cpt(OverlayPlugin, "Over1:")
    trans1 = Cpt(TransformPlugin, "Trans1:")

    threshold = Cpt(EpicsSignal, "cam1:ThresholdEnergy")
    cam_energy = Cpt(EpicsSignal, "cam1:Energy")
    gain = Cpt(EpicsSignal, "cam1:GainMenu")
    apply = Cpt(EpicsSignal, "cam1:ThresholdApply")

    threshold_read = Cpt(EpicsSignal, "cam1:ThresholdEnergy_RBV")
    energy_read = Cpt(EpicsSignal, "cam1:Energy_RBV")
    gain_read = Cpt(EpicsSignal, "cam1:GainMenu_RBV")
    apply_read = Cpt(EpicsSignal, "cam1:ThresholdApply_RBV")

    def set_primary_roi(self, num):
        """Old spelling for raw stats hints; no longer narrows the recorded readout."""
        if isinstance(num, bool) or not isinstance(num, Integral):
            raise ValueError("stats index must be an integer in 1–5")
        return self.hint_stats(num, corrected=False)

    def hint_stats(self, stats, *, corrected=False):
        """Replace stats-total hints, preserving all totals and unrelated readouts.

        Call between runs. ``stats`` is an integer or iterable of integers in 1–5;
        an empty iterable clears stats hints. Selection lasts for this session.
        """
        if not isinstance(corrected, bool):
            raise ValueError("corrected must be a boolean")
        if isinstance(stats, Integral):
            stats = [stats]
        try:
            selection = list(stats)
        except TypeError as exc:
            raise ValueError("stats must be an integer or iterable of integers in 1–5") from exc
        if any(isinstance(n, bool) or not isinstance(n, Integral) or not 1 <= n <= 5
               for n in selection):
            raise ValueError("stats indices must be integers in 1–5 (not booleans)")
        selection = sorted(set(int(n) for n in selection))
        hint_bit = Kind.hinted & ~Kind.normal
        for n in range(1, 6):
            plugin = getattr(self, f"stats{n}")
            plugin.kind |= Kind.normal
            for leaf, mode in ((plugin.total, False), (plugin.total_corrected, True)):
                leaf.kind = (leaf.kind & ~hint_bit) | Kind.normal
                if n in selection and mode == corrected:
                    leaf.kind |= Kind.hinted
        return {"stats": selection, "corrected": corrected,
                "fields": list(self.hints["fields"])}

    @property
    def calculations(self):
        """Named read-only calculation signals (not dynamically added Components)."""
        return MappingProxyType({name: calc.signal for name, calc in self._roi_calculations.items()})

    def _check_calculation_configuration(self):
        if self._staged != Staged.no or self._snapshot_reading:
            raise RuntimeError("Configure ROI calculations between runs, while unstaged and not reading")

    def add_roi_calculation(self, name, function, *, corrected=True, description=""):
        """Register ``function(roi)`` as an exactly named scalar event field.

        ``roi`` is an immutable mapping of stats indices 1–5 to this read's totals.
        Use a pure function returning a finite number, e.g.::

            det.add_roi_calculation(
                "refl", lambda roi: roi[1] - 0.5 * (roi[4] - roi[1]),
                corrected=True, description="ROI1 minus surrounding background")

        Register between runs. Names must be unique across all devices in a stream.
        Returns a read-only signal exposing the last successful parent snapshot.
        """
        with self._snapshot_lock:
            self._check_calculation_configuration()
            if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
                raise ValueError("Calculation name must be a public identifier, e.g. 'refl'")
            if not callable(function):
                raise ValueError("Calculation must be callable")
            if not isinstance(corrected, bool) or not isinstance(description, str):
                raise ValueError("corrected must be boolean and description must be a string")
            existing = {walk.item.name for walk in self.walk_signals()}
            existing.update(self._roi_calculations)
            existing.add(self._image_name)
            if name in existing:
                raise ValueError(f"Field name already in use: {name}")
            signal = _SnapshotSignal(name=name, parent=self, kind="normal")
            self._roi_calculations[name] = _ROICalculation(signal, function, corrected, description)
            return signal

    def remove_roi_calculation(self, name):
        """Remove a calculation between runs; remaining fields/hints are preserved."""
        with self._snapshot_lock:
            self._check_calculation_configuration()
            calc = self._roi_calculations.pop(name)
            if self._correction_snapshot is not None:
                self._correction_snapshot = {
                    signal: reading for signal, reading in self._correction_snapshot.items()
                    if signal is not calc.signal
                }

    def hint_calculations(self, names, *, clear_stats=True):
        """Replace calculation hints, normally clearing ROI-total hints.

        All calculations and raw/corrected totals remain recorded. Pass
        ``clear_stats=False`` to retain the current stats hints as well.
        """
        with self._snapshot_lock:
            self._check_calculation_configuration()
            if not isinstance(clear_stats, bool):
                raise ValueError("clear_stats must be boolean")
            if isinstance(names, str):
                names = [names]
            try:
                names = list(names)
            except TypeError as exc:
                raise ValueError("names must be a name or iterable of names") from exc
            if any(not isinstance(name, str) or name not in self._roi_calculations for name in names):
                raise ValueError("Unknown ROI calculation name")
            if clear_stats:
                self.hint_stats([])
            for name, calc in self._roi_calculations.items():
                calc.signal.kind = "hinted" if name in names else "normal"
            return {"calculations": [name for name in self._roi_calculations if name in names],
                    "fields": list(self.hints["fields"])}

    @property
    def hints(self):
        result = super().hints
        for calc in self._roi_calculations.values():
            if calc.signal.kind & Kind.normal:
                result["fields"].extend(calc.signal.hints["fields"])
        return result

    def describe(self):
        result = super().describe()
        for name, calc in self._roi_calculations.items():
            if calc.signal.kind & Kind.normal:
                if name in result:
                    raise ValueError(f"Calculation field collides with detector readout: {name}")
                result.update(calc.signal.describe())
                result[name].update(roi_input="corrected" if calc.corrected else "raw",
                                    calculation_description=calc.description)
        return result

    @staticmethod
    def _finite_scalar(value, label):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError(f"{label} must be a finite numeric scalar, got {value!r}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite, got {value!r}")
        return value

    def _attenuation_state(self):
        if not callable(self.attenuation_provider):
            raise RuntimeError(f"{self.name}: no attenuation provider configured")
        state = self.attenuation_provider()
        timestamp = ttime.time()
        if not isinstance(state, Mapping):
            raise ValueError("attenuation provider must return a state mapping")
        try:
            factor = self._finite_scalar(state["attenuation_factor"], "attenuation factor")
            transmission = self._finite_scalar(state["transmission"], "transmission")
            energy = self._finite_scalar(state["energy_eV"], "attenuation energy")
            labels = state["inserted"]
            if isinstance(labels, (str, bytes)):
                raise ValueError("inserted foils must be a sequence of labels")
            labels = list(labels)
        except (KeyError, TypeError) as exc:
            raise ValueError("incomplete or invalid attenuation state") from exc
        if not (factor >= 1 and 0 < transmission <= 1
                and math.isclose(factor * transmission, 1.0, rel_tol=1e-12)):
            raise ValueError("invalid attenuation factor/transmission")
        if not (energy > 0 and _attenuator_data.ENERGY_MIN_EV <= energy
                <= _attenuator_data.ENERGY_MAX_EV):
            raise ValueError("attenuation energy outside the tabulated range")
        if any(not isinstance(label, str) or label not in _attenuator_data.FOIL_LAYOUT
               for label in labels) or len(set(labels)) != len(labels):
            raise ValueError("invalid or duplicate inserted foil labels")
        labels.sort(key=_attenuator_data._foil_sort_key)
        return factor, energy, ",".join(labels), timestamp

    def read(self):
        """Read raw data once, then publish one validated attenuation snapshot.

        Energy/foils must remain settled from exposure through all detector reads.
        Child corrected/provenance reads expose only the last successful snapshot.
        """
        with self._snapshot_lock:
            if self._snapshot_reading:
                raise RuntimeError(f"{self.name}: recursive detector read")
            self._snapshot_reading = True
            try:
                result = OrderedDict()
                for _, component in self._get_components_of_kind(Kind.normal):
                    if isinstance(component, _SnapshotSignal):
                        continue
                    if isinstance(component, StatsWCentroid):
                        result.update(component._read_without_correction())
                    else:
                        result.update(component.read())
                totals = []
                for n in range(1, 6):
                    plugin = getattr(self, f"stats{n}")
                    if plugin.total.name not in result:
                        raise RuntimeError(f"Missing required raw total: {plugin.total.name}")
                    raw = result[plugin.total.name]
                    value = self._finite_scalar(raw["value"], plugin.total.name)
                    totals.append((plugin.total_corrected, value, raw["timestamp"]))
                factor, energy, foils, timestamp = self._attenuation_state()
                snapshot = {}
                for signal, value, raw_time in totals:
                    product = self._finite_scalar(value * factor, signal.name)
                    snapshot[signal] = {"value": product, "timestamp": raw_time}
                for signal, value in ((self.attenuation_factor_used, factor),
                                      (self.attenuation_energy_eV_used, energy),
                                      (self.attenuation_foils_used, foils)):
                    snapshot[signal] = {"value": value, "timestamp": timestamp}
                raw_rois = MappingProxyType({n: value for n, (_, value, _) in enumerate(totals, 1)})
                corrected_rois = MappingProxyType({
                    n: snapshot[signal]["value"] for n, (signal, _, _) in enumerate(totals, 1)
                })
                for name, calc in self._roi_calculations.items():
                    if not calc.signal.kind & Kind.normal:
                        continue
                    if name in result or any(signal.name == name for signal in snapshot):
                        raise ValueError(f"Calculation field collides with detector readout: {name}")
                    try:
                        value = calc.function(corrected_rois if calc.corrected else raw_rois)
                        value = self._finite_scalar(value, name)
                    except Exception as exc:
                        raise ValueError(f"ROI calculation {name!r} failed: {exc}") from exc
                    # No individual dependency tracking: use the newest timestamp
                    # among the five stats inputs from this acquisition snapshot.
                    snapshot[calc.signal] = {"value": value,
                                             "timestamp": max(t for _, _, t in totals)}
                # Respect manual leaf omission in read/describe alike; the helper
                # restores both totals. Required raw totals may never be omitted.
                for signal, reading in snapshot.items():
                    if signal.kind & Kind.normal:
                        result[signal.name] = dict(reading)
                self._correction_snapshot = snapshot
                return result
            finally:
                self._snapshot_reading = False

    # This is breaking some of the scans trying to reset trshold and gain

    def apply_threshold(self, energy=16.1, threshold=11.5, gain="autog"):
        if 1.5 < energy < 24:
            yield from bps.mv(self.cam_energy, energy)
        else:
            raise ValueError(
                "The energy range for Pilatus is 1.5 to 24 keV. The entered value is {}".format(
                    energy
                )
            )

        if 1.5 < threshold < 24:
            yield from bps.mv(self.threshold, threshold)
        else:
            raise ValueError(
                "The threshold range for Pilatus is 1.5 to 24 keV. The entered value is {}".format(
                    threshold
                )
            )

        # That will need to be checked and tested
        if gain == "autog":
            yield from bps.mv(self.gain, 1)
        elif gain == "uhighg":
            yield from bps.mv(self.gain, 3)
        else:
            raise ValueError(
                "The gain used is unknown. It shoul be either autog or uhighg"
            )
        yield from bps.mv(self.apply, 1)

    def read_threshold(self):
        return self.energy_read, self.threshold_read, self.gain_read

    def trigger(self):
        if self._staged != Staged.yes:
            raise RuntimeError("This detector is not ready to trigger."
                               "Call the stage() method before triggering.")

        self._status = self._status_type(self)
        fail_count = 0
        def _acq_done(*, data, pvname):
            nonlocal fail_count
            data.get()
            if data.alarm_status is not AlarmStatus.NO_ALARM:

 
                if fail_count < 2:
                    # so two extra tries seems reasonable
                    print('Detector did not respond, trying again, in case it needs to initialize connection\n\n\n\n\n')
                    self._acquisition_signal.put(1, use_complete=True, callback=_acq_done, 
                                     callback_data=self.cam.detector_state)
                
                    fail_count += 1
                    time.sleep(1)
                else:
                    # if it fails again, there is probably something wrong
                    print('\n\nFailed again!\nDid you forget to run "RE(restartwaxs())??\n\n\n\n\n')
                    self._status.set_exception(
                        RuntimeError(f"FAILED {pvname}: {data.alarm_status}: {data.alarm_severity}")
                    )
            else:
                self._status._finished()

        self._acquisition_signal.put(1, use_complete=True, callback=_acq_done, 
                                     callback_data=self.cam.detector_state)
        self.generate_datum(self._image_name, ttime.time())
        return self._status



class FakeDetector(Device):
    acq_time = Cpt(Signal, value=10)

    _default_configuration_attrs = ("acq_time",)
    _default_read_attrs = ()

    def trigger(self):
        st = self.st = DeviceStatus(self)

        from threading import Timer

        self.t = Timer(self.acq_time.get(), st._finished)
        self.t.start()
        return st



class SAXSPositions(Device):
    x = Cpt(EpicsMotor, "X}Mtr")
    y = Cpt(EpicsMotor, "Y}Mtr")
    z = Cpt(EpicsMotor, "Z}Mtr")



#####################################################
# ------ NOT TESTED AFTER DATA SECURITY CHANGES -----
# Pilatus 300kw definition

# pil300KW = Pilatus("XF:12IDC-ES:2{Det:300KW}", name="pil300KW", asset_path="pilatus300kw-1")  # , detector_id="WAXS")
# pil300KW.set_primary_roi(1)

# pil300kwroi1 = EpicsSignal(
#     "XF:12IDC-ES:2{Det:300KW}Stats1:Total_RBV", name="pil300kwroi1"
# )
# pil300kwroi2 = EpicsSignal(
#     "XF:12IDC-ES:2{Det:300KW}Stats2:Total_RBV", name="pil300kwroi2"
# )
# pil300kwroi3 = EpicsSignal(
#     "XF:12IDC-ES:2{Det:300KW}Stats3:Total_RBV", name="pil300kwroi3"
# )
# pil300kwroi4 = EpicsSignal(
#     "XF:12IDC-ES:2{Det:300KW}Stats4:Total_RBV", name="pil300kwroi4"
# )

# pil300KW.stats1.kind = "hinted"
# pil300KW.stats1.total.kind = "hinted"
# pil300KW.cam.num_images.kind = "config"
# pil300KW.cam.ensure_nonblocking()



# "multi_count" plan is dedicated to the time resolved Pilatus runs when the number of images in area detector is more than 1

class WAXS_Motors(Device):
    arc = Cpt(EpicsMotor, "XF:12IDC-ES:2{WAXS:1-Ax:Arc}Mtr",name='arc')
    bs_x = Cpt(EpicsMotor, "XF:12ID2C-ES{MCS:2-Ax:1}Mtr",name='bs_x')
    bs_y = Cpt(EpicsMotor, "XF:12IDC-ES:2{BS:WAXS-Ax:y}Mtr",name='bs_y')
    test = 5
    bsx_offset = -58 # ToDo: change this to 58.5 but the bsz offset to adjust 
                # offset from the beam center to the beamstop in mm
                # this value should be reset in the motor offset - not here
                # the procedure is to move the motor to the negative limit (outboard) and run home_forward.set(1) on the waxs beamstop x
                # waxs.bs_x.home_forward.set(1).  this should reset position correctly
                # if the beamstop mounting is changed or bent, this value may need to be tweaked
    bsz_offset = 249.69871 
                # distance from the center of arc rotation (sample position) to the beamstop
                # in mm   
                # if the beamstop mounting is changed or bent, this value may need to be tweaked
    bsx_safe_pos = 15
                # x position of the beamstop when it IS NOT in the beam (out of the way direct beam and scattering)
    
    # when moving the waxs detector, the beamstop must be moved to a new position
    # the beamstop is moved to a new position based on the angle of the waxs detector
    # =========================================================================
    # TEMPORARY (beamstop X motor unplugged) - 2026-06-23
    # The waxs beamstop x motor has been unplugged because it is not functioning
    # correctly.  While unplugged, do NOT move the beamstop motor at all.
    # The beamstop is physically in position only for waxs arc = 0 deg.
    # Valid arc positions are therefore: exactly 0 deg (+/- 0.1 mm buffer), or
    # 14.5 deg and above (beamstop out of the way of beam/scattering).
    # Anything in between is invalid and must error out cleanly *without*
    # commanding the (unplugged) beamstop motor.
    #
    # TO REVERT: delete this temporary block and uncomment the ORIGINAL block
    # below (and likewise restore the original stop()).
    def set(self, arc_value):
        bs_in_pos_angle = 0.0   # arc angle (deg) where the beamstop is in position
        bs_in_pos_buffer = 0.1  # buffer (mm/deg) around the in-position angle
        bs_out_min_angle = 14.5 # min arc angle (deg) where the beamstop is safely out

        if not (
            abs(arc_value - bs_in_pos_angle) <= bs_in_pos_buffer
            or arc_value >= bs_out_min_angle
        ):
            raise ValueError(
                f"The waxs detector cannot be moved to {arc_value} deg \n"
                "The waxs beamstop x motor is temporarily unplugged.\n"
                f"Only arc = {bs_in_pos_angle} deg (+/- {bs_in_pos_buffer}) or "
                f"arc >= {bs_out_min_angle} deg are allowed right now."
            )

        # beamstop motor is unplugged - move the arc only, do NOT touch bs_x
        st_arc = self.arc.set(arc_value)
        return st_arc

    def stop(self, *args, **kwargs):
        # beamstop motor is unplugged - stop the arc only
        st_arc = self.arc.stop()
        return st_arc
    # =========================================================================
    # ORIGINAL set()/stop() - RESTORE THIS WHEN THE BEAMSTOP X MOTOR IS FIXED
    # def set(self, arc_value):
    #     st_arc = self.arc.set(arc_value)
    #     # start moving the arc stage and return the status
    #
    #     if self.arc.limits[0] <= arc_value <= 10.1:
    #         calc_value = self.calc_waxs_bsx(arc_value)
    #         # calculate the position of the beamstop based on the angle of the waxs detector
    #     elif 10.1 < arc_value <= 13:
    #         # the beamstop cannot be moved to block the beam
    #         # this move is not safe
    #         raise ValueError(
    #             f"The waxs detector cannot be moved to {arc_value} deg \n"
    #             "Do NOT take data between 10.1 and 13 degrees WAXS arc"
    #         )
    #     else:
    #         calc_value = self.bsx_safe_pos # out of the path of the beam and scattering
    #
    #     st_x = self.bs_x.set(calc_value)
    #     # move the beamstop to the new position
    #     return st_arc & st_x # return both statuses
    # def stop(self, *args, **kwargs):
    #     # stop the arc stage and the beamstop
    #     st_arc = self.arc.stop()
    #     st_x = self.bs_x.stop()
    #     return st_arc & st_x
    # =========================================================================
    # calculate the position of the beamstop based on the angle of the waxs detector
    # the beamstop is on the arc stage, so as the angle of the waxs detector changes, the position of the beamstop must also change
    def calc_waxs_bsx(self, arc_value):
        bsx_pos = ( 
            self.bsx_offset # offset from the beam center to the beamstop in mm
            - (self.bsz_offset # distance from the center of arc rotation (sample position) to the beamstop
            * np.tan( # beamstop movement is a linear movement on the arc stage
                np.deg2rad(arc_value)))) # the angle of the waxs detector arc in degrees
        # 2025 March 26
        
        return bsx_pos


class WAXS_Detector(Pilatus):
    status_description = WAXS_STATUS
## real positions of the SAXS detector and the beamstop
    ## WAXS det position and beamstop (mounted on the same stage)
    motors = Cpt(WAXS_Motors,"",add_prefix= "", kind="normal")

## constants for the beam center calculation
    beam_center_x_px = Cpt(Signal,value =103, kind="normal")
    beam_center_y_px = Cpt(Signal,value =1256, kind="normal")
    sdd_mm = Cpt(Signal,value =280.0, kind="normal")
    pixel_size_mm = Cpt(Signal,value =0.172, kind="normal") # in mm
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    

class DetMotor(Device):
    # x/y/z are recorded (kind='normal') but NOT auto-plotted.  They are read into every scan's
    # primary stream (for the SDD/filename token) via the scan-naming preprocessor, so hinting any
    # of them would clutter the BestEffortCallback plot with the detector position in every scan.
    # (An EpicsMotor's user_readback defaults to kind='hinted', so 'normal' here is also applied to
    # each user_readback at instance time -- see startup/smibase/pilatus.py.)  When the SDD z motor
    # is actually scanned it is still plotted, because BEC takes the x-axis from the scanned motor
    # (start_doc 'motors'/'dimensions'), not from kind.
    x = Cpt(EpicsMotor, "X}Mtr",kind="normal")
    y = Cpt(EpicsMotor, "Y}Mtr",kind="normal")
    z = Cpt(EpicsMotor, "Z}Mtr",kind="normal")


class SAXS_Detector(Pilatus):
    status_description = SAXS_STATUS

    def selected_beamstop_motors(self, *, read_signal=_read_signal):
        """Return the reported rod/pin selection's motors, or None if unselected."""
        selection = str(read_signal(self.active_beamstop)).removesuffix("_removed")
        if selection not in ("rod", "pin"):
            return None
        return (getattr(self.beamstop, "x_" + selection), getattr(self.beamstop, "y_" + selection))

## real positions of the SAXS detector and the beamstop
    ## SAXS det position
    motor = Cpt(DetMotor,"XF:12IDC-ES:2{Det:1M-Ax:",add_prefix= "", kind="normal")
    ## stages for SAXS beamstops (two beamstops, each with their own offset from the beam center)
    beamstop = Cpt(SAXSBeamStops,"XF:12IDC-ES:2{BS:SAXS-Ax:",add_prefix= "", kind="normal")

## the virtual positions of the beamcenter (in pixels) and the sample distance
    # values will be over written by the beam center calculation
    # based on the motor positions and the constant offsets

    beam_center_x_px = Cpt(Signal,value =-744, kind="normal")
    beam_center_x_mm = Cpt(Signal,value =127.968, kind="config")
    beam_center_y_px = Cpt(Signal,value =-1107, kind="normal")
    beam_center_y_mm = Cpt(Signal,value =190.404, kind="config")
    sample_distance_mm = Cpt(Signal,value =0.0, kind="normal")
    active_beamstop = Cpt(Signal,value ='none', kind="normal")

## constants for the beam center calculation
    # offsets will be reset by the calc_offsets function
    # all other values should be set here from calibration / lookup table
    pixel_size_mm = Cpt(Signal,value =0.172, kind="config") # in mm
    # offset from 0th column pixel to the beam center at saxs position x = 0
    beam_offset_x_mm = Cpt(Signal,value =mdsave.get('saxs_beam_offset_x_mm',128.398), kind="config") 
    # offset from 0th row pixel to the beam center at saxs position y = 0
    beam_offset_y_mm = Cpt(Signal,value =mdsave.get('saxs_beam_offset_y_mm',190.404), kind="config")
    # difference between the position.z and the actual sample-detector distance
    sample_offset_z_mm = Cpt(Signal,value =mdsave.get('saxs_sample_offset_z_mm',0.0), kind="config")
    

## constants for the beamstop position
    rod_offset_x_mm = Cpt(Signal,value = mdsave.get('saxs_rod_offset_x_mm',6.8), kind="config")
    # position of the beamstop when it IS in the beam x
    rod_offset_y_mm = Cpt(Signal,value = mdsave.get('saxs_rod_offset_y_mm',0.0), kind="config") 
    # position of the beamstop when it IS in the beam y
    rod_safe_pos = Cpt(Signal,value = mdsave.get('saxs_rod_safe_pos',-200), kind="config") 
    # x position of the beamstop when it IS NOT in the beam (out of the way for the pin diode)
    pd_offset_x_mm = Cpt(Signal,value = mdsave.get('saxs_pd_offset_x_mm',-227), kind="config") 
    # position of the beamstop when it IS in the beam x
    pd_offset_y_mm = Cpt(Signal,value = mdsave.get('saxs_pd_offset_y_mm',6.8), kind="config") 
    # position of the beamstop when it IS in the beam y
    pd_safe_pos = Cpt(Signal,value = mdsave.get('saxs_pd_safe_pos',0.0), kind="config") 
    # x position of the beamstop when it IS NOT in the beam (out of the way for the rod)


# subscribe the virtual signals to the motors, so they are updated when the motors move
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.motor.x.subscribe(self.update_beam_center)
        self.motor.y.subscribe(self.update_beam_center)
        self.motor.z.subscribe(self.update_beam_center) # if there is wobble in the track, the x an y center will vary
        # Infer the initially-active beamstop from the live stage positions.  Guard against
        # unconnected positioners (``.position is None`` on a fresh/fake/disconnected device): in
        # that case leave ``active_beamstop`` at its 'none' default.  On real, connected hardware
        # every ``.position`` is a number so this guard never changes behaviour.
        _positions = (
            self.beamstop.x_pin.position,
            self.beamstop.x_rod.position,
        )
        if any(p is None for p in _positions):
            return
        pin_safe = abs(self.beamstop.x_pin.position - self.pd_safe_pos.get()) < 1 
        rod_safe = abs(self.beamstop.x_rod.position - self.rod_safe_pos.get()) < 1
        rod_in = abs(self.beamstop.x_rod.position - self.rod_offset_x_mm.get())
        pin_in = abs(self.beamstop.x_pin.position - self.pd_offset_x_mm.get())
        if(rod_in < 1 and pin_safe):
            self.active_beamstop.set('rod')
        elif(pin_in < 1 and rod_safe):
            self.active_beamstop.set('pin')
        elif(rod_in < 11 and pin_safe):
            self.active_beamstop.set('rod_removed')
        elif(pin_in < 11 and rod_safe):
            self.active_beamstop.set('pin_removed')
        else:
            self.active_beamstop.set('none')



# callback function to update the beam center based on the motor positions will be called often
    def update_beam_center(self, *args, **kwargs):
        # based on the position, update the offsets from a calibration file
        # Guard against unconnected positioners (``.position is None`` on a fresh/fake/disconnected
        # device); the subscription that calls this fires once at construction time.  On real,
        # connected hardware the positions are always numbers so this guard never changes behaviour.
        if any(getattr(self.motor, ax).position is None for ax in ("x", "y", "z")):
            return
        self.calc_offsets(self.motor.z.position) # account for the wobble in the track
        # use the offsets and the motor positions to update the virtual beam center in mm, and then convert to pixels
        self.beam_center_x_mm.put(
            -self.motor.x.position - self.beam_offset_x_mm.get()
        )
        self.beam_center_y_mm.put(
            -self.motor.y.position - self.beam_offset_y_mm.get()
        )
        self.sample_distance_mm.put(
            self.motor.z.position + self.sample_offset_z_mm.get()
        )
        self.beam_center_x_px.put(
            np.abs(self.beam_center_x_mm.get()) / self.pixel_size_mm.get()
        )
        self.beam_center_y_px.put(
            np.abs(self.beam_center_y_mm.get()) / self.pixel_size_mm.get()
        )
        ...
    # move the beamstop to the calculated position of the beam center
    def insert_beamstop(self, beamstop='rod'):
        if beamstop == 'rod' or beamstop == 'bar':
            #move pd to safe position
            yield from bps.mv(self.beamstop.x_pin, self.pd_safe_pos.get())
            #move rod to beam center
            yield from bps.mv(self.beamstop.x_rod, self.rod_offset_x_mm.get())
            yield from bps.mv(self.active_beamstop,'rod')
        elif beamstop == 'pd' or beamstop == 'pin':
            #move rod to safe position
            yield from bps.mv(self.beamstop.x_rod, self.rod_safe_pos.get())
            #move pd to beam center
            yield from bps.mv(self.beamstop.x_pin, self.pd_offset_x_mm.get(),
                              self.beamstop.y_pin, self.pd_offset_y_mm.get())
            yield from bps.mv(self.active_beamstop,'pin')
        else:
            raise ValueError("beamstop must be either 'rod' or 'pin'")
        
    def remove_beamstop(self):
        active_beamstop = self.active_beamstop.get()
        if active_beamstop == 'rod':
            yield from self.remove_rod()
        elif active_beamstop == 'pin':
            yield from self.remove_pin()
        elif active_beamstop in ('rod_removed', 'pin_removed'):
            return
        else:
            raise ValueError('beamstop is not in place')

    def remove_rod(self):
        # remove the rod beamstop by 5 mm, only if it is the active beamstop, if not error
        warn('beamstop will be removed, run restore_beamstop to put it back')
        if abs(self.beamstop.x_pin.position - self.pd_safe_pos.get())>1 and 'rod' not in self.active_beamstop.get():
            raise ValueError('Beamstop is not in')
        else:
            yield from bps.mv(self.beamstop.x_rod,self.rod_offset_x_mm.get()+5)
            yield from bps.mv(self.active_beamstop,'rod_removed')
    
    def remove_pin(self):
        # remove the pin diode beamstop by 5 mm, only if it is the active beamstop, if not error
        
        warn('beamstop will be removed, run restore_beamstop to put it back')
        if abs(self.beamstop.x_rod.position - self.rod_safe_pos.get())>1 and 'pin' not in self.active_beamstop.get():
            raise ValueError('Beamstop is not in')
        else:
            yield from bps.mv(self.beamstop.x_pin,self.pd_offset_x_mm.get() + 5)
            yield from bps.mv(self.active_beamstop,'pin_removed')
    
    def restore_pin(self):
        yield from bps.mv(self.beamstop.x_pin,self.pd_offset_x_mm.get())
        yield from bps.mv(self.active_beamstop,'pin')
    def restore_rod(self):
        yield from bps.mv(self.beamstop.x_rod,self.rod_offset_x_mm.get())
        yield from bps.mv(self.active_beamstop,'rod')
    
    def restore_beamstop(self):
        if self.active_beamstop.get() == 'rod_removed':
            yield from self.restore_rod()
        elif self.active_beamstop.get() == 'pin_removed':
            yield from self.restore_pin()
        else:
            raise ValueError('Beamstop is not removed - please check system manually before continuing\nIf getting the above error all the time, try to go into alignment mode\n by RE(smi.modeAlignment()) and then to measurement by RE(smi.modeMeasurement())')

    
    def save_beamstop(self):
        if self.active_beamstop.get() == 'rod':
            self.save_rod_position()
        elif self.active_beamstop.get() == 'pin':
            self.save_pd_position()
        else:
            warn('beamstop is not in position, please run restore_beamstop (i.e. smi.modeMeasurement()) and try again')

    def save_all_offsets(self):
        _config.persist_from_signals(self, {
            'saxs_rod_offset_x_mm': 'rod_offset_x_mm',
            'saxs_rod_safe_pos': 'rod_safe_pos',
            'saxs_pd_offset_x_mm': 'pd_offset_x_mm',
            'saxs_pd_offset_y_mm': 'pd_offset_y_mm',
            'saxs_pd_safe_pos': 'pd_safe_pos',
        })

    def save_rod_position(self):
        self.rod_offset_x_mm.set(self.beamstop.x_rod.position)
        _config.persist_from_signals(self, {'saxs_rod_offset_x_mm': 'rod_offset_x_mm'})
        self.add_calibration_point(self.motor.z.position, self.get_current_offset_dict())


    def save_pd_position(self):
        self.pd_offset_x_mm.set(self.beamstop.x_pin.position)
        self.pd_offset_y_mm.set(self.beamstop.y_pin.position)
        _config.persist_from_signals(self, {
            'saxs_pd_offset_x_mm': 'pd_offset_x_mm',
            'saxs_pd_offset_y_mm': 'pd_offset_y_mm',
        })
        self.add_calibration_point(self.motor.z.position, self.get_current_offset_dict())

    
    def calc_offsets(self, distance, verbose=False):
        # Beam-to-pixel offsets vary with z (track wobble)
        attr_map = {
            "beam_offset_x":   self.beam_offset_x_mm,
            "beam_offset_y":   self.beam_offset_y_mm,
        }
        for key, sig in attr_map.items():
            sig.put(self._interpolate_offset(distance, key))

        # Beamstop must also track the wobble so it stays centered on the beam.
        # The beamstop is on the same carriage but at a different z from the
        # detector face.  The beam offset change (wobble) at the detector face
        # is the reference; the beamstop sees a scaled version based on its
        # lever arm ratio.  For now, assume the beamstop is close enough to
        # the detector face that the ratio ≈ 1 (i.e. same lateral shift).
        #
        # rod_offset_x = nominal_rod_x + delta_beam_offset_x
        # where delta = current interpolated offset - nominal (at reference z)
        nominal_beam_offset_x = mdsave.get('saxs_beam_offset_x_mm', 128.398)
        nominal_beam_offset_y = mdsave.get('saxs_beam_offset_y_mm', 190.404)

        delta_x = self.beam_offset_x_mm.get() - nominal_beam_offset_x
        delta_y = self.beam_offset_y_mm.get() - nominal_beam_offset_y

        # Apply the wobble correction to the beamstop positions
        base_rod_x = mdsave.get('saxs_rod_offset_x_mm', 6.8)
        base_rod_y = mdsave.get('saxs_rod_offset_y_mm', 0.0)
        base_pd_x  = mdsave.get('saxs_pd_offset_x_mm', -227.0)
        base_pd_y  = mdsave.get('saxs_pd_offset_y_mm', 6.8)

        # =====================================================================
        # TEMPORARY (beamstop restore over-correction) - 2026-06-23
        # The z-wobble delta was over-correcting the SAXS beamstop restore so
        # restore_beamstop()/modeMeasurement() landed off the saved position.
        # While debugging, use the saved nominal value DIRECTLY (no delta), so
        # the beamstop restores to EXACTLY the value saved via save_beamstop().
        # NOTE: this only affects where the beamstop is parked; the beam-center
        # calculation above still uses the full wobble correction.
        #
        # ROOT CAUSE + PROPER FIX: see docs/SAXS_BEAMSTOP_WOBBLE.md.  In short,
        # save_beamstop() stores the absolute FINAL position at that distance
        # (wobble already baked in), but calc_offsets re-applies the wobble delta
        # on restore -> the delta is double-counted.
        #
        # TO REVERT: delete these 4 lines and uncomment the 4 ORIGINAL lines
        # (the "- delta_x"/"- delta_y" versions) below.
        self.rod_offset_x_mm.put(base_rod_x)
        self.rod_offset_y_mm.put(base_rod_y)
        self.pd_offset_x_mm.put(base_pd_x)
        self.pd_offset_y_mm.put(base_pd_y)
        # ORIGINAL (wobble-corrected) - RESTORE WHEN DONE DEBUGGING:
        # self.rod_offset_x_mm.set(base_rod_x - delta_x)
        # self.rod_offset_y_mm.set(base_rod_y - delta_y)
        # self.pd_offset_x_mm.set(base_pd_x - delta_x)
        # self.pd_offset_y_mm.set(base_pd_y - delta_y)
        # =====================================================================

        # Apply linear correction for sample_offset_z
        linear_coeffs = mdsave.get("saxs_sample_offset_z_linear", None)
        if linear_coeffs is not None:
            slope, intercept = linear_coeffs
            self.sample_offset_z_mm.put(slope * distance + intercept)
        else:
            self.sample_offset_z_mm.put(
                self._interpolate_offset(distance, "sample_offset_z")
            )

        if verbose:
            print(f"\nOffsets for distance {distance:.3f} mm:")
            print(f"  beam_offset_x: {self.beam_offset_x_mm.get():.4f} mm")
            print(f"  beam_offset_y: {self.beam_offset_y_mm.get():.4f} mm")
            print(f"  delta_x: {delta_x:.4f}, delta_y: {delta_y:.4f}")
            print(f"  rod_offset_x: {self.rod_offset_x_mm.get():.4f} mm")
            print(f"  pd_offset_x: {self.pd_offset_x_mm.get():.4f} mm")

    def _distance_key(self, distance):
        """Convert float distance to canonical string key."""
        return f"{float(distance):.6f}"
    
    def _interpolate_offset(self, distance, key, clamp=True):

        cal = mdsave.get("distance_calibration", {})
        if not cal:
            return 0.0

        valid_points = []

        for d_str, offsets in cal.items():
            if key in offsets:
                valid_points.append((float(d_str), offsets[key]))

        if not valid_points:
            return 0.0

        valid_points.sort()

        distances = np.array([p[0] for p in valid_points])
        values = np.array([p[1] for p in valid_points])

        if len(distances) == 1:
            return values[0]

        if clamp:
            if distance <= distances[0]:
                return values[0]
            if distance >= distances[-1]:
                return values[-1]

        return float(np.interp(distance, distances, values))

    def add_calibration_point(self, distance, offsets_dict):
        """
        Add or update a calibration point.
        offset_dict looks like
        {
            "beam_offset_x": 0.12,
            "beam_offset_y": -0.03,
            "rod_offset_x": 0.00,
            "rod_offset_y": 0.01,
            "pd_offset_x": -0.05,
            "pd_offset_y": 0.02,
            "sample_offset_z": 0.10,
        }

        Parameters
        ----------
        distance : float
            Sample distance in mm.
        offsets_dict : dict
            Dictionary of offsets in mm.
        """

        if "distance_calibration" not in mdsave:
            mdsave["distance_calibration"] = {}

        key = self._distance_key(distance)

        mdsave["distance_calibration"][key] = offsets_dict.copy()

        print(f"Added calibration point at {float(key):.3f} mm")
    

    def get_current_offset_dict(self, include_zeros=True):
        """
        Return a dictionary of the current offset values (in mm).

        Parameters
        ----------
        include_zeros : bool
            If False, parameters equal to 0.0 are omitted.
        """

        attr_map = {
            "beam_offset_x": self.beam_offset_x_mm,
            "beam_offset_y": self.beam_offset_y_mm,
            "rod_offset_x": self.rod_offset_x_mm,
            "rod_offset_y": self.rod_offset_y_mm,
            "pd_offset_x": self.pd_offset_x_mm,
            "pd_offset_y": self.pd_offset_y_mm,
            "sample_offset_z": self.sample_offset_z_mm,
        }

        offset_dict = {}

        for key, tk_var in attr_map.items():
            value = float(tk_var.get())

            if include_zeros or abs(value) > 1e-12:
                offset_dict[key] = value

        return offset_dict


def set_energy_cam(cam, en_ev, thresh_ev=None, gain=1):
     
    en = en_ev / 1000 # change to kev
    thresh = thresh_ev / 1000 if thresh_ev is not None else None # change to kev

    if not thresh:
        if en<2 : # invalid energy
            en = 16.1
            gain = 1
        elif en<4:
            gain = 3
        elif en < 7:
            gain = 2
        elif en < 20:
            gain = 1
        else:
            gain = 0    
        if en < 2.6:
            thresh = 1.6
        elif en < 3.5:
            thresh = 1.7
        elif en < 4:
            thresh = 1.8
        elif en < 5:
            thresh = 2

        elif 13 < en < 22 and 'pil900KW' in cam.name: ## avoid the fluoresence from the waxs beamstop
            thresh = 11.5
        else:
            thresh = en/2

    cam.cam_energy.put(en)
    cam.threshold_energy.put(thresh)
    cam.gain_menu.put(gain)
    cam.threshold_apply.put(1)

    cam.energyset.set(en) # store so it remembers on failure and resets
