"""Rough cut of the submission video from one capture take (studio/e2e/demo-video-capture.mjs) and a cut list.

  python scripts/video_rough_cut.py --take <take dir> [--cutlist docs/submission/video/cutlist.json] --out <dir> [--ffmpeg ffmpeg]

The cut list (JSON) is the single source for picture and words. Each segment has a storyboard shot number, its narration
(the voice-over text, also burnt in as captions for the silent draft) and its clips. A clip is
`{"chapter": <capture chapter>, "from": <s into the chapter>, "dur": <s of output>, "speed": <playback factor>}`.
Chapters are located through the take's manifest (`video_start`), never by hand-typed times. Title and end cards are plain
text on the Studio background, with no logos.

Outputs in --out: `rough_cut.mp4` (1920x1080, 30 fps, H.264 plus a silent AAC track, captions burnt in),
`rough_cut_clean.mp4` (the same picture without captions, for the voice-over edit), `narration.srt` and `report.json`
(segment times, source chapters, and the ffprobe checks: duration < 180 s, 1920x1080, 30 fps).
Only footage of the app is used. Nothing is generated except the two text cards.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

FONT = "C\\:/Windows/Fonts/segoeui.ttf"           # drawtext path syntax (escaped drive colon)
FONT_BOLD = "C\\:/Windows/Fonts/segoeuib.ttf"
BG = "0x0d1016"                                    # Studio --bg


def run(cmd: list[str], cwd: str) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg failed ({r.returncode}): {' '.join(cmd[:6])} ...\n{r.stderr[-1500:]}")


def card(ff: str, out: str, cwd: str, title: str, sub: str, seconds: float) -> None:
    esc = lambda t: t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’")   # noqa: E731
    vf = (f"drawtext=fontfile='{FONT_BOLD}':text='{esc(title)}':fontcolor=0xe9edf4:fontsize=88:x=(w-text_w)/2:y=(h/2)-90,"
          f"drawtext=fontfile='{FONT}':text='{esc(sub)}':fontcolor=0x8f9aae:fontsize=38:x=(w-text_w)/2:y=(h/2)+30,"
          f"fade=t=in:st=0:d=0.4,fade=t=out:st={seconds - 0.4:.2f}:d=0.4")
    run([ff, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={BG}:s=1920x1080:r=30:d={seconds}", "-vf", vf,
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", out], cwd)


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def captions(segments: list[dict], max_words: int = 14) -> str:
    """Split each segment's narration into caption cues of <= max_words, timed in proportion to their word counts."""
    out, n = [], 1
    for s in segments:
        words = (s.get("narration") or "").split()
        if not words:
            continue
        chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
        t, span = s["start"], s["end"] - s["start"]
        for c in chunks:
            d = span * len(c) / len(words)
            out.append(f"{n}\n{srt_time(t)} --> {srt_time(t + d - 0.05)}\n{' '.join(c)}\n")
            t += d
            n += 1
    return "\n".join(out)


def probe(ff_probe: str, path: str) -> dict:
    r = subprocess.run([ff_probe, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
                        "-show_entries", "format=duration", "-of", "json", path], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--take", required=True)
    ap.add_argument("--cutlist", default=os.path.join(os.path.dirname(__file__), "..", "docs", "submission", "video", "cutlist.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--ffmpeg", default="ffmpeg")
    a = ap.parse_args(argv)
    ff, ffp = a.ffmpeg, os.path.join(os.path.dirname(a.ffmpeg), "ffprobe") if os.path.dirname(a.ffmpeg) else "ffprobe"
    take = os.path.abspath(a.take)
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(take, "manifest.json"), encoding="utf-8") as fh:
        man = json.load(fh)
    with open(a.cutlist, encoding="utf-8") as fh:
        cut = json.load(fh)
    chapters = {c["shot"]: c for c in man["chapters"]}
    src = os.path.join(take, "take.mp4")
    parts, report, t = [], {"take": os.path.basename(take), "renderer": man.get("renderer"), "segments": []}, 0.0
    if cut.get("title"):
        card(ff, "p000_title.mp4", out, cut["title"]["text"], cut["title"]["sub"], cut["title"]["seconds"])
        parts.append("p000_title.mp4")
        t += cut["title"]["seconds"]
    timed = []
    for si, seg in enumerate(cut["segments"], 1):
        start = t
        for ci, clip in enumerate(seg["clips"]):
            ch = chapters.get(clip["chapter"])
            if ch is None:
                raise SystemExit(f"segment {seg['shot']}: chapter {clip['chapter']!r} is not in the take")
            speed = float(clip.get("speed", 1.0))
            src_from = ch["video_start"] + float(clip.get("from", 0.0))
            src_len = float(clip["dur"]) * speed
            if src_from + src_len > ch["video_end"] + 0.05:
                raise SystemExit(f"segment {seg['shot']} clip {ci}: {src_len:.1f} s from {clip.get('from', 0)} s overruns chapter "
                                 f"{clip['chapter']} ({ch['video_end'] - ch['video_start']:.1f} s)")
            name = f"p{si:02d}{ci}_{clip['chapter']}.mp4"
            run([ff, "-y", "-loglevel", "error", "-ss", f"{src_from:.3f}", "-t", f"{src_len:.3f}", "-i", src,
                 "-vf", f"setpts=PTS/{speed},fps=30,format=yuv420p", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", name], out)
            parts.append(name)
            t += float(clip["dur"])
        timed.append({**seg, "start": start, "end": t})
        report["segments"].append({"shot": seg["shot"], "start": round(start, 2), "end": round(t, 2),
                                   "chapters": [c["chapter"] for c in seg["clips"]], "narration_words": len((seg.get("narration") or "").split())})
    if cut.get("end"):
        card(ff, "p999_end.mp4", out, cut["end"]["text"], cut["end"]["sub"], cut["end"]["seconds"])
        parts.append("p999_end.mp4")
        t += cut["end"]["seconds"]
    with open(os.path.join(out, "parts.txt"), "w", encoding="utf-8") as fh:
        fh.write("".join(f"file '{p}'\n" for p in parts))
    with open(os.path.join(out, "narration.srt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(captions(timed))
    run([ff, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "parts.txt", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
         "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "rough_cut_clean.mp4"], out)
    style = "FontName=Segoe UI,FontSize=15,PrimaryColour=&H00F4EDE9,BackColour=&H99000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=36"
    run([ff, "-y", "-loglevel", "error", "-i", "rough_cut_clean.mp4", "-vf", f"subtitles=narration.srt:force_style='{style}'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "copy", "-movflags", "+faststart", "rough_cut.mp4"], out)
    checks = {}
    for f in ("rough_cut.mp4", "rough_cut_clean.mp4"):
        p = probe(ffp, os.path.join(out, f))
        v = next(s for s in p["streams"] if s["codec_type"] == "video")
        dur = float(p["format"]["duration"])
        checks[f] = {"duration_s": round(dur, 2), "under_3_min": dur < 180, "size": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"],
                     "ok": dur < 180 and (v["width"], v["height"]) == (1920, 1080) and v["r_frame_rate"] == "30/1"}
    report["checks"] = checks
    with open(os.path.join(out, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    for p in parts:
        os.remove(os.path.join(out, p))
    print(json.dumps(checks))
    return 0 if all(c["ok"] for c in checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
