# -*- coding: utf-8 -*-
"""
The TITLE gate. RUNBOOK step A2b+.

⭐ THE CLAIM UNDER TEST, and it is a claim about a BLIND SPOT.

`parsergate` scores the UNION of three parsers, so when anitopy rescued an
episode our own parser had mangled, the headline number stayed green — and
**our own TITLE stayed wrong on every one of those files.** Series identity
consumes the title, not the episode. `A2-fix` moved *series keys still carrying
an `E##` token* from **9.1% to 0.00%** while the parser gate moved 97.38 →
96.78, and that is the whole reason this gate exists.

🚨 THE METRIC IS SELF-REFERENTIAL, AND MOST OF THIS FILE IS ABOUT WHY.

    CONTAMINATED = an episode MARKER is still in the title,
                   AND its number is the one the parser called the episode.

**Both halves are load-bearing**, and the first version of the gate had only
the second. Read on its first run, 2 of the first 5 accusations were false:
`５→９～私に恋したお坊さん～ ＃05` (the show is *called* `5→9`) and
`ラスト・コップ２nd ＃02` (*Last Cop 2nd*). ⚠ `LEDGER.md` records the same trap
pointing the other way — *"One Piece really does reach episode 1121, so four
digits is not the tell"* — and a number-only test walks into it either way.

⚠ AND THE OBVIOUS METRIC WAS MEASURED AND REJECTED. RUNBOOK A2b+ asks for
*"the share of same-show files whose series key differs"*. Probe A2b+/1
measured it: **21.6% of entries carry more than one script**, and grouping by
(entry, script) does not save it either, because `Space Ironmen Kyodyne` and
`Uchuu Tetsujin Kyoudain` are both Latin, both one entry, and both right. That
number is kept as a **trend line and is not gated**.
"""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.dev import titlegate as G                       # noqa: E402
from tsubasa.naming.episode import parse_ours                # noqa: E402
from tsubasa.paths import corpus_root, load_config           # noqa: E402

BASELINE = ROOT / G.BASELINE


# ==========================================================================
# ⭐ the metric -- both halves, and the cases that defeated half of it
# ==========================================================================

# ⭐ THE DETECTOR IS TESTED ON CONSTRUCTED `Parsed` OBJECTS, NOT ON FILENAMES,
# and that separation is deliberate.
#
# This gate's fixtures were real corpus names that WERE contaminated. Then the
# gate did its job: the parser was fixed and **6.45% became 0.15%** — and four
# of these checks went red because their inputs are no longer broken. A gate
# whose fixtures are the very defect it is meant to outlive cannot survive its
# own success.
#
# So: the DETECTOR is exercised directly on `(title, episode)` pairs, and the
# PARSER's behaviour on real names gets its own regression check below.
@pytest.mark.parametrize("title,episode", [
    # The broadcast double-marker shape, as it looked before the fix.
    (u"舞いあがれ! S01E124 第124回「私たちの翼」", 124),
    (u"ワンピース S10E026 第1025話 最悪の世代全滅!", 1025),
    (u"NARUTO ナルト 疾風伝 S17E01 第349話 心を隠す面", 349),
    (u"ムカムカパラダイス 第06話 「チョキチョキ恐竜」", 6),
    # ⚠ ONE MARKER EACH. Every fixture above carries BOTH `S##E##` and `第N話`,
    # so a mutation deleting either pattern SURVIVED — the other still caught
    # every case. Same shape as the kana epenthetic-vowel mutant in
    # `LEDGER.md`: *the rule was fine; the check could not feel it.*
    (u"S01E21 Pagan Village and Priest's Contract", 21),
    (u"EP03 Fuyu no Sakura", 3),
    (u"作品名 第06話 サブタイトル", 6),
])
def test_a_surviving_episode_MARKER_is_caught(title, episode):
    """🚨 The defect `parsergate` cannot see: the episode came out RIGHT and
    the title kept the marker, so the union score stays green while series
    identity breaks."""
    from tsubasa.naming.episode import Parsed
    assert G.episode_survives_in_title(Parsed(title=title, episode=episode))


