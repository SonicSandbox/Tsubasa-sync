# -*- coding: utf-8 -*-
u"""
RUNBOOK step 3c-0 — ⭐ THE END-TO-END BENCHMARK, ON REAL MEDIA.

===========================================================================
⭐ WHAT THIS SUITE SEES THAT NO OTHER SUITE CAN
===========================================================================

Every other suite drives a stage, or drives `sync()` over a **synthetic**
Matroska with **generated** subtitles whose timing is exact. `vnbench` — the
release number — scores **names** through `same_series` and never calls `sync()`
at all; it sat at 80.0% through the whole of 3a and 3b and would have done so if
every one of them were broken.

This one assembles a real library in a temp directory from the staged media and
runs the whole product over it. ⭐ **The defect class it reaches is the one units
structurally cannot**: cross-slot state, a report composed from the plan rather
than from what happened, and a write landing in the wrong folder.

===========================================================================
🚨 EVERY CHECK HERE WAS REBUILT AFTER AN ADVERSARIAL PASS DEFEATED IT
===========================================================================

Three agents returned about **fifty** findings against the first version, and
one aimed fifteen mutations at the precise thing each check is named after —
**all fifteen survived.** The corrections worth carrying:

  ⭐ **`tree()` compared names and sizes, and a retime is length-preserving.**
     A dry run that rewrote every candidate in place, a REFUSED file mangled,
     and a library modified under `--out` were all invisible. It carries a
     CONTENT HASH now, and these checks compare `after == before` on it.
  ⭐ **The Sintel fixture's source and output were the same path**, so several
     checks compared a file with itself; a mutant writing one byte passed.
  ⭐ **One check asserted a RULING as though it were a defect.** `xfail` #1 said
     a second run must take nothing, while `test_pipeline.py::
     test_ONE_FOLDER_mode_converges_and_never_trashes_its_own_output` is green
     asserting the opposite — Sonic ruled dedupe rule 5 promoted, and the file
     goes to the trash, *recoverable, never deleted*. Two suites contradicting
     each other. The claim here is now the ruling's own.
  ⭐ **`assert X or True`** — vacuously true, and only a mutation run found it.

⛔ **WHAT THIS STRUCTURALLY CANNOT COVER**, because a tick gets read as the
whole claim:

  * **one episode of one show, plus Sintel.** A SHAPE benchmark, not a coverage
    one — `vnbench`'s 350 pairs are the population number
  * **the runtime gate's real work.** `track_2.mkv` is a subtitle-only Matroska,
    so its duration is the muxer's echo of the same track and every yomi pair
    sits at ratio 0.93–1.00. `LONG_RATIO` and the `IMPOSSIBLE` branch are
    `test_duration.py`'s
  * **the mask path** (B6), and **whether a player renders the result**
  * ⚠ **two independent witnesses to the broadcast cut.** `shincaps` is
    `nanakoraws` shifted by a constant 33.233 s — 300 of 303 cue starts — so
    the pair tests offset-INVARIANCE, not agreement between two recordings
"""
import io
import json
import numbers
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.dev import e2ebench as E                            # noqa: E402

BASELINE = ROOT / E.BASELINE


@pytest.fixture(scope="module")
def measured():
    u"""Every scenario, run ONCE. ⚠ Read-only observed data, not a live tree —
    each scenario got its own temp directory and destroyed it."""
    try:
        mat = E.material()
        return E.measure(mat=mat)
    except E.Missing as exc:
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)


@pytest.fixture(scope="module")
def facts(measured):
    return E.facts(measured)


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no %s. Record it with "
                    "`python -m tsubasa.dev e2e --baseline`." % E.BASELINE)
    with io.open(str(BASELINE), encoding="utf-8") as fh:
        return json.load(fh)


# ==========================================================================
# the material, before anything is claimed about what it produced
# ==========================================================================

def test_the_staged_container_still_AGREES_WITH_ITS_OWN_SOURCE(measured):
    u"""⭐ THE FIXTURE IS CHECKED, NOT TRUSTED.

    `track_2.mkv` was made by an ffmpeg line in a README. A stale, truncated or
    differently-remuxed copy would still exist and still parse, and every number
    below it would be measured against a floor recorded from a different file.
    `verify_material()` re-derives the one fact that matters on every run.
    """
    fx = measured["fixture"]
    assert fx["cues"] == 323, fx
    assert fx["worst_cue_disagreement"] <= 0.002, fx
    assert fx["codec"] == u"S_TEXT/ASS", fx


