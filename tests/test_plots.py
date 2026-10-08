"""M7: plot figures build without error (Agg backend) and the runner saves PNGs (SPEC §8.2)."""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from srsfe.core.params import Params  # noqa: E402
from srsfe.plots import figures, runner  # noqa: E402
from srsfe.tools import REGISTRY, Result  # noqa: E402
from tests import golden  # noqa: E402

AXES = {"bode": 2, "spectrum": 2, "budget": 1, "noise": 1}


@pytest.fixture(scope="module")
def design_all(golden_params: dict[str, Any]) -> Result:
    return REGISTRY["d"].calc("0").run(Params.from_dict(golden_params))


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "bode", "spectrum", "budget", "noise")
@pytest.mark.parametrize("plot", list(AXES))
def test_figures_build(design_all: Result, plot: str) -> None:
    """Each plot builds a Figure from the golden Design/All result, with its panels."""
    fig = figures.make(design_all, plot)
    assert isinstance(fig, Figure)
    assert len(fig.axes) == AXES[plot]
    fig.canvas.draw()  # full render, catches layout/formatter errors


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "bode")
def test_bode_for_analyze(golden_params: dict[str, Any]) -> None:
    """Bode builds for an Analyze result (no harmonics table, resonance from f0_calc)."""
    p = Params.from_dict(golden_params).replace(**golden.ANALYZE_INPUTS)
    fig = figures.make(REGISTRY["a"].calcs[0].run(p), "bode")
    fig.canvas.draw()


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "spectrum", "noise")
@pytest.mark.parametrize(("calc", "plot"), [("2", "spectrum"), ("4", "noise"), ("5", "noise")])
def test_single_calc_figures(golden_params: dict[str, Any], calc: str, plot: str) -> None:
    """Plots also build from the narrower calcs that offer them (no signal / no lock-in data)."""
    r = REGISTRY["d"].calc(calc).run(Params.from_dict(golden_params))
    assert plot in r.plots
    figures.make(r, plot).canvas.draw()


@pytest.mark.errors
def test_unavailable_or_unknown_plot(golden_params: dict[str, Any]) -> None:
    """A plot the result does not offer raises ValueError; an unknown name raises KeyError."""
    sizing = REGISTRY["d"].calc("1").run(Params.from_dict(golden_params))
    with pytest.raises(ValueError):
        figures.make(sizing, "budget")
    with pytest.raises(KeyError):
        figures.make(sizing, "polar")


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "runner")
def test_runner_saves_pngs(design_all: Result, tmp_path: Path) -> None:
    """runner.main reads a Result JSON and writes <prefix><plot>.png for each plot."""
    src = tmp_path / "result.json"
    src.write_text(design_all.to_json(), encoding="utf-8")
    out = tmp_path / "plots"
    assert runner.main([str(src), "bode", "budget", "--save", str(out), "--prefix", "golden_"]) == 0
    for plot in ("bode", "budget"):
        png = out / f"golden_{plot}.png"
        assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.smoke
@pytest.mark.spec("§8.2", "runner")
def test_runner_as_subprocess(design_all: Result, tmp_path: Path) -> None:
    """`python -m srsfe.plots.runner <result.json> <plot> --save DIR` works as a subprocess."""
    src = tmp_path / "r.json"
    src.write_text(design_all.to_json(), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "srsfe.plots.runner", str(src), "noise", "--save", str(tmp_path)],
        capture_output=True, text=True, env={"MPLBACKEND": "Agg", **_env()},
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "noise.png").is_file()


@pytest.mark.schema
def test_figures_never_use_pyplot() -> None:
    """plots/figures.py builds Figures directly: no pyplot import, never plt.show()."""
    tree = ast.parse(Path(figures.__file__).read_text(encoding="utf-8"))
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert not any("pyplot" in m for m in imported) and "show" not in called


@pytest.mark.schema
@pytest.mark.spec("§2", "core-pure")
def test_core_imports_no_ui_libraries() -> None:
    """Importing every core module pulls in neither textual nor matplotlib."""
    code = (
        "import sys, pkgutil, importlib, srsfe.core as c\n"
        "for m in pkgutil.iter_modules(c.__path__): importlib.import_module(f'srsfe.core.{m.name}')\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('textual', 'matplotlib')]\n"
        "assert not bad, bad\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=_env())
    assert proc.returncode == 0, proc.stderr


def _env() -> dict[str, str]:
    import os

    return dict(os.environ)
