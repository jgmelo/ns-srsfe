# SRS-FE — Specification v1.0

Design calculator for the resonant transimpedance front end (TIA) of an SRS photodetector.
This file is the single source of truth. If code and spec disagree, the spec wins; if the
spec is wrong, update the spec first, then the code.

All values are SI. Constants: e = 1.602176634e-19 C, k_B = 1.380649e-23 J/K.

---

## 1. Scope and model assumptions

- Topology: opamp TIA with **parallel R‖L‖C in the feedback path**. No DC-block capacitor,
  no reactive parts at the input. The photodiode capacitance C_d only enters via noise gain.
- At resonance |Z_f(f₀)| = R, so R is the transimpedance gain.
- Laser: **bare pulse train** (no modulation in the spectrum model), repetition rate f_rep,
  pulses of width τ_p treated as impulses.
- SRS signal: alternate pulses carry I₀(1 ± m/2) → a line of amplitude m·I₀ at f_rep/2.
  The signal frequency is f₀ (expected f₀ = f_rep/2).
- Every power-dependent quantity is evaluated at **both** P_min and P_max.

---

## 2. Package layout

```
srsfe/
├── pyproject.toml
├── CLAUDE.md
├── docs/SPEC.md
├── profiles/
│   └── golden.json
├── src/srsfe/
│   ├── __init__.py
│   ├── __main__.py            # `python -m srsfe` launches the TUI
│   ├── core/                  # pure computation — never imports textual or matplotlib
│   │   ├── constants.py
│   │   ├── params.py          # Params dataclass, field metadata (unit, default, key, group)
│   │   ├── units.py           # engineering-notation parse/format
│   │   ├── profiles.py        # JSON profile store
│   │   ├── tank.py            # TankResult, tank_from_dwell, tank_from_lc, z_f
│   │   ├── spectrum.py        # photocurrent, harmonics, signal
│   │   ├── noise.py           # noise densities, v_rms, SNR, lock-in ENBW
│   │   ├── budget.py          # output occupancy
│   │   ├── moku.py            # LSB, quantization noise
│   │   ├── warnings.py        # DesignWarning dataclass + checks
│   │   └── sweep.py           # generic sweep engine
│   ├── tools/
│   │   ├── base.py            # Tool, Calc, Result, registry
│   │   ├── design.py          # "Design from t_dwell"
│   │   └── analyze.py         # "Analyze existing tank"
│   ├── plots/
│   │   ├── figures.py         # pure functions: Result -> matplotlib Figure
│   │   └── runner.py          # subprocess entry: render from serialized Result
│   └── tui/
│       ├── app.py
│       ├── keymap.py
│       ├── screens/{launcher,tool_screen,profiles,plot_menu,dialogs,help}.py
│       └── widgets/{eng_input,field_group,results_table,warnings_panel}.py
└── tests/
    ├── conftest.py            # loads profiles/golden.json
    ├── test_units.py
    ├── test_profiles.py
    ├── test_tank.py
    ├── test_spectrum.py
    ├── test_noise.py
    ├── test_budget.py
    ├── test_warnings.py
    ├── test_sweep.py
    ├── test_tools.py
    ├── test_keymap.py
    └── test_tui.py            # Textual App.run_test() smoke tests
```

### Architecture rules

1. `core/` functions take **explicit arguments**, never the whole `Params`.
   Example: `tank_from_dwell(r, f0, t_dwell, n_tau, mode="settling") -> TankResult`.
2. Both tank constructors return the same `TankResult`; everything downstream accepts a
   `TankResult` and does not care how it was built.
3. Tools are the only place where `Params` is unpacked into core calls.
4. Adding a tool = one new file in `tools/` + registration. No TUI changes.

---

## 3. Parameters

### 3.1 Inputs

