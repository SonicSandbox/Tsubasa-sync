# -*- coding: utf-8 -*-
u"""
One subtitle per (video x language), and where the losers go. RUNBOOK 3a.
Authority: `05-interface.md` §Naming and dedupe, `LEDGER-HOT.md`,
`doctrine/robustness` §destructive.

⭐ THE TWO CLAIMS THIS SUITE EXISTS FOR, and neither is about ranking:

    1. NOTHING IS EVER DELETED. `LEDGER-HOT.md`: *never delete a user's file
       -- trash only.* Checked structurally, by reading the module's own
       source, because a prose rule about deletion is the exact shape
       `doctrine/robustness` says will be forgotten.

    2. A REFUSED CANDIDATE NEVER WINS, and that is a GATE rather than a sort
       key. Sorting by it makes the least-bad refusal win whenever every
       candidate was refused -- writing the best of several rejected files,
       which is the confidently wrong answer Rule 2 forbids.

⚠ The ranking itself is *"a robustness backstop, not a core feature"* in
Sonic's own words, so it is checked once per rule and not elaborated.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tsubasa import dedupe as D                              # noqa: E402
from tsubasa import sidecar as S                             # noqa: E402
from tsubasa import verdict as V                             # noqa: E402
from tsubasa.align import Fit                                # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def a_fit(segments=((None, 0.0),)):
    u"""A `Fit` that yields a CONFIDENT verdict. ⚠ It asserts its own outcome,
    because a fixture that quietly stopped being confident would send every
    check below down the no-winner branch, where they would still pass."""
    fit = Fit(list(segments), 0.80, 0.20, (0.0, 0.80),
              [(t * 120.0, 40, 0.80, None, None) for t in range(6)],
              [], [0.0], 300, 300, [])
    return fit


def confident(segments=((None, 0.0),)):
    v = V.verdict(a_fit(segments))
    assert v.outcome == V.CONFIDENT, "the fixture is not the state under test"
    return v


def refused():
    return V.Verdict(V.REFUSED, u"measured, and not a match")


def cand(name, verdict=None, cues=300, content_end=1400.0, folder=u"lib"):
    if verdict is None:
        verdict = confident()
    return D.Candidate(os.path.join(folder, name), S.parse(name), verdict,
                       cues, content_end)


# ---------------------------------------------------------------------------
# ⛔ CLAIM 1 -- nothing is ever deleted
# ---------------------------------------------------------------------------

def test_the_module_contains_NO_DELETION_PRIMITIVE_at_all():
    u"""🚨 THE STRUCTURAL VERSION OF *never delete a user's file*.

    `doctrine/robustness`: *can this be a script, a gate, a schema constraint
    or a type? If yes, that is the version that ships.* Prose about deletion is
    what a future edit walks straight past; this check reads the file.
    """
    called = _called_names(os.path.join(ROOT, "tsubasa", "dedupe.py"))
    assert called, "the AST walk found no calls at all -- it is not looking"
    for primitive in D.DELETION_PRIMITIVES:
        assert primitive not in called, (
            "dedupe.py calls %r. Nothing this tool does may be unrecoverable "
            "(05-interface.md); the losers go to TRASH." % primitive)


def _called_names(path):
    u"""Every name this module CALLS, from its syntax tree. -> set

    ⚠ The AST rather than the text, and that is the whole point. A text scan
    fails on the module's own documentation -- the first version of this check
    did -- and it can be silenced by rewording a docstring instead of by
    fixing the code. A syntax tree has no comments in it.
    """
    import ast
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Attribute):
                names.add(target.attr)             # os.remove(...) -> remove
            elif isinstance(target, ast.Name):
                names.add(target.id)               # remove(...)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:               # from os import remove
                names.add(alias.asname or alias.name)
    return names


def test_the_guard_above_would_actually_fire(tmp_path):
    u"""⛔ A check that scans for strings is worthless if its needle list is
    empty or its exclusion swallows everything. This proves the mechanism."""
    assert len(D.DELETION_PRIMITIVES) >= 5
    assert "remove" in D.DELETION_PRIMITIVES
    called = _called_names(os.path.join(ROOT, "tsubasa", "dedupe.py"))
    assert "move" in called, (
        "the fallback is a MOVE; if `shutil.move` is gone the check above is "
        "measuring a module that no longer does the job")
    # ⭐ The scanner run against a file that DOES delete, so the check is
    # proved able to fire rather than merely observed passing.
    # ⚠ In `tmp_path`, never beside the suite: a scratch file inside `tests/`
    # is litter the moment a run is interrupted.
    scratch = tmp_path / "scan_probe.py"
    scratch.write_text(u"import os\ndef go(p):\n    os.remove(p)\n",
                       encoding="utf-8")
    assert "remove" in _called_names(str(scratch)), (
        "the scanner did not see an outright `os.remove` -- it cannot have "
        "been protecting anything")


def test_trash_is_DRY_RUN_by_default(tmp_path):
    u"""⭐ `doctrine/robustness`: *a destructive tool is dry-run by default,
    and its first dry run is a design review.*"""
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"1\n", encoding="utf-8")
    result = D.trash(str(victim), str(tmp_path / D.TRASH_DIR))
    assert result.performed is False
    assert victim.exists(), "a default call moved the file"
    assert result.reason, "a dry run said nothing about what it would do"


def test_the_local_fallback_MOVES_and_keeps_the_original_name(tmp_path, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"payload", encoding="utf-8")
    root = tmp_path / D.TRASH_DIR

    result = D.trash(str(victim), str(root), dry_run=False)
    assert result.performed and result.method == u"local"
    assert not victim.exists()
    landed = root / "Show.ja.srt"
    assert landed.exists(), "the file did not arrive in the trash"
    assert landed.read_text(encoding="utf-8") == u"payload", (
        "the bytes changed on the way to the trash")


def test_a_second_file_of_the_same_name_does_not_overwrite_the_first(tmp_path, monkeypatch):
    u"""🚨 A trash that overwrites is a delete with extra steps."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    root = tmp_path / D.TRASH_DIR
    for i, text in enumerate((u"first", u"second")):
        folder = tmp_path / ("f%d" % i)
        folder.mkdir()
        victim = folder / "Show.ja.srt"
        victim.write_text(text, encoding="utf-8")
        D.trash(str(victim), str(root), dry_run=False)
    landed = sorted(p.name for p in root.iterdir())
    # ⚠ `Show.ja (2).srt`, not `Show (2).ja.srt`: the counter goes before the
    # EXTENSION, so the whole original name -- language tag included -- stays
    # intact and recognisable. That is what *recoverable in the way the user
    # already knows* means.
    assert landed == ["Show.ja (2).srt", "Show.ja.srt"], landed
    assert (root / "Show.ja.srt").read_text(encoding="utf-8") == u"first"


