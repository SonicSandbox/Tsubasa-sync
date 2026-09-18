# -*- coding: utf-8 -*-
u"""
The command line. RUNBOOK step 3c. Authority: `05-interface.md` §*The CLI
output — RULED, do not redesign*, `LEDGER.md` §Interface.

===========================================================================
🚨 THE THREE CLAIMS THAT CARRY THIS FILE
===========================================================================

  1. **Refusals and errors are printed FIRST.** `05-interface.md`: *the one
     thing needing attention must not sit below 23 successes.* ⭐ Asserted by
     LINE INDEX on a mixed report, not by reading the source for a `sort`.
  2. ⛔ **No positive word precedes a problem.** `LEDGER.md` §Interface: a GUI
     painted a run containing refusals green because *"11 confident, 1
     refused"* contains the word `confident`. The summary is
     `SyncReport.summary()` — checked where it lives — and this file asserts
     the CLI does not put anything in front of it.
  3. ⛔ **The CLI decides nothing.** Every word, number and reason on screen
     came from a `Result`. Asserted by feeding a `Result` a value and
     requiring that value back verbatim, so a CLI that recomputed anything
     would have to reproduce it exactly to stay green.

⚠ AND THE COLUMNS ARE MEASURED IN CELLS, NOT CHARACTERS. `05-interface.md`'s
own worked example is `片田舎のおっさん S02E01.ass`; a CJK character takes two
of them. A suite built only from ASCII fixtures cannot see the misalignment
that produces, which is why every layout check here has a Japanese twin.

⚠ THE END-TO-END CHECKS drive `main()` over a real synthetic Matroska with a
real subtitle beside it, because the ruled output is a claim about what a
person sees after a real run — not about a formatter.
"""
import io
import json
import os
import sys
import unicodedata

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import api as API                                # noqa: E402
from tsubasa import cli as CLI                                # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa.verdict import CONFIDENT, ERROR, REFUSED         # noqa: E402