@pytest.mark.parametrize("name,expected", [
    (u"【連続テレビ小説】舞いあがれ！.S01E124.第124回「私たちの翼」.WEBRip.Amazon.ja.srt",
     u"舞いあがれ!"),
    (u"ワンピース.S10E026.第1025話 最悪の世代全滅!.WEBRip.Amazon.ja.srt",
     u"ワンピース"),
    (u"NARUTO－ナルト－.疾風伝.S17E01.第349話.心を隠す面.WEB-DL.Hulu.ja.srt",
     u"NARUTO ナルト 疾風伝"),
    (u"ムカムカパラダイス(1993) 第06話 「チョキチョキ恐竜」 (640x480).srt",
     u"ムカムカパラダイス"),
])
def test_the_broadcast_DOUBLE_MARKER_shape_now_parses_clean(name, expected):
    """⭐ THE FIX THIS GATE PAID FOR, pinned as a regression check.

    `第N話` searches the RAW filename so noise stripping cannot eat it — which
    meant `cut` indexed a different string from the one the title is sliced
    from, and so was never set at all. The title kept everything. And because
    the *episode* came out right, `parsergate` was green over it.

    Measured over the full catalogue: **6.45% → 0.15%**, 13,137 files → 299.

    ⚠ `NARUTO ナルト 疾風伝` keeps `疾風伝` on purpose — it is the only thing
    separating Shippuuden from Naruto, and dropping it is subsync's original
    defect (`06-edge-cases.md` §2.4).
    """
    verdict, _key, parsed = G.classify(name)
    assert parsed.title == expected, (parsed.title, expected)
    assert verdict == G.CLEAN, verdict


@pytest.mark.parametrize("name", [
    # ⛔ STILL CONTAMINATED, AND CORRECTLY SO. The name BEGINS with the marker,
    # so there is no series title in it at all — the folder carries that.
    # Cutting at 0 would trade a contaminated title for an EMPTY one, which is
    # worse: an empty key pairs with every video sharing an episode number
    # (`08-probes.md` §C, 4,133 files).
    u"S01E01-The Harvest Festival and the Crowded Driver's Box [9267DE3E].ass",
])
def test_a_name_that_is_ONLY_a_marker_is_reported_not_emptied(name):
    """⭐ The residual 0.15%, named rather than hidden. The gate reports it;
    the parser deliberately does not "fix" it into nothing."""
    verdict, key, parsed = G.classify(name)
    assert parsed.episode is not None
    assert key, "the title was emptied -- an empty key pairs with everything"
    assert verdict == G.CONTAMINATED


@pytest.mark.parametrize("name,why", [
    (u"５→９～私に恋したお坊さん～ ＃05.srt", u"the show is CALLED 5→9"),
    (u"ラスト・コップ２nd ＃02.srt", u"the show is CALLED Last Cop 2nd"),
    (u"Mobile Suit Gundam 0080 - 03.srt", u"0080 is the title"),
    (u"Mob Psycho 100 - 100.srt", u"100 is the title AND the episode"),
    (u"86 - 07.srt", u"86 is the title"),
])
def test_a_TITLE_that_merely_contains_the_number_is_NOT_accused(name, why):
    """🚨 THE HALF THE FIRST VERSION DID NOT HAVE, and it was wrong on 2 of its
    first 5 accusations because of it.

    ⭐ These carry no episode MARKER inside the title, so the pattern half of
    the test refuses to fire however the digits line up. `Mob Psycho 100` at
    episode 100 is the sharpest case: number-equality alone accuses it, and it
    is plainly correct.
    """
    verdict, _key, parsed = G.classify(name)
    assert parsed.episode is not None, "the fixture must parse an episode"
    assert verdict != G.CONTAMINATED, (why, parsed.title, parsed.episode)


