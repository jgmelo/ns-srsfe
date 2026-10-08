"""Generate docs/tests.html: a self-contained catalog of the test suite.

Usage (from the repo root):
    python scripts/test_catalog.py            # collect only
    python scripts/test_catalog.py --run      # also run the tests and show pass/fail
    python scripts/test_catalog.py --check    # exit 1 if the catalog has issues

Data comes from pytest collection: per test its file (topic), docstring, kind marker,
spec(...) markers and parametrized cases. SPEC coverage is checked against
tests/spec_items.py.
"""

from __future__ import annotations

import argparse
import html
import inspect
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.spec_items import KINDS, SECTION_BY_KEY, SECTIONS  # noqa: E402

DEFAULT_OUT = ROOT / "docs" / "tests.html"


# -- data model ----------------------------------------------------------------


@dataclass
class TestFunc:
    topic: str
    path: str
    name: str
    line: int
    doc: str
    kinds: list[str]
    specs: list[tuple[str, tuple[str, ...]]]
    cases: list[str] = field(default_factory=list)  # parametrize ids; empty = not parametrized
    outcomes: list[str] = field(default_factory=list)

    @property
    def anchor(self) -> str:
        return f"t-{self.topic}-{self.name}"

    @property
    def n_cases(self) -> int:
        return max(len(self.cases), 1)

    @property
    def kind(self) -> str:
        return self.kinds[0] if self.kinds else "?"

    @property
    def status(self) -> str | None:
        if not self.outcomes:
            return None
        if "failed" in self.outcomes:
            return "failed"
        if all(o == "passed" for o in self.outcomes):
            return "passed"
        return "skipped"


class Collector:
    """pytest plugin: records collected items and (with --run) their outcomes."""

    def __init__(self) -> None:
        self.funcs: dict[tuple[str, str], TestFunc] = {}
        self.module_docs: dict[str, str] = {}
        self.node_to_func: dict[str, TestFunc] = {}

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            path = Path(item.path).relative_to(ROOT).as_posix()
            topic = Path(path).stem.removeprefix("test_")
            name = getattr(item, "originalname", item.name)
            key = (path, name)
            if key not in self.funcs:
                func = getattr(item, "function", None)
                self.funcs[key] = TestFunc(
                    topic=topic,
                    path=path,
                    name=name,
                    line=item.location[1] + 1,
                    doc=(inspect.getdoc(func) or "") if func else "",
                    kinds=sorted({m.name for m in item.iter_markers() if m.name in KINDS}),
                    specs=[(m.args[0], tuple(m.args[1:])) for m in item.iter_markers("spec")
                           if m.args],
                )
                module = getattr(item, "module", None)
                self.module_docs.setdefault(topic, (inspect.getdoc(module) or "") if module else "")
            callspec = getattr(item, "callspec", None)
            if callspec is not None:
                self.funcs[key].cases.append(callspec.id)
            self.node_to_func[item.nodeid] = self.funcs[key]

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        func = self.node_to_func.get(report.nodeid)
        if func is None:
            return
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            func.outcomes.append(report.outcome)


def collect(run: bool) -> Collector:
    collector = Collector()
    args = ["-q", "-p", "no:cacheprovider", str(ROOT / "tests")]
    if not run:
        args.insert(0, "--collect-only")
    code = pytest.main(args, plugins=[collector])
    if code not in (pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED):
        sys.exit(f"pytest exited with {code!r}")
    return collector


def find_issues(funcs: list[TestFunc]) -> list[str]:
    issues: list[str] = []
    for f in funcs:
        where = f"{f.path}::{f.name}"
        if not f.doc:
            issues.append(f"{where}: no docstring")
        if len(f.kinds) != 1:
            issues.append(f"{where}: needs exactly one kind marker, has {f.kinds or 'none'}")
        for section, items in f.specs:
            sec = SECTION_BY_KEY.get(section)
            if sec is None:
                issues.append(f"{where}: unknown spec section {section!r}")
                continue
            for it in items:
                if it not in sec.items:
                    issues.append(f"{where}: unknown spec item {section} {it!r}")
    return issues


