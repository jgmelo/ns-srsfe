"""Test-catalog vocabulary: test kinds and the SPEC items tests can cover.

- KINDS are registered as pytest markers in conftest.py; every test carries exactly one.
- SECTIONS lists what SPEC.md says should be tested. A test declares what it covers with
  `@pytest.mark.spec("<section>", "<item>", ...)`. scripts/test_catalog.py compares the two.

Keep SECTIONS in step with docs/SPEC.md.
"""

from dataclasses import dataclass

KINDS: dict[str, str] = {
    "golden": "Compares against SPEC §9 golden values",
    "formula": "Checks a SPEC §4 formula or rule on other inputs (limits, identities, modes)",
    "schema": "Data layout matches SPEC: fields, order, defaults, metadata, file format",
    "validation": "Accepts good input / rejects bad input",
    "round_trip": "save → load or format → parse gives back the same thing",
    "api": "An operation does what it says (copy, rename, list, migrate, …)",
    "errors": "Bad files or operations are handled as specified (error or warning)",
    "warning": "A W01–W09 condition fires or does not fire",
    "smoke": "Imports, screens or plots build/run without crashing",
}


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    items: dict[str, str]  # item slug → label


def _warnings() -> dict[str, str]:
    out = {"fields": "Warning carries id, message, severity, power, fields"}
    for i in range(1, 10):
        out[f"W0{i}:fires"] = f"W0{i} fires"
        out[f"W0{i}:silent"] = f"W0{i} does not fire"
    return out


def _named(*names: str) -> dict[str, str]:
    return {n: n for n in names}


