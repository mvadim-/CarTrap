from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from cartrap import __version__


def test_package_import_smoke() -> None:
    assert __version__ == "0.1.0"