def test_the_reference_is_a_REAL_container_read_by_the_REAL_reader(measured):
    u"""🚨 THE SEAM THE `pipeline` SUITE HAS TO FAKE, AND WHERE IT ONCE LIED.

    `pipeline`'s fixtures inject a reader, and that double once returned bare
    floats for `Track.cues` where the real reader returns `Cue` objects — every
    seam check green, `sync()` raising on **every real container**. Nothing here
    injects anything.

    ⚠ IT ASSERTS THE TWO REFERENCES ARE PRESENT, NOT HOW MANY ROWS THERE ARE.
    It used to assert `len(references) == 2`, which is a production count
    (`07-test-plan.md` guard 3) — and worse, a count that only holds while both
    ABEMA and Netflix collapse into one `und` slot. An adversarial pass
    simulated the language fix and this check went red with a message about
    Matroska, which would have read as the reader breaking.
    """
    rows = measured["scenarios"]["one_folder"]["write"]["results"]
    references = sorted(row["reference"] for row in rows.values())
    assert references, "nothing was measured at all"
    assert any(u"S_TEXT/UTF8" in r and u"24 cues" in r for r in references), \
        references
    assert any(u"S_TEXT/ASS" in r and u"323 cues" in r for r in references), \
        references


def test_a_dry_run_changes_NOTHING_on_disk(measured):
    u"""⛔ `doctrine/robustness`: a destructive tool is dry-run by default.

    🚨 CHECKED BY CONTENT. `tree()` used to be `{name: size}` and a retime is
    length-preserving — `00:00:01,918` and `00:00:00,888` are the same byte
    count — so an adversary rewrote every candidate in place during a dry run
    and this check stayed green. `LEDGER-HOT.md` already records a third-party
    binary that wrote a file with a destroyed cue while its own `--dry-run` was
    set; that is exactly the shape.
    """
    one = measured["scenarios"]["one_folder"]
    assert one["dry_changed_the_tree"] is False, (
        "the dry run changed the tree: %s gone, %s overwritten in place"
        % (one["dry_survival"]["gone"],
           one["dry_survival"]["overwritten_in_place"]))
    assert one["dry_survival"]["untouched"] is True, one["dry_survival"]
    assert one["dry"]["counts"]["written"] == 0, one["dry"]["summary"]
    # ⭐ AND IT STILL MEASURED — otherwise the lines above are satisfied by a
    # run that did nothing at all, the vacuous pass `0 broken of 0` names.
    assert one["dry"]["counts"]["confident"] >= 2, one["dry"]["summary"]


# ==========================================================================
# ⭐ a correct pair lands BESIDE ITS VIDEO, with the measured offset
# ==========================================================================

def test_the_output_lands_BESIDE_ITS_VIDEO_and_not_where_the_subtitle_was(
        measured):
    u"""🚨 THE DEFECT THAT SURVIVED TO A DRY RUN.

    `apply_plan` defaults to *the source's own folder*, which is right for a
    function that knows nothing about videos — so a perfectly retimed subtitle
    was written into the **downloads** folder, where no player will ever look.
    ⛔ It survived a check that asserted the new files **by BASENAME**.

    ⚠ REBUILT TWICE. First against the one-folder scenario, where the two
    answers are the same directory and a mutant pointing every write at the
    subtitle's folder survived. Then again because the two-folder scenario
    produced a single output — `all()` over one element — until its subtitles
    were given tags that do not collapse into one slot.
    """
    cell = measured["scenarios"]["two_folders"]
    rows = [row for row in cell["run"]["results"].values() if row["output"]]
    assert cell["video_dir"] != cell["sub_dir"], cell
    # ⭐ MORE THAN ONE, so `all()` below is not a statement about one element.
    assert cell["written"] >= 2, (
        "only %d file(s) were written, so 'every output' is a claim about "
        "%d thing(s): %s" % (cell["written"], cell["written"],
                             cell["run"]["summary"]))
    assert len(rows) == cell["written"], (len(rows), cell["written"])
    assert cell["every_output_is_beside_its_video"] is True, cell["outputs"]
    assert set(cell["outputs"]) == {cell["video_dir"]}, cell["outputs"]
    for row in rows:
        video_stem = os.path.splitext(os.path.basename(row["video"]))[0]
        assert row["output"].startswith(video_stem), (row["output"],
                                                      video_stem)


