"""Which subtitle might belong to which video — by name alone.

    python scan_a_library.py                   # a demo library, built in a temp folder
    python scan_a_library.py VIDEOS            # subtitles sitting beside the videos
    python scan_a_library.py VIDEOS SUBTITLES  # videos and subtitles in different places

`scan()` opens none of your files. It reads names, so it is fast and safe to run
over a whole library. It returns candidates, not decisions: `sync()` settles the
pairs by timing.
"""
import sys
import tempfile
from pathlib import Path

import tsubasa


def demo_library():
    """Empty placeholder files with real release names. Enough for scan()."""
    root = Path(tempfile.mkdtemp(prefix="tsubasa-demo-"))
    names = {
        "videos": [
            "[NanakoRaws] Yomi no Tsugai S01E18 (AT-X TV 1080p HEVC AAC).mkv",
            "[SubsPlease] Hell Mode S2 - 10 (1080p) [DD805213].mkv",
            "[SubsPlease] Hell Mode S2 - 11 (1080p) [1A2B3C4D].mkv",
            "Frieren S01E05.mkv",
        ],
        "subs": [
            # Japanese titles, against the English romanisation on the videos
            "黄泉のツガイ.S01E18.WEBRip.ABEMA.ja[cc].srt",
            # numbered from the start of the series: S2 - 10 is episode 22
            "ヘルモード.～やり込み好きのゲーマーは廃設定の異世界で無双する～"
            ".S02E22.祈りが満ちて.WEBRip.ABEMA.ja[cc].srt",
            "ヘルモード.～やり込み好きのゲーマーは廃設定の異世界で無双する～"
            ".S02E23.WEBRip.ABEMA.ja[cc].srt",
            "Frieren S01E05.en.srt",
            "notes.txt",                       # junk is ignored, not an error
        ],
    }
    for folder, files in names.items():
        (root / folder).mkdir()
        for name in files:
            (root / folder / name).touch()
    return root / "videos", root / "subs"


def main(argv):
    if len(argv) >= 2:
        videos, subs = argv[1], (argv[2] if len(argv) >= 3 else None)
    else:
        videos, subs = demo_library()
        print("demo library:", videos.parent)

    scan = tsubasa.scan(videos=videos, subs=subs)
    print(scan.summary())

    print("\nwhat might pair:")
    for video, candidates in scan.pairings():
        print(f"  {video.name}")
        print(f"      read as: {video.title!r}  season {video.season}  "
              f"episode {video.episode}")
        for c in candidates:
            print(f"      -> {c.subtitle.name}   [{c.identity}, "
                  f"language {c.subtitle.lang}]")

    print("\nnothing offered:")
    for video, reason in scan.unpaired():
        print(f"  {video.name}\n      {reason}")
    if not scan.unpaired():
        print("  (none)")


if __name__ == "__main__":
    main(sys.argv)