def test_BOTH_halves_of_the_rule_are_required(monkeypatch):
    """⚠ Asserted as a property, not inferred from the two lists above.

    A marker whose number is NOT the extracted episode is not contamination —
    it is a title that genuinely contains something marker-shaped — and the
    number alone is not contamination either.
    """
    from tsubasa.naming.episode import Parsed
    # marker present, number does NOT match -> not contamination
    assert not G.episode_survives_in_title(
        Parsed(title=u"Show 第99話", episode=4))
    # number matches, NO marker -> not contamination
    assert not G.episode_survives_in_title(
        Parsed(title=u"Gundam 0080", episode=80))
    # both -> contamination
    assert G.episode_survives_in_title(
        Parsed(title=u"Show 第04話", episode=4))


def test_full_width_digits_in_a_marker_are_caught():
    """⚠ Built from a LITERAL, never a format string. `LEDGER.md` §Harness
    records this trap twice in one day — a "full-width" fixture written as
    `u"（０%d）" % i` emits an ASCII digit and passes against broken code."""
    from tsubasa.naming.episode import Parsed
    assert G.episode_survives_in_title(Parsed(title=u"作品 第０４話", episode=4))
    assert G.episode_survives_in_title(Parsed(title=u"作品 ＃０４", episode=4))


def test_an_EMPTY_title_is_its_own_verdict_not_a_pass():
    """⚠ An empty key agrees with every other empty key, so a gate that scored
    only agreement would call this perfect. It also pairs with **every** video
    sharing an episode number — `08-probes.md` §C measured 4,133 files."""
    verdict, key, _p = G.classify(u"[SGS][Deadman_Wonderland][12][BDrip].ass")
    assert verdict == G.EMPTY and key == u""


def test_a_name_with_no_episode_is_never_contaminated():
    """A film has no episode, so there is nothing that could have survived."""
    for name in (u"Inception (2010).en.srt", u"君を愛したひとりの僕へ.2022.srt"):
        verdict, _key, parsed = G.classify(name)
        assert parsed.episode is None
        assert verdict != G.CONTAMINATED, name


# ==========================================================================
# the corpus pass -- skips loudly rather than passing vacuously
# ==========================================================================