def test_the_downloads_folder_is_not_written_to(measured):
    u"""⭐ The other half of the same promise, and it was never asserted.

    🚨 BY CONTENT — comparing names alone was green against a run that appended
    bytes to every source in the folder.
    """
    cell = measured["scenarios"]["two_folders"]
    assert cell["downloads_survival"]["overwritten_in_place"] == [], \
        cell["downloads_survival"]
    assert cell["recoverable"]["all_recoverable"] is True, (
        "these left the downloads folder and are not in the trash: %s"
        % cell["recoverable"]["unrecoverable"])


def test_junk_in_the_subtitle_folder_is_ignored_SILENTLY(measured):
    u"""⛔ `05-interface.md`: junk is expected input, not an error — surasura's
    real case is a subtitle folder full of `.txt`. A refusal per `.txt` is noise
    that a real refusal then hides in.

    ⚠ THE JUNK HAD TO CHANGE. The first version staged only `.txt`/`.jpg`/
    `.nfo`, and `discover.classify` returns `None` for those so they never
    become items at all — the *"silently"* half of the claim was a tautology it
    was impossible to break. A prose `.srt` and an empty `.srt` CAN reach a
    result, because the extension is what discovery classifies on.
    """
    cell = measured["scenarios"]["two_folders"]
    assert cell["run"]["counts"]["errored"] == 0, (
        "junk produced %d ERROR result(s): %s"
        % (cell["run"]["counts"]["errored"], cell["run"]["summary"]))
    # ⭐ THE DENOMINATOR, so a vacuous pass is visible — and ignoring a file
    # means LEAVING IT ALONE, not merely declining to report it.
    after = cell["downloads_after"]
    for junk in cell["junk_staged"]:
        assert junk in after, (junk, sorted(after))
    assert cell["downloads_survival"]["untouched"] is True, \
        cell["downloads_survival"]


def test_the_written_cues_MOVED_BY_THE_OFFSET_the_report_stated(measured):
    u"""⭐ THE SUBSTANCE. A file in the right place with the wrong timing is the
    failure this tool exists to prevent.

    🚨 THE SOURCE'S FIRST CUE IS READ **BEFORE** THE RUN. It used to be read
    afterwards, and wherever the output path equals the source path that
    compared the file with itself: `moved` was structurally 0.0 and the offset
    structurally ~0, so a mutant that shifted every Sintel timestamp by five
    seconds passed. `SINTEL_SUB` now differs from the output name as well.

    ⚠ DERIVED, NEVER PINNED — `written_first_cue − source_first_cue == offset`
    stays true when the corpus changes and when the aligner improves.
    """
    cues = measured["scenarios"]["one_folder"]["written_cues"]
    assert len(cues) >= 2, ("only %d file(s) written, so this check covers "
                            "%d of them" % (len(cues), len(cues)))
    for name, cell in sorted(cues.items()):
        assert cell["source_first_cue"] is not None, (name, cell)
        assert cell["first_cue"] is not None, (name, cell)
        assert cell["from"] != name, (
            "%s: the source and the output are the same file, so this check "
            "is comparing it with itself" % name)
        moved = cell["first_cue"] - cell["source_first_cue"]
        assert abs(moved - cell["offset"]) <= 0.002, (
            "%s: the report said %+.4f and the cues moved %+.4f"
            % (name, cell["offset"], moved))


def test_a_subtitle_that_is_its_own_tracks_extraction_aligns_at_EXACTLY_ZERO(
        measured):
    u"""⭐ THE ONE PAIR WHOSE ANSWER IS KNOWN WITHOUT MEASURING ANYTHING.

    `Sintel-60s.srt` is ffmpeg's own extraction of `Sintel-60s.mkv`'s track, so
    the honest end-to-end answer is zero. ⚠ `LEDGER-HOT.md`: identical-source
    pairs give a FLAT plateau, and taking its argmax put all five probe pairs
    0.30–0.33 s early.

    ⚠ It comes back `strong`, not `locked`, and the reason is the excess ladder
    — `verdict._WORDS` puts `locked` at 4.0× and this pair measures 3.57×.
    (An earlier docstring here claimed a runtime cap did it. There is no such
    cap: the only one fires on `runtime_check == "absent"` and this reads
    `weak`.)
    """
    rows = measured["scenarios"]["one_folder"]["write"]["results"]
    sintel = [row for row in rows.values() if u"Sintel" in row["video"]]
    assert len(sintel) == 1, sorted(rows)
    assert abs(sintel[0]["offset"]) < 1e-9, sintel[0]["offset"]
    assert sintel[0]["match"] == 100, sintel[0]["match"]


