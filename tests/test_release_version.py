"""The app version lives in two places that must agree: the Mac app's Info.plist
(packaging/vidrop.spec) and the frontend package. A release bumps both."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), "r") as f:
        return f.read()


def test_the_version_lives_in_one_place_and_the_spec_and_build_script_read_it():
    package = json.loads(_read("frontend", "package.json"))["version"]
    lock = json.loads(_read("frontend", "package-lock.json"))
    assert package == lock["version"] == lock["packages"][""]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", package)

    spec = _read("packaging/vidrop.spec")
    assert '"frontend", "package.json"' in spec
    assert '"CFBundleShortVersionString": VERSION' in spec and '"CFBundleVersion": VERSION' in spec
    assert not re.search(r'"CFBundle(?:Short)?Version(?:String)?":\s*"\d', spec)  # no second, hard-coded copy

    build = _read("scripts", "build.sh")
    assert "frontend/package.json" in build and 'RELEASE_DIR="$RELEASE_ROOT/v$VERSION"' in build


def test_the_bundle_identifier_is_vidrops_own():
    spec = _read("packaging/vidrop.spec")
    assert 'bundle_identifier="com.vidrop.app"' in spec
    assert "omniflow" not in spec.lower()