| Name | Sym | Unit | Default | Group | Key | Description |
|---|---|---|---|---|---|---|
| `r_f` | R | Ω | 100e3 | Tank | r | Feedback resistor; transimpedance gain at f₀ |
| `f_0` | f₀ | Hz | 20e6 | Tank | f | Tank resonance = signal frequency (f_rep/2) |
| `t_dwell` | t_dwell | s | 1e-6 | Tank | d | Pixel dwell time; sets Q |
| `n_tau` | N_τ | – | 5 | Tank | n | Tank time constants that must fit in one dwell |
| `q_mode` | – | – | "settling" | Tank | q | Q criterion: "settling" or "bandwidth" |
| `l_f` | L | H | null | Tank (Analyze) | l | Existing tank inductance |
| `c_f` | C | F | null | Tank (Analyze) | c | Existing tank capacitance |
| `p_min` | P_min | W | 1e-4 | Light | i | Minimum average optical power on PD |
| `p_max` | P_max | W | 1e-3 | Light | x | Maximum average optical power on PD |
| `resp` | ℜ | A/W | 0.6 | Light | r | PD responsivity |
| `f_rep` | f_rep | Hz | 40e6 | Light | f | Laser repetition rate |
| `tau_p` | τ_p | s | 2e-12 | Light | w | Optical pulse width |
| `m` | m | – | 1e-5 | Light | m | SRS modulation depth ΔI/I |
| `c_d` | C_d | F | 6e-12 | Noise | c | PD parasitic capacitance |
| `en_opamp` | e_n | V/√Hz | 2.5e-9 | Noise | e | Opamp input voltage noise |
| `nep` | NEP | W/√Hz | 7.1e-15 | Noise | p | PD noise-equivalent power |
| `temp` | Temp | K | 295 | Noise | t | Temperature for Johnson noise of R |
| `k_crest` | k_crest | – | 3 | Noise | k | Noise crest factor (peak/rms) |
| `tau_lia` | τ_LIA | s | 200e-9 | Lock-in | t | Lock-in integration time |
| `n_lia` | n_LIA | – | 1 | Lock-in | o | Lock-in filter order, 1–4 |
| `v_swing` | V_swing | V | 2.0 | Opamp/Moku | s | Opamp linear output swing, 0-to-peak |
| `en_moku` | e_n,Moku | V/√Hz | 30e-9 | Opamp/Moku | e | Moku input voltage noise |
| `n_bits` | N_bits | bit | 12 | Opamp/Moku | b | Moku ADC resolution |
| `v_range` | V_range | Vpp | 1.0 | Opamp/Moku | v | Moku input range (1 or 10 only) |
| `f_max` | f_max | Hz | 200e6 | Spectrum | f | Highest harmonic frequency included |

Validation: all numeric inputs > 0 except `m` ≥ 0; `n_lia` ∈ {1,2,3,4}; `v_range` ∈ {1, 10};
`n_bits` integer; `q_mode` ∈ {"settling", "bandwidth"}; `p_min` ≤ `p_max`.

### 3.2 Derived (read-only)

| Name | Unit | Description |
|---|---|---|
| `q` | – | Tank quality factor |
| `l_f`, `c_f` | H, F | Tank L, C (derived in Design tool) |
| `f0_calc` | Hz | Resonance from L, C (Analyze tool); `TankResult.f_res` |
| `tau_tank` | s | Tank ring-down time constant |
| `bw_3db`, `b_eq` | Hz | Tank −3 dB and noise-equivalent bandwidth |
| `enbw_lia` | Hz | Lock-in ENBW |
| `i_0` | A | Average photocurrent |
| `q_p`, `i_pk` | C, A | Charge per pulse, peak pulse current |
| `f_n`, `i_n`, `z_n`, `att_n`, `v_n` | Hz, A, Ω, dB, V | Per-harmonic frequency, line current 2·I₀, \|Z_f\|, attenuation re R, output amplitude |
| `v_n_sum`, `v_n_rss` | V | Coherent sum and RSS of v_n |
| `i_sig`, `v_sig` | A, V | Signal current and output amplitude at f₀ |
| `i_sh`, `i_r`, `i_en`, `i_nep`, `i_elec`, `i_tot` | A/√Hz | Noise densities; i_elec = √(i_r²+i_en²+i_nep²) |
| `v_dens` | V/√Hz | Output noise density R·i_tot |
| `v_rms`, `v_rms_lia` | V | Output rms noise over B_eq and over ENBW |
| `v_coh` | V | Worst-case coherent output peak |
| `occ_swing`, `occ_moku` | % | Occupancy of opamp swing / Moku range |
| `snr`, `snr_lia`, `shot_clear` | dB | SNR over B_eq, lock-in SNR, shot-noise clearance |
| `lsb`, `v_q` | V | ADC LSB, quantization noise rms |
| `settles` | bool | N_τ·τ_tank ≤ t_dwell·(1 + 1e-9) (Analyze tool; slack absorbs float rounding only) |

