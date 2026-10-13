"""Load standalone protocol/transport without importing Home Assistant on Windows."""
import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'custom_components/axpert_max_twin'
namespace = types.ModuleType('axpert_max_twin')
namespace.__path__ = [str(PACKAGE)]
sys.modules.setdefault('axpert_max_twin', namespace)


def load(name):
    full = 'axpert_max_twin.' + name
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, PACKAGE / (name+'.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module
