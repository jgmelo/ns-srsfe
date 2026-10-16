# Ideas (not in SPEC)

Logged per CLAUDE.md: ideas beyond the current SPEC, to discuss before implementing.

## Design-space map (§6.5) — later
- Lock-in SNR on the map, with τ_LIA following t_dwell (e.g. τ_LIA = k·t_dwell); W01 boundary.
- SNR at the Moku: include e_n,Moku (and quantization v_q) in the output noise, i.e.
  √(v_dens² + e_n,Moku²) — Friis: the TIA gain shrinks the Moku's input-referred share.
- Any numeric input on x / y, any output as the colour, "at least / at most" targets.
- Overlay several bases (Design vs Buy) or several gains R on one map.