@pytest.fixture(scope="module")
def measured():
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    try:
        rows, _skipped, _sealed = G.iter_rows(cfg, root, sample=8000)
    except IOError as exc:
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)
    if len(rows) < 2000:
        pytest.skip("SKIPPED, NOT PASSED: only %d catalogue rows" % len(rows))
    return G.measure(rows)


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no %s. Record it with "
                    "`python -m tsubasa.dev titlegate --all --baseline`."
                    % G.BASELINE)
    with io.open(str(BASELINE), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_baseline_was_recorded_from_a_FULL_pass(baseline):
    """⛔ The parser gate's 97.38% was an 800-file SAMPLE recorded as a floor,
    taken before the parser was rewritten, and it was never comparable to
    anything. `LEDGER.md` §Harness, twice. The gate refuses `--baseline`
    without `--all`; this asserts the artefact agrees."""
    assert baseline.get("sampled") is False, baseline
    assert baseline.get("rows", 0) > 100000, baseline


def test_contamination_has_not_regressed(measured, baseline):
    """⚠ A CEILING, not a floor. This number must go DOWN, so the suite fails
    when it rises — the opposite direction from every other gate here, and it
    is written into the artefact's own `//` note so nobody re-records it the
    wrong way round."""
    n = measured["rows"]
    rate = 100.0 * measured["verdicts"].get(G.CONTAMINATED, 0) / n
    ceiling = baseline["contaminatedPct"]
    # ⚠ The sample is ~4% of the catalogue, so a few tenths is sampling noise
    # rather than a regression. The denominator is printed either way.
    assert rate <= ceiling + 1.0, (
        "contaminated %.2f%% over %d sampled rows, baseline ceiling %.2f%%"
        % (rate, n, ceiling))


def test_every_verdict_is_reachable_on_real_names(measured):
    """⚠ A fixture where every row looks the same tests one branch and leaves
    the other to production — it is what let `0 broken of 0` look like
    coverage. All three verdicts must occur in the real catalogue."""
    seen = measured["verdicts"]
    assert set(seen) == {G.CLEAN, G.CONTAMINATED, G.EMPTY}, sorted(seen)
    assert sum(seen.values()) == measured["rows"]


def test_the_gate_reads_filenames_only(measured):
    """⭐ Rule 4. Not one file is opened, which is why a full pass over 203,591
    rows costs seconds. If this ever needs media, it has stopped being a gate
    and become a run."""
    assert measured["rows"] > 0
    assert G.classify(u"Show - 01.srt")[0] in (G.CLEAN, G.CONTAMINATED,
                                               G.EMPTY)


def test_the_sealed_slice_is_excluded_and_something_WAS_excluded():
    """🔒 A test's candidate pool can break the seal silently — `LEDGER.md`
    §Logic records exactly that, in a unit test, noticed only because it made a
    number *worse*.

    ⭐ Two claims, two assertions: sealed shows are absent from the rows, **and
    the exclusion actually fired**. Asserting only the first passes against a
    corpus that happens to contain no sealed shows at all.
    """
    from tsubasa.dev import corpus as C

    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    rows, skipped, sealed_shows = G.iter_rows(cfg, root, sample=None)

    assert sealed_shows > 0, "the manifest lists no sealed shows at all"
    assert skipped > 0, (
        "nothing was skipped as sealed -- the exclusion never fired, so this "
        "check would pass against a gate that reads the sealed slice")

    manifest = C.load_manifest(cfg)
    sealed = {C.split_key(show)
              for scope in manifest.get("scopes", {}).values()
              for show in scope.get("sealed", [])}
    leaked = [r for r in rows[:20000]
              if C.split_key(r.get("show") or u"") in sealed]
    assert not leaked, "%d sealed rows survived: %r" % (
        len(leaked), [r.get("show") for r in leaked[:3]])


def test_the_sample_is_DRAWN_not_a_prefix():
    """🚨 `catalog.jsonl` is ordered by jimaku entry id, so *"the first N"* is
    the OLDEST shows, not a cross-section.

    Measured at A2c: a prefix read film pollution as **6.4%** where a strided
    pass over the same file read **39.9%** (`LEDGER.md` §Harness). *The cheap
    version of a sample is a different population wearing the same sample
    size.*
    """
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    everything, _s, _z = G.iter_rows(cfg, root, sample=None)
    drawn, _s, _z = G.iter_rows(cfg, root, sample=3000)
    assert len(drawn) == 3000
    prefix_entries = {r.get("entry") for r in everything[:3000]}
    drawn_entries = {r.get("entry") for r in drawn}
    # A real draw spans far more of the catalogue than its first 3,000 rows do.
    assert len(drawn_entries) > 3 * len(prefix_entries), (
        "the sample covers %d entries and the first 3,000 rows cover %d -- "
        "this looks like a prefix, not a draw"
        % (len(drawn_entries), len(prefix_entries)))


def test_the_SPLIT_number_is_reported_but_not_gated(measured, baseline):
    """⛔ It is a trend line. 21.6% of entries carry more than one script, and
    `Space Ironmen Kyodyne` / `Uchuu Tetsujin Kyoudain` are both Latin, both
    one entry, and both right. **Tuning against it would be tuning against the
    corpus.** It is recorded so a large move is visible, and asserted only to
    be present and sane."""
    assert 0.0 <= baseline["offModalPct"] <= 100.0
    assert measured["groups"] > 0 and measured["groupedFiles"] > 0
    assert measured["offModal"] <= measured["groupedFiles"]