def test_the_measured_offset_AGREES_WITH_AN_INDEPENDENTLY_MEASURED_ONE(
        measured):
    u"""⭐ `doctrine/evidence`: make the instrument disagree with something you
    already know.

    `12-alignment.md` §5 measured every yomi18 subtitle against the episode's
    AUDIO. This aligns against the video's own TRACK, so
    `cue_vs_cue = mask[sub] − mask[track]`.

    ⚠ IT USED TO CHECK ONE NUMBER. `derived_check` read only the one-folder
    scenario, where dedupe supersedes ABEMA — so `MASK_OFFSETS["abema"]` was
    never reached, and its derivation (−0.22) is smaller than the tolerance
    (0.25), meaning that half could not have told the right answer from zero.
    Both subtitles are now aligned in their own runs.
    """
    rows = E.derived_check(measured)
    got = sorted(name for name, _m, _d, _a in rows)
    assert got == ["abema", "netflix"], (
        "the instrument check covered %s; MASK_OFFSETS names abema and netflix"
        % (got,))
    for which, measured_offset, derived, agrees in rows:
        assert agrees, (
            "%s: end to end %+.4f but §5's measurements derive %+.4f — a "
            "%.4f s disagreement" % (which, measured_offset, derived,
                                     abs(measured_offset - derived)))


# ==========================================================================
# ⭐ the broadcast cut
# ==========================================================================

def test_a_real_broadcast_cut_is_SOLVED_and_lands_on_the_MEASURED_offsets(
        measured):
    u"""🚨 AND THREE DOCUMENTS EXPECTED THIS FILE TO BE REFUSED.

    `RUNBOOK.md` 3c-0 asked for *"the four MUST_REFUSE pairs write nothing"* and
    `yomi18/README.md` marks both cut files MUST REFUSE. Both describe the
    **speech mask**, where §5 measured the break as invisible. This drives the
    **cue-vs-cue** path, where finding it is what B3's split search is for. ⛔ So
    asserting a refusal would have been a check asserting the defect.

    ⚠ **THE OFFSETS ARE THE CLAIM; THE BREAK'S POSITION IS NOT.** `Fit.gaps`
    comes back `[(222.4, 336.34)]` — the aligner itself calls the crossing
    undetermined across **113.9 s** — and `_boundary_time` returns a REFERENCE
    CUE START, so 222.4 is a grid position. The check below asserts the break
    is inside the span the tool claims, and pins the two OFFSETS, which are
    measurements.

    ⚠ And `CUT_TRUTH` is subsync's, measured cue-vs-cue against a file
    byte-identical to this reference. Real, reproduced through the whole
    product for the first time — not an independent modality.
    """
    cell = measured["scenarios"]["broadcast_cut"][u"nanakoraws.atx.cut.srt"]
    assert cell["outcome"] == u"CONFIDENT", (cell["outcome"], cell["run"])
    assert len(cell["segments"]) == 2, cell["segments"]

    at, first = cell["segments"][0]
    second = cell["segments"][1][1]
    assert at is not None, cell["segments"]
    assert abs(first - E.CUT_TRUTH["first"]) <= E.CUT_OFFSET_TOLERANCE, (
        "first segment %+.4f against a measured %+.3f"
        % (first, E.CUT_TRUTH["first"]))
    assert abs(second - E.CUT_TRUTH["second"]) <= E.CUT_OFFSET_TOLERANCE, (
        "second segment %+.4f against a measured %+.3f"
        % (second, E.CUT_TRUTH["second"]))
    assert abs(at - E.CUT_TRUTH["break"]) <= E.CUT_BREAK_TOLERANCE, (
        "the break landed at %.1f s; the truth puts it at %.0f s"
        % (at, E.CUT_TRUTH["break"]))
    # ⭐ AND THE TRUTH'S BREAK IS INSIDE THE SPAN THE TOOL DISCLAIMS, which is
    # the honest form of the claim and survives the aligner getting better at
    # narrowing it.
    spans = cell["undetermined_spans"]
    assert spans, "the tool reported no undetermined span at all"
    assert any(a - E.CUT_BREAK_TOLERANCE <= E.CUT_TRUTH["break"] <= b
               for a, b in spans), (E.CUT_TRUTH["break"], spans)