def git_describe(exclude: Path) -> str:
    """Short HEAD hash, with "-dirty" if anything but the catalog itself is modified."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        head = git("rev-parse", "--short", "HEAD")
        rel = exclude.resolve().relative_to(ROOT).as_posix()
        dirty = git("status", "--porcelain", "--", ".", f":(exclude){rel}")
    except (OSError, ValueError, subprocess.CalledProcessError):
        return "unknown"
    return f"{head}-dirty" if dirty else head


# -- HTML ----------------------------------------------------------------------

e = html.escape

CSS = """
:root {
  --bg: #fbfbfa; --surface: #ffffff; --surface-2: #f3f3f1; --text: #1d1d1b;
  --muted: #6b6b66; --border: #e3e3df; --accent: #2f5fb3; --accent-soft: #e6edf8;
  --ok: #24804a; --bad: #c0362c; --skip: #8a8a84; --heat: 47, 95, 179;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --surface: #1e1e1c; --surface-2: #262624; --text: #e9e9e5;
    --muted: #9a9a94; --border: #34342f; --accent: #8fb0ef; --accent-soft: #24304a;
    --ok: #5cc68a; --bad: #f07a6f; --skip: #8a8a84; --heat: 143, 176, 239;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
code, .mono { font-family: ui-monospace, "Cascadia Code", Consolas, monospace; font-size: 12.5px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.layout { display: grid; grid-template-columns: 230px minmax(0, 1fr); min-height: 100vh; }
nav { position: sticky; top: 0; align-self: start; height: 100vh; overflow-y: auto;
  padding: 20px 16px; border-right: 1px solid var(--border); background: var(--surface); }
nav h1 { font-size: 15px; margin: 0 0 2px; }
nav .meta { color: var(--muted); font-size: 12px; margin-bottom: 16px; }
nav ul { list-style: none; margin: 0 0 16px; padding: 0; }
nav li a { display: flex; justify-content: space-between; padding: 3px 6px; border-radius: 4px;
  color: var(--text); }
nav li a:hover { background: var(--surface-2); text-decoration: none; }
nav li.sub a { padding-left: 18px; color: var(--muted); }
nav .count { color: var(--muted); font-size: 12px; }
nav label { display: block; font-size: 12px; color: var(--muted); margin: 8px 0 4px; }
#q { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg); color: var(--text); font: inherit; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 12px;
  border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
  white-space: nowrap; }
button.chip { cursor: pointer; font: inherit; font-size: 12px; }
button.chip[aria-pressed="true"] { background: var(--accent); border-color: var(--accent);
  color: var(--surface); }
main { padding: 24px 32px 64px; max-width: 1200px; }
h2 { font-size: 20px; margin: 36px 0 4px; padding-top: 8px; }
h2:first-child { margin-top: 0; }
h3 { font-size: 15px; margin: 0; }
.lead { color: var(--muted); margin: 0 0 14px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px;
  margin: 12px 0 20px; }
.tile { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 14px; }
.tile .v { font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile .l { color: var(--muted); font-size: 12px; }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; background: var(--surface);
  border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--border); text-align: left;
  vertical-align: top; }
th { background: var(--surface-2); font-weight: 600; font-size: 12px; color: var(--muted); }
tr:last-child td { border-bottom: 0; }
.matrix td, .matrix th { text-align: center; font-variant-numeric: tabular-nums; }
.matrix td:first-child, .matrix th:first-child { text-align: left; }
.matrix .fn { display: block; color: var(--muted); font-size: 11px; }
.matrix .empty { color: var(--border); }
.matrix tfoot td { font-weight: 600; background: var(--surface-2); }
.issues { border: 1px solid var(--bad); border-radius: 8px; padding: 10px 14px; margin: 0 0 20px; }
.issues h3 { color: var(--bad); }
.issues ul { margin: 6px 0 0; padding-left: 18px; }
.sections { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(330px, 100%), 1fr)); gap: 12px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
  padding: 12px 14px; }
