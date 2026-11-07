"""Source-checkout compatibility entry point for ``python -m operon.worker``."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from operon.worker import main


if __name__ == '__main__':
    main()
