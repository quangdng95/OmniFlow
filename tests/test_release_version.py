"""The app version lives in two places that must agree: the Mac app's Info.plist
(vidrop.spec) and the frontend package. A release bumps both."""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), "r") as f:
        return f.read()


def test_the_mac_app_and_the_frontend_package_have_the_same_version():
    spec = _read("vidrop.spec")
    short = re.search(r'"CFBundleShortVersionString":\s*"([^"]+)"', spec).group(1)
    build = re.search(r'"CFBundleVersion":\s*"([^"]+)"', spec).group(1)
    package = json.loads(_read("frontend", "package.json"))["version"]
    lock = json.loads(_read("frontend", "package-lock.json"))
    assert short == build == package == lock["version"] == lock["packages"][""]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", short)


def test_the_bundle_identifier_is_vidrops_own():
    spec = _read("vidrop.spec")
    assert 'bundle_identifier="com.vidrop.app"' in spec
    assert "omniflow" not in spec.lower()
