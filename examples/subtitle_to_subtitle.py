"""Retime one subtitle against another subtitle file.

    python subtitle_to_subtitle.py SUBTITLE REFERENCE   # writes SUBTITLE-stem.retimed.ext
    python subtitle_to_subtitle.py                      # a generated demo

For when you have a subtitle that is in time — say, an English one — and another
that is not. The result makes the second agree with the first. It cannot know
whether the reference itself matches the video.

Nothing is written by tsubasa here: `render()` returns the retimed file as bytes,
in its original format and encoding, and this script decides the name.
"""
import random
import sys
import tempfile
from pathlib import Path

import tsubasa


def srt(starts, text):
    def stamp(t):
        ms = round(t * 1000)
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    return "".join(f"{i}\n{stamp(t)} --> {stamp(t + 1.5)}\n{text} {i}\n\n"
                   for i, t in enumerate(starts, 1))


def demo_pair():
    """A reference, and a subtitle 2.5 s late with a 10 s jump at 12:00 —
    the shape a TV broadcast with an ad break leaves behind."""
    rng, starts, t = random.Random(1), [], 5.0
    while t < 1400:
        starts.append(round(t, 3))
        t += rng.uniform(1.8, 9.0)
    late = [s + 2.5 if s < 720 else s + 12.5 for s in starts]
    root = Path(tempfile.mkdtemp(prefix="tsubasa-demo-"))
    reference = root / "Show - 01.en.srt"
    subtitle = root / "Show - 01.ja.srt"
    reference.write_text(srt(starts, "line"), encoding="utf-8")
    subtitle.write_text(srt(late, "台詞"), encoding="utf-8")
    return subtitle, reference


def main(argv):
    if len(argv) >= 3:
        subtitle, reference = Path(argv[1]), Path(argv[2])
    else:
        subtitle, reference = demo_pair()
        print("demo:", subtitle.parent)

    r = tsubasa.sync_to_reference(subtitle, reference)
    print(f"{r.outcome}  {subtitle.name}  against  {reference.name}")

    if r.outcome != "CONFIDENT":
        # REFUSED: measured, and not good enough to trust. ERROR: not measured.
        # Both always carry a reason. A partial reference is refused on purpose:
        # a cut in the part it does not cover would be invisible.
        print(" ", r.reason)
        return

    # Each segment is (until, offset): the offset applies up to `until` on the
    # corrected clock, and the last segment's `until` is None — to the end.
    # More than one segment means a cut, such as a removed ad break.
    for until, offset in r.segments:
        if until is None:
            where = "to the end"
        else:
            where = f"until {int(until // 60)}:{int(until % 60):02}"
        print(f"  {offset:+.2f} s {where}")
    print(f"  {r.match_percent}% of reference lines matched — {r.verdict_word}")

    out = tsubasa.render(r)
    target = subtitle.with_name(f"{subtitle.stem}.retimed{out.ext}")
    if target.exists():
        print(f"  {target.name} already exists — not overwriting it")
        return
    target.write_bytes(out.data)
    print(f"  wrote {target}")
    if out.dropped_in_gap:
        print(f"  {out.dropped_in_gap} line(s) fell inside the removed stretch "
              f"and were left out")


if __name__ == "__main__":
    main(sys.argv)