.card header { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.card .frac { color: var(--muted); font-size: 12px; font-variant-numeric: tabular-nums; }
.bar { height: 4px; background: var(--surface-2); border-radius: 2px; margin: 6px 0 8px; }
.bar span { display: block; height: 100%; background: var(--ok); border-radius: 2px; }
.items { list-style: none; margin: 0; padding: 0; }
.items li { display: grid; grid-template-columns: 16px 1fr; gap: 6px; padding: 2px 0; }
.items .tests { grid-column: 2; font-size: 12px; }
.yes { color: var(--ok); } .no { color: var(--bad); }
.items li.gap > span:nth-child(2) { color: var(--muted); }
.sec-only { font-size: 12px; color: var(--muted); margin-top: 6px; }
.tests-table { table-layout: fixed; }
.tests-table th:nth-child(1) { width: 27%; } .tests-table th:nth-child(2) { width: 37%; }
.tests-table th:nth-child(3) { width: 10%; } .tests-table th:nth-child(4) { width: 16%; }
.tests-table th:nth-child(5) { width: 10%; }
.tests-table code { overflow-wrap: anywhere; }
details summary { white-space: nowrap; }
.where { display: block; color: var(--muted); font-size: 11.5px; }
details summary { cursor: pointer; color: var(--accent); }
details ul { margin: 4px 0 0; padding-left: 16px; max-height: 220px; overflow-y: auto; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
.dot.passed { background: var(--ok); } .dot.failed { background: var(--bad); }
.dot.skipped { background: var(--skip); }
.kinds-legend { display: grid; grid-template-columns: max-content 1fr; gap: 4px 12px;
  margin: 10px 0 0; font-size: 13px; }
.hidden { display: none !important; }
@media (max-width: 800px) {
  .layout { grid-template-columns: minmax(0, 1fr); }
  nav { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--border); }
  main { padding: 16px; }
  .tests-table { table-layout: auto; min-width: 640px; }
  .tests-table th { width: auto !important; }
}
@media print {
  nav { display: none; } .layout { display: block; } main { max-width: none; }
  details > ul { max-height: none; }
}
"""

JS = """
const q = document.getElementById('q');
const chips = [...document.querySelectorAll('button[data-kind]')];
function apply() {
  const text = q.value.trim().toLowerCase();
  const kinds = chips.filter(c => c.getAttribute('aria-pressed') === 'true').map(c => c.dataset.kind);
  document.querySelectorAll('tr[data-row]').forEach(tr => {
    const okText = !text || tr.dataset.text.includes(text);
    const okKind = !kinds.length || kinds.includes(tr.dataset.kind);
    tr.classList.toggle('hidden', !(okText && okKind));
  });
  document.querySelectorAll('section.topic').forEach(sec => {
    const any = sec.querySelector('tr[data-row]:not(.hidden)');
    sec.classList.toggle('hidden', !any);
  });
}
q.addEventListener('input', apply);
chips.forEach(c => c.addEventListener('click', () => {
  c.setAttribute('aria-pressed', c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
  apply();
}));
"""


def heat(count: int, maximum: int) -> str:
    if count == 0 or maximum == 0:
        return ""
    alpha = 0.10 + 0.45 * count / maximum
    return f' style="background: rgba(var(--heat), {alpha:.2f})"'


def spec_label(section: str, items: tuple[str, ...]) -> str:
    return f"{section} {', '.join(items)}" if items else section


def render(funcs: list[TestFunc], module_docs: dict[str, str], issues: list[str],
           ran: bool, version: str) -> str:
    topics: dict[str, list[TestFunc]] = defaultdict(list)
    for f in funcs:
        topics[f.topic].append(f)
    kinds_used = list(KINDS)
    n_funcs = len(funcs)
    n_cases = sum(f.n_cases for f in funcs)

    # SPEC coverage: (section, item) → tests; section-only references.
    covered: dict[tuple[str, str], list[TestFunc]] = defaultdict(list)
    section_refs: dict[str, list[TestFunc]] = defaultdict(list)
    for f in funcs:
        for section, items in f.specs:
            if not items:
                section_refs[section].append(f)
            for it in items:
                covered[(section, it)].append(f)
    total_items = sum(len(s.items) for s in SECTIONS)
    covered_items = sum(1 for s in SECTIONS for it in s.items if covered.get((s.key, it)))

    out: list[str] = []
    w = out.append
    w("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    w("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    w("<title>SRS-FE test catalog</title>")
    w(f"<style>{CSS}</style></head><body><div class='layout'>")

    # -- nav
    w("<nav><h1>SRS-FE test catalog</h1>")
    w(f"<div class='meta'>{e(version)} · {datetime.now():%Y-%m-%d %H:%M}</div>")
    w("<ul><li><a href='#overview'>Overview</a></li>")
    w(f"<li><a href='#spec'>SPEC coverage <span class='count'>{covered_items}/{total_items}"
      "</span></a></li>")
    w("<li><a href='#topics'>Topics</a></li>")
    for topic, fs in topics.items():
        w(f"<li class='sub'><a href='#topic-{e(topic)}'>{e(topic)}"
          f"<span class='count'>{sum(f.n_cases for f in fs)}</span></a></li>")
    w("<li><a href='#kinds'>Kinds</a></li></ul>")
    w("<label for='q'>Filter tests</label><input id='q' type='search' placeholder='name, text, §…'>")
    w("<label>Kind</label><div class='chips'>")
    for k in kinds_used:
        w(f"<button class='chip' data-kind='{k}' aria-pressed='false' title='{e(KINDS[k])}'>"
          f"{k}</button>")
    w("</div></nav><main>")

    # -- overview
    w("<section id='overview'><h2>Overview</h2>")
    w("<p class='lead'>Generated from pytest collection. A <em>function</em> is one "
      "<code>def test_…</code>; parametrized functions expand into several <em>cases</em>.</p>")
    if issues:
        w("<div class='issues'><h3>Catalog issues</h3><ul>")
        for i in issues:
            w(f"<li class='mono'>{e(i)}</li>")
        w("</ul></div>")
    w("<div class='tiles'>")
    tiles = [(n_funcs, "test functions"), (n_cases, "test cases"), (len(topics), "topics (files)"),
             (f"{covered_items}/{total_items}", "SPEC items covered")]
    if ran:
        cases_failed = sum(o == "failed" for f in funcs for o in f.outcomes)
        tiles.append((cases_failed, "failed cases (last run)"))
    for v, label in tiles:
        w(f"<div class='tile'><div class='v'>{v}</div><div class='l'>{label}</div></div>")
    w("</div>")

    # topic × kind matrix
    cell: dict[tuple[str, str], list[TestFunc]] = defaultdict(list)
    for f in funcs:
        cell[(f.topic, f.kind)].append(f)
    maximum = max((sum(x.n_cases for x in v) for v in cell.values()), default=0)
    w("<h3>Cases by topic and kind</h3><p class='lead'>Cell: cases (functions). "
      "Empty columns show kinds no test exercises yet.</p>")
    w("<div class='scroll'><table class='matrix'><thead><tr><th>Topic</th>")
    for k in kinds_used:
        w(f"<th title='{e(KINDS[k])}'>{k}</th>")
    w("<th>Total</th></tr></thead><tbody>")
    for topic, fs in topics.items():
        w(f"<tr><td><a href='#topic-{e(topic)}'>{e(topic)}</a></td>")
        for k in kinds_used:
            c = cell.get((topic, k), [])
            nc = sum(x.n_cases for x in c)
            if c:
                w(f"<td{heat(nc, maximum)}>{nc}<span class='fn'>{len(c)} fn</span></td>")
            else:
                w("<td class='empty'>·</td>")
        w(f"<td><b>{sum(x.n_cases for x in fs)}</b><span class='fn'>{len(fs)} fn</span></td></tr>")
    w("</tbody><tfoot><tr><td>Total</td>")
    for k in kinds_used:
        c = [f for f in funcs if f.kind == k]
        w(f"<td>{sum(x.n_cases for x in c) or '·'}"
          f"{f'<span class=fn>{len(c)} fn</span>' if c else ''}</td>")
    w(f"<td>{n_cases}<span class='fn'>{n_funcs} fn</span></td></tr></tfoot></table></div>")
    w("</section>")

    # -- spec coverage
    w("<section id='spec'><h2>SPEC coverage</h2>")
    w("<p class='lead'>Items listed in <code>tests/spec_items.py</code> against the "
      "<code>@pytest.mark.spec(…)</code> markers. ✗ = no test yet.</p><div class='sections'>")
    for s in SECTIONS:
        n_cov = sum(1 for it in s.items if covered.get((s.key, it)))
        pct = 100 * n_cov / len(s.items) if s.items else 0
        w(f"<div class='card' id='spec-{e(s.key)}'><header><h3>{e(s.key)} {e(s.title)}</h3>"
          f"<span class='frac'>{n_cov}/{len(s.items)}</span></header>"
          f"<div class='bar'><span style='width:{pct:.0f}%'></span></div><ul class='items'>")
        for it, label in s.items.items():
            tests = covered.get((s.key, it), [])
            if tests:
                links = ", ".join(f"<a href='#{t.anchor}'>{e(t.name)}</a>" for t in tests)
                w(f"<li><span class='yes'>✓</span><span>{e(label)}</span>"
                  f"<span class='tests'>{links}</span></li>")
            else:
                w(f"<li class='gap'><span class='no'>✗</span><span>{e(label)}</span></li>")
        w("</ul>")
        if section_refs.get(s.key):
            links = ", ".join(f"<a href='#{t.anchor}'>{e(t.name)}</a>"
                              for t in section_refs[s.key])
            w(f"<div class='sec-only'>Also referenced by: {links}</div>")
        w("</div>")
    w("</div></section>")

    # -- topics
    w("<section id='topics'><h2>Topics</h2><p class='lead'>One section per test file.</p></section>")
    for topic, fs in topics.items():
        nc = sum(f.n_cases for f in fs)
        w(f"<section class='topic' id='topic-{e(topic)}'><h2>{e(topic)}</h2>")
        w(f"<p class='lead'><code>{e(fs[0].path)}</code> · {len(fs)} functions · {nc} cases"
          f"{' — ' + e(module_docs.get(topic, '')) if module_docs.get(topic) else ''}</p>")
        w("<div class='scroll'><table class='tests-table'><thead><tr><th>Test</th>"
          "<th>What it checks</th><th>Kind</th><th>SPEC</th><th>Cases</th></tr></thead><tbody>")
        for f in fs:
            specs = "<br>".join(
                f"<a href='#spec-{e(sec)}'>{e(spec_label(sec, items))}</a>" for sec, items in f.specs
            ) or "<span class='where'>—</span>"
            if f.cases:
                lis = "".join(f"<li class='mono'>{e(c)}</li>" for c in f.cases)
                cases = f"<details><summary>{len(f.cases)} cases</summary><ul>{lis}</ul></details>"
            else:
                cases = "1"
            dot = f"<span class='dot {f.status}' title='{f.status}'></span>" if f.status else ""
            text = " ".join([f.name, f.doc, f.kind, *(spec_label(s, i) for s, i in f.specs),
                             *f.cases]).lower()
            w(f"<tr data-row data-kind='{e(f.kind)}' data-text='{e(text)}' id='{e(f.anchor)}'>"
              f"<td>{dot}<code>{e(f.name)}</code><span class='where'>{e(f.path)}:{f.line}</span></td>"
              f"<td>{e(f.doc) or '<span class=no>no docstring</span>'}</td>"
              f"<td><span class='chip' title='{e(KINDS.get(f.kind, ''))}'>{e(f.kind)}</span></td>"
              f"<td>{specs}</td><td>{cases}</td></tr>")
        w("</tbody></table></div></section>")

    # -- kinds legend
    w("<section id='kinds'><h2>Kinds</h2><p class='lead'>Every test carries exactly one kind "
      "marker (registered in <code>tests/conftest.py</code> from <code>tests/spec_items.py</code>)."
      "</p><div class='kinds-legend'>")
    for k, desc in KINDS.items():
        w(f"<span class='chip'>{k}</span><span>{e(desc)}</span>")
    w("</div></section>")

    w(f"</main></div><script>{JS}</script></body></html>")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="store_true", help="run the tests and show pass/fail")
    ap.add_argument("--check", action="store_true", help="exit 1 if the catalog has issues")
    ap.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    collector = collect(args.run)
    funcs = list(collector.funcs.values())
    issues = find_issues(funcs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(funcs, collector.module_docs, issues, args.run, git_describe(args.out)), encoding="utf-8")
    print(f"wrote {args.out} ({len(funcs)} functions, "
          f"{sum(f.n_cases for f in funcs)} cases, {len(issues)} issues)")
    for i in issues:
        print(f"  issue: {i}", file=sys.stderr)
    return 1 if args.check and issues else 0


if __name__ == "__main__":
    sys.exit(main())
