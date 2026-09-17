# -*- coding: utf-8 -*-
u"""Turn a `--onedir` build into the shipped zip. RUNBOOK 4c · §3.

    python packaging/package_standalone.py <dist folder> --repo <clone> --out <dir>

`<dist folder>` is PyInstaller's output holding `tsubasa/`. Produces:

    <out>/tsubasa-windows-x64.zip
    <out>/SHA256SUMS

⚠ **GPL-3.0 TRAVELS WITH BINARIES** (`STANDALONE-BUILD-SCOPE.md` trap 11).
`LICENSE` and `THIRD_PARTY_LICENSES.md` go INSIDE the zip, beside the
executables — not merely in the repository the zip came from. A person who
downloads a zip and never visits GitHub still has to receive them.

⚠ **AND `README-FIRST.txt` IS NOT DECORATION.** The build is unsigned (ruled),
so the first thing Windows does is warn about it. Trap 7: one line saying what
to expect, no session spent on SmartScreen. It sits beside the executables
because that is where somebody who just unzipped is looking.

⛔ Nothing here is piped and nothing is deleted outside `<out>`.
"""
import argparse
import hashlib
import io
import os
import shutil
import sys
import zipfile

ZIP_NAME = u"tsubasa-windows-x64.zip"

READ_ME = u"""\
tsubasa %(version)s -- pair subtitles to videos and retime them to match.

WHAT TO DO
  Double-click  tsubasa-gui.exe
  Drop a folder that has your videos and your subtitles in it, press Sync.
  Or, from a terminal:  tsubasa.exe <folder>

THE FIRST TIME, WINDOWS WILL WARN YOU
  This build is not code-signed, so SmartScreen shows
  "Windows protected your PC". Click "More info", then "Run anyway".
  Windows Defender may also quarantine a freshly-downloaded copy. Nothing
  here phones home, and the full source is at the address below.

IF SOMETHING GOES WRONG
  Run  tsubasa.exe --version  and include everything it prints. It reports
  the build, whether it is whole, and whether it found ffmpeg.

FFMPEG
  Not included. Videos that are Matroska (.mkv) with a subtitle track inside
  need nothing. Anything else needs ffmpeg and ffprobe on your PATH, or the
  folder holding them in the TSUBASA_FFMPEG environment variable.

WHERE IT KEEPS THINGS
  %%LOCALAPPDATA%%\\tsubasa -- the pairing cache, what it has already synced,
  this app's settings, and the fallback trash. Nothing is written beside your
  media except the subtitles it syncs.

LICENCE
  GPL-3.0-or-later. See LICENSE and THIRD_PARTY_LICENSES.md beside this file.
  Source: https://github.com/SonicSandbox/Tsubasa-sync
"""

#: ⛔ Shipped INSIDE the zip. The repository satisfies the source requirement;
#: these satisfy the one about the binary carrying its terms with it.
CARRY = (u"LICENSE", u"THIRD_PARTY_LICENSES.md")


def _ask_the_app(exe):
    u"""-> (version, exit code, everything it said).

    ⚠ EVERY FAILURE IS NAMED, because the first version threw the evidence
    away: with `_internal/` gone the exe exits `0xFFFFFFFF` and stderr says
    *"Failed to load Python DLL 'python310.dll'"*, and this function died at
    `splitlines()[0]` with `IndexError: list index out of range` — caught, and
    with the wrong message.

    ⚠ AND A TIMEOUT. A hanging executable would otherwise hang the release
    step with no output at all.
    """
    import subprocess
    try:
        done = subprocess.run([exe, u"--version"], capture_output=True,
                              timeout=300)
    except OSError as exc:
        return u"", -1, u"%s could not be run at all: %s" % (exe, exc)
    except subprocess.TimeoutExpired:
        return u"", -1, u"%s --version did not answer within 300 s" % exe

    said = (done.stdout + done.stderr).decode("utf-8", "replace")
    lines = said.splitlines()
    if not lines or not lines[0].startswith(u"tsubasa "):
        return u"", (done.returncode or -1), (
            u"%s --version did not print `tsubasa <version>` on its first "
            u"line. It said:\n%s" % (exe, said.strip() or u"(nothing)"))
    return lines[0].split()[-1], done.returncode, said.strip()


