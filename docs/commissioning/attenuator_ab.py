"""Commissioning draft: MOVE to SWAXS_user_scripts/commissioning when complete.

Load with %run -i .../attenuator_ab.py in the beamline console. Importing this
module constructs no hardware. See README.md for the data model and limitations.
"""

from itertools import combinations
import json
import math

import numpy as np
import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from ophyd import Signal

from smi_beamline.devices import attenuator_data as ad


def _positive(value, name, allow_zero=False):
    value = float(value)
    if not math.isfinite(value) or (value < 0 if allow_zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return value


def _integer(value, name, minimum=1):
    if isinstance(value, bool) or int(value) != value or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return int(value)


def _labels(labels):
    labels = tuple(labels)
    if len(set(labels)) != len(labels) or any(l not in ad.FOIL_LAYOUT for l in labels):
        raise ValueError(f"Unknown or duplicate foil labels: {labels}")
    return tuple(sorted(labels, key=ad._foil_sort_key))


def validate_tests(tests, pairs=5, transmission_min=1e-9, transmission_max=1e-6):
    """Normalize explicit test dicts; validate both total stack transmissions."""
    pairs = _integer(pairs, "pairs")
    lo = _positive(transmission_min, "transmission_min")
    hi = _positive(transmission_max, "transmission_max")
    if not lo < hi <= 1:
        raise ValueError("Require 0 < transmission_min < transmission_max <= 1")
    result, ids = [], set()
    for i, test in enumerate(tests):
        energy = _positive(test["energy_eV"], "energy_eV")
        if not 6000 <= energy <= 20000:
            raise ValueError("Commissioning energies must be within 6000–20000 eV")
        name = str(test.get("id", f"test_{i:03d}"))
        if not name or name in ids:
            raise ValueError("Test IDs must be nonempty and unique")
        ids.add(name)
        a, b = _labels(test["a"]), _labels(test["b"])
        if a == b:
            raise ValueError(f"{name}: A and B must differ")
        transmissions = [ad.transmission(state, energy) for state in (a, b)]
        if any(not lo <= t <= hi for t in transmissions):
            raise ValueError(f"{name}: modeled A/B transmissions {transmissions} outside [{lo}, {hi}]")
        result.append(dict(id=name, energy_eV=energy, a=list(a), b=list(b),
                           pairs=_integer(test.get("pairs", pairs), "pairs"),
                           modeled_a=transmissions[0], modeled_b=transmissions[1]))
    if not result:
        raise ValueError("At least one test is required")
    return result


def make_ab_tests(energies_eV=(6000, 8800, 16000, 19500), *, pairs=5,
                  transmission_min=3e-9, transmission_max=3e-7, max_foils=4):
    """Generate full-rank A/B stack designs; all reference foils are fitted too.

    At each energy A is the brightest allowed stack. Select B states using
    variance-weighted row pivoting, then add independent validation equations.
    No nominal reference thickness is assumed known by the analysis.
    """
    _integer(pairs, "pairs")
    max_foils = _integer(max_foils, "max_foils")
    if max_foils > 4:
        raise ValueError("Preview enumeration is limited to four foils per stack")
    if not 0 < transmission_min < transmission_max <= 1:
        raise ValueError("Invalid transmission bounds")
    labels = list(ad.FOIL_LAYOUT)
    combos = [c for n in range(1, max_foils + 1) for c in combinations(range(24), n)]
    incidence = np.zeros((len(combos), 24))
    for row, combo in zip(incidence, combos):
        row[list(combo)] = 1
    tests = []
    for energy in energies_eV:
        if not math.isfinite(energy) or not 6000 <= energy <= 20000:
            raise ValueError("Energies must be within 6000–20000 eV")
        tau = np.array([ad.foil_optical_depth(l, energy) for l in labels])
        trans = np.exp(-(incidence @ tau))
        valid = (trans >= transmission_min) & (trans <= transmission_max)
        rows, trans = incidence[valid], trans[valid]
        active = np.any(rows, axis=0)
        if not len(rows):
            raise ValueError(f"No allowed stacks at {energy} eV")
        ref = int(np.argmax(trans))
        design = rows - rows[ref]
        weighted = design[:, active] / np.sqrt(1 / trans[:, None] + 1 / trans[ref])
        residual = weighted.copy()
        chosen = []
        for _ in range(int(active.sum())):
            norms = np.einsum("ij,ij->i", residual, residual)
            j = int(np.argmax(norms))
            if norms[j] < 1e-20:
                raise ValueError(f"No identifiable design at {energy} eV with these bounds")
            chosen.append(j)
            q = residual[j] / np.sqrt(norms[j])
            residual -= np.outer(residual @ q, q)
        information = weighted[chosen].T @ weighted[chosen]
        for _ in range(int(active.sum())):
            covariance = np.linalg.inv(information)
            score = np.einsum("ij,jk,ik->i", weighted, covariance, weighted)
            score[chosen + [ref]] = -1
            j = int(np.argmax(score))
            if score[j] <= 0:
                break
            chosen.append(j)
            information += np.outer(weighted[j], weighted[j])
        for n, j in enumerate(chosen):
            tests.append(dict(id=f"E{energy:g}_{n:03d}", energy_eV=energy,
                              a=[l for l, v in zip(labels, rows[ref]) if v],
                              b=[l for l, v in zip(labels, rows[j]) if v], pairs=pairs))
    return validate_tests(tests, pairs, transmission_min, transmission_max)


def preview_ab(tests, *, pairs=5, exposure_s=5, dark_frames=3,
               sensitivity_wait_s=20, foil_settle_s=0.5,
               transmission_min=1e-9, transmission_max=1e-6,
               energy_move_s=180, stack_move_s=4, shutter_cycle_s=1,
               readout_s=0.2, geometry_s=30):
    """Pure preview, with explicit estimated overheads; never resolves live devices."""
    tests = validate_tests(tests, pairs, transmission_min, transmission_max)
    exposure_s = _positive(exposure_s, "exposure_s")
    dark_frames = _integer(dark_frames, "dark_frames", 1)
    costs = dict(sensitivity_wait_s=sensitivity_wait_s, foil_settle_s=foil_settle_s,
                 energy_move_s=energy_move_s, stack_move_s=stack_move_s,
                 shutter_cycle_s=shutter_cycle_s, readout_s=readout_s, geometry_s=geometry_s)
    costs = {k: _positive(v, k, allow_zero=True) for k, v in costs.items()}
    energies = list(dict.fromkeys(t["energy_eV"] for t in tests))
    n_pairs = sum(t["pairs"] for t in tests)
    frames = 2 * n_pairs + len(energies) * dark_frames
    exposure = frames * exposure_s
    overhead = (frames * costs["readout_s"] + 2 * n_pairs * (
        costs["stack_move_s"] + costs["foil_settle_s"] + costs["shutter_cycle_s"])
        + len(energies) * (costs["energy_move_s"] + 2 * costs["sensitivity_wait_s"])
        + costs["geometry_s"])
    report = dict(tests=tests, energies_eV=energies, n_tests=len(tests), n_pairs=n_pairs,
                  frames=frames, exposure_seconds=exposure, overhead_seconds=overhead,
                  estimated_seconds=exposure + overhead, estimated_minutes=(exposure + overhead)/60,
                  estimate_assumptions=costs, dark_frames=dark_frames, exposure_s=exposure_s)
    print(f"{len(tests)} tests, {n_pairs} A/B pairs, {frames} frames: "
          f"{exposure/60:.1f} min exposure; ~{report['estimated_minutes']:.1f} min total. "
          "Energy tracking, foil retries and suspender waits may extend this.")
    return report


def summarize_test(test, observations, dark_counts):
    """Mean log(A/B), uncertainty floored by counting noise, common-dark derivative."""
    dark = float(np.mean(dark_counts))
    dark_var = max(dark / len(dark_counts),
                   float(np.var(dark_counts, ddof=1) / len(dark_counts)) if len(dark_counts)>1 else 0)
    a, b = np.array(observations, dtype=float).T
    if np.any(a <= dark) or np.any(b <= dark):
        raise RuntimeError(f"{test['id']}: signal is not above measured dark")
    logs = np.log(a-dark) - np.log(b-dark)
    n = len(logs)
    shot_var = float(np.sum(a/(a-dark)**2 + b/(b-dark)**2) / n**2)
    empirical = float(np.var(logs, ddof=1)/n) if n > 1 else 0
    independent = max(shot_var, empirical)
    gradient = float(np.mean(1/(b-dark) - 1/(a-dark)))
    variance = independent + gradient**2 * dark_var
    depth = float(np.mean(logs))
    ratio = math.exp(-depth)
    return dict(test_id=test["id"], energy_eV=test["energy_eV"], pairs=n,
                delta_optical_depth=depth, delta_optical_depth_sigma=math.sqrt(variance),
                transmission_ratio=ratio, transmission_ratio_sigma=ratio*math.sqrt(variance),
                independent_variance=independent, dark_gradient=gradient,
                dark_variance=dark_var, dark_counts=dark)


def fit_foils(tests, summaries):
    """GLS optical-depth fit at each energy, retaining shared dark covariance.

    Unidentifiable individual foils are reported separately, never assigned a
    nominal value. Returned covariance matrices support subsequent energy fits.
    """
    labels = list(ad.FOIL_LAYOUT)
    by_id = {t["id"]: t for t in tests}
    results, diagnostics = [], []
    for energy in dict.fromkeys(s["energy_eV"] for s in summaries):
        ss = [s for s in summaries if s["energy_eV"] == energy]
        x = np.array([[int(l in by_id[s["test_id"]]["b"]) -
                       int(l in by_id[s["test_id"]]["a"]) for l in labels] for s in ss], float)
        y = np.array([s["delta_optical_depth"] for s in ss])
        g = np.array([s["dark_gradient"] for s in ss])
        c = np.diag([s["independent_variance"] for s in ss]) + np.outer(g,g)*ss[0]["dark_variance"]
        chol = np.linalg.cholesky(c)
        w, z = np.linalg.solve(chol, x), np.linalg.solve(chol, y)
        u, singular, vt = np.linalg.svd(w, full_matrices=True)
        rank = int(np.sum(singular > (singular[0]*1e-10 if len(singular) else 0)))
        basis = vt[:rank].T
        tau = basis @ ((u[:, :rank].T @ z) / singular[:rank])
        covariance = (basis / singular[:rank]**2) @ basis.T
        identifiable = np.sum(vt[rank:]**2, axis=0) < 1e-12
        chi2 = float(np.sum((w@tau-z)**2))
        dof = len(y)-rank
        inflation = max(1., chi2/dof) if dof > 0 else 1.
        covariance *= inflation
        diagnostics.append(dict(energy_eV=energy, rank=rank, equations=len(y),
                                chi_squared=chi2, dof=dof, covariance=covariance.tolist(),
                                labels=labels, unidentifiable=[l for l,v in zip(labels,identifiable) if not v]))
        for i, label in enumerate(labels):
            if not identifiable[i]:
                continue
            base, multiple = ad.FOIL_LAYOUT[label]
            nominal_um = ad.BASE_FOILS[base]["thickness_um"]*multiple
            nominal_tau = ad.foil_optical_depth(label, energy)
            sigma = math.sqrt(max(0., covariance[i,i]))
            valid = bool(tau[i] > 0 and tau[i] < 700)
            t = math.exp(-float(tau[i])) if valid else -1.
            results.append(dict(foil=label, energy_eV=energy, optical_depth=float(tau[i]),
                                optical_depth_sigma=sigma, transmission=t,
                                transmission_sigma=t*sigma if valid else -1., attenuation_factor=1/t if valid else -1.,
                                attenuation_factor_sigma=sigma/t if valid else -1.,
                                effective_thickness_um=float(tau[i]/nominal_tau*nominal_um),
                                thickness_sigma_um=sigma/nominal_tau*nominal_um,
                                thickness_scale=float(tau[i]/nominal_tau),
                                thickness_scale_sigma=sigma/nominal_tau,
                                valid=valid, fit_reduced_chi_squared=chi2/dof if dof else -1.))
    return results, diagnostics


def _resolve(name, value):
    if value is not None:
        return value
    from IPython import get_ipython
    ip = get_ipython()
    if ip is not None and name in ip.user_ns:
        return ip.user_ns[name]
    raise ValueError(f"Supply {name}, or load this plan in the live beamline namespace")


def _poll(signal, predicate, *, timeout=10, interval=0.25, description="readback"):
    for _ in range(math.ceil(timeout/interval)+1):
        value = yield from bps.rd(signal)
        if predicate(value):
            return value
        yield from bps.sleep(interval)
    raise RuntimeError(f"{description} did not confirm: {value!r}")


def _fast_shutter(fs, opened):
    yield from bps.abs_set(fs.open_cpt if opened else fs.close_cpt, 1, wait=True)
    yield from _poll(fs.status_pv, lambda v: float(v) == (0 if opened else 7),
                     description="fast shutter")


def _sensitivity(detector, energy_eV, wait_s=20, attempts=3):
    """Message-based set_energy_cam equivalent for pil2M, with delayed reapply."""
    en = energy_eV/1000
    gain = 2 if en < 7 else (1 if en < 20 else 0)
    threshold = en/2
    last = None
    for attempt in range(attempts):
        # Apply ONLY after all parameter writes have completed.
        # These detector-level aliases are setpoint-only EpicsSignals. Waiting on
        # the camera SignalWithRBV here could deadlock before ThresholdApply.
        yield from bps.mv(detector.cam_energy, en, detector.threshold, threshold,
                          detector.gain, gain)
        yield from bps.abs_set(detector.apply, 1, wait=True)
        yield from bps.abs_set(detector.cam.energyset, en, wait=True)
        yield from bps.sleep(wait_s)
        last = [(yield from bps.rd(detector.energy_read)),
                (yield from bps.rd(detector.threshold_read)),
                (yield from bps.rd(detector.gain_read))]
        ready = (abs(float(last[0])-en) <= .05 and abs(float(last[1])-threshold) <= .05
                 and float(last[2]) == gain)
        # Always do the requested second set/wait, even if first RBVs look right.
        if attempt >= 1 and ready:
            yield from _poll(detector.cam.detector_state, lambda v: str(v) in ("0", "Idle"),
                             description="Pilatus idle")
            return dict(energy_keV=en, threshold_keV=threshold, gain=gain, attempts=attempt+1)
    raise RuntimeError(f"Pilatus sensitivity failed to confirm after {attempts} writes: {last}")


class _EventFields:
    def __init__(self, prefix, values):
        self.signals = {k: Signal(name=f"{prefix}_{k}", value=v) for k,v in values.items()}

    def update(self, values):
        for k,v in values.items():
            yield from bps.abs_set(self.signals[k], v, wait=True)

    def emit(self, stream, values):
        yield from self.update(values)
        yield from bps.create(name=stream)
        for signal in self.signals.values():
            yield from bps.read(signal)
        yield from bps.save()


def beam_roi_layout(center, detector_size, beam_size=(128, 64), side_size=(128, 128), gap=16):
    """Three nonoverlapping rectangles in full-camera pixels; never silently clip."""
    bw, bh = [_integer(v, "beam_size") for v in beam_size]
    sw, sh = [_integer(v, "side_size") for v in side_size]
    gap = _integer(gap, "side_gap_px", 0)
    cx, cy = center
    x, y = round(cx-bw/2), round(cy-bh/2)
    rectangles = [(x,y,bw,bh), (x-gap-sw,round(cy-sh/2),sw,sh),
                  (x+bw+gap,round(cy-sh/2),sw,sh)]
    width, height = detector_size
    if any(x<0 or y<0 or x+w>width or y+h>height for x,y,w,h in rectangles):
        raise ValueError(f"Beam/side ROIs exceed camera bounds {detector_size}: {rectangles}")
    return rectangles


def summarize_shape(test, observations, dark, roi_areas):
    """Paired B-minus-A shape/background proxies, not a surface-roughness fit.

    Moment errors use measured repeat scatter only. Normalized side signals use
    counting variance, repeat scatter, and shared side/core dark uncertainty.
    """
    n = len(observations)
    result = dict(test_id=test["id"], energy_eV=test["energy_eV"], pairs=n)
    for key in ("centroid_x_px", "centroid_y_px", "sigma_x_px", "sigma_y_px", "sigma_xy_px2"):
        valid = all(a["shape_valid"] and b["shape_valid"] for a,b in observations)
        a = np.array([a[key] for a,b in observations])
        b = np.array([b[key] for a,b in observations])
        result[key+"_a"] = float(a.mean()) if valid else -1.
        result[key+"_b"] = float(b.mean()) if valid else -1.
        result[key+"_delta"] = float((b-a).mean()) if valid else -1.
        result[key+"_delta_sem"] = float(np.std(b-a,ddof=1)/np.sqrt(n)) if valid and n>1 else -1.
        if key in ("sigma_x_px", "sigma_y_px"):
            d = b*b-a*a
            result[key+"_variance_delta"] = float(d.mean()) if valid else -1.
            result[key+"_variance_delta_sem"] = float(np.std(d,ddof=1)/np.sqrt(n)) if valid and n>1 else -1.
    result["moments_valid"] = bool(valid)
    result["moment_sem_valid"] = bool(valid and n>1)
    for side in ("left", "right"):
        core_dark = np.array([d["raw_counts"] for d in dark])
        side_dark = np.array([d[side+"_counts"] for d in dark])
        dc, ds = core_dark.mean(), side_dark.mean()
        vc = max(dc/len(dark), np.var(core_dark,ddof=1)/len(dark) if len(dark)>1 else 0)
        vs = max(ds/len(dark), np.var(side_dark,ddof=1)/len(dark) if len(dark)>1 else 0)
        vals, variances, gradients = [], [], []
        area = roi_areas[side]
        for a,b in observations:
            row, vr, gr = [], [], []
            for f in (a,b):
                c, s = f["raw_counts"]-dc, f[side+"_counts"]-ds
                if c <= 0:
                    raise RuntimeError("Core not above dark in shape analysis")
                row.append(s/c/area)
                vr.append((f[side+"_counts"]/c**2 + s*s*f["raw_counts"]/c**4)/area**2)
                gr.append(np.array([-1/c, s/c**2])/area)
            vals.append(row)
            variances.append(sum(vr))
            gradients.append(gr[1]-gr[0])
        vals = np.array(vals)
        delta = vals[:,1]-vals[:,0]
        g = np.mean(gradients,axis=0)
        variance = max(sum(variances)/n**2, np.var(delta,ddof=1)/n if n>1 else 0)
        variance += g[0]**2*vs + g[1]**2*vc
        result[side+"_per_pixel_per_core_a"] = float(vals[:,0].mean())
        result[side+"_per_pixel_per_core_b"] = float(vals[:,1].mean())
        result[side+"_per_pixel_per_core_delta"] = float(delta.mean())
        result[side+"_per_pixel_per_core_delta_sem"] = float(np.sqrt(variance))
    return result


def attenuator_ab_calibration(tests=None, *, pairs=5, exposure_s=5, dark_frames=3,
                             dry_run=False, sensitivity_wait_s=20, sensitivity_attempts=3,
                             foil_settle_s=0.5, max_pixel_rate=1e6,
                             transmission_min=1e-9, transmission_max=1e-6,
                             estimate_overheads=None, detector=None, energy=None,
                             attenuators1=None, attenuators2=None, fs=None, smi=None,
                             tracked_energy_move=None, beam_shape=True,
                             beam_roi_size=(128,64), side_roi_size=(128,128),
                             side_gap_px=16, centroid_threshold=0., md=None):
    """One-run A/B calibration; returns UID, ratios, per-foil fits and diagnostics.

    Default designs cover all 24 positions at >=2 energies. ``tests`` can instead
    be explicit dictionaries: id, energy_eV, a, b, pairs. A/B order alternates AB,
    BA across repeats. ``dry_run=True`` performs no device lookup, reads or writes.
    """
    if tests is None:
        tests = make_ab_tests(pairs=pairs)
    report = preview_ab(tests, pairs=pairs, exposure_s=exposure_s, dark_frames=dark_frames,
                        sensitivity_wait_s=sensitivity_wait_s, foil_settle_s=foil_settle_s,
                        transmission_min=transmission_min, transmission_max=transmission_max,
                        **(estimate_overheads or {}))
    _positive(max_pixel_rate, "max_pixel_rate")
    _integer(sensitivity_attempts, "sensitivity_attempts", 2)
    _positive(centroid_threshold, "centroid_threshold", allow_zero=True)
    # Validate sizes without live geometry, including in dry-run mode.
    beam_roi_layout((10000,10000),(20000,20000),beam_roi_size,side_roi_size,side_gap_px)
    if dry_run:
        return report
    detector = _resolve("pil2M", detector)
    energy = _resolve("energy", energy)
    banks = [_resolve("attenuators1", attenuators1), _resolve("attenuators2", attenuators2)]
    fs, smi = _resolve("fs", fs), _resolve("smi", smi)
    tracked_energy_move = _resolve("energy_walk", tracked_energy_move)
    tests = report["tests"]
    summaries, results, diagnostics = [], [], []
    shape_summaries = []
    raw = _EventFields("ab", dict(test_id="", pair=0, state="", energy_eV=0.,
                                 actual_energy_eV=0., labels="", exposure_s=float(exposure_s),
                                 modeled_transmission=0., raw_counts=0., max_pixel_rate=0., saturated=False))
    settings = _EventFields("sensitivity", dict(energy_eV=0., energy_keV=0., threshold_keV=0., gain=0, attempts=0))
    fit_fields = _EventFields("fit", dict(energy_eV=0., rank=0, equations=0, dof=0,
                                        chi_squared=0., labels="", unidentifiable="", covariance_json=""))
    summary_fields = None
    result_fields = None
    geometry_started = False
    shape_fields = _EventFields("shape", dict(centroid_x_px=0.,centroid_y_px=0.,sigma_x_px=0.,
        sigma_y_px=0.,sigma_xy_px2=0.,shape_valid=False,left_counts=0.,right_counts=0.,
        left_counts_per_s_per_pixel=0.,right_counts_per_s_per_pixel=0.))
    roi_fields = _EventFields("roi", dict(energy_eV=0.,roi_index=0,x=0,y=0,width=0,height=0,
                                         centroid_threshold=float(centroid_threshold)))
    shape_summary_fields = None
    rectangles = None

    def configure_shape(en):
        nonlocal rectangles
        # smi's beam position/geometry is the center; no recentering between A and B.
        r = detector.roi1
        cx = (yield from bps.rd(r.min_xyz.min_x)) + (yield from bps.rd(r.size.x))/2
        cy = (yield from bps.rd(r.min_xyz.min_y)) + (yield from bps.rd(r.size.y))/2
        width = yield from bps.rd(detector.cam.array_size.array_size_x)
        height = yield from bps.rd(detector.cam.array_size.array_size_y)
        rectangles = beam_roi_layout((cx,cy),(width,height),beam_roi_size,side_roi_size,side_gap_px)
        port = yield from bps.rd(detector.cam.port_name)
        for i,(x,y,w,h) in enumerate(rectangles,1):
            roi, stats = getattr(detector,f"roi{i}"), getattr(detector,f"stats{i}")
            yield from bps.mv(roi.nd_array_port,port,roi.enable,1,roi.blocking_callbacks,1,
                              roi.min_xyz.min_x,x,roi.min_xyz.min_y,y,roi.size.x,w,roi.size.y,h,
                              roi.bin_.x,1,roi.bin_.y,1,roi.reverse.x,0,roi.reverse.y,0,
                              roi.roi_enable.x,1,roi.roi_enable.y,1,roi.enable_scale,0)
            for signal,want in ((roi.min_xyz.min_x,x),(roi.min_xyz.min_y,y),(roi.size.x,w),(roi.size.y,h)):
                yield from _poll(signal,lambda v: v==want,description="ROI geometry")
            roi_port = yield from bps.rd(roi.port_name)
            yield from bps.mv(stats.nd_array_port,roi_port,stats.enable,1,
                              stats.compute_statistics,1,stats.blocking_callbacks,1)
            if i==1:
                yield from bps.mv(stats.compute_centroid,1,stats.centroid_threshold,centroid_threshold)
            yield from roi_fields.emit("roi_settings",dict(energy_eV=en,roi_index=i,x=x,y=y,width=w,height=h))

    def exact(labels):
        yield from _fast_shutter(fs, False)
        for bank, prefix in zip(banks, ("1", "2")):
            want = ["f"+l.split("_")[1] for l in labels if l.startswith(prefix+"_")]
            yield from bps.mv(bank, want)
        yield from bps.sleep(foil_settle_s)
        actual = []
        for bank, prefix in zip(banks, ("1", "2")):
            for i in range(1,13):
                foil = getattr(bank, f"f{i}")
                value = yield from bps.rd(foil.status)
                if value == foil.open_val:
                    actual.append(f"{prefix}_{i}")
                elif value != foil.close_val:
                    raise RuntimeError(f"Unknown foil state {prefix}_{i}: {value}")
        if _labels(actual) != _labels(labels):
            raise RuntimeError(f"Foil readbacks {actual} differ from requested {labels}")

    def frame(test, pair, state, *, dark=False):
        labels = test["a"] if state == "A" else test["b"]
        if not dark:
            yield from exact(labels)
        actual_energy = float((yield from bps.rd(energy.energy.readback)))
        if abs(actual_energy-test["energy_eV"]) > 2:
            raise RuntimeError("Energy readback differs from test energy")
        modeled = ad.transmission(labels, actual_energy)
        if not transmission_min <= modeled <= transmission_max:
            raise RuntimeError("Stack outside transmission bounds at measured energy")
        old_id = yield from bps.rd(detector.cam.array_counter)
        watched = [detector.stats1,detector.stats5]
        if beam_shape:
            watched += [detector.stats2,detector.stats3]
        old_stats_ids = []
        for stats in watched:
            old_stats_ids.append((yield from bps.rd(stats.unique_id)))
        if not dark:
            yield from _fast_shutter(fs, True)
        try:
            yield from bps.trigger(detector, group="ab_frame")
            yield from bps.wait(group="ab_frame")
        finally:
            yield from _fast_shutter(fs, False)
        new_id = yield from bps.rd(detector.cam.array_counter)
        if new_id == old_id:
            raise RuntimeError("Camera did not produce a fresh frame")
        # Camera array counters can be reset independently of NDArray unique IDs.
        ids = []
        for stats, old in zip(watched, old_stats_ids):
            ids.append((yield from _poll(stats.unique_id, lambda v: v != old,
                                         description="fresh statistics")))
        if len(set(ids)) != 1:
            raise RuntimeError("Statistics refer to different frames")
        counts = float((yield from bps.rd(detector.stats1.total)))
        maximum = float((yield from bps.rd(detector.stats5.max_value)))
        duration = float((yield from bps.rd(detector.cam.acquire_time)))
        if abs(duration-exposure_s) > 1e-6:
            raise RuntimeError("Exposure time changed during calibration")
        if not all(math.isfinite(v) and v >= 0 for v in (counts, maximum)):
            raise RuntimeError("Invalid raw statistics")
        rate = maximum/duration
        saturated = rate >= max_pixel_rate
        values = dict(test_id=test["id"], pair=pair, state="dark" if dark else state,
                      energy_eV=test["energy_eV"], actual_energy_eV=actual_energy,
                      labels=",".join(labels), modeled_transmission=modeled,
                      raw_counts=counts, max_pixel_rate=rate, saturated=saturated)
        yield from raw.update(values)
        shape = {}
        if beam_shape:
            signals = dict(centroid_x_px=detector.stats1.centroid.x,centroid_y_px=detector.stats1.centroid.y,
                           sigma_x_px=detector.stats1.sigma_x,sigma_y_px=detector.stats1.sigma_y,
                           sigma_xy_px2=detector.stats1.sigma_xy,left_counts=detector.stats2.total,
                           right_counts=detector.stats3.total)
            for key,signal in signals.items():
                shape[key] = float((yield from bps.rd(signal)))
            valid = all(math.isfinite(v) for v in shape.values())
            valid = valid and shape["sigma_x_px"]>=0 and shape["sigma_y_px"]>=0 and not dark
            valid = valid and 0<=shape["centroid_x_px"]<rectangles[0][2] and 0<=shape["centroid_y_px"]<rectangles[0][3]
            for side in ("left","right"):
                if not math.isfinite(shape[side+"_counts"]) or shape[side+"_counts"]<0:
                    raise RuntimeError("Invalid side ROI counts")
            shape = {k:v if math.isfinite(v) else -1. for k,v in shape.items()}
            shape["centroid_x_px"] += rectangles[0][0]
            shape["centroid_y_px"] += rectangles[0][1]
            shape["shape_valid"] = bool(valid)
            for side,rect in zip(("left","right"),rectangles[1:]):
                shape[side+"_counts_per_s_per_pixel"] = shape[side+"_counts"]/(duration*rect[2]*rect[3])
            yield from shape_fields.update(shape)
        yield from bps.create(name="dark" if dark else "primary")
        yield from bps.read(detector)  # preserves TIFF asset documents and raw stats
        yield from bps.read(energy)
        for signal in raw.signals.values():
            yield from bps.read(signal)
        if beam_shape:
            for signal in shape_fields.signals.values():
                yield from bps.read(signal)
        yield from bps.save()
        if saturated:
            raise RuntimeError(f"Pixel rate {rate:g}/s >= {max_pixel_rate:g}/s; frame recorded as saturated")
        return dict(raw_counts=counts,**shape)

    def body():
        nonlocal geometry_started, summary_fields, result_fields, shape_summary_fields
        yield from _fast_shutter(fs, False)
        geometry_started = True
        yield from smi.modeAlignment(technique="gisaxs")
        # Explicit full-frame saturation channel and the normal direct-beam ROI.
        port = yield from bps.rd(detector.cam.port_name)
        roi_port = yield from bps.rd(detector.roi1.port_name)
        yield from bps.mv(detector.roi1.nd_array_port, port, detector.roi1.enable, 1,
                          detector.stats1.nd_array_port, roi_port,
                          detector.stats5.nd_array_port, port)
        for stats in (detector.stats1, detector.stats5):
            yield from bps.mv(stats.enable, 1, stats.compute_statistics, 1,
                              stats.blocking_callbacks, 1)
        for en in report["energies_eV"]:
            yield from _fast_shutter(fs, False)
            print(f"A/B calibration: tracked energy move to {en:g} eV")
            yield from tracked_energy_move(en)
            setup = yield from _sensitivity(detector, en, sensitivity_wait_s, sensitivity_attempts)
            yield from settings.emit("detector_settings", dict(energy_eV=en, **setup))
            yield from smi.setDirectBeamROI(technique="gisaxs")
            if beam_shape:
                yield from configure_shape(en)
            subset = [t for t in tests if t["energy_eV"] == en]
            yield from exact(subset[0]["a"])
            dark = []
            for i in range(dark_frames):
                dark.append((yield from frame(subset[0], i, "A", dark=True)))
            for test in subset:
                observations = []
                for pair in range(test["pairs"]):
                    counts = {}
                    for state in ("AB" if pair % 2 == 0 else "BA"):
                        counts[state] = yield from frame(test, pair, state)
                    observations.append((counts["A"], counts["B"]))
                summary = summarize_test(test, [(a["raw_counts"],b["raw_counts"]) for a,b in observations],
                                         [d["raw_counts"] for d in dark])
                summaries.append(summary)
                if summary_fields is None:
                    summary_fields = _EventFields("ratio", summary)
                yield from summary_fields.emit("ab_summary", summary)
                if beam_shape:
                    shape_summary = summarize_shape(test,observations,dark,
                        dict(left=rectangles[1][2]*rectangles[1][3],right=rectangles[2][2]*rectangles[2][3]))
                    shape_summaries.append(shape_summary)
                    if shape_summary_fields is None:
                        shape_summary_fields = _EventFields("shape_test",shape_summary)
                    yield from shape_summary_fields.emit("shape_summary",shape_summary)
            fitted, diag = fit_foils(subset, [s for s in summaries if s["energy_eV"] == en])
            results.extend(fitted)
            diagnostics.extend(diag)
            for result in fitted:
                if result_fields is None:
                    result_fields = _EventFields("foil", result)
                yield from result_fields.emit("foil_summary", result)
                print(f"att{result['foil']} @ {en:g} eV: T={result['transmission']:.5g} "
                      f"+/- {result['transmission_sigma']:.2g}; "
                      f"t={result['effective_thickness_um']:.4g} +/- {result['thickness_sigma_um']:.2g} um")
            for item in diag:
                yield from fit_fields.emit("fit_diagnostics", dict(
                    energy_eV=en, rank=item["rank"], equations=item["equations"],
                    dof=item["dof"], chi_squared=item["chi_squared"],
                    labels=",".join(item["labels"]), unidentifiable=",".join(item["unidentifiable"]),
                    covariance_json=json.dumps(item["covariance"])))
                print(f"Fit rank {item['rank']}; unresolved: {item['unidentifiable']}")

    def cleanup():
        # Fail closed. Never restore an open shutter or retract foils during cleanup.
        yield from _fast_shutter(fs, False)
        if geometry_started:
            yield from detector.restore_beamstop()

    def prepared_body():
        yield from _fast_shutter(fs, False)
        yield from _poll(detector.cam.detector_state, lambda v: str(v) in ("0", "Idle"),
                         description="Pilatus idle before setup")
        # FileStore captures frames_per_point when staged: timing must precede stage.
        for _ in range(2):
            yield from bps.mv(detector.cam.acquire_time, exposure_s,
                              detector.cam.acquire_period, exposure_s+.01,
                              detector.cam.num_images, 1)
        yield from _poll(detector.cam.num_images, lambda v: int(v) == 1,
                         description="single frame per trigger")
        yield from bps.mv(detector.cam.image_mode, 0, detector.cam.trigger_mode, 0)
        return (yield from bpp.stage_wrapper(body(), [detector]))

    run_md = dict(md or {})
    run_md.update(plan_name="attenuator_ab_calibration", commissioning_destination="SWAXS_user_scripts",
                  ab_tests=tests, exposure_s=exposure_s, dark_frames=dark_frames,
                  sensitivity_wait_s=sensitivity_wait_s, max_pixel_rate=max_pixel_rate,
                  transmission_bounds=[transmission_min, transmission_max],
                  analysis_model="monoenergetic log-ratio GLS; counting floor + repeat scatter + shared dark",
                  foil_layout={k: list(v) for k,v in ad.FOIL_LAYOUT.items()},
                  estimated_seconds=report["estimated_seconds"])
    run_md.update(beam_shape=beam_shape,beam_roi_size=list(beam_roi_size),side_roi_size=list(side_roi_size),
                  side_gap_px=side_gap_px,centroid_threshold=centroid_threshold,
                  shape_interpretation="paired broadening and side background proxies; not surface roughness")
    # stage_wrapper also unstages on failures; run_wrapper records failed stop docs.
    uid = yield from bpp.run_wrapper(bpp.finalize_wrapper(prepared_body(), cleanup()), md=run_md)
    return dict(uid=uid, ab_summary=summaries, foil_summary=results, fit_diagnostics=diagnostics,
                shape_summary=shape_summaries)