# ⭐ REUSED, NOT REBUILT. `doctrine/tooling` §anti-rederivation.
from test_pipeline import (                                   # noqa: E402
    MKV_CUES, RUNTIME, _shifted, _srt, _tree, _write, _write_mkv, CUE_STARTS,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def a_result(outcome=CONFIDENT, video=u"/lib/Show S01E01.mkv",
             subtitle=u"/lib/[Grp] Show - 01.ja.srt", **kw):
    u"""A `Result` with the invariants satisfied. ⚠ Built through the real
    constructor, which raises on a refusal carrying a confidence word and on a
    CONFIDENT with none — so a fixture that drifts fails loudly here rather
    than rendering something impossible."""
    fields = dict(reason=u"", segments=[(None, -2.0)], match_rate=0.96,
                  excess_over_chance=4.3, raw_excess=4.3, episode=1,
                  verdict_word=u"locked", runtime_check=u"held")
    if outcome != CONFIDENT:
        fields.update(verdict_word=None, reason=u"measured, and not a match")
    fields.update(kw)
    return API.Result(video, subtitle, outcome, **fields)


def a_report(results, **kw):
    return PIPE.SyncReport(results, **kw)


def render(report, **kw):
    return CLI.render(report, **kw)


def one_episode(folder, stem=u"Show S01E01", delay=2.0, sub_name=None):
    folder = str(folder)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    video = os.path.join(folder, stem + u".mkv")
    _write_mkv(video, MKV_CUES, duration_s=RUNTIME, per_cluster=4)
    sub = _write(os.path.join(folder, sub_name or (u"[Grp] %s.ja.srt" % stem)),
                 _shifted(delay))
    return video, sub


class Stream(object):
    u"""A stand-in for stdout that keeps what was written. ⚠ It also answers
    `reconfigure` by raising `AttributeError`, which is the branch `_console_utf8`
    takes on a stream that has no such method — the real case on Python 2 and on
    a `StringIO`."""

    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    @property
    def text(self):
        return u"".join(self.parts)

    @property
    def lines(self):
        return self.text.splitlines()


@pytest.fixture()
def out():
    return Stream()


@pytest.fixture()
def err():
    return Stream()


# ---------------------------------------------------------------------------
# 🚨 CLAIM 1 — refusals and errors are printed FIRST
# ---------------------------------------------------------------------------

def test_a_REFUSAL_is_printed_ABOVE_every_success():
    u"""🚨 `05-interface.md`: *the one thing needing attention must not sit
    below 23 successes.*

    ⭐ ASSERTED BY LINE INDEX, on a report whose refusal is LAST in the list.
    A check that fed them in the right order already would be green against a
    renderer that did no ordering at all.
    """
    report = a_report([a_result(subtitle=u"/lib/ok-%d.ja.srt" % i)
                       for i in range(23)]
                      + [a_result(REFUSED, subtitle=u"/lib/bad.ja.srt")])
    lines = render(report)
    where_bad = next(i for i, l in enumerate(lines) if u"bad.ja.srt" in l)
    where_good = next(i for i, l in enumerate(lines) if u"ok-0.ja.srt" in l)
    assert where_bad < where_good, u"\n".join(lines)


def test_an_ERROR_is_printed_above_every_success_too():
    u"""⚠ ERROR and REFUSED are different outcomes and this ordering is about
    *needs attention*, which both are. `03-permissions.md`: there is no fourth
    outcome, so the two together are the whole of it."""
    report = a_report([a_result(subtitle=u"/lib/ok.ja.srt"),
                       a_result(ERROR, subtitle=u"/lib/broken.ja.srt")])
    lines = render(report)
    assert (next(i for i, l in enumerate(lines) if u"broken" in l)
            < next(i for i, l in enumerate(lines) if u"ok.ja.srt" in l))


def test_the_ordering_holds_when_EVERYTHING_is_refused():
    u"""⚠ The control. A renderer that simply reversed the list would pass the
    check above and fail here."""
    report = a_report([a_result(REFUSED, subtitle=u"/lib/a.ja.srt"),
                       a_result(REFUSED, subtitle=u"/lib/b.ja.srt")])
    lines = render(report)
    assert (next(i for i, l in enumerate(lines) if u"a.ja.srt" in l)
            < next(i for i, l in enumerate(lines) if u"b.ja.srt" in l))


# ---------------------------------------------------------------------------
# ⛔ CLAIM 2 — no positive word precedes a problem
# ---------------------------------------------------------------------------

def test_the_summary_is_the_LIBRARY_S_and_nothing_is_put_in_front_of_it():
    u"""⛔ `LEDGER.md` §Interface: a GUI painted a run containing refusals green
    because *"11 confident, 1 refused"* contains the word `confident`.

    ⭐ `SyncReport.summary()` already leads with what is wrong and is checked
    where it lives. The claim HERE is that the CLI does not reimplement it and
    does not prepend anything — so the last line ends with the library's own
    sentence, verbatim.
    """
    report = a_report([a_result(), a_result(REFUSED, subtitle=u"/lib/x.srt")])
    lines = render(report)
    assert lines[-1].strip() == report.summary()


def test_the_summary_line_LEADS_with_the_refusal_even_with_an_elapsed_time():
    report = a_report([a_result(), a_result(REFUSED, subtitle=u"/lib/x.srt")])
    tail = render(report, elapsed=3.14)[-1].strip()
    assert tail.startswith(u"1 refused"), tail
    assert tail.endswith(u"3.1 s"), tail


def test_no_confidence_word_appears_on_a_REFUSED_line():
    u"""⛔ `LEDGER.md` §Interface, from the other side. A refusal carries **no
    word at all** — `Result` raises if one is set, so the renderer has nothing
    to filter; this is the check that keeps it that way.

    ⭐ AND THE STRUCTURAL HALF: a refused line never goes through `_evidence`
    at all, which is why a mutant that made `_evidence` invent a word could not
    reach it. Asserted here so the branch cannot quietly start calling it.
    """
    report = a_report([a_result(REFUSED, subtitle=u"/lib/x.srt",
                                reason=u"measured, and not a match")])
    lines = render(report)
    block = u"\n".join(lines)
    for word in (u"locked", u"strong", u"fair", u"uncertain"):
        assert word not in block, (word, block)
    # ⛔ No evidence line at all: a refusal has no match percentage to stand
    # behind, and printing one would be evidence for a claim not made.
    assert u"% match" not in block, block


# ---------------------------------------------------------------------------
# ⛔ CLAIM 3 — the CLI decides nothing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("word", [u"locked", u"strong", u"fair", u"uncertain"])
def test_the_confidence_word_is_REPRODUCED_never_derived(word):
    u"""⛔ Every one of the four, verbatim. A CLI that recomputed the band from
    `excess_over_chance` would have to reproduce `verdict.py` exactly to stay
    green — and `05-interface.md` measured that a single threshold refuses 16%
    of correct pairs, so a second implementation is a second defect."""
    report = a_report([a_result(verdict_word=word, excess_over_chance=99.0)])
    assert word in u"\n".join(render(report))


def test_the_match_PERCENTAGE_is_the_results_own():
    u"""⚠ THE RATE IS CHOSEN SO TRUNCATION AND ROUNDING DISAGREE. At 0.913 both
    give 91 and a mutant that recomputed the percentage its own way was a
    no-op; 0.918 is 91 truncated and 92 rounded, and `Result.match_percent`
    rules that it is 92."""
    report = a_report([a_result(match_rate=0.918)])
    assert int(0.918 * 100) != int(round(0.918 * 100)), u"the fixture is blind"
    assert u"92% match" in u"\n".join(render(report))


def test_the_REASON_is_printed_verbatim_not_summarised():
    reason = (u"no subtitle track; on the audio the first 3:42 want a "
              u"different offset")
    report = a_report([a_result(REFUSED, reason=reason)])
    block = u" ".join(l.strip() for l in render(report))
    assert reason in block, block


def test_the_EPISODE_column_is_the_results_own_number():
    u"""⛔ THE NUMBER IS ON THE `Result`, and the renderer may not re-derive it.

    ⭐ Asserted by DISAGREEING WITH THE FILENAME on purpose: the video is
    `Show S01E01.mkv` and the result says episode 7. A renderer that parsed the
    name would print 01. The source-import check next door cannot see this —
    a re-parse with an already-imported `re` adds no import at all.
    """
    report = a_report([a_result(video=u"/lib/Show S01E01.mkv", episode=7)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u" 07 " in line, line
    assert u" 01 " not in line, line


def test_a_result_with_NO_episode_leaves_the_column_blank():
    u"""⚠ A film has no episode, and `Result.episode` is None. Printing `00`
    would be a number nothing measured."""
    report = a_report([a_result(episode=None)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"00" not in line, line


def test_the_cli_imports_no_decision_making_module():
    u"""⛔ READ FROM THE SOURCE, because *it happens not to call one today* is a
    statement about today's code. `05-interface.md`: the library is the
    product and the CLI is a thin wrapper — the moment this file can reach a
    threshold or an aligner, there are two answers to one question."""
    import ast
    src = io.open(os.path.join(ROOT, "tsubasa", "cli.py"),
                  encoding="utf-8").read()
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(u".")[0])
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(u".")[0] for a in node.names)
    for banned in ("align", "arbitrate", "dedupe", "duration", "cues",
                   "movies", "explicit", "sidecar", "naming"):
        assert banned not in imported, \
            u"cli.py imports %s; a decision has moved into the wrapper" % banned


# ---------------------------------------------------------------------------
# ⭐ the ruled shape — evidence, and `old → new`
# ---------------------------------------------------------------------------

def test_every_confident_line_carries_EVIDENCE_never_a_bare_tick():
    u"""`05-interface.md`: *evidence on every line — `96% match · locked`,
    never a bare tick.*"""
    report = a_report([a_result()])
    lines = render(report)
    tick = next(i for i, l in enumerate(lines) if u"✓" in l)
    evidence = lines[tick + 1]
    assert u"96% match" in evidence and u"locked" in evidence, evidence


def test_old_to_new_is_shown_when_the_name_changed():
    u"""`05-interface.md`: *the user sees what happened to their folder before
    trusting it.*"""
    report = a_report([a_result(output_path=u"/lib/Show S01E01.ja.srt")])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"[Grp] Show - 01.ja.srt" in line
    assert u"→" in line and u"Show S01E01.ja.srt" in line


def test_an_IN_PLACE_retime_does_not_print_an_arrow_pointing_at_itself():
    u"""⭐ Found by LOOKING at a real run. `--no-rename` writes back over the
    subtitle's own name, and `x → x` is noise on the one line whose job is to
    say what changed."""
    same = u"/lib/[Grp] Show - 01.ja.srt"
    report = a_report([a_result(subtitle=same, output_path=same)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"→" not in line, line
    assert u"retimed in place" in line, line


def test_a_DRY_RUN_shows_no_arrow_because_nothing_moved():
    u"""⚠ `output_path` is set ONLY when a file actually moved, so a dry run
    correctly has no arrow — and `summary()` says *would sync* rather than
    *synced*, which is the other half of the same honesty.

    ⛔ AND IT MAY NOT CLAIM TO HAVE RETIMED IN PLACE EITHER. A mutant that
    substituted the SOURCE path for the missing output printed no arrow — and
    passed — while telling the user the file had been rewritten where it sat.
    Found by `probe_adj30`.
    """
    lines = render(a_report([a_result(output_path=None)]))
    block = u"\n".join(lines)
    assert u"→" not in block, block
    assert u"retimed in place" not in block, block


def test_a_CUT_file_shows_both_offsets_the_boundary_and_the_gap():
    u"""`05-interface.md`'s ruled line: `-33.07 / -42.96 @3:18   CUT 9.9s`."""
    report = a_report([a_result(segments=[(None, -33.07), (198.0, -42.96)],
                                verdict_word=u"strong", match_rate=0.91)])
    block = u"\n".join(render(report))
    assert u"-33.07 / -42.96" in block, block
    assert u"@3:18" in block, block
    assert u"CUT 9.9s" in block, block
    assert u"2 segments" in block, block
    assert u"⚑" in block, u"a cut file is not marked as one"


def test_a_D9_DROP_is_counted_on_the_result_line():
    u"""`05-interface.md`, `D9`: cues removed are *dropped, counted, and
    reported on the result line*."""
    report = a_report([a_result(dropped_in_gap=3)])
    assert u"3 cues dropped" in u"\n".join(render(report))


def test_the_drop_count_is_not_said_TWICE():
    u"""⚠ `apply` already puts a full sentence in `Result.notes` explaining what
    a dropped cue WAS, and the first version printed a count line as well — so
    the report said *"1 cue dropped"* twice in a row, once ungrammatically
    (*"1 cue ... were dropped"*). Found by looking at a real run."""
    note = u"1 cue dropped: it is timed inside a stretch this video does not have"
    report = a_report([a_result(dropped_in_gap=1, notes=[note])])
    block = u"\n".join(render(report))
    assert block.count(u"1 cue dropped") == 2, block   # the count, and the note
    assert u"were dropped" not in block, block


def test_an_offset_that_rounds_to_zero_is_never_NEGATIVE_zero():
    u"""⚠ A second run over its own output aligns at about `-1e-9`, and
    `%+.2f` renders that as `-0.00` — a small negative shift, on the line that
    means NOTHING MOVED. ⛔ `x + 0.0 or 0.0` does not fix it: that catches an
    exact `-0.0` and `-1e-9` is truthy."""
    for tiny in (-1e-9, -0.0, -0.004):
        report = a_report([a_result(segments=[(None, tiny)])])
        block = u"\n".join(render(report))
        assert u"-0.00" not in block, (tiny, block)
        assert u"+0.00s" in block, (tiny, block)


def test_SETTLED_videos_are_said_out_loud(tmp_path):
    u"""⭐ RUNBOOK 3a-bis. A run that printed nothing over a folder of finished
    episodes is indistinguishable from one that broke."""
    report = a_report([], settled=[(u"/lib/Show S01E01.mkv",
                                    u"already in sync — nothing changed")])
    lines = render(report)
    # ⛔ NOT `in the whole block`. `SyncReport.summary()` says *1 already in
    # sync* too, so a renderer that dropped the dedicated line entirely was
    # green against the summary alone. Found by `probe_adj30`.
    assert lines[-1].strip() == report.summary()
    body = [l for l in lines[:-1] if l.strip()]
    assert any(u"already in sync" in l and u"nothing to do" in l
               for l in body), u"\n".join(lines)


# ---------------------------------------------------------------------------
# ⚠ display width — every layout claim has a Japanese twin
# ---------------------------------------------------------------------------

def test_width_counts_CELLS_not_characters():
    u"""⚠ THE THREE CLASSES ARE SEPARATE, and a fixture missing one cannot see
    a rule that drops it. `LEDGER-HOT.md` records the same shape for encoding:
    *an ASCII fixture cannot test an encoding rule.*

      * `W`  — Wide: ordinary CJK, 片田舎
      * `F`  — Fullwidth: the ASCII range's double-width twins, ＳＯ２. ⛔ The
                first version had none, and a mutant that counted only `W`
                survived a check named for counting cells.
      * combining — no cell of its own
    """
    assert CLI._width(u"abc") == 3
    assert CLI._width(u"片田舎") == 6, u"Wide"
    # ⛔ FULLWIDTH LITERALS, never a format string. `u"%d" % 2` emits an ASCII
    # digit and the fixture would be half-real (`LEDGER-HOT.md`).
    assert CLI._width(u"ＳＯ２") == 6, u"Fullwidth"
    assert CLI._width(u"Ａ") == 2 and CLI._width(u"A") == 1
    assert CLI._width(u"片田舎のおっさん S02E01.ass") == 27
    # ⚠ A combining mark occupies no cell of its own.
    assert CLI._width(u"て\u3099") == 2


def _cells(text):
    u"""An INDEPENDENT width, written here on purpose.

    🚨 `LEDGER.md` trap 10: *a check whose expectation is computed by the code
    under test cannot fail.* The first version of the check below measured both
    lines with `CLI._width`, so replacing `_width` with `len` kept the two
    sides agreeing and the mutant survived — against the single most important
    layout property in this file. Found by `probe_adj30`.
    """
    wide = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        wide += 2 if unicodedata.east_asian_width(ch) in (u"W", u"F") else 1
    return wide


def test_a_CJK_name_pads_to_the_same_column_as_an_ASCII_one():
    u"""🚨 THE DEFECT A `%-30s` FORMAT PRODUCES, and it is invisible to `len()`.
    This tool's files are mostly Japanese; a report that lines up under ASCII
    fixtures and is ragged on real data is the whole point of this check.

    ⛔ MEASURED WITH `_cells`, NOT WITH `CLI._width` — see above.
    """
    ascii_line = next(l for l in render(a_report(
        [a_result(subtitle=u"/lib/Show - 01.ja.srt",
                  output_path=u"/lib/out.ja.srt")])) if u"✓" in l)
    cjk_line = next(l for l in render(a_report(
        [a_result(subtitle=u"/lib/片田舎のおっさん S02E01.ass",
                  output_path=u"/lib/out.ja.srt")])) if u"✓" in l)
    assert _cells(ascii_line.split(u"→")[0]) == _cells(cjk_line.split(u"→")[0]), \
        u"the arrow does not land in the same column:\n%s\n%s" \
        % (ascii_line, cjk_line)


def test_a_long_name_is_clipped_from_the_MIDDLE():
    u"""⚠ A release name's distinguishing parts are its group and its episode,
    at opposite ends. Cutting the tail leaves twenty files all reading
    `[SubsPlease] Some Very Long Show Ti…`."""
    name = u"[SubsPlease] A Very Long Show Title Indeed - 07 (1080p).ja.srt"
    got = CLI._clip(name, 34)
    assert CLI._width(got) <= 34
    assert got.startswith(u"[SubsPlease]")
    assert got.endswith(u".ja.srt")


def test_clipping_a_CJK_name_never_OVERSHOOTS_the_column():
    u"""⚠ A wide character cannot be half-included. A clipper that counted
    characters would land one cell over on every odd boundary."""
    name = u"黄泉のツガイ.S01E18.風神と雷神.WEBRip.Netflix.ja[cc].srt"
    for cells in range(2, 40):
        assert CLI._width(CLI._clip(name, cells)) <= cells, cells


def test_the_header_FITS_and_keeps_the_end_of_a_long_path():
    u"""⭐ Found by looking: a real temp path pushed the counts to column 100.
    ⚠ Clipped from the LEFT here, the opposite of a filename — a path's tail is
    the part that identifies it."""
    scan = API.Scan([], [], _Candidates(), _Films(), {}, {})
    long_path = u"C:\\Users\\Someone\\AppData\\Local\\Temp\\x\\library\\Katainaka S2"
    line = CLI._header(long_path, scan)
    assert CLI._width(line) <= CLI.LINE, (CLI._width(line), line)
    assert line.rstrip().endswith(scan.summary())
    assert u"Katainaka S2" in line


class _Candidates(object):
    def for_video(self, video):
        return []


class _Films(object):
    pairs = ()
    refusals = ()


# ---------------------------------------------------------------------------
# arguments — ⛔ every refusal is a sentence, never a traceback
# ---------------------------------------------------------------------------

def test_the_flags_map_to_the_library_s_own_arguments():
    opts = CLI.parse([u"/lib", u"--subs", u"/subs", u"--out", u"/out",
                      u"--no-recurse", u"--keep-all", u"--verbose",
                      u"--dry-run", u"--json", u"--no-results"])
    assert opts[u"roots"] == [u"/lib"]
    assert opts[u"subs"] == u"/subs" and opts[u"out"] == u"/out"
    assert opts[u"recurse"] is False and opts[u"keep_all"] is True
    assert opts[u"dry_run"] and opts[u"json"] and opts[u"verbose"]
    assert opts[u"results"] is False


def test_pair_is_repeatable_and_takes_TWO_paths():
    opts = CLI.parse([u"--pair", u"a.mkv", u"a.srt",
                      u"--pair", u"b.mkv", u"b.srt"])
    assert opts[u"pairs"] == [(u"a.mkv", u"a.srt"), (u"b.mkv", u"b.srt")]


@pytest.mark.parametrize("argv,expect", [
    ([u"--pair", u"only.mkv"], u"TWO paths"),
    ([u"--subs"], u"needs a value"),
    ([u"--nonsense"], u"not an option"),
])
def test_a_command_that_cannot_be_run_is_REFUSED_in_a_sentence(argv, expect):
    u"""⛔ `03-permissions.md` §hand-back: state what was measured, why it fell
    short, and what would change it. ⚠ Never a traceback: a stack trace tells
    the user about our call stack, not about their command."""
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse(argv)
    assert expect in u"%s" % caught.value


def test_a_manifest_names_the_ENTRY_that_is_wrong(tmp_path):
    u"""⛔ A manifest is typed by hand or generated by somebody else's script,
    and *"list index out of range"* three frames down says nothing about which
    line to fix."""
    bad = tmp_path / "pairs.json"
    _write(bad, u'[["a.mkv", "a.srt"], ["b.mkv"]]')
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"entry 2" in u"%s" % caught.value


def test_a_manifest_that_is_not_JSON_says_so(tmp_path):
    bad = tmp_path / "pairs.json"
    _write(bad, u"not json at all")
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"not valid JSON" in u"%s" % caught.value


def test_a_manifest_that_is_a_JSON_OBJECT_says_so(tmp_path):
    bad = tmp_path / "pairs.json"
    _write(bad, u'{"a.mkv": "a.srt"}')
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"list of [video, subtitle]" in u"%s" % caught.value


def test_a_manifest_round_trips(tmp_path):
    good = tmp_path / "pairs.json"
    _write(good, json.dumps([["a.mkv", "a.srt"], ["b.mkv", "b.srt"]]))
    assert CLI.parse([u"--pairs", str(good)])[u"pairs"] == \
        [(u"a.mkv", u"a.srt"), (u"b.mkv", u"b.srt")]


# ---------------------------------------------------------------------------
# end to end — ⚠ over a real Matroska, because the ruled output is a claim
# about what a person sees after a real run
# ---------------------------------------------------------------------------

def test_a_real_run_writes_and_reports_it(tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)

    code = CLI.main([str(folder)], out=out, err=err)
    assert code == 0, out.text + err.text
    assert os.path.isfile(str(folder / "Show S01E01.ja.srt"))
    assert u"1 synced" in out.text, out.text
    assert u"→" in out.text


def test_a_DRY_RUN_moves_NOT_ONE_BYTE(tmp_path, out, err, monkeypatch):
    u"""⛔ HASHED, NOT LISTED. `05-interface.md`: *every intended action
    printed, nothing written, nothing trashed.* ⚠ `LEDGER-HOT.md` trap 0d — a
    retime is length-preserving, so a name-and-size snapshot is blind to it."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    before = _tree(str(tmp_path))

    code = CLI.main([str(folder), u"--dry-run"], out=out, err=err)
    assert code == 0, out.text + err.text
    assert _tree(str(tmp_path)) == before
    assert u"would sync" in out.text, out.text


def test_a_REFUSAL_exits_NON_ZERO(tmp_path, out, err, monkeypatch):
    u"""🚨 The whole point of the tool is that it declines to produce a
    confidently wrong file. A script piping this into something else has to be
    able to tell."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    video, _sub = one_episode(folder)
    wrong = _write(folder / "wrong.srt",
                   _srt([3.3 + 7.8 * i for i in range(180)]))

    code = CLI.main([u"--pair", video, wrong], out=out, err=err)
    assert code == 1, out.text
    assert u"✗" in out.text and u"REFUSED" in out.text


def test_a_CONTRADICTORY_pair_of_flags_exits_2_with_the_librarys_sentence(
        tmp_path, out, err, monkeypatch):
    u"""⭐ `sync()` refuses `--out` with `--no-rename` by raising, in a sentence
    written for a person. Printing that is better than re-deriving the rule
    here and letting the two drift."""
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    code = CLI.main([str(folder), u"--out", str(tmp_path / "o"),
                     u"--no-rename"], out=out, err=err)
    assert code == 2
    assert u"contradict" in err.text, err.text
    assert u"Traceback" not in err.text


def test_suffix_writes_a_retimed_copy_beside_the_original_from_the_CLI(
        tmp_path, out, err, monkeypatch):
    u"""⭐ 0.1.2: `--suffix _rt`, end to end through the command a person types.
    The original stays byte-identical and the copy keeps its language tag."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    _video, sub = one_episode(folder)
    original = open(sub, "rb").read()

    code = CLI.main([str(folder), u"--suffix", u"_rt"], out=out, err=err)

    assert code == 0, (out.text, err.text)
    copy = os.path.join(str(folder), u"[Grp] Show S01E01_rt.ja.srt")
    assert os.path.isfile(copy), os.listdir(str(folder))
    assert open(sub, "rb").read() == original


def test_suffix_with_no_rename_exits_2_and_says_why(tmp_path, out, err,
                                                     monkeypatch):
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    code = CLI.main([str(folder), u"--suffix", u"_rt", u"--no-rename"],
                    out=out, err=err)
    assert code == 2
    assert u"suffix" in err.text and u"Traceback" not in err.text, err.text


def test_force_on_a_SCAN_exits_2_rather_than_silently_ignoring_it(
        tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    code = CLI.main([str(folder), u"--force"], out=out, err=err)
    assert code == 2
    assert u"explicit pairs only" in err.text, err.text


def test_a_folder_AND_explicit_pairs_together_is_refused(tmp_path, out, err):
    code = CLI.main([u"/lib", u"--pair", u"a.mkv", u"a.srt"], out=out, err=err)
    assert code == 2
    assert u"not both" in err.text, err.text


def test_no_arguments_prints_the_usage_and_exits_2(out, err):
    assert CLI.main([], out=out, err=err) == 2
    assert u"tsubasa <folder>" in err.text


def test_help_prints_the_usage_and_exits_0(out, err):
    assert CLI.main([u"--help"], out=out, err=err) == 0
    assert u"tsubasa <folder>" in out.text
    # ⚠ Every flag the parser accepts is in the help. A flag nobody can find is
    # a flag that does not exist.
    # ⭐ READ FROM THE PARSER'S SOURCE, not listed here. The list this replaced
    # was typed by hand, so the claim above held only until someone added a
    # flag and not the list — which is exactly what `--suffix` would have done.
    import inspect
    import re
    accepted = set(re.findall(r'arg == u"(--[a-z-]+)"',
                              inspect.getsource(CLI.parse)))
    assert len(accepted) >= 12, sorted(accepted)
    for flag in sorted(accepted):
        assert flag in out.text, flag


# ---------------------------------------------------------------------------
# --json
# ---------------------------------------------------------------------------

def test_json_is_one_valid_object_per_result(tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)

    code = CLI.main([str(folder), u"--json"], out=out, err=err)
    assert code == 0, err.text
    rows = [json.loads(line) for line in out.lines if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row[u"outcome"] == CONFIDENT
    assert row[u"verdict_word"] == u"locked"
    # ⚠ The raw multiple belongs HERE and never in the default output.
    assert u"raw_excess" in row and u"excess_over_chance" in row
    assert row[u"output_path"].endswith(u"Show S01E01.ja.srt")


def test_json_carries_EVERY_field_Result_carries():
    u"""🚨 `05-interface.md`: *the same structure the library returns.* ⭐ Read
    off `Result.__slots__`, so a field added there and forgotten here fails —
    which is the whole risk, since `Result`'s shape is a compatibility promise
    to hato and fields are *added, never renamed*."""
    row = CLI.as_json(a_result())
    for field in API.Result.__slots__:
        assert field in row, u"--json drops Result.%s" % field


def test_json_is_NEVER_SILENT_over_a_settled_library(tmp_path, out, err,
                                                     monkeypatch):
    u"""⛔ Found by looking. A settled library produces no `Result` at all, so
    `--json` printed nothing and exited 0 — exactly what a broken run looks
    like. The summary goes to STDERR so a pipe stays pure NDJSON."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    for _ in range(3):
        CLI.main([str(folder)], out=Stream(), err=Stream())

    code = CLI.main([str(folder), u"--json"], out=out, err=err)
    assert code == 0
    assert out.text.strip() == u"", u"stdout should be pure NDJSON: %r" % out.text
    assert u"already in sync" in err.text, err.text


def test_verbose_puts_the_raw_multiple_on_its_OWN_line():
    u"""⚠ Appended to the evidence line first, and measured at over 150 cells on
    a real run — past the edge of every terminal, so the part a bug report needs
    was the part that scrolled off."""
    report = a_report([a_result(raw_excess=4.33, cluster_coherence=1.0,
                                reference=u"track 0 (S_TEXT/ASS, jpn)")])
    plain = u"\n".join(render(report))
    loud = u"\n".join(render(report, verbose=True))
    assert u"4.33× chance" not in plain
    assert u"4.33× chance" in loud
    for line in loud.splitlines():
        assert CLI._width(line) <= 100, (CLI._width(line), line)


# ---------------------------------------------------------------------------
# 🚨 `--version` — RUNBOOK 4c trap 12. The one command a standalone user runs
# ---------------------------------------------------------------------------
#
# `STANDALONE-BUILD-SCOPE.md` trap 12: *the user cannot ask what version they
# have, so the first bug report is unanswerable.* And trap 8, which is why it
# prints more than a number: **a frozen build that lost its alias table still
# runs, still exits 0, and is quietly far worse** — settled by name 80.0% →
# 51.4%, with nothing raising anywhere. A person holding a zip has no pip to
# reinstall and no traceback to read.
#
# ⛔ These drive `main()`, not `version_lines()` alone, because the ORDERING
# inside `main` is half the feature: `--version` names no folder, so a branch
# placed after the *"you gave me nothing to do"* refusal prints USAGE to
# stderr and exits 2.

def _truncate_the_alias_table(monkeypatch):
    u"""Make `self_check()` see 10 of the entries the header declares.

    ⚠ THE REAL `Table` TYPE, not a stand-in. `LEDGER-HOT.md`: *a fake that
    disagrees with the real thing about a type measures the fake* — and
    `self_check()` reads `len()`, `.meta` and the private key map.
    """
    from tsubasa.naming import alias as ALIAS
    real = ALIAS.load()
    monkeypatch.setattr(ALIAS, "_CACHED",
                        ALIAS.Table(dict(list(real._keys.items())[:10]),
                                    real._names, dict(real.meta)))


def _truncate_the_vocabulary(monkeypatch):
    u"""The same, for the decoration vocabulary. ⚠ It needed its own: the
    alias pair was guarded and its twin was not, and four mutants printing the
    wrong vocabulary numbers survived every check."""
    from tsubasa.naming import decoration as DECO
    real = DECO.load()
    monkeypatch.setattr(DECO, "_CACHED",
                        DECO.Vocabulary(set(sorted(real.tokens)[:3]),
                                        dict(real.meta)))


def test_version_first_line_is_the_contract_and_carries_nothing_else(out, err):
    u"""⭐ `tsubasa <version>`, two tokens, nothing else on the line. The
    release job reads it to prove the frozen app was built from the same tag
    as the wheel (`STANDALONE-BUILD-SCOPE.md` §7), and it is the line a person
    quotes into an issue."""
    import tsubasa

    assert CLI.main([u"--version"], out=out, err=err) == 0
    first = out.text.splitlines()[0]
    # 🚨 AN EXACT COMPARE, NOT `.split()`. `str.split()` collapses runs and
    # strips the ends, so two spaces, a TAB between the tokens and a trailing
    # space all survived it — and a release job doing `line.split(" ")[1]` or
    # an equality compare breaks on every one of the three.
    assert first == u"tsubasa %s" % tsubasa.__version__, repr(first)


def test_version_needs_no_folder_and_never_prints_USAGE(out, err):
    u"""🚨 THE ORDERING IS THE FEATURE. Placed below the no-roots branch,
    `tsubasa --version` answers with the whole help text on stderr and exit 2
    — a correct-looking implementation that is useless for its one job."""
    code = CLI.main([u"--version"], out=out, err=err)
    assert code == 0, u"stderr was: %r" % err.text
    assert u"pair subtitles to videos" not in out.text + err.text, out.text
    assert err.text == u"", err.text


def test_version_is_offered_in_the_help_text():
    u"""⚠ A flag nobody is told about is a flag nobody runs, and `--help` is
    where a person holding a zip looks."""
    assert u"--version" in CLI.USAGE


def test_version_REPORTS_A_BUILD_THAT_LOST_ITS_DATA_and_exits_nonzero(
        out, err, monkeypatch):
    u"""🚨 TRAP 8, AND IT IS WHY THIS COMMAND EXISTS AT ALL.

    A truncated alias table costs 28.6 points of pairing quality and raises
    nothing — `selfcheck.py`'s whole note. ⭐ Both defences are asserted,
    because `doctrine/release` §3 wants both: the OUTPUT names the problem,
    **and** the exit code is non-zero, so a release gate that forgets to read
    the output still fails.
    """
    _truncate_the_alias_table(monkeypatch)
    code = CLI.main([u"--version"], out=out, err=err)
    lines = out.text.splitlines()
    assert code == 1, out.text
    assert lines[-1] == u"NOT ok", lines
    assert any(line.startswith(u"PROBLEM:") for line in lines), lines
    assert any(u"truncated" in line for line in lines), lines


def test_version_says_FROZEN_only_when_it_is(out, err, monkeypatch):
    u"""⭐ The standalone's own line, and the branch `STANDALONE-BUILD-SCOPE.md`
    trap 1 says has never run. A bug report from a zip and one from a `pip
    install` are different bugs, and nothing else on screen tells them apart."""
    assert CLI.main([u"--version"], out=out, err=err) == 0
    # ⚠ ON THE HOST LINE, not the whole output. A substring search over
    # everything reads `_FROZEN_HINT` — *"If this application is frozen…"* —
    # and any note a raising `find_spec` produces, so a genuinely unfrozen
    # broken build would have failed it.
    assert not out.text.splitlines()[1].endswith(u", frozen"), out.text

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    loud = Stream()
    assert CLI.main([u"--version"], out=loud, err=err) == 0
    host = loud.text.splitlines()[1]
    assert host.endswith(u", frozen"), host


def test_every_word_version_prints_is_ASCII_even_when_the_build_is_BROKEN(
        monkeypatch):
    u"""🚨 MEASURED, NOT TIDY — and it is this project's worst bug class.

    `selfcheck.py`: a frozen Windows app's stdout is cp1252 as a pipe and
    **cp437 as a console**, and the PyInstaller bootloader runs Python
    isolated so `PYTHONIOENCODING` is ignored. An em dash in a diagnostic
    killed a frozen app on the line reporting the very fault it existed to
    report. ⚠ cp1252 is NOT the bar — it carries an em dash and a `·`; ASCII
    is.

    ⭐ The one thing that may be non-ASCII is a PATH, evidence and reported
    verbatim, so every path is removed and every other literal must be ASCII.

    🚨 AND *EVERY* PATH IS THREE PATHS, NOT ONE. The first version of this
    check removed `check.data_dir` alone — but `_compare`'s sentences embed
    the DATA FILE's path (`alias._GZIP`, `decoration._DATA`), and both are
    derived from `__file__`. ⛔ Measured by an adversarial pass: copied to
    a folder named `さとし`, a CORRECT build failed this check with
    `'ascii' codec can't encode characters in position 184-186` — a position
    inside `_GZIP`. **The check written to protect Japanese users failed for
    Japanese users**, and only because the fixture happened to overwrite the
    one path it knew how to remove.

    ⚠ AND ALL THREE OF `_compare`'S BRANCHES ARE DRIVEN, not just the
    truncated one. The other two — *did not load* and *no header* — are the
    ones that carry `_FROZEN_HINT`, and they print **only** on a frozen build
    that collected no data files, which is the one environment where a cp437
    stdout exists. An em dash there was measured to lose the entire
    diagnostic, not one line of it.
    """
    from tsubasa import selfcheck as SC
    from tsubasa.naming import alias as ALIAS
    from tsubasa.naming import decoration as DECO

    real = ALIAS.load()
    states = {
        u"truncated": (ALIAS.Table(dict(list(real._keys.items())[:10]),
                                   real._names, dict(real.meta)),
                       DECO.load()),
        u"absent": (ALIAS.Table(), DECO.Vocabulary()),
        u"no header": (ALIAS.Table(real._keys, real._names,
                                   dict((k, v) for k, v in real.meta.items()
                                        if k != u"keys")),
                       DECO.load()),
    }
    # ⭐ Every path the output can carry, from the modules that own them —
    # never a hand-written list, which is what drifts.
    paths = [ALIAS._GZIP, ALIAS._DATA_DIR, DECO._DATA,
             u"C:\\Users\\さとし\\Desktop\\つばさ\\data"]

    for name, (table, vocab) in states.items():
        monkeypatch.setattr(ALIAS, "_CACHED", table)
        monkeypatch.setattr(DECO, "_CACHED", vocab)
        check = SC.self_check()
        check.data_dir = paths[-1]
        lines = CLI.version_lines(check=check)
        assert any(line.startswith(u"PROBLEM:") for line in lines), \
            u"%s did not produce a PROBLEM: %r" % (name, lines)
        for line in lines:
            rest = line
            for path in paths:
                rest = rest.replace(path, u"")
            try:
                rest.encode("ascii")
            except UnicodeEncodeError as exc:
                raise AssertionError(
                    u"the %s state printed a non-ASCII literal, which a "
                    u"frozen Windows console (cp437) cannot render: %r "
                    u"(%s)" % (name, line, exc))


def test_version_reads_ffmpeg_and_the_table_off_the_real_SelfCheck(monkeypatch):
    u"""⚠ Read off `SelfCheck`, never recomputed — `05-interface.md`'s rule one
    process boundary out. ⭐ And ffmpeg is asserted in BOTH directions: a
    standalone user's machine routinely has none, and *"ffmpeg found"* on a
    machine without it sends a bug report the wrong way."""
    from tsubasa import selfcheck as SC
    from tsubasa.container import ffmpeg as FF

    # 🚨 THE FAKE HONOURS `tool`, AND THE FIRST VERSION DID NOT. Ignoring it
    # made `check.ffmpeg` and `check.ffprobe` indistinguishable, so a mutant
    # reading the WRONG one survived all seven checks — and on a machine with
    # ffmpeg but no ffprobe (exactly what `set_ffmpeg()` and `$TSUBASA_FFMPEG`
    # exist for) it prints *"ffmpeg not found"* with ffmpeg sitting right
    # there. `LEDGER-HOT.md`: a fake that disagrees with the real thing about
    # anything measures the fake.
    def only(*present):
        return lambda tool=u"ffprobe", cache_dir=None: (
            u"/opt/%s" % tool if tool in present else None)

    monkeypatch.setattr(FF, "find", only(u"ffmpeg", u"ffprobe"))
    found = CLI.version_lines(check=SC.self_check())
    monkeypatch.setattr(FF, "find", only())
    absent = CLI.version_lines(check=SC.self_check())
    monkeypatch.setattr(FF, "find", only(u"ffmpeg"))
    half = CLI.version_lines(check=SC.self_check())

    assert u"ffmpeg found" in found[2], found
    assert u"ffmpeg not found" in absent[2], absent
    assert u"ffmpeg found" in half[2], (
        u"ffmpeg is here and ffprobe is not; this line is about FFMPEG: %r"
        % half[2])

    real = SC.self_check()
    assert u"aliases %s/%s" % (real.alias_entries,
                               real.alias_declared) in found[2], found
    assert u"vocabulary %s/%s" % (real.vocabulary_tokens,
                                  real.vocabulary_declared) in found[2], found
    assert found[-1] == u"ok" and absent[-1] == u"ok", (found, absent)

    # ⭐ A NOTE REACHES THE SCREEN, and nothing asserted that: deleting the
    # notes line outright survived every check. ⚠ The state is FORCED rather
    # than relied on — on a machine with ffprobe and every optional import,
    # `notes` is empty, so the old coverage was an accident of this box.
    assert any(l.startswith(u"note: ") and u"ffprobe" in l for l in absent), \
        u"the ffprobe note never reached the screen: %r" % absent

    # 🚨 A WHOLE BUILD HOLDS `loaded` AND `declared` EQUAL, so everything above
    # is blind to a line that prints one of them twice — `LEDGER-HOT.md`'s
    # *list what your fixtures hold constant; that list is the defect
    # surface*. ⚠ BOTH tables, because for a while only the alias pair was
    # guarded and four mutants on the vocabulary pair survived.
    # ⚠ The declared counts are DERIVED, never pinned: both tables are
    # regenerated and grow, and a literal fails on every refresh.
    monkeypatch.setattr(FF, "find", only(u"ffmpeg", u"ffprobe"))
    _truncate_the_alias_table(monkeypatch)
    _truncate_the_vocabulary(monkeypatch)
    broken = CLI.version_lines(check=SC.self_check())
    assert u"aliases 10/%s" % real.alias_declared in broken[2], broken
    assert u"vocabulary 3/%s" % real.vocabulary_declared in broken[2], broken


def test_version_never_prints_the_word_None_at_a_user(monkeypatch):
    u"""⚠ A table whose header does not declare a size gives `declared is
    None`, and `%s` renders that as the literal `None` — *"aliases 0/None"* —
    on the one command a stuck user is told to run, in the one state trap 8
    exists to detect. It reads like a crash and it is not one."""
    from tsubasa import selfcheck as SC
    from tsubasa.naming import alias as ALIAS

    real = ALIAS.load()
    monkeypatch.setattr(ALIAS, "_CACHED", ALIAS.Table(
        real._keys, real._names,
        dict((k, v) for k, v in real.meta.items() if k != u"keys")))
    lines = CLI.version_lines(check=SC.self_check())
    assert u"None" not in u"\n".join(lines), lines
    assert u"/?" in lines[2], lines[2]


def test_version_reports_the_build_it_was_HANDED_not_the_one_it_imports():
    u"""⚠ `version_lines(check=X)` could ignore `X.version` and read the module
    global instead — and nothing would notice, because on any real run the two
    agree. Two mutants survived on exactly that.

    ⭐ It matters the moment a caller inspects another installation's
    `SelfCheck`, which is what the parameter is for.
    """
    from tsubasa import selfcheck as SC

    check = SC.self_check()
    check.version = u"9.9.9-elsewhere"
    assert CLI.version_lines(check=check)[0] == u"tsubasa 9.9.9-elsewhere"


def test_a_DRY_RUN_NAMES_THE_FILE_IT_WOULD_TRASH():
    u"""🚨 `--dry-run` is *"print every intended action"*, and the one
    intended action that cannot be undone was the only one it left out.

    The summary counted `Result.superseded`, which is *paths actually moved*
    and is therefore always empty on a dry run -- so the whole section was
    skipped. Measured: *"7 would sync"* against a real run's *"1 subtitle
    superseded → trash"* over the same folder.

    ⭐ NAMED, NOT COUNTED. Reading a dry run is how you decide whether you
    agree with it, and *"1 subtitle"* is not something anyone can agree with.
    """
    # 🚨 THE LOSER MUST NOT APPEAR AS A RESULT ROW, and that is the
    # whole fixture. On the scan path a candidate that loses its slot is
    # `superseded`, NOT a line -- so the only place its name can legitimately
    # appear is the section under test. The first version of this check used
    # the same filename for the loser and for a rendered row, and **a mutant
    # that deleted the naming loop survived**: the assertion was reading the
    # row above it. The name below is deliberately unlike every other name in
    # the report.
    lines = render(a_report([
        a_result(subtitle=u"/lib/[Erai-raws] Show - 01.ja.srt",
                 would_supersede=[u"/lib/OnlyInTheTrashLine.ja.srt"]),
    ]))
    text = u"\n".join(lines)
    assert u"would be superseded" in text, text
    assert u"OnlyInTheTrashLine.ja.srt" in text, text
    # ⚠ AND IT DOES NOT CLAIM THE PAST TENSE. A dry run saying *"superseded
    # → trash"* reads as a file that has already moved.
    assert u"1 subtitle superseded" not in text, text


def test_a_run_that_WROTE_reports_the_trash_in_the_PAST_tense():
    u"""⚠ The other side of the check above: the live wording must survive
    the dry-run wording being added beside it."""
    text = u"\n".join(render(a_report([
        a_result(subtitle=u"/lib/[Erai-raws] Show - 01.ja.srt",
                 output_path=u"/lib/Show S01E01.ja.srt",
                 superseded=[u"/lib/[shincaps] Show - 01.ja.srt"]),
    ])))
    assert u"1 subtitle superseded → trash" in text, text
    assert u"would be superseded" not in text, text