SECTIONS: list[Section] = [
    Section("§0", "Constants (preamble)", {"constants": "e and k_B values"}),
    Section("§2", "Architecture rules", {
        "core-pure": "core/ never imports textual or matplotlib",
        "tank-result": "Both tank constructors return the same TankResult",
        "tool-registry": "Adding a tool = one file + registration",
    }),
    Section("§3.1", "Inputs", {
        "fields": "Field names and order",
        "defaults": "Default values",
        "metadata": "Unit, symbol, group, key, description per field",
        "types": "Field types (number / integer / text)",
        "positive": "Numeric inputs > 0",
        "m-nonneg": "m ≥ 0",
        "n-lia": "n_lia ∈ {1,2,3,4}",
        "v-range": "v_range ∈ {1, 10}",
        "n-bits": "n_bits integer",
        "q-mode": 'q_mode ∈ {"settling", "bandwidth"}',
        "p-order": "p_min ≤ p_max",
    }),
    Section("§4.1", "Tank formulas", {
        "q-settling": "Q, settling mode",
        "q-bandwidth": "Q, bandwidth mode",
        "l-c": "L and C from R, Q, ω₀",
        "from-lc": "f₀_calc and Q from existing L, C",
        "tau": "τ_tank",
        "z-f": "Z_f(f)",
        "bw": "BW₋₃dB and B_eq",
    }),
    Section("§4.2", "Light and spectrum", {
        "i0": "I₀, q_p, I_pk",
        "harmonics-range": "n = 1 … ⌊f_max/f_rep⌋",
        "v-n": "Vₙ and attₙ",
    }),
    Section("§4.3", "Signal", {"signal": "I_sig, V_sig"}),
    Section("§4.4", "Noise densities", {
        "i-sh": "i_sh", "i-r": "i_R", "i-en": "i_en", "i-nep": "i_NEP",
        "i-tot": "i_tot and i_elec", "v-rms": "v_dens and V_rms",
    }),
    Section("§4.5", "Lock-in", {"enbw": "ENBW for n = 1…4", "v-rms-lia": "V_rms,LIA"}),
    Section("§4.6", "Budget and SNR", {
        "v-coh": "V_coh", "occupancy": "occ_swing, occ_moku",
        "snr": "SNR and SNR_LIA", "shot-clear": "shot_clear",
    }),
    Section("§4.7", "Moku", {"lsb": "LSB and V_q"}),
    Section("§5", "Warnings", _warnings()),
    Section("§6", "Tools: Result", {"result-json": "Result is JSON-serializable (round trip)"}),
    Section("§6.1", "Design tool", {
        "sizing": "Calc 1 Sizing", "spectrum": "Calc 2 Spectrum", "budget": "Calc 3 Budget",
        "noise": "Calc 4 Noise", "lockin": "Calc 5 Lock-in", "all": "Calc 0 All",
        "missing-required": "Missing required inputs are reported, nothing runs",
        "optional-gating": "Optional inputs gate dependent outputs/warnings",
    }),
    Section("§6.2", "Analyze tool", {
        "outputs": "f0_calc, q, tau_tank, bw_3db, b_eq",
        "optional": "f_0 enables W06; t_dwell + n_tau enable settles, W07",
    }),
    Section("§6.3", "Sweep engine", {
        "sweep": "One run per value, requested outputs collected",
        "per-power": "Per-power outputs expand to name@p_min / name@p_max",
        "no-mutate": "Input Params not mutated",
    }),
    Section("§7", "Profiles", {
        "file-format": "File format (schema_version, name, notes, created, modified, params)",
        "inputs-only": "Stores inputs only, never derived values",
        "nulls": "Unset fields stored as null",
        "list": "list()", "load-save": "save → load round trip", "save-as": "save_as",
        "duplicate": "duplicate", "rename": "rename", "delete": "delete",
        "unknown-keys": "Unknown keys → warn and drop",
        "missing-keys": "Missing keys → null",
        "wrong-type": "Wrong type → error",
        "migrate": "migrate() upgrades older schema_versions",
        "default-profile": "default.json created from defaults if missing",
        "last-used": "App opens the last-used profile",
        "dirty-flag": "Dirty flag in header; prompt on switch/quit",
    }),
    Section("§8.1", "TUI screens and inputs", {
        "launcher": "Launcher", "tool-screen": "Tool screen", "plot-menu": "Plot menu",
        "profiles": "Profiles screen", "dialogs": "Dialogs",
        "eng-input": "Engineering-notation input",
        "eng-invalid": "Invalid input → reason",
        "eng-format": "Engineering formatting of results",
        "calc-validates": "Calculate validates first",
        "stale": "Editing inputs marks results stale",
    }),
    Section("§8.2", "Plots", {
        "bode": "Bode", "spectrum": "Spectrum", "budget": "Budget", "noise": "Noise",
        "runner": "Subprocess runner renders from serialized Result",
    }),
    Section("§8.3", "Key map", {
        "collisions": "No key collisions at any level, every tool",
        "navigation": "Group/field keys and Esc navigate the focus tree",
    }),
    Section("§9", "Golden profile", {"profile": "profiles/golden.json loads and is valid"}),
    Section("§9.1", "Golden scalar values", _named(
        "q", "l_f", "c_f", "tau_tank", "bw_3db", "b_eq", "f_n", "z_n", "att_n", "enbw_lia",
        "i_r", "i_en", "i_nep", "i_elec", "lsb", "v_q",
    )),
    Section("§9.2", "Golden per-power values", _named(
        "i_0", "q_p", "i_pk", "v_n", "v_n_sum", "v_n_rss", "i_sig", "v_sig", "i_sh", "i_tot",
        "v_dens", "v_rms", "v_coh", "occ_swing", "occ_moku", "snr", "snr_lia", "shot_clear",
    )),
    Section("§9.3", "Golden expected warnings", {
        "w02": "W02 fires for n_lia 1, 2; not 3, 4",
        "w03": "W03 at P_max only",
        "w04": "W04 at both powers",
        "silent": "W01, W05, W08, W09 do not fire",
    }),
    Section("§9.4", "Analyze tool golden", {
        "tank": "f0_calc, q, tau_tank",
        "settles": "settles = True (equality within tolerance)",
        "no-warnings": "No W06/W07",
    }),
]

SECTION_BY_KEY: dict[str, Section] = {s.key: s for s in SECTIONS}
