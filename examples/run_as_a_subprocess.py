"""Run tsubasa in a separate process and read its results as they arrive.

    python run_as_a_subprocess.py VIDEO SUBTITLE
    python run_as_a_subprocess.py                  # a demo pair (placeholder files)

The pattern for a desktop app: the work happens outside your process, so you can
cancel it by ending the child, and nothing it does can freeze or crash your UI.
Each result is one line of JSON on stdout, in the same shape as the library's
`Result`. The one-line summary goes to stderr. The exit code is 0 when every pair
was decided and written (or would be), 1 when something was REFUSED or ERRORED,
and 2 when the command itself was wrong.

⚠ In an app frozen with PyInstaller, `sys.executable` is your app, not Python.
Relaunch your own executable with a flag of your choosing, and in that child call
`tsubasa.cli.main(["--pair", video, subtitle, "--json"])`.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def demo_pair():
    root = Path(tempfile.mkdtemp(prefix="tsubasa-demo-"))
    video, subtitle = root / "Show - 01.mkv", root / "Show - 01.ja.srt"
    video.touch()                            # empty: will come back as an ERROR
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nline\n\n",
                        encoding="utf-8")
    return video, subtitle


def main(argv):
    if len(argv) >= 3:
        video, subtitle = argv[1], argv[2]
    else:
        video, subtitle = demo_pair()

    command = [sys.executable, "-m", "tsubasa",
               "--pair", str(video), str(subtitle),
               "--json", "--dry-run"]       # drop --dry-run to write
    # UTF-8 on the child, or a Japanese path in a traceback can raise before
    # the real error is printed.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    # stderr goes to a temporary file rather than a pipe: reading one pipe to
    # the end while the other fills up is how a child process deadlocks.
    with tempfile.TemporaryFile() as err:
        child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err,
                                 env=env, encoding="utf-8")
        for line in child.stdout:            # one result per line, as it lands
            result = json.loads(line)
            # "subtitle" is null when the video itself could not be read
            tried = Path(result["subtitle"]).name if result["subtitle"] else "-"
            print(f"{result['outcome']:9}  {Path(result['video']).name}  <-  {tried}")
            if result["outcome"] == "CONFIDENT":
                print(f"           offset {result['offset']:+.2f} s, "
                      f"{result['match_percent']}% match, {result['verdict_word']}")
            else:
                print(f"           {result['reason']}")
        code = child.wait()
        err.seek(0)
        summary = err.read().decode("utf-8", "replace").strip()

    print(f"\nexit code {code}: {summary}")


if __name__ == "__main__":
    main(sys.argv)
