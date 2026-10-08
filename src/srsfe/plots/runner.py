"""Plot subprocess entry (SPEC §8.2): python -m srsfe.plots.runner <result.json> <plot>...

Runs outside the TUI so matplotlib's GUI loop never blocks Textual. Without --save the
figures are shown in windows; with --save DIR they are written as PNG files instead.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from srsfe.plots.figures import FIGURES, make
from srsfe.tools.base import Result


def save(result: Result, plot: str, path: Path) -> Path:
    """Render one plot to a PNG file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    make(result, plot).savefig(path, dpi=120)
    return path


def show(result: Result, plots: list[str]) -> None:
    """Open one window per plot and block until they are closed (subprocess only)."""
    import matplotlib.pyplot as plt

    for plot in plots:
        fig = make(result, plot)
        manager = plt.figure(num=plot).canvas.manager  # a GUI window to host the Figure
        assert manager is not None
        fig.set_canvas(manager.canvas)
        manager.canvas.figure = fig
        manager.set_window_title(f"SRS-FE — {plot}")
    plt.show()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m srsfe.plots.runner")
    ap.add_argument("result", type=Path, help="Result JSON file")
    ap.add_argument("plots", nargs="+", choices=sorted(FIGURES), help="plot name(s)")
    ap.add_argument("--save", type=Path, metavar="DIR",
                    help="write <DIR>/<prefix><plot>.png instead of showing")
    ap.add_argument("--prefix", default="", help="file name prefix, e.g. '<profile>_'")
    args = ap.parse_args(argv)
    result = Result.from_json(args.result.read_text(encoding="utf-8"))
    if args.save is not None:
        for plot in args.plots:
            print(save(result, plot, args.save / f"{args.prefix}{plot}.png"))
    else:
        show(result, args.plots)
    return 0


if __name__ == "__main__":
    sys.exit(main())
