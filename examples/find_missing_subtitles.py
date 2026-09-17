"""Which videos have no subtitle in a given language?

    python find_missing_subtitles.py                 # a demo folder
    python find_missing_subtitles.py FOLDER          # Japanese, by default
    python find_missing_subtitles.py FOLDER en       # any language tag

This is the question a subtitle downloader asks before it fetches anything.
`ja`, `jpn`, `JA` and `ja-JP` all mean Japanese. A subtitle whose name carries
no language at all (`Show - 03.srt`) does not count as any language, so a video
with only that one is still reported.
"""
import sys
import tempfile
from pathlib import Path

import tsubasa


def demo_folder():
    root = Path(tempfile.mkdtemp(prefix="tsubasa-demo-"))
    for name in ("Show - 01.mkv", "Show - 01.en.srt",     # English only
                 "Show - 02.mkv", "Show - 02.jpn.srt",    # Japanese, spelled jpn
                 "Show - 03.mkv", "Show - 03.srt",        # no language in the name
                 "Show - 04.mkv"):                        # nothing at all
        (root / name).touch()
    return root


def main(argv):
    folder = argv[1] if len(argv) >= 2 else demo_folder()
    lang = argv[2] if len(argv) >= 3 else "ja"

    scan = tsubasa.scan(folder)
    missing = scan.unpaired(lang=lang)

    print(f"{len(missing)} of {len(scan.videos)} videos have no '{lang}' subtitle:")
    for video, reason in missing:
        episode = "?" if video.episode is None else video.episode
        print(f"  {video.title} — episode {episode}\n      {reason}")


if __name__ == "__main__":
    main(sys.argv)
