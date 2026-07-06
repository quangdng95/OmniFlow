"""OmniFlow backend package.

Import convention (enforced by tests/test_import_convention.py): modules
reference each other ONLY module-attribute style —

    from backend import classify, config
    config.load_session()

never `from backend.config import load_session` — a value import freezes the
reference and silently defeats the test suite's monkeypatching, which patches
functions on their home module. No re-exports here for the same reason.
"""