def test_the_OS_trash_is_used_when_the_machine_has_one(tmp_path):
    u"""⚠ THE SEAM EXISTS SO THIS PATH IS NOT *code that never runs in the
    local configuration* -- `07-test-plan.md` forbids that by name, and
    `send2trash` is NOT installed on the build machine."""
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"1", encoding="utf-8")
    seen = []
    result = D.trash(str(victim), str(tmp_path / D.TRASH_DIR), dry_run=False,
                     sender=seen.append)
    assert seen == [str(victim)], "the OS sender was not called"
    assert result.method == u"os" and result.performed


def test_a_REFUSING_system_trash_falls_back_to_the_local_one(tmp_path):
    u"""⭐ 0.1.2. A locked file, a network share, a drive with no recycle bin:
    the system trash refuses real files. It used to let the exception out, and
    the run stopped half-done — nothing lost, but a superseded subtitle left
    beside its replacement. The local trash is exactly as recoverable, and it
    exists for when the system trash is not there."""
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"payload", encoding="utf-8")
    root = tmp_path / D.TRASH_DIR

    def refuse(path):
        raise OSError(5, "Access is denied")

    result = D.trash(str(victim), str(root), dry_run=False, sender=refuse)

    assert (result.method, result.performed) == (u"local", True), result
    assert not victim.exists()
    landed = root / "Show.ja.srt"
    assert landed.read_text(encoding="utf-8") == u"payload", \
        u"the bytes must survive the fallback unchanged"
    assert u"refused" in result.reason and str(root) in result.reason, \
        u"the fallback must say where the file went: %r" % result.reason


