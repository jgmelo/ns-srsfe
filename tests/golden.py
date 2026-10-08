"""Expected golden outputs, transcribed verbatim from docs/SPEC.md §9.

Inputs come from profiles/golden.json (conftest fixtures); this file holds the expected
results only. Never edit a value to make a test pass (CLAUDE.md).
Compare with pytest.approx(rel=REL); dB values with abs=DB_ABS.
"""

REL = 1e-3
DB_ABS = 0.01

# §9.1 scalar values
Q = 12.566
L_F = 63.326e-6  # H
C_F = 1.0000e-12  # F
TAU_TANK = 200.00e-9  # s
BW_3DB = 1.5915e6  # Hz
B_EQ = 2.5000e6  # Hz
F_N = [40e6, 80e6, 120e6, 160e6, 200e6]  # Hz
Z_N = [5297.7, 2121.6, 1364.1, 1010.5, 803.79]  # Ω
ATT_N = [-25.52, -33.47, -37.30, -39.91, -41.90]  # dB

# §9.4 Analyze tool golden
ANALYZE_INPUTS = {"l_f": 63.3257e-6, "c_f": 1e-12, "r_f": 100e3, "f_0": 20e6,
                  "t_dwell": 1e-6, "n_tau": 5}
ANALYZE_F0_CALC = 20.000e6  # Hz
ANALYZE_Q = 12.566
ANALYZE_TAU_TANK = 200e-9  # s

# §9.2 per-power values: {"p_min": ..., "p_max": ...}
I_0 = {"p_min": 60.000e-6, "p_max": 600.00e-6}  # A
Q_P = {"p_min": 1.5000e-12, "p_max": 15.000e-12}  # C
I_PK = {"p_min": 0.75000, "p_max": 7.5000}  # A
_V_N_MIN = [0.63573, 0.25459, 0.16369, 0.12125, 0.096454]  # V
V_N = {"p_min": _V_N_MIN, "p_max": [10 * v for v in _V_N_MIN]}  # "×10" in SPEC
V_N_SUM = {"p_min": 1.2717, "p_max": 12.717}  # V
V_N_RSS = {"p_min": 0.72095, "p_max": 7.2095}  # V
I_SIG = {"p_min": 600.00e-12, "p_max": 6.0000e-9}  # A
V_SIG = {"p_min": 60.000e-6, "p_max": 600.00e-6}  # V

# §9.1 noise / lock-in / Moku scalars
ENBW_LIA = {1: 1.25e6, 2: 0.625e6, 3: 0.46875e6, 4: 0.390625e6}  # Hz, by n_lia
I_R = 4.0363e-13  # A/√Hz
I_EN = 1.8851e-12  # A/√Hz
I_NEP = 4.2600e-15  # A/√Hz
I_ELEC = 1.9279e-12  # A/√Hz
LSB = 244.14e-6  # V
V_Q = 70.477e-6  # V

# §9.2 noise / SNR
I_SH = {"p_min": 4.3848e-12, "p_max": 1.3866e-11}  # A/√Hz
I_TOT = {"p_min": 4.7899e-12, "p_max": 1.3999e-11}  # A/√Hz
V_DENS = {"p_min": 479.0e-9, "p_max": 1.3999e-6}  # V/√Hz
V_RMS = {"p_min": 757.34e-6, "p_max": 2.2135e-3}  # V
SNR = {"p_min": -25.033, "p_max": -14.349}  # dB
SNR_LIA = {  # dB, by n_lia
    1: {"p_min": -22.023, "p_max": -11.338},
    2: {"p_min": -19.013, "p_max": -8.328},
    3: {"p_min": -17.763, "p_max": -7.079},
    4: {"p_min": -16.971, "p_max": -6.287},
}
SHOT_CLEAR = {"p_min": 7.137, "p_max": 17.137}  # dB