---

## 4. Formulas

### 4.1 Tank
- ω₀ = 2πf₀
- Q = π·f₀·t_dwell / N_τ (`settling`, default) or Q = f₀·t_dwell (`bandwidth`)
- L = R / (Q·ω₀), C = Q / (R·ω₀)
- From existing parts: f₀_calc = 1/(2π√(LC)), Q = R·√(C/L)
- τ_tank = Q / (π·f₀)
- Z_f(f) = R / [1 + jQ(f/f₀ − f₀/f)]
- `TankResult.f_res` is the tank's own resonance, used in Z_f: f_res = f_0 (Design),
  f_res = f₀_calc (Analyze). The input `f_0` is always the signal frequency.
- BW₋₃dB = f₀/Q, B_eq = (π/2)·BW₋₃dB

### 4.2 Light and spectrum
- I₀ = P·ℜ, q_p = I₀/f_rep, I_pk = q_p/τ_p
- Lines: I₀ at DC (shorted by L — no output), 2·I₀ at fₙ = n·f_rep, m·I₀ at f₀
- n = 1 … ⌊f_max/f_rep⌋ (floor taken on f_max/f_rep·(1 + 1e-9); slack absorbs float
  rounding only, so f_max = k·f_rep includes harmonic k)
- Vₙ = 2·I₀·|Z_f(fₙ)|, attₙ = 20·log₁₀(|Z_f(fₙ)|/R)

### 4.3 Signal
- I_sig = m·I₀, V_sig = I_sig·R (amplitude)

### 4.4 Noise (input-referred, A/√Hz)
- i_sh = √(2eI₀)
- i_R = √(4k_B·Temp/R)
- i_en = e_n·√(1/R² + (ω₀C_d)²)
- i_NEP = NEP·ℜ
- i_tot = √(i_sh² + i_R² + i_en² + i_NEP²)
- v_dens = R·i_tot, V_rms = v_dens·√B_eq

### 4.5 Lock-in
- ENBW: n=1: 1/(4τ), n=2: 1/(8τ), n=3: 3/(32τ), n=4: 5/(64τ), τ = τ_LIA
- V_rms,LIA = v_dens·√ENBW

### 4.6 Budget and SNR
- V_coh = ΣVₙ + V_sig + k_crest·V_rms
- occ_swing = 100·V_coh / V_swing
- occ_moku = 100·2·V_coh / V_range
- SNR = 20·log₁₀(V_sig / (√2·V_rms)); SNR_LIA uses V_rms,LIA
- shot_clear = 20·log₁₀(i_sh / i_elec)

### 4.7 Moku
- LSB = V_range / 2^N_bits, V_q = LSB/√12

---

## 5. Warnings

