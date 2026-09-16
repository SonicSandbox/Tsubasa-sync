# -*- coding: utf-8 -*-
"""
    python -m tsubasa.dev <command> [options]

Commands:
    corpus      statistics, the train/validation/sealed split, and verification
    roundtrip   read every real corpus file and require a zero shift to produce
                byte-identical output (dev + validation only; sealed untouched)
    container   RUNBOOK 1d: time the native Matroska reader against the block
                walk, and require the two to agree (needs TSUBASA_MEDIA)
    e2e         RUNBOOK 3c-0: assemble a real library in a TEMP directory from
                the staged media and run the whole product over it -- the only
                thing that measures scan() -> sync() end to end
"""
import sys

from ..paths import ConfigError


def _make_console_utf8():
    """Stop a CJK show name from killing a report on a cp1252 console.

    Windows consoles default to the system ANSI codepage.  Printing a Japanese
    filename to one raises UnicodeEncodeError -- and a print that throws
    mid-loop stops the work after it, silently.  A batch editor once skipped
    three of fourteen edits exactly this way and reported eleven OK.

    errors="replace" is correct HERE because this is a human-readable console
    stream.  It is emphatically NOT correct for decoding a subtitle file: a
    Shift-JIS caption read with errors="replace" turned all 346 cues into
    U+FFFD while the ASCII timestamps survived, so the tool reported CONFIDENT
    and wrote perfect timing with no readable text (LEDGER.md, Data).
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _make_console_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(__doc__.lstrip("\n"))
        return 0 if argv else 2

    command, rest = argv[0], argv[1:]

    if command == "corpus":
        from . import corpus
        return corpus.main(rest)

    if command == "roundtrip":
        from . import roundtrip
        return roundtrip.main(rest)

    if command == "cache":
        from . import cachebench
        return cachebench.main(rest)

    if command == "vnbench":
        from . import vnbench
        return vnbench.main(rest)

    if command == "e2e":
        from . import e2ebench
        return e2ebench.main(rest)

    if command == "kanagate":
        from . import kanagate
        return kanagate.main(rest)

    if command == "decoration":
        from . import decoration
        return decoration.main(rest)

    if command == "alias":
        from . import alias
        return alias.main(rest)

    if command == "container":
        from . import containerbench
        return containerbench.main(rest)

    if command == "parsergate":
        from . import parsergate
        return parsergate.main(rest)

    if command == "seriesgate":
        from . import seriesgate
        return seriesgate.main(rest)

    if command == "titlegate":
        from . import titlegate
        return titlegate.main(rest)

    sys.stderr.write("unknown command %r\n" % command)
    sys.stderr.write(__doc__.lstrip("\n"))
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigError as exc:
        # A tooling fault, announced as one.  The oracle's own runner reported
        # a missing pytest as "corpus 1", which reads exactly like one failing
        # test -- four wrong diagnoses have been traced to that confusion.
        sys.stderr.write("\nCONFIG ERROR (tooling fault, not a test failure)\n")
        sys.stderr.write("  %s\n" % exc)
        sys.exit(3)