def sha256(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", help="PyInstaller's --distpath, holding tsubasa/")
    ap.add_argument("--repo", required=True, help="the clone, for the licences")
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", default=None)
    args = ap.parse_args()

    app = os.path.join(os.path.abspath(args.dist), u"tsubasa")
    if not os.path.isdir(app):
        sys.exit(u"no `tsubasa/` folder under %s — point this at "
                 u"PyInstaller's --distpath" % args.dist)
    out = os.path.abspath(args.out)
    if not os.path.isdir(out):
        os.makedirs(out)

    # =====================================================================
    # 🚨 A BUILD THAT SAYS `NOT ok` MAY NOT BE PACKAGED
    # =====================================================================
    # ⛔ MEASURED 2026-09-17: with `aliases.tsv.gz` moved aside, this script
    # produced a correctly-named, correctly-checksummed 29 MB zip and exited
    # 0 — while the app's own `--version`, run seconds earlier, exited 1 and
    # printed the PROBLEM sentence. It read the version off stdout and never
    # looked at the return code. That is trap 8's artefact, packaged for
    # release: settles by name 51.4% instead of 80.0%, with nothing raising.
    #
    # ⚠ Only the ORDER of steps in `release.yml` (package, then smoke) kept
    # this off a release page. A human running the natural order — test, then
    # ship — got no warning at all. `doctrine/release`: the version stamp is a
    # PRECONDITION of staging, not a step someone remembers.
    exe = os.path.join(app, u"tsubasa.exe" if os.name == "nt" else u"tsubasa")
    reported, code, why = _ask_the_app(exe)
    if code != 0:
        sys.exit(u"⛔ REFUSING TO PACKAGE. `%s --version` exited %s, which "
                 u"means self_check() found this build is silently worse "
                 u"than it should be. Packaging it would produce a zip that "
                 u"installs, runs, exits 0 and pairs badly.\n\n%s"
                 % (exe, code, why))

    version = args.version or reported
    if args.version and reported != args.version:
        sys.exit(u"⛔ the app reports version %r and %r was asked for. "
                 u"`10-deployment.md`'s release proof rests on the artefact's "
                 u"version equalling the local one." % (reported, args.version))

    for name in CARRY:
        source = os.path.join(os.path.abspath(args.repo), name)
        if not os.path.isfile(source):
            sys.exit(u"%s is not in the repo at %s — GPL-3.0 travels with the "
                     u"binary and this zip may not ship without it" % (name,
                                                                       source))
        shutil.copy2(source, os.path.join(app, name))
        print(u"carried  %s" % name)

    notes = os.path.join(app, u"README-FIRST.txt")
    with io.open(notes, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(READ_ME % {u"version": version})
    print(u"wrote    README-FIRST.txt")

    zip_path = os.path.join(out, ZIP_NAME)
    root = os.path.dirname(app)
    # ⛔ THE WALK HAD NO EXCLUSIONS, and a `.held` file left behind by the
    # smoke test's own table-removal check travelled into a shipped zip.
    # Anything a harness parks in the bundle is not a deliverable.
    junk = (u".held", u".pyc", u".pyo", u".pdb", u".tmp", u".log")
    skipped = []
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(app):
            dirs[:] = sorted(d for d in dirs if d != u"__pycache__")
            for name in sorted(files):
                if name.endswith(junk):
                    skipped.append(name)
                    continue
                full = os.path.join(base, name)
                z.write(full, os.path.relpath(full, root).replace(os.sep, u"/"))
    if skipped:
        # ⚠ NAMED, never silent. A file excluded from the zip that the app
        # actually needed is the next defect, and it must not be invisible.
        print(u"skipped  %d non-deliverable file(s): %s"
              % (len(skipped), u", ".join(sorted(set(skipped))[:6])))
    size = os.path.getsize(zip_path)
    print(u"zipped   %s  %.1f MB" % (ZIP_NAME, size / 1024.0 / 1024.0))

    # ⚠ The format `sha256sum -c` reads: two spaces, then a path relative to
    # the file. A checksum nobody can verify with the standard tool is a
    # checksum nobody verifies.
    digest = sha256(zip_path)
    with io.open(os.path.join(out, u"SHA256SUMS"), "w", encoding="utf-8",
                 newline="\n") as fh:
        fh.write(u"%s  %s\n" % (digest, ZIP_NAME))
    print(u"sha256   %s" % digest)
    print(u"version  %s" % version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
