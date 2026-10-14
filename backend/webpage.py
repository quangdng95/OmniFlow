"""The built index.html with its absolute URLs filled in.

Share previews (og:image, twitter:image, og:url) need ABSOLUTE addresses, but the same build is served from more
than one place (the web version's host(s) and the Mac app on 127.0.0.1). index.html therefore carries the
placeholder below and each server fills in its own origin when it serves the page.
"""

import os

from flask import Response

from backend import paths

PLACEHOLDER = "__PUBLIC_ORIGIN__"


def render_index(origin):
    with open(os.path.join(paths.WEB_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read().replace(PLACEHOLDER, origin.rstrip("/"))
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache"  # the page itself is never cached; its hashed assets are
    return response