| ID | Condition | Message | Severity | Power | Fields |
|---|---|---|---|---|---|
| W01 | τ_LIA > t_dwell | Lock-in smears adjacent pixels | warn | – | tau_lia, t_dwell |
| W02 | ENBW > B_eq/5 | Tank, not lock-in, limits noise bandwidth | info | – | enbw_lia, b_eq |
| W03 | occ_swing > 100 | Output exceeds opamp swing | warn | each | v_coh, occ_swing, v_swing |
| W04 | occ_moku > 100 | Output exceeds Moku input range | warn | each | v_coh, occ_moku, v_range |
| W05 | v_dens < 3·e_n,Moku | Moku noise not negligible vs TIA output noise | warn | each | v_dens, en_moku |
| W06 | \|f₀_calc − f_0\|/f_0 > 0.01 | Tank resonance off signal frequency (Analyze) | warn | – | f0_calc, f_0 |
| W07 | not `settles` (N_τ·τ_tank > t_dwell·(1 + 1e-9)) | Tank does not settle within dwell (Analyze) | warn | – | settles, tau_tank, n_tau, t_dwell |
| W08 | τ_p > 1/(10·f_max) | Impulse approximation questionable | info | – | tau_p, f_max |
| W09 | \|f_0 − f_rep/2\|/f_0 > 0.01 | Signal frequency is not f_rep/2 | warn | – | f_0, f_rep |

Power "each": checked separately at P_min and P_max; the warning carries the power it fired at.

Warnings (`DesignWarning`) carry `id`, `message`, `severity` ("warn" | "info"), `power` (None | "p_min" | "p_max"),
and the names of the fields involved (used to put ⚠ next to result rows).

---

## 6. Tools and calculations

`Tool` declares: `name`, `key`, `description`, `calcs: list[Calc]`, `groups` (ordered,
with group key and field keys). `Calc` declares: `name`, `key` (digit), `required`,
`optional`, `outputs`, `plots`, `run(params) -> Result`.
`Result` holds scalar outputs, per-power outputs (`{"p_min": ..., "p_max": ...}`), tables
(harmonics), and warnings; it must be JSON-serializable (used by the plot subprocess and sweep).
It also records the input `params` it was computed from. In JSON, non-finite floats (e.g. SNR =
−inf when m = 0) are written as `{"$float": "-inf" | "inf" | "nan"}` so the file stays strict JSON.

### 6.1 Design from t_dwell (key `d`)

| Key | Calc | Required | Optional | Plots |
|---|---|---|---|---|
| 1 | Sizing | r_f, f_0, t_dwell, n_tau | q_mode | Bode |
| 2 | Spectrum | Sizing + p_min, p_max, resp, f_rep, f_max | tau_p | Spectrum stems |
| 3 | Budget | Spectrum + Noise + k_crest, v_swing, v_range | – | Budget bar |
| 4 | Noise | Sizing + p_min, p_max, resp, c_d, en_opamp, nep, temp, m | en_moku, n_bits, v_range | Noise contributions |
| 5 | Lock-in | Noise + tau_lia, n_lia | – | Noise contributions |
| 0 | All | union of the above | – | all |

Calcs with an optional input compute the dependent outputs/warnings only when it is set
(e.g. W05 only if `en_moku` is set; `i_pk` and W08 only if `tau_p` is set).
A calc also returns the outputs and warnings of the calcs it builds on ("Sizing +" etc.).
Warnings by stage: Spectrum W08, W09 · Noise W05 · Budget W03, W04 · Lock-in W01, W02.

### 6.2 Analyze existing tank (key `a`)

Single calc (key `1`, group `t` Tank). Required: l_f, c_f, r_f. Optional: f_0 (enables W06), t_dwell + n_tau
(enable `settles`, W07). Outputs: f0_calc, q, tau_tank, bw_3db, b_eq, settles. Plot: Bode.

### 6.3 Sweep engine (core only in v1; UI later, launcher key `w`)

`sweep(calc, params, field, values, outputs) -> list[dict]` — runs the calc once per value
with `field` replaced, collects the requested outputs (per-power outputs expand to
`<name>@p_min`, `<name>@p_max`). Must not mutate the input `Params`.

---

## 7. Profiles

- One JSON file per profile in `./profiles/` (configurable in Settings).
- Stores **inputs only** (never derived values). Unset fields stored as `null`.
- File format:
  ```json
  {"schema_version": 1, "name": "golden", "notes": "...",
   "created": "ISO-8601", "modified": "ISO-8601", "params": {...}}
  ```
- API: `list()`, `load(name)`, `save(params, name)`, `save_as`, `duplicate`, `rename`, `delete`.
- On load: unknown keys → warn and drop; missing keys → null; wrong type → error.
  `migrate(data)` upgrades older `schema_version`s.
