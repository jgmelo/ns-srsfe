"""Entry point: `python -m srsfe` launches the TUI."""

import sys


def main() -> int:
    # The Textual app arrives in M8; until then there is nothing to launch.
    print("srsfe: TUI not implemented yet (milestone M8).", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