def test_the_split_search_finds_the_SAME_break_under_a_DIFFERENT_offset(
        measured):
    u"""⭐ OFFSET-INVARIANCE, and that is precisely what it is.

    ⚠ IT IS NOT TWO WITNESSES, and the first version of this file said it was.
    `shincaps` and `nanakoraws` differ by a single constant: **300 of 303 cue
    starts are exactly 33.233 s apart**, three distinct deltas in the whole
    file. It is one timing dataset presented twice.

    So what this tests is that shifting an entire subtitle does not move where
    the split search puts the break — which is real, and an adversarial pass
    showed it kills the reference-axis/subtitle-axis confusion `fit.py` warns
    about, a confusion the check above does not see. ⛔ It is NOT independent
    confirmation of the break's position, and it must not be described as such.
    """
    cuts = measured["scenarios"]["broadcast_cut"]
    a = cuts[u"nanakoraws.atx.cut.srt"]
    b = cuts[u"shincaps.atx.cut.srt"]
    assert len(a["segments"]) == 2, a["segments"]
    assert len(b["segments"]) == 2, b["segments"]
    assert a["segments"][0][0] is not None, a["segments"]
    assert b["segments"][0][0] is not None, b["segments"]
    assert abs(a["segments"][0][0] - b["segments"][0][0]) <= 1.0, (
        "the same broadcast, shifted, put the break %.1f s apart"
        % abs(a["segments"][0][0] - b["segments"][0][0]))
    # ⭐ ...while the offsets differ by the constant between the two files.
    assert abs(a["segments"][0][1] - b["segments"][0][1]) > 10.0, (
        a["segments"], b["segments"])


def test_D9_drops_the_stranded_cue_and_the_file_still_PARSES(measured):
    u"""⭐ `D9`: cues inside a removed stretch are dropped, counted, reported.

    ⚠ AND THE LOOP IS REQUIRED TO HAVE RUN. `LEDGER-HOT.md`: *loop over
    literals and assert the loop ran.* Without the length assertion an empty
    mapping passed this with zero assertions executed — demonstrated by an
    adversarial pass.
    """
    cuts = measured["scenarios"]["broadcast_cut"]
    assert sorted(cuts) == [u"nanakoraws.atx.cut.srt",
                            u"shincaps.atx.cut.srt"], sorted(cuts)
    for staged, cell in sorted(cuts.items()):
        assert cell["dropped_in_gap"] == 1, (staged, cell["dropped_in_gap"])
        assert cell["written_cues"] is not None, staged
        assert cell["written_cues"] == cell["source_cues"] - 1, (
            "%s: %d source cues, %d written, %d reported dropped"
            % (staged, cell["source_cues"], cell["written_cues"],
               cell["dropped_in_gap"]))
        assert cell["written_first_cue"] is not None, staged
        # ⭐ AND THE SOURCE IS UNTOUCHED, by content.
        assert cell["source_untouched"] is True, staged


# ==========================================================================
# ⭐ nothing is written for a pair that must not be made
# ==========================================================================

def test_the_wrong_episode_changes_NOTHING_on_the_discovery_path(measured):
    u"""The name filters it before a byte of either file is read.

    🚨 BY CONTENT. `set(after) == set(before)` was green against a run that
    appended bytes to the refused file — a REFUSED pair that mangled the user's
    subtitle reporting as having written nothing. `tree()` already had the
    information and `set()` threw it away.
    """
    d = measured["scenarios"]["wrong_episode"]["discovery"]
    assert d["nothing_changed_on_disk"] is True, (
        "new files %s; gone %s; overwritten in place %s"
        % (d["new_files"], d["survival"]["gone"],
           d["survival"]["overwritten_in_place"]))
    assert len(d["run"]["unpaired"]) == 1, d["run"]
    assert u"no subtitle" in d["run"]["summary"], d["run"]["summary"]


