"""Entry point: tkinter GUI."""

from __future__ import annotations

import sys


def main() -> int:
    # Import lazily để PyInstaller không bị nặng khi `--help`
    from .gui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
