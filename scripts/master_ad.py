"""Master a rendered ad's audio to a loudness target, without touching the picture.

Two-pass EBU R128 loudnorm: measure, then apply linearly so the mix balance
set in film/src/config.ts is preserved; a limiter after it keeps true peak
under -1 dBTP.

    python scripts/master_ad.py film/out/backseat_30s_raw.mp4 film/out/backseat_30s.mp4
    python scripts/master_ad.py raw.mp4 out.mp4 --bitrate 320k
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

TARGET_LUFS = -14.0
TRUE_PEAK = -1.0
LRA = 11.0


def measure(path: str, extra: str = "") -> dict:
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", path, "-af",
         f"{extra}loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={LRA}:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr  # fmt: skip
    return json.loads(re.findall(r"\{[^{}]+\}", out)[-1])


def main() -> int:
    args = sys.argv[1:]
    bitrate = "256k"
    if "--bitrate" in args:
        i = args.index("--bitrate")
        bitrate = args[i + 1]
        del args[i : i + 2]
    source, dest = args[0], args[1]
    first = measure(source)
    params = (
        f"loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK}:LRA={LRA}"
        f":measured_I={first['input_i']}:measured_TP={first['input_tp']}"
        f":measured_LRA={first['input_lra']}:measured_thresh={first['input_thresh']}"
        f":offset={first['target_offset']}:linear=true"
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-i", source, "-c:v", "copy",
         "-af", f"{params},alimiter=limit=0.84:level=false,aresample=48000",
         "-c:a", "aac", "-b:a", bitrate, "-movflags", "+faststart", dest],
        check=True,
    )  # fmt: skip
    final = measure(dest)
    print(f"in:  {first['input_i']} LUFS, true peak {first['input_tp']} dBTP")
    print(f"out: {final['input_i']} LUFS, true peak {final['input_tp']} dBTP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
