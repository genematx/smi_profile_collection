"""Versioned effective-thickness correction, independent of the nominal CXRO tables.

Source: Tiled smi/raw, foil_summary of scan 1171324. Values below are micrometres
and one-standard-error uncertainties, already inflated by each energy fit's
reduced chi-square. Combine each foil's marginal estimates independently; no
claim of independent errors between different foils is made.
"""

from math import sqrt

CALIBRATION_ID = "smi-attenuators-1171327-v2"
SOURCE_UID = "7cd58d5e-7f31-4fe4-b64f-aad0bde951db"
ENERGIES_EV = (16000, 19500)
AGREEMENT_SIGMA = 3.0

# foil: (thickness at 16 keV, sigma, thickness at 19.5 keV, sigma)
MEASUREMENTS_UM = {
    "1_1": (62.202026757, .124687628, 62.206062917, .264606336),
    "1_2": (125.149572693, .244191381, 125.305280087, .486668052),
    "1_3": (250.226978031, .478318372, 250.565501407, .900087473),
    "1_5": (67.988325438, .124133762, 68.042189203, .308633230),
    "1_6": (138.473071070, .217570078, 137.884395364, .456406237),
    "1_7": (271.609579156, .445286433, 271.547239907, .870739359),
    "1_8": (580.123806850, .908617574, 580.677151896, 1.467709138),
    "1_9": (32.330324642, .080700348, 32.802022138, .224675360),
    "1_10": (68.544282315, .114099473, 68.385011305, .291628869),
    "1_11": (135.344337741, .224031367, 135.209602677, .451826532),
    "1_12": (272.331974808, .438857359, 272.503597995, .872554307),
    "2_1": (20.160492299, .060785761, 20.003075804, .244071630),
    "2_2": (40.671777569, .091558271, 39.989725902, .244721756),
    "2_3": (81.075460347, .159587876, 79.531451361, .374494009),
    "2_4": (182.633435530, .285801166, 179.808976644, .638862875),
    "2_5": (112.206968655, 1.065372629, 109.279384460, 3.443753499),
    "2_7": (437.733208546, 1.063952248, 443.847489719, 4.720561235),
    "2_8": (880.742371526, 1.520496691, 882.639105203, 4.998954659),
    "2_9": (9.164932749, 1.087738545, 14.504928751, 3.842292147),
    "2_10": (18.797983664, 1.166067066, 21.805352131, 3.647621550),
    "2_11": (41.328126112, .784368104, 40.652698190, 3.110596429),
    "2_12": (56.506706940, 1.302892274, 56.192439886, 3.729305949),
}


def combine(a, sa, b, sb):
    """Marginal inverse-variance mean with two-point scatter inflation."""
    z = abs(a-b) / sqrt(sa*sa + sb*sb)
    weight = 1/sa**2 + 1/sb**2
    return {"effective_thickness_um": (a/sa**2 + b/sb**2)/weight,
            "thickness_sigma_um": sqrt(max(1., z*z)/weight),
            "agreement_z": z, "accepted": a > 0 and b > 0 and z <= AGREEMENT_SIGMA}


RESULTS = {label: combine(*values) for label, values in MEASUREMENTS_UM.items()}
ACCEPTED = {label: result for label, result in RESULTS.items() if result["accepted"]}

# Follow-up scan 1171325 used unchanged references plus one target foil.
# Retain the original 19.5 keV disagreement separately from the adopted 16–17
# keV estimate below. Al 2_6 is explicitly adopted as a single-energy baseline.
FOLLOWUP_SOURCE_UID = "4348a125-4a82-414e-9c5c-15c1513303e7"
FOLLOWUP_MEASUREMENTS_UM = {
    "2_3": (80.864874228, .069285489, 80.081459635, .198609586),
    "2_4": (181.949508589, .208323134, 180.192981610, .349200249),
}
FOLLOWUP_RESULTS = {label: combine(*values) for label, values in FOLLOWUP_MEASUREMENTS_UM.items()}
FOLLOWUP_SINGLE_ENERGY_UM = {"2_6": {16000: (219.115923040, .550377025)}}
INTERMEDIATE_SOURCE_UID = "c6c85ff7-a83f-46ba-a7d6-208faab3087f"
REPEAT_SOURCE_UID = "b5c3729a-6c7f-4eef-ae77-107f4dab8393"
# (run UID, energy eV, thickness um, standard error um)
LOW_ENERGY_MEASUREMENTS = {
    "2_3": (
        (FOLLOWUP_SOURCE_UID, 16000, 80.86487422831703, .06928548929655229),
        (INTERMEDIATE_SOURCE_UID, 16500, 80.71467988679669, .10375238693718658),
        (INTERMEDIATE_SOURCE_UID, 17000, 80.78494691116069, .06898675117480195),
        (REPEAT_SOURCE_UID, 17000, 80.79405240958587, .06899632916748646),
    ),
    "2_4": (
        (FOLLOWUP_SOURCE_UID, 16000, 181.9495085888787, .20832313383275008),
        (INTERMEDIATE_SOURCE_UID, 16500, 181.78085902938565, .28141376918214356),
        (INTERMEDIATE_SOURCE_UID, 17000, 182.05041700585247, .1845053224608939),
        (REPEAT_SOURCE_UID, 17000, 181.7385769970181, .17055908955826443),
    ),
}

for _label, _result in ACCEPTED.items():
    _result.update(source_uids=[SOURCE_UID], energies_eV=list(ENERGIES_EV),
                   basis="16/19.5 keV agreement")

for _label, _measurements in LOW_ENERGY_MEASUREMENTS.items():
    _weight = sum(1/s**2 for _, _, t, s in _measurements)
    _mean = sum(t/s**2 for _, _, t, s in _measurements)/_weight
    _chi = sum(((t-_mean)/s)**2 for _, _, t, s in _measurements)
    _reduced_chi = _chi/(len(_measurements)-1)
    ACCEPTED[_label] = dict(effective_thickness_um=_mean,
        thickness_sigma_um=sqrt(max(1., _reduced_chi)/_weight), accepted=True,
        reduced_chi_squared=_reduced_chi,
        source_uids=list(dict.fromkeys(uid for uid, _, _, _ in _measurements)),
        energies_eV=sorted({e for _, e, _, _ in _measurements}),
        basis="16–17 keV follow-ups; 19.5 keV disagreement retained")

ACCEPTED["2_6"] = dict(effective_thickness_um=219.11592304045496,
    thickness_sigma_um=.5503770250539165, accepted=True,
    source_uids=[FOLLOWUP_SOURCE_UID], energies_eV=[16000],
    basis="single-energy 16 keV baseline; insertion unreliable")

UNRESOLVED = {
    "1_4": "Only 19.5 keV is usable (563.065410 +/- 1.608679 um); no high-energy cross-check",
}
REMAINING_ISSUES = {
    **UNRESOLVED,
    "2_3": "16 / 19.5 keV disagreement persists: 3.79 sigma initially, 3.72 sigma in follow-up",
    "2_4": "16 / 19.5 keV disagreement persists: 4.04 sigma initially, 4.32 sigma in follow-up",
    "2_6": "Follow-up: 219.115923 +/- 0.550377 um at 16 keV; insertion failed at 19.5 keV",
}