def test_a_refusal_after_the_file_LEFT_its_path_claims_nothing(tmp_path):
    u"""⚠ The system trash raised AND the file is gone from its path. Where it
    went is not ours to know, so nothing more is moved and nothing is claimed:
    performed=False, with the reason in words."""
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"payload", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere.srt"
    root = tmp_path / D.TRASH_DIR

    def move_then_raise(path):
        os.rename(path, str(elsewhere))
        raise OSError(5, "Access is denied")

    result = D.trash(str(victim), str(root), dry_run=False,
                     sender=move_then_raise)

    assert (result.method, result.performed) == (u"os", False), result
    assert u"no longer at its path" in result.reason
    assert not root.exists(), u"a file that is not there was 'moved' anyway"


def test_the_environment_switch_forces_the_local_path(tmp_path, monkeypatch):
    u"""The same shape as `TSUBASA_NO_NATIVE_DEMUX=1` for the container
    reader: a way to reach the fallback on a machine that has the fast path."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    victim = tmp_path / "Show.ja.srt"
    victim.write_text(u"1", encoding="utf-8")
    seen = []
    result = D.trash(str(victim), str(tmp_path / D.TRASH_DIR), dry_run=False,
                     sender=seen.append)
    assert seen == [], "the OS sender ran with the switch set"
    assert result.method == u"local"


def test_trashing_something_already_gone_is_not_an_error(tmp_path):
    result = D.trash(str(tmp_path / "nope.srt"), str(tmp_path / D.TRASH_DIR))
    assert result.performed is False and "already gone" in result.reason


# ---------------------------------------------------------------------------
# ⛔ CLAIM 2 -- rule 1 is a GATE
# ---------------------------------------------------------------------------

def test_when_NOTHING_is_confident_there_is_no_winner():
    u"""🚨 The whole reason rule 1 is not a sort key. The best of several
    refused files is still a refused file."""
    plan = D.plan(u"Show - 01", [cand(u"a.ja.srt", refused(), cues=900),
                                 cand(u"b.ja.srt", refused(), cues=100)])
    assert plan.winner is None
    assert plan.writes == []
    assert plan.superseded == [], "a refused candidate was sent to the trash"
    assert plan.reason, "nothing was written and nothing said why"


def test_a_confident_candidate_beats_a_refused_one_with_far_more_cues():
    u"""Rule 3 must not be able to overturn rule 1."""
    win = cand(u"small.ja.srt", confident(), cues=100)
    plan = D.plan(u"Show - 01", [cand(u"huge.ja.srt", refused(), cues=9000), win])
    assert plan.winner is win, plan.winner


def test_an_UNALIGNED_candidate_cannot_win_either():
    u"""⚠ `None` is not confident. An unmeasured file has the same standing as
    a refused one -- there is no verdict behind it."""
    plan = D.plan(u"Show - 01", [D.Candidate(u"lib/x.ja.srt",
                                             S.parse(u"x.ja.srt"), None, 5000)])
    assert plan.winner is None and plan.reason


def test_an_unaligned_candidate_does_not_win_the_SEGMENT_tiebreak():
    u"""🚨 Rule 4 prefers FEWER segments, so a missing segment list read as
    zero would sort an unmeasured file first. A missing value is not a good
    value."""
    unaligned = D.Candidate(u"lib/x.ja.srt", S.parse(u"x.ja.srt"), None, 300)
    assert unaligned.segments > 1
    good = cand(u"y.ja.srt", confident(((300.0, 0.0), (None, -9.8))))
    assert D.rank([unaligned, good], u"Show")[0] is good


# ---------------------------------------------------------------------------
# the ranking -- one check per rule, and no more
# ---------------------------------------------------------------------------

def test_rule_2_prefers_a_non_SDH_candidate():
    plain = cand(u"a.ja.srt", cues=300)
    sdh = cand(u"b.ja.sdh.srt", cues=300)
    assert D.plan(u"Show", [sdh, plain]).winner is plain


def test_rule_2_takes_SDH_when_it_is_the_ONLY_one():
    u"""*Not SDH, UNLESS SDH is the only one* -- the second half, which a
    preference-only check would never exercise."""
    sdh = cand(u"b.ja.sdh.srt")
    plan = D.plan(u"Show", [sdh])
    assert plan.winner is sdh and plan.writes


def test_rule_3_prefers_more_cues():
    more = cand(u"a.ja.srt", cues=500)
    assert D.plan(u"Show", [cand(u"b.ja.srt", cues=200), more]).winner is more


def test_rule_3_prefers_wider_runtime_coverage_when_cues_tie():
    u"""⚠ THE WIDER ONE IS NAMED SO IT SORTS LAST BY PATH, deliberately.

    🚨 The first version used `a` (wide) and `b` (narrow), and a mutation
    removing coverage from the sort key SURVIVED -- the path tiebreak at the
    bottom put `a` first anyway, so the check passed for a reason that had
    nothing to do with the rule it names. **A tiebreak check has to make the
    rule under test the only thing that can decide.**
    """
    wider = cand(u"z.ja.srt", cues=300, content_end=1400.0)
    narrow = cand(u"a.ja.srt", cues=300, content_end=600.0)
    assert D.plan(u"Show", [narrow, wider]).winner is wider


def test_rule_4_prefers_fewer_segments():
    u"""*An uncut source is cleaner than a repaired broadcast.*"""
    uncut = cand(u"a.ja.srt", confident())
    repaired = cand(u"b.ja.srt", confident(((300.0, 0.0), (None, -9.8))))
    assert D.plan(u"Show", [repaired, uncut]).winner is uncut


def test_rule_5_breaks_a_tie_toward_the_name_the_video_already_has():
    u"""⚠ The matching candidate is named so it sorts LAST by path -- same
    trap as the coverage check above. With `Show - 01` against `[Erai-raws]…`
    the path order already favoured the right answer, so a mutation deleting
    rule 5 entirely survived."""
    named = cand(u"Zebra - 01.ja.srt")
    other = cand(u"Alpha - 01.ja.srt")
    assert D.plan(u"Zebra - 01", [other, named]).winner is named


def test_the_order_is_DETERMINISTIC_when_everything_ties():
    u"""⚠ Without a total order the winner depends on what the filesystem
    listed first, so two machines disagree and the results DB disagrees with
    itself. `LEDGER.md` §Harness: an instrument that is not deterministic reads
    as a defect somewhere else entirely."""
    a, b = cand(u"a.ja.srt"), cand(u"b.ja.srt")
    assert D.rank([a, b], u"Show")[0] is D.rank([b, a], u"Show")[0]


def test_every_loser_is_superseded_and_none_is_lost():
    cands = [cand(u"a.ja.srt", cues=500), cand(u"b.ja.srt", cues=400),
             cand(u"c.ja.srt", refused(), cues=900)]
    plan = D.plan(u"Show", cands)
    assert plan.winner is cands[0]
    assert set(id(c) for c in plan.superseded) == {id(cands[1]), id(cands[2])}
    assert len(plan.superseded) + len(plan.writes) == len(cands), (
        "a candidate was neither written nor superseded -- it vanished")


# ---------------------------------------------------------------------------
# 🚨 WHAT AN ADVERSARIAL PASS FOUND, 2026-09-09 — all of it green beforehand
# ---------------------------------------------------------------------------

def test_the_LANGUAGE_comes_from_the_winner_not_from_the_input_order():
    u"""🚨 Taking it from `candidates[0]` made the output name depend on
    ARGUMENT ORDER: a Japanese winner beside an untagged 10-cue file was
    written as `Show - 01.ass` — **no language tag at all** — and reversing the
    list gave `Show - 01.ja.srt`. Both trashed the loser.

    ⛔ The untagged form is precisely the subliminal defect `sidecar.py` exists
    to fix, produced by this module: a correctly-aligned Japanese subtitle
    reads back as *"no subtitle present"* and is re-fetched forever."""
    untagged = cand(u"Show - 01.srt", cues=10)
    japanese = cand(u"[Erai] Show - 01.ja.ass", cues=900)
    for order in ([untagged, japanese], [japanese, untagged]):
        plan = D.plan(u"Show - 01", order)
        assert plan.winner is japanese, plan.winner
        assert plan.writes[0][1] == u"Show - 01.ja.ass", plan.writes


def test_a_NON_FINITE_measurement_cannot_destroy_the_total_order():
    u"""🚨 Every comparison with NaN is False, so `sorted()` degraded to input
    order and the `c.path` tiebreak never ran: the same three candidates
    returned three different winners depending on how they were passed, and
    `plan()` trashed whichever lost. The docstring under the tiebreak promised
    exactly the guarantee NaN was breaking."""
    import itertools
    broken = cand(u"a.ja.srt", cues=float("nan"))
    middle = cand(u"b.ja.srt", cues=300)
    best = cand(u"c.ja.srt", cues=500)
    winners = {D.plan(u"Show", list(order)).winner.path
               for order in itertools.permutations([broken, middle, best])}
    assert winners == {best.path}, winners


def test_a_non_finite_value_never_WINS_a_tiebreak_it_did_not_earn():
    u"""⭐ Not merely made deterministic. A missing measurement is not a good
    one — the same argument `Candidate.segments` already makes."""
    broken = cand(u"a.ja.srt", cues=float("inf"))
    real = cand(u"z.ja.srt", cues=10)
    assert D.plan(u"Show", [broken, real]).winner is real


def test_trash_REFUSES_a_directory(tmp_path):
    u"""🚨 `shutil.move` falls back to copytree + **`shutil.rmtree`** when the
    destination is on another volume — the ordinary case here, media on a NAS
    and the trash on the system drive. An adversarial pass forced `EXDEV` and
    recorded `rmtree` on a season folder. This module's docstring claims
    `rmtree` *"is not imported and must never be"*; it was reachable one call
    deeper, and the AST check cannot see that because it scans this file only.

    ⭐ Restricting the input to a FILE is what makes the claim true rather than
    nearly true — for a plain file the cross-device path is copy2 + unlink,
    which IS a move."""
    folder = tmp_path / "Season 1"
    folder.mkdir()
    (folder / "ep01.ja.srt").write_text(u"x", encoding="utf-8")

    result = D.trash(str(folder), str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert result.performed is False
    assert "not a file" in result.reason
    assert folder.exists() and (folder / "ep01.ja.srt").exists()


def test_keep_all_SAYS_what_it_did_not_write():
    u"""⚠ It relaxes the dedupe, never the verdict — so silence about the
    candidates it skipped reads as *"everything was kept"*, which is the one
    thing the flag's name promises. `DedupePlan.reason`'s own contract: a
    silent nothing reads as success."""
    plan = D.plan(u"Show", [cand(u"a.ja.srt"),
                            cand(u"b.ja.srt", refused()),
                            D.Candidate(u"lib/c.ja.srt",
                                        S.parse(u"c.ja.srt"), None, 300)],
                  keep_all=True)
    assert len(plan.writes) == 1
    assert any("not written" in n for n in plan.notes), plan.notes
    assert any("does not relax the verdict" in n for n in plan.notes)


def test_an_empty_slot_is_not_an_error():
    plan = D.plan(u"Show", [])
    assert plan.winner is None and plan.reason


# ---------------------------------------------------------------------------
# --keep-all
# ---------------------------------------------------------------------------

def test_keep_all_writes_every_candidate_and_trashes_NOTHING():
    cands = [cand(u"[Erai-raws] Show - 01.ja.ass"),
             cand(u"[SubsPlease] Show - 01.ja.ass"),
             cand(u"Show - 01.ja.ass")]
    plan = D.plan(u"Show - 01", cands, keep_all=True)
    assert len(plan.writes) == 3
    assert plan.superseded == [], "--keep-all trashed something"


def test_keep_all_names_are_DISTINCT():
    u"""🚨 A collision here is data loss: the second write overwrites the first
    and `--keep-all` has kept one."""
    cands = [cand(u"[Erai-raws] Show - 01.ja.ass"),
             cand(u"[SubsPlease] Show - 01.ja.ass"),
             cand(u"Show - 01.ja.ass")]
    names = [n for _c, n in D.plan(u"Show - 01", cands, keep_all=True).writes]
    assert len(set(names)) == len(names), names


def test_keep_all_names_round_trip_to_the_same_language():
    u"""🚨 SPEC AMENDED HERE. `05-interface.md` says `<video>.<lang>.<tag>`,
    with the tag AFTER the language -- and our own reader then returns `und`
    for every file we just wrote, because a tag is not a flag and it violates
    the right-hand constraint. A second run would see a folder of untagged
    files and redo all of it. The tag goes BEFORE the language."""
    cands = [cand(u"[Erai-raws] Show - 01.ja.ass"),
             cand(u"[SubsPlease] Show - 01.ja.ass")]
    for _c, name in D.plan(u"Show - 01", cands, keep_all=True).writes:
        assert S.parse(name).lang == u"ja", "%r read back as %r" % (
            name, S.parse(name).lang)


def test_the_keep_all_tag_names_the_SOURCE_not_the_language():
    u"""⚠ The first version took everything after the video stem in the
    FILENAME, which is `.ja` -- so both candidates were tagged with the
    language they already share."""
    cands = [cand(u"[Erai-raws] Show - 01.ja.ass"),
             cand(u"[SubsPlease] Show - 01.ja.ass")]
    names = [n.lower() for _c, n in
             D.plan(u"Show - 01", cands, keep_all=True).writes]
    # ⚠ Compared case-insensitively: the tag is cut from NFKC-FOLDED text, and
    # that is deliberate. Locating the video name in the folded string and
    # slicing the ORIGINAL by that index cut in the wrong place — NFKC changes
    # length (`Ⅷ` → `VIII`), and `[Ⅷ]Show - 01` produced the tag `ⅧSho01`,
    # containing a fragment of the video's own name. Losing the user's casing
    # in a disambiguating tag is the far smaller cost.
    assert any(u"erai-raws" in n for n in names), names
    assert any(u"subsplease" in n for n in names), names


def test_the_keep_all_tag_survives_a_LENGTH_CHANGING_fold():
    u"""🚨 The specific input that exposed the index drift."""
    cands = [cand(u"[Ⅷ]Show - 01.ja.ass"), cand(u"Show - 01.ja.ass")]
    names = [n for _c, n in D.plan(u"Show - 01", cands, keep_all=True).writes]
    assert any(u"viii" in n.lower() for n in names), names
    assert not any(u"sho" in n.lower().replace(u"show - 01", u"")
                   for n in names), (
        "the tag contains a fragment of the video's own name: %s" % names)


def test_the_candidate_already_named_after_the_video_keeps_the_plain_name():
    u"""⭐ It is the one rule 5 prefers; handing IT the digest puts the ugliest
    name on the most likely file."""
    cands = [cand(u"Show - 01.ja.ass"), cand(u"[Erai-raws] Show - 01.ja.ass")]
    by_path = {os.path.basename(c.path): n
               for c, n in D.plan(u"Show - 01", cands, keep_all=True).writes}
    assert by_path[u"Show - 01.ja.ass"] == u"Show - 01.ja.ass", by_path


def test_a_keep_all_tag_is_STABLE_across_processes():
    u"""⚠ `hash(str)` is randomised per process, so a digest built on it gives
    the same folder different filenames on a second run."""
    import hashlib
    # ⚠ TWO CANDIDATES WITH THE SAME STEM, so the second one's tag collides
    # and falls through to the digest. Without that the digest branch is never
    # reached and this check is a vacuous pass -- which is what the first
    # version of it was, and the denominator assertion below caught.
    cands = [D.Candidate(u"lib/x/Show.extra.ja.srt",
                         S.parse(u"Show.extra.ja.srt"), confident()),
             D.Candidate(u"lib/y/Show.extra.ja.srt",
                         S.parse(u"Show.extra.ja.srt"), confident())]
    once = [n for _c, n in D.plan(u"Show", cands, keep_all=True).writes]
    again = [n for _c, n in D.plan(u"Show", cands, keep_all=True).writes]
    assert once == again
    assert any(hashlib.sha1(c.path.encode("utf-8")).hexdigest()[:8] in n
               for c in cands for n in once), (
        "no digest appeared, so this check is not looking at the digest path")


def test_two_candidates_with_the_SAME_BASENAME_still_get_distinct_names():
    u"""🚨 Both took the *"already named after the video, keep the plain name"*
    branch, which returned early **without registering anything** — so the
    collision-avoidance mechanism was bypassed for exactly the branch that
    needs it most, and `plan()` raised on two ordinary files in two folders."""
    same = [D.Candidate(u"lib/A/Show.ja.srt", S.parse(u"Show.ja.srt"), confident()),
            D.Candidate(u"lib/B/Show.ja.srt", S.parse(u"Show.ja.srt"), confident())]
    names = [n for _c, n in D.plan(u"Show", same, keep_all=True).writes]
    assert len(set(names)) == 2, names
    assert u"Show.ja.srt" in names, "the first one lost its natural name"


def test_the_collision_guard_still_fires_if_the_derivation_ever_fails(monkeypatch):
    u"""⚠ The tag derivation now makes a collision unreachable, so the guard is
    a last resort — and a last resort nothing can trigger is a guard nobody
    knows is broken. Defeat the derivation and prove the guard still catches
    it, because a collision here is data loss."""
    monkeypatch.setattr(D, "_distinguishing_tag",
                        lambda c, used, video_stem=u"": u"same")
    same = [D.Candidate(u"lib/A/Show.ja.srt", S.parse(u"Show.ja.srt"), confident()),
            D.Candidate(u"lib/B/Show.ja.srt", S.parse(u"Show.ja.srt"), confident())]
    with pytest.raises(ValueError) as e:
        D.plan(u"Show", same, keep_all=True)
    assert "destroy" in str(e.value)


def test_keep_all_still_refuses_a_candidate_that_was_not_confident():
    u"""⛔ `--keep-all` relaxes the DEDUPE, never the verdict."""
    plan = D.plan(u"Show", [cand(u"a.ja.srt"), cand(u"b.ja.srt", refused())],
                  keep_all=True)
    assert len(plan.writes) == 1


# ---------------------------------------------------------------------------
# the plan performs nothing
# ---------------------------------------------------------------------------

def test_a_plan_touches_no_filesystem(tmp_path):
    u"""⭐ `plan()` is a decision; `trash()` is the only thing that moves a
    byte, and it is dry-run by default. Nothing between them can act."""
    victim = tmp_path / "Show - 01.ja.srt"
    victim.write_text(u"payload", encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    D.plan(u"Show - 01", [cand(u"Show - 01.ja.srt", folder=str(tmp_path)),
                          cand(u"other.ja.srt", folder=str(tmp_path))])
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert victim.read_text(encoding="utf-8") == u"payload"


# ---------------------------------------------------------------------------
# 🚨 A SPECULATIVE LOSER IS NEVER TRASHED
#
# `discover.Candidates._absolute_fallback` offers a whole season to a video
# that was offered nothing, on the chance that one of the two filenames counts
# episodes from the start of the SERIES rather than the SEASON. The losers of
# that guess are, in the case that prompted it, subtitles for episodes the
# user has no video for yet.
# ---------------------------------------------------------------------------

def test_a_speculative_loser_is_LEFT_ALONE_and_never_superseded():
    u"""🚨 THE GUARD THE WHOLE FALLBACK RESTS ON.

    `plan` supersedes every non-winner, and that is right for a candidate that
    claimed the slot BY NAME. A speculative candidate claimed nothing. Without
    this, offering E17/E18/E22 to a video that is season-2 episode 10 and
    letting E22 win sends the other two to the trash — `LEDGER-HOT.md`'s
    *A SLOT CANNOT DECIDE WHAT TO THROW AWAY* through a door the cross-slot
    rules do not cover, because no slot WRITES those files.
    """
    winner = cand(u"Show S02E22.ja.srt")
    winner.speculative = True
    losers = [cand(u"Show S02E17.ja.srt", verdict=refused()),
              cand(u"Show S02E18.ja.srt", verdict=refused())]
    for c in losers:
        c.speculative = True

    plan = D.plan(u"Show - 10", [winner] + losers)

    assert plan.winner is winner
    assert plan.superseded == [], (
        "a speculative loser was sent to the trash: %s"
        % [os.path.basename(c.path) for c in plan.superseded])
    assert any(u"episode numbers might be counted differently" in n
               for n in plan.notes), plan.notes


def test_a_NON_speculative_loser_is_still_superseded():
    u"""⛔ THE CONTROL. The exemption is for guesses only — a candidate that
    claimed the slot by name and lost is still superseded, or the fix has
    quietly turned dedupe off."""
    winner = cand(u"Show - 10.ja.srt")
    loser = cand(u"other/Show - 10.ja.srt", verdict=refused())
    plan = D.plan(u"Show - 10", [winner, loser])
    assert plan.winner is winner
    assert [c.path for c in plan.superseded] == [loser.path]


def test_a_MIXED_slot_supersedes_only_the_one_that_claimed_it():
    u"""⭐ Both kinds in one slot, which is the state a real run reaches when
    a by-name candidate and a guess compete."""
    winner = cand(u"Show - 10.ja.srt")
    by_name = cand(u"other/Show - 10.ja.srt", verdict=refused())
    guess = cand(u"Show S02E17.ja.srt", verdict=refused())
    guess.speculative = True

    plan = D.plan(u"Show - 10", [winner, by_name, guess])
    superseded = [os.path.basename(c.path) for c in plan.superseded]
    assert superseded == [u"Show - 10.ja.srt"], superseded
    assert all(u"S02E17" not in s for s in superseded)


def test_a_speculative_candidate_defaults_to_FALSE():
    u"""⚠ Every existing caller keeps the old behaviour exactly. A default of
    True would trash nothing, anywhere, and read as this feature working."""
    assert D.Candidate(u"lib/x.ja.srt", S.parse(u"x.ja.srt")).speculative \
        is False