- One active profile at a time; app opens last-used profile, fallback `default.json`
  (created from defaults if missing). Last-used name stored in a small settings file.
- Dirty flag: header shows `profile: <name>*` with unsaved changes; switching/quitting prompts.

---

## 8. TUI

Textual. Header `SRS-FE │ profile: <name>[*]`; footer shows live keys.

### 8.1 Screens

**Launcher** — left: tool list from registry + Profiles + Settings; right: description of
highlighted item.

**Tool screen** (generic, built from the Tool declaration)
- Top: calc tab bar (`1`…`5`, `0`).
- Left: collapsible input groups. Field styling depends on selected calc:
  required = accent; required-and-empty = red border; optional = normal;
  unused = dimmed (still editable). Groups containing required fields auto-expand.
- Inputs accept engineering notation (`100k`, `2p`, `20M`, `1e-6`, `1µ`/`1u`); unit label
  beside each field; stored as SI; invalid → red with reason.
- Right: results table (columns P_min / P_max where applicable, engineering formatting,
  ⚠ on rows tied to a warning) above a warnings panel.
- Calculate validates first; missing required fields → toast listing them, nothing runs.
- Editing any input marks results stale (greyed) until recalculated.

**Plot menu** — checkbox list of plots available for the current Result; show or save PNG
to `./plots/<profile>_<plot>.png`.

**Profiles** — table: name, modified, notes.

**Dialogs** — unsaved changes; delete confirmation.

### 8.2 Plots

Pure functions in `plots/figures.py`: `Result -> Figure`. Displayed by spawning
`python -m srsfe.plots.runner <result.json> <plot_name>` so matplotlib's GUI loop never
blocks Textual. Plots:
- **Bode**: |Z_f| (dB re 1 Ω) and phase vs log f, 1 MHz … f_max; mark f₀ and fₙ.
- **Spectrum**: stems of Iₙ and Vₙ vs f, signal line at f₀; both powers.
- **Budget**: stacked bar of ΣVₙ, V_sig, k_crest·V_rms at P_min and P_max with V_swing
  and V_range/2 reference lines.
- **Noise**: bar of i_sh, i_R, i_en, i_NEP at both powers.

### 8.3 Key map

Focus is a tree: **screen → group → field**. Letters act only when focus is not inside a
text input. Group key expands the group and enters it; field key starts editing; Esc goes
up one level. Every option shows its key hint, e.g. `[r] r_f`.

**Always active (even while typing):** Esc up/back · F1 help · F5 calculate ·
Ctrl+S save · Ctrl+Q quit · Ctrl+P command palette.

| Context | Keys |
|---|---|
| Launcher | `d` Design · `a` Analyze · `w` Sweep (later) · `o` Profiles · `t` Settings · `q` quit |
| Tool, top level | `1`–`5`,`0` calc tabs · `c` calculate · `p` plot menu · `v` focus results · `s` save · `w` save-as · `o` profiles · `?` help · `q` quit · group keys below |
| Design groups | `t` Tank · `l` Light · `n` Noise · `i` Lock-in · `m` Opamp/Moku · `f` Spectrum (single field → edits f_max directly) |
| Tank fields (Design) | `r` r_f · `f` f_0 · `d` t_dwell · `n` n_tau · `q` q_mode |
| Light fields | `i` p_min · `x` p_max · `r` resp · `f` f_rep · `w` tau_p · `m` m |
| Noise fields | `c` c_d · `e` en_opamp · `p` nep · `t` temp · `k` k_crest |
| Lock-in fields | `t` tau_lia · `o` n_lia |
| Opamp/Moku fields | `s` v_swing · `e` en_moku · `b` n_bits · `v` v_range |
| Tank fields (Analyze) | `l` l_f · `c` c_f · `r` r_f · `f` f_0 · `d` t_dwell · `n` n_tau |
| Plot menu | `b` Bode · `s` spectrum · `u` budget · `n` noise (toggle) · Enter show · `v` save PNG · Esc close |
| Profiles | Enter/`l` load · `n` new (save-as) · `d` duplicate · `r` rename · `e` edit notes · `x` delete · Esc back |
| Unsaved dialog | `s` save · `d` discard · `c`/Esc cancel |
| Delete dialog | `y` yes · `n`/Esc no |

