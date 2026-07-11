"""PyInstaller entry point for the frozen mission-engine executable.

Kept as a real file (not -c) so the spec build is reproducible. See
build-exe.ps1.
"""

import sys

from mission_engine.adapters.cli import main

if __name__ == "__main__":
    sys.exit(main())
