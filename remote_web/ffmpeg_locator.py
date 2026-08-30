"""Architecture-aware ffmpeg binary resolution for remote_web's unfrozen
(non-PyInstaller) execution (spec §5.1).

backend.paths.get_ffmpeg_path() always looks for a file literally named
`ffmpeg` at the repo root - correct only because OmniFlow.spec already staged
the matching-architecture binary under that exact name at BUILD time.
remote_web runs unfrozen (`python3 -m remote_web.app`, no PyInstaller step),
so nothing performs that selection - this module does its own resolution
instead, entirely inside remote_web/, and never calls
backend.paths.get_ffmpeg_path().

Both source binaries are real, Git-LFS-tracked files at the repo root,
confirmed present during this design's review (see the spec's §5.1):
./ffmpeg (arm64) and ./ffmpeg-x86_64 (Intel).
"""

import os
import platform
import subprocess

from backend import paths

_BAD_CPU_TYPE_ERRNO = 86


def _exec_ok(path):
    try:
        subprocess.run([path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def resolve_ffmpeg_binary():
    name = "ffmpeg" if platform.machine() == "arm64" else "ffmpeg-x86_64"
    candidate = os.path.join(paths.BASE_DIR, name)
    if not os.path.exists(candidate):
        return None
    if not os.access(candidate, os.X_OK):
        try:
            os.chmod(candidate, 0o755)
        except OSError:
            pass
    if not os.access(candidate, os.X_OK):
        return None
    if not _exec_ok(candidate):
        return None
    return candidate


def ffmpeg_unavailable_message():
    # Unlike backend.paths.ffmpeg_unavailable_message() (which tells an END
    # USER which .dmg to download instead), remote_web is one long-running
    # deployment on one machine - an unresolvable ffmpeg here means the
    # DEPLOYMENT itself is broken, not that the visitor picked the wrong
    # installer. The actionable audience is whoever runs the Mac, not the
    # phone on the other end.
    return (
        "❌ Lỗi: Không tìm thấy FFmpeg khả dụng cho kiến trúc CPU của máy chủ này "
        f"({platform.machine()}). Vui lòng liên hệ quản trị viên để kiểm tra lại triển khai."
    )