def test_the_wrong_episode_is_REFUSED_when_the_user_asserts_the_pair(measured):
    u"""⭐ The name cannot help — the user said these two go together — so the
    VERDICT is the only thing between them and a library timed to the wrong
    episode."""
    e = measured["scenarios"]["wrong_episode"]["explicit"]
    assert e["nothing_changed_on_disk"] is True, (
        "new files %s; overwritten in place %s"
        % (e["new_files"], e["survival"]["overwritten_in_place"]))
    rows = list(e["run"]["results"].values())
    assert len(rows) == 1, e["run"]
    assert rows[0]["outcome"] == u"REFUSED", rows[0]
    # ⛔ A refusal carries no confidence word. `LEDGER.md` §Interface: a GUI
    # painted a run green because "11 confident, 1 refused" contains the word.
    assert rows[0]["word"] is None, rows[0]["word"]
    assert rows[0]["reason"].strip(), rows[0]
    # ⭐ `03-permissions.md` §hand-back: what was measured, why it fell short.
    assert u"%" in rows[0]["reason"], rows[0]["reason"]


# ==========================================================================
# ⭐ cross-slot state — the class no unit check and no mutant could reach
# ==========================================================================

def test_a_two_show_library_with_bare_episode_numbers_KEEPS_EVERY_SOURCE(
        measured):
    u"""🚨 THE LIBRARY THAT LOST EVERYTHING, on real media this time.

    An ordinary library of two shows using bare episode numbers lost **every
    subtitle it had** and the report said `2 synced`. `dedupe.plan` supersedes
    the losers of its slot from the candidates it was given, and the file it
    supersedes is **another slot's winner**. ⛔ The defect lived in the gap, so
    no unit check and no mutant could reach it.

    ⚠ An in-place rewrite is expected here and is not a loss: both sources are
    already named `01.srt`, which is what the tool would write, so the retime
    lands on the source. What must never happen is a file GOING.
    """
    cell = measured["scenarios"]["two_shows_bare_episodes"]
    assert cell["survival"]["gone"] == [], cell["survival"]["gone"]
    assert cell["recoverable"]["all_recoverable"] is True, cell["recoverable"]
    # ⭐ AND IT DID THE WORK. Every source surviving is also what a tool that
    # did nothing at all would produce.
    assert cell["run"]["counts"]["written"] == 2, cell["run"]["summary"]


def test_a_second_run_CONVERGES_and_everything_it_moved_is_RECOVERABLE(
        measured):
    u"""⭐ THE RULING, ASSERTED AS THE RULING.

    `test_pipeline.py::test_ONE_FOLDER_mode_converges_and_never_trashes_its_own
    _output` rules this over a synthetic library and Sonic ruled dedupe rule 5
    promoted to make it so: run 1 writes the canonical name and leaves the
    source; run 2 recognises the canonical file as the winner and sends the
    stale original **to the trash — recoverable, never deleted**; run 3 changes
    nothing. This is that ruling on real files.

    🚨 AN EARLIER VERSION OF THIS CHECK ASSERTED THE OPPOSITE, as an `xfail`
    calling the behaviour a defect. It would have gone red the day 3a-bis
    "fixed" it and taken `test_pipeline.py` red with it. ⛔ Two suites
    contradicting each other about one run is worse than either being wrong.

    ⚠ AND THE OLD MEASURE WAS A DELTA — *present after run 1 and absent after
    run 2* — which filters out everything **run 1** took. Run 1 takes three of
    five sources here, so a regression that also took the fourth on the first
    run would have read as the defect being fixed. Both runs are watched.
    """
    cell = measured["scenarios"]["second_run"]
    assert cell["recoverable"]["all_recoverable"] is True, (
        "these left the library and are not in the trash: %s"
        % cell["recoverable"]["unrecoverable"])
    assert cell["third_run_changed_nothing"] is True, (
        "run 3 changed the tree, so the run does not converge")
    assert cell["overwritten_in_place"] == [], cell["overwritten_in_place"]
    # ⭐ The denominator, so this cannot pass on a run that moved nothing.
    assert cell["taken_by_the_first_run"], (
        "run 1 superseded nothing, so convergence is untested here")


