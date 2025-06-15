# tests/conftest.py
import sys
from unittest.mock import MagicMock

# Create mock objects for modules that are not available
MOCK_MODULES = {
    "apt": MagicMock(),
    "apt_pkg": MagicMock(),
    "aptsources": MagicMock(),
    "aptsources.sourceslist": MagicMock(),
}

MOCK_MODULES["apt"].Cache.return_value.commit = MagicMock()
MOCK_MODULES["aptsources"].sourceslist.SourcesList = MagicMock()

sys.modules.update(MOCK_MODULES)
