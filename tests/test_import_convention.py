"""Meta-test: enforce the backend package's import convention.

Every cross-module reference inside backend/ must be module-attribute style
(`from backend import config` … `config.load_session()`). A value import
(`from backend.config import load_session`) freezes the reference at import
time and silently defeats the test suite's monkeypatching — patched functions
would no longer intercept and tests would hit the real network. And only
server.py (the facade) may import backend.app, keeping app.py at the top of
the dependency DAG (no cycles).
"""

import os
import re

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")

VALUE_IMPORT = re.compile(r"^\s*from backend\.\w+ import ", re.M)
APP_IMPORT = re.compile(r"^\s*(?:from backend import .*\bapp\b|from backend\.app import |import backend\.app\b)", re.M)


def _backend_sources():
    for name in sorted(os.listdir(BACKEND_DIR)):
        if name.endswith(".py"):
            with open(os.path.join(BACKEND_DIR, name)) as f:
                yield name, f.read()


def test_backend_modules_never_value_import_from_siblings():
    offenders = [name for name, src in _backend_sources() if VALUE_IMPORT.search(src)]
    assert offenders == [], f"value imports (from backend.x import y) found in: {offenders}"


def test_only_the_facade_imports_backend_app():
    offenders = [name for name, src in _backend_sources() if name != "app.py" and APP_IMPORT.search(src)]
    assert offenders == [], f"backend modules must not import backend.app: {offenders}"