def test_out_LEAVES_THE_LIBRARY_ALONE_and_mirrors_its_shape(measured):
    u"""⭐ `--out`'s promise is two halves and only one was ever checked here.

    ⚠ `test_pipeline.py::test_out_dir_MIRRORS_and_does_not_flatten` already
    asserts the mirroring over a two-show synthetic library with all four full
    relative paths — strictly stronger than anything this file can say about
    it. What this adds is the other half, on real files: **the library is not
    written to**, checked by CONTENT rather than by name.
    """
    cell = measured["scenarios"]["out_dir"]
    assert cell["library_untouched"] is True, cell["library_survival"]
    assert cell["mirrored"] is True, sorted(cell["out_tree"])
    folders = {rel.split(u"/")[0] for rel in cell["out_tree"]}
    assert len(folders) == 2, sorted(cell["out_tree"])


def test_keep_all_writes_EVERY_release_and_supersedes_NOTHING(measured):
    u"""⭐ `--keep-all` ON FILES SOMEBODY ELSE WROTE — owed to this step.

    `HANDOFF.md` carried it as open: *"it needs a library that actually has two
    releases of one episode. The synthetic fixtures cover the mechanics;
    nothing covers it on files somebody else wrote."* ABEMA and Netflix are two
    real releases of one episode.

    ⛔ `--keep-all` means there is no single winner, so nothing is superseded
    and the trash stays empty. ⚠ Two shows, because with one show every output
    lands in `out/` directly and that is what mirroring AND flattening both
    look like.
    """
    cell = measured["scenarios"]["keep_all"]
    assert cell["nothing_superseded"] is True, cell["run"]
    assert cell["trash_is_empty"] is True, cell["run"]
    assert cell["library_untouched"] is True, cell["run"]
    # ⭐ Three: both yomi releases kept, plus Sintel.
    assert cell["distinct_outputs"] == 3, sorted(cell["outputs"])
    assert cell["mirrored"] is True, sorted(cell["out_tree"])
    assert len(cell["out_folders"]) == 2, cell["out_folders"]


# ==========================================================================
# 🚨 THE DEFECT THIS BENCHMARK FOUND, and its control
# ==========================================================================

def test_two_LANGUAGES_beside_one_video_are_two_slots_and_both_survive(
        measured):
    u"""⭐ `05-interface.md`: a language IS the slot.

    🚨 THIS BENCHMARK FOUND THIS DEFECT AND IT IS NOW FIXED — the arc is worth
    keeping, because it is the whole argument for the step existing.
    `sidecar.parse_path` read only DOT-separated tokens, so `.ja[cc].srt` and
    `.en[cc].srt` — the form ABEMA, Netflix and Amazon all write — both
    resolved to `und`, **two different languages shared one slot, and dedupe
    trashed one of them.** `.ja-jp.srt` read `und` too, though
    `05-interface.md` §*Filename tags* lists both forms by name and rules that
    `ja-jp` and `.jpn.` must dedupe together.

    ⭐ Measured before the fix: **4,677 of 40,572** real corpus subtitle
    filenames (11.53%) read `und` while carrying a resolvable code. After:
    **8** (0.02%), every one a shape the guard refuses on purpose —
    `ja[no-sdh]`, `ja[cc][no furigana]`. ⛔ **Zero slots in that corpus could
    ever have exhibited the loss**, because it is Japanese-only; it took a
    constructed bilingual library to see it at all, which is exactly the class
    `07-test-plan.md` says a real-data pass structurally cannot reach.

    ⚠ It was held as `xfail(strict=True)` for one session on the ground that
    `sidecar` is one of the four shapes 3b froze. **Ruled: the freeze is on the
    SHAPE, and this is a conformance defect against a written spec line** — the
    fields are unchanged and only the values move, toward what the spec says.
    """
    cell = measured["scenarios"]["two_languages"]["bracketed"]
    assert cell["survival"]["gone"] == [], cell["survival"]["gone"]
    assert cell["both_languages_survived"] is True, cell["survival"]


