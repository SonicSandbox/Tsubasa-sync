"""Pair and retime a whole folder — measuring first, writing only when asked.

    python sync_a_folder.py FOLDER            # measure only: writes and trashes NOTHING
    python sync_a_folder.py FOLDER --write    # write the retimed subtitles

With no FOLDER it runs on a demo folder of EMPTY placeholder files. Nothing in it
can be measured, so every result is an ERROR — which is useful in its own way: it
shows that a result that is not CONFIDENT always says why. Point it at real videos
to see CONFIDENT results with offsets.

⚠ `dedupe=False` below: the new subtitle is ADDED beside the video, and every
original is left exactly where it was. Without it, subtitles that lose a slot go to
the trash — recoverable, but a surprise if you did not expect it.
"""
import sys
import tempfile
from pathlib import Path

import tsubasa


def demo_folder():
    root = Path(tempfile.mkdtemp(prefix="tsubasa-demo-"))
    for name in ("Show - 01.mkv", "Show - 01.ja.srt",
                 "Show - 02.mkv", "Show - 02.ja.srt"):
        (root / name).touch()
    return root


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    write = "--write" in argv
    demo = not args
    folder = demo_folder() if demo else args[0]

    scan = tsubasa.scan(folder)
    report = tsubasa.sync(
        scan,
        write=write,
        dedupe=False,              # keep every original
        # A real run remembers what it synced, so re-running a settled folder
        # costs almost nothing. The demo should not add to that record.
        results=False if demo else None,
    )

    for r in report:
        # `subtitle` is None when the video itself could not be read: no
        # subtitle was tried, and `reason` says why.
        tried = Path(r.subtitle).name if r.subtitle else "(no subtitle tried)"
        print(f"{r.outcome:9}  {Path(r.video).name}  <-  {tried}")
        if r.outcome == "CONFIDENT":
            print(f"           offset {r.offset:+.2f} s, {r.match_percent}% match, "
                  f"{r.verdict_word}"
                  + (f", {len(r.segments)} segments" if len(r.segments) > 1 else ""))
            if r.output_path:
                print(f"           written: {r.output_path}")
        else:
            print(f"           {r.reason}")

    print("\n" + report.summary())
    if not write and report.confident:
        print("(nothing was written — run again with --write)")


if __name__ == "__main__":
    main(sys.argv)
