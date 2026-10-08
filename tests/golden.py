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
