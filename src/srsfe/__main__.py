"""Entry point: `python -m srsfe` launches the TUI."""

import sys


def main() -> int:
    from srsfe.tui.app import SrsfeApp

    SrsfeApp().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
