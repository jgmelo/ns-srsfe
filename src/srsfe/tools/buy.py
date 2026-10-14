"""Buy: a vendor-built resonant detector specified from t_dwell (SPEC §6.4).

The vendor builds the resonant front end to our specs, so the tank shape (Q, τ_tank,
bandwidths, harmonic attenuation) is estimated exactly as in Design from r_f (the
vendor's transimpedance gain at f₀), f_0, t_dwell and n_tau. Only the detector's NEP and
the shot noise of the light are counted as noise; L, C, the Johnson noise of R, the opamp
voltage noise and C_d do not enter.
"""

from __future__ import annotations

from srsfe.tools.base import Group, Tool, register
from srsfe.tools.design import OPT, OUT, REQ, Variant, make_calcs

TOOL_KEY = "b"

BUY = Variant(
    tool_key=TOOL_KEY,
    req={**REQ, "noise": ("p_min", "p_max", "resp", "nep", "m")},
    opt=OPT,
    out={
        **OUT,
        "sizing": ("q", "tau_tank", "bw_3db", "b_eq"),
        "noise": ("i_0", "i_sig", "v_sig", "i_sh", "i_nep", "i_elec", "i_tot", "v_dens",
                  "v_rms", "snr", "shot_clear", "lsb", "v_q"),
    },
    detector_noise=True,
)

GROUPS = (
    Group("Tank", "t", ("r_f", "f_0", "t_dwell", "n_tau", "q_mode")),
    Group("Light", "l", ("p_min", "p_max", "resp", "f_rep", "tau_p", "m")),
    Group("Noise", "n", ("nep", "k_crest")),
    Group("Lock-in", "i", ("tau_lia", "n_lia")),
    Group("Opamp/Moku", "m", ("v_swing", "en_moku", "n_bits", "v_range")),
    Group("Spectrum", "f", ("f_max",)),
)

TOOL = register(Tool(
    name="Buy (vendor detector)",
    key=TOOL_KEY,
    description="Vendor-built resonant detector made to our specs: r_f is the vendor's "
                "transimpedance gain at f_0 and the tank shape is estimated from t_dwell as "
                "in Design. Noise is the shot noise of the light plus the detector NEP only. "
                "Spectrum, budget, lock-in and Moku as in Design.",
    calcs=make_calcs(BUY),
    groups=GROUPS,
))