def test_the_CONTROL__the_same_two_files_dotted_keep_both_languages(measured):
    u"""⭐ THE HALF THAT MUST PASS, and it is the evidence.

    ⚠ REBUILT AFTER AN ADVERSARIAL PASS. The original control was `dotted`
    alone, and it did not isolate the language reader: under the dotted tags the
    sidecar STEM also comes to match the video, so both files are written **in
    place over themselves** while the bracketed arm writes a new name and
    trashes. Two mechanisms differed, not one.

    So the evidence is now three arms:
      `dotted_apart`   dotted tags, a stem the video does NOT match -> both
                       survive as NEW files. The tag is the only difference
                       from `bracketed` that can matter.
      `same_language`  one language, two files -> one MUST lose its slot, which
                       is what proves these arms are not simply incapable of
                       losing a file.
    """
    arms = measured["scenarios"]["two_languages"]

    apart = arms["dotted_apart"]
    assert apart["survival"]["untouched"] is True, apart["survival"]
    assert apart["run"]["counts"]["written"] == 2, apart["run"]["summary"]
    langs = sorted(row["lang"] for row in apart["run"]["results"].values())
    assert langs == [u"en", u"ja"], langs

    # ⭐ AND THE ARMS CAN LOSE A FILE — otherwise the one above proves nothing.
    same = arms["same_language"]
    assert same["survival"]["gone"], (
        "two files of ONE language both survived, so these arms cannot "
        "distinguish a language slot from anything else: %s" % same["survival"])


# ==========================================================================
# the floor
# ==========================================================================

def _differences(got, want, path=u""):
    u"""Every leaf on which two fact trees disagree. -> [(path, got, want)]

    🚨 EXHAUSTIVE, AND IT WAS NOT. The floor comparison used to hand-enumerate
    which keys of `one_folder` and `broadcast_cut` to check, so **any key added
    under those two branches was never compared** — an adversarial pass flipped
    `dry_changed_the_tree` in the floor and doctored `source_cues`, and both
    passed. The sibling check that guards the floor's coverage compared only
    TOP-LEVEL keys, so it could not see it either.

    ⚠ Floats compare with `OFFSET_DRIFT`, because an offset is a measurement.
    Everything else compares exactly, because a count is a decision.
    """
    out = []
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return [(path, got, want)]
        for key in sorted(set(want) | set(got)):
            out += _differences(got.get(key, u"<absent>"),
                                want.get(key, u"<absent>"),
                                u"%s.%s" % (path, key))
        return out
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return [(path, got, want)]
        for i, (g, w) in enumerate(zip(got, want)):
            out += _differences(g, w, u"%s[%d]" % (path, i))
        return out
    if isinstance(want, bool) or isinstance(got, bool):
        return [] if got is want else [(path, got, want)]
    if isinstance(want, numbers.Real) and isinstance(got, numbers.Real):
        if isinstance(want, int) and isinstance(got, int):
            return [] if got == want else [(path, got, want)]
        return ([] if abs(got - want) <= E.OFFSET_DRIFT
                else [(path, got, want)])
    return [] if got == want else [(path, got, want)]


def test_the_end_to_end_facts_still_MATCH_THE_RECORDED_FLOOR(facts, baseline):
    u"""⚠ A FLOOR, NEVER A TARGET — the same contract as
    `vn-bench-baseline.json`. The suite fails when an answer MOVES; a deliberate
    change is re-recorded with `python -m tsubasa.dev e2e --baseline` and the
    reason goes in `RUNBOOK.md`.

    ⚠ Corpus PROPERTIES are deliberately not in the floor. `source_cues: 303`
    was, compared exactly — a property of a file somebody else wrote, which
    rots the moment the fixture is re-staged, and whose rot-proof form
    (`written == source − 1`) is asserted directly above.
    """
    diffs = _differences(facts, baseline)
    assert not diffs, u"\n".join(
        u"  %s: now %r, floor %r" % (p, g, w) for p, g, w in diffs)


def test_the_floor_covers_every_scenario_the_benchmark_RUNS(facts, baseline):
    u"""⚠ A floor that has drifted out of date silently stops guarding what it
    never learned about — the same shape as a harness that is not in the
    runner. ⭐ `_differences` walks both trees, so a key present on one side
    only is now a difference at any depth; this states the top-level case
    with a message a human can act on."""
    assert sorted(facts) == sorted(baseline), (
        "scenarios not in the floor: %s; in the floor but not run: %s"
        % (sorted(set(facts) - set(baseline)),
           sorted(set(baseline) - set(facts))))