Keys are declared next to the data they act on (field metadata, group, tool, screen).
`test_keymap.py` asserts no collisions within any level, for every registered tool.

---

## 9. Golden test case

Profile `profiles/golden.json`. Relative tolerance 1e-3 (`pytest.approx(rel=1e-3)`).

### 9.1 Scalar values

| Output | Value |
|---|---|
| q | 12.566 |
| l_f | 63.326e-6 H |
| c_f | 1.0000e-12 F |
| tau_tank | 200.00e-9 s |
| bw_3db | 1.5915e6 Hz |
| b_eq | 2.5000e6 Hz |
| f_n | 40, 80, 120, 160, 200 MHz |
| z_n | 5297.7, 2121.6, 1364.1, 1010.5, 803.79 Ω |
| att_n | −25.52, −33.47, −37.30, −39.91, −41.90 dB (abs tol 0.01) |
| enbw_lia (n=1,2,3,4) | 1.25e6, 0.625e6, 0.46875e6, 0.390625e6 Hz |
| i_r | 4.0363e-13 A/√Hz |
| i_en | 1.8851e-12 A/√Hz |
| i_nep | 4.2600e-15 A/√Hz |
| i_elec | 1.9279e-12 A/√Hz |
| lsb | 244.14e-6 V |
| v_q | 70.477e-6 V |

### 9.2 Per-power values

| Output | P_min = 0.1 mW | P_max = 1 mW |
|---|---|---|
| i_0 | 60.000e-6 A | 600.00e-6 A |
| q_p | 1.5000e-12 C | 15.000e-12 C |
| i_pk | 0.75000 A | 7.5000 A |
| v_n | 0.63573, 0.25459, 0.16369, 0.12125, 0.096454 V | ×10 |
| v_n_sum | 1.2717 V | 12.717 V |
| v_n_rss | 0.72095 V | 7.2095 V |
| i_sig | 600.00e-12 A | 6.0000e-9 A |
| v_sig | 60.000e-6 V | 600.00e-6 V |
| i_sh | 4.3848e-12 A/√Hz | 1.3866e-11 A/√Hz |
| i_tot | 4.7899e-12 A/√Hz | 1.3999e-11 A/√Hz |
| v_dens | 479.0e-9 V/√Hz | 1.3999e-6 V/√Hz |
| v_rms | 757.34e-6 V | 2.2135e-3 V |
| v_coh | 1.2740 V | 12.724 V |
| occ_swing | 63.70 % | 636.2 % |
| occ_moku | 254.8 % | 2545 % |
| snr | −25.033 dB | −14.349 dB |
| snr_lia (n=1) | −22.023 dB | −11.338 dB |
| snr_lia (n=2) | −19.013 dB | −8.328 dB |
| snr_lia (n=3) | −17.763 dB | −7.079 dB |
| snr_lia (n=4) | −16.971 dB | −6.287 dB |
| shot_clear | +7.137 dB | +17.137 dB |

dB values: absolute tolerance 0.01 dB.

### 9.3 Expected warnings (golden, n_lia = 1)

- W02 fires (1.25 MHz > 0.5 MHz); also fires for n_lia = 2; not for 3, 4.
- W03 fires at P_max only. W04 fires at both powers.
- W01, W05, W08, W09 do not fire.

### 9.4 Analyze tool golden

Inputs l_f = 63.3257e-6 H, c_f = 1e-12 F, r_f = 100e3 Ω, f_0 = 20e6, t_dwell = 1e-6, n_tau = 5
→ f0_calc = 20.000e6 Hz, q = 12.566, tau_tank = 200e-9 s, settles = True (equality within
the 1e-9 rounding slack counts as settling), no W06/W07.
