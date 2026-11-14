# -*- coding: utf-8 -*-
u"""
RUNBOOK B6 -- a video with NO subtitle track, measured against the speech in its
own audio (`--vad` / `sync(vad=True)`). Based on Mattias's Tsubasa-sync #4.

⭐ MEDIA-FREE. The speech module is INJECTED (`sync(speech=...)`, the same seam
shape as `reader=`), so every rule the pipeline and the verdict apply to a
speech mask runs here without whisper.cpp. What Silero and whisper actually
hear on real audio is `test_vad.py`'s, on the Yomi set.

THE CLAIMS:

  1. 🚨 TWO SIGNALS, NOT ONE. Timing (Silero onsets against `MASK_BAND`) AND the
     text witness must both pass. Timing alone refuses; a witness that could
     not run refuses with its reason; a coherent cluster lifts nothing on a
     mask (positive control first: the same cluster DOES lift a cue pair).
  2. ⭐ THE HARDEST WRONG PAIR: identical timing, different words. Only the
     witness can refuse it, and it is driven explicitly.
  3. ⛔ ONE OFFSET on a mask (`12-alignment.md` §5 ruling 1): a cut subtitle is
     refused, never split -- and the same subtitle IS split against a cue
     track, so the single offset is the rule, not the data.
  4. ⭐ The cost guard: a pair the timing refuses never pays for a
     transcription, and `mask_would_accept` agrees with `verdict()` everywhere.
  5. ⛔ `speech.py` refuses a whisper.cpp it has not proven: the exact
     version, and its defaults read back through our structs.

⚠ JAPANESE fixture text, different on every line, built by joining LITERALS:
an ASCII fixture cannot test `normalise()`'s any-script rule (`LEDGER-HOT`:
`%d` emits ASCII), and a repeated line would let every window match every
other.
"""
import ctypes
import io
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import api as API                                # noqa: E402
from tsubasa import container as CONTAINER                    # noqa: E402
from tsubasa import cues as CUES                              # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa import speech as SPEECH                          # noqa: E402
from tsubasa import verdict as V                              # noqa: E402
from tsubasa import witness as W                              # noqa: E402
from tsubasa.align import align, unique_starts                # noqa: E402
from tsubasa.align.objective import MR_TOL                    # noqa: E402
from tsubasa.arbitrate import Cluster                         # noqa: E402

from test_verdict import AGREEING, make_fit                   # noqa: E402


# ---------------------------------------------------------------------------
# fixtures -- an episode's speech, its subtitle, and another episode's words
# ---------------------------------------------------------------------------

RUNTIME = 1420.0
LAG = SPEECH.ONSET_LAG

_HEAD = (u"今日はどこへ行くの", u"あの山の向こうに", u"本当に大丈夫なのか",
         u"ちょっと待ってくれ", u"もう時間がないんだ", u"誰が来たと思う",
         u"そんなこと言われても", u"一緒に帰ろうよ", u"約束は守るから",
         u"気をつけて行ってね", u"それは違うと思う", u"静かにしなさい",
         u"ここで何をしている")
_TAIL = (u"兄さん", u"お母さん", u"先生", u"みんな", u"あいつら", u"お前",
         u"村の人たち", u"ユキ", u"ダラ", u"アサ", u"ジン", u"影森さん",
         u"山田くん", u"お嬢様", u"若様")
_OTHER_HEAD = (u"雨が降りそうだな", u"腹が減ったよ", u"この店は初めてだ",
               u"列車が遅れている", u"手紙を読んでくれ", u"窓を開けておいて",
               u"財布をなくした", u"海まで歩こう", u"写真を撮ってもいい",
               u"宿題が終わらない", u"鍵はどこにある", u"猫が逃げたぞ",
               u"明日は晴れるかな")
_OTHER_TAIL = (u"かもしれない", u"らしいよ", u"だろうね", u"じゃないか",
               u"のはずだ", u"と聞いた", u"って本当", u"ですよね",
               u"なんだけど", u"に決まってる", u"だったっけ", u"でしょう",
               u"みたいだ", u"かな", u"よね")


def _lines(heads, tails, n):
    u"""`n` distinct Japanese lines, joined from literals -- never formatted."""
    out = [h + u"、" + t for t in tails for h in heads]
    assert len(out) >= n and len(set(out[:n])) == n
    return out[:n]


def _starts(seed, runtime=RUNTIME):
    u"""Cue moments with a real episode's irregular rhythm (3-12 s apart)."""
    rnd = np.random.RandomState(seed)
    t, out = 4.0, []
    while t < runtime - 20.0:
        out.append(round(t, 3))
        t += float(rnd.uniform(3.0, 12.0))
    return out


#: The episode's speech, in VIDEO time: one onset per line, plus speech the
#: subtitle has no line for (a scream, a background voice).
VIDEO_STARTS = _starts(18)
#: ⚠ The subtitle is 2.0 s EARLY, so the answer is +2.0: the offset is what is
#: ADDED to every subtitle time (`12-alignment.md` §1).
SHIFT = 2.0
LINES = _lines(_HEAD, _TAIL, len(VIDEO_STARTS))
OTHER_LINES = _lines(_OTHER_HEAD, _OTHER_TAIL, len(VIDEO_STARTS))


def _onsets(video_starts=VIDEO_STARTS, seed=5):
    u"""What Silero reports: each line's speech starting `LAG` late, and 25
    onsets of speech nobody subtitled. RAW, as `speech_onsets` returns them --
    (t0, t1) pairs, lag NOT removed.

    ⚠ No per-onset jitter ON PURPOSE: jitter AND stray onsets together leave
    `_refine`'s plateau on a one-hit spike 0.30 s off (B1's refine, not B6's;
    `12-alignment.md` §5b), which would hide the 0.29 s lag this fixture is
    here to see removed. Real residuals are `test_vad.py`'s."""
    rnd = np.random.RandomState(seed)
    on = [t + LAG for t in video_starts]
    on += [float(x) for x in rnd.uniform(10.0, RUNTIME - 10.0, 25)]
    return [(t, t + 1.2) for t in sorted(on)]


def _stamp(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return u"%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _srt(starts, lines):
    out = []
    for i, (t, text) in enumerate(zip(starts, lines)):
        out.append(u"%d\n%s --> %s\n%s\n\n"
                   % (i + 1, _stamp(t), _stamp(t + 1.5), text))
    return u"".join(out)


def _write(path, text):
    with io.open(str(path), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return str(path)


def _heard(lines=LINES, video_starts=VIDEO_STARTS):
    u"""What whisper hears in each witness window: the lines SPOKEN there."""
    def heard(_video, duration):
        out = []
        for start in W.windows(duration):
            said = [ln for t, ln in zip(video_starts, lines)
                    if start <= t < start + W.WINDOW_S]
            out.append((start, u"".join(said)))
        return out
    return heard


class FakeSpeech(object):
    u"""The speech module's shape, with every call counted."""

    ONSET_LAG = SPEECH.ONSET_LAG
    SpeechUnavailable = SPEECH.SpeechUnavailable

    def __init__(self, onsets=None, heard=None, onsets_error=None,
                 heard_error=None):
        self.onsets = _onsets() if onsets is None else onsets
        self.heard = heard or _heard()
        self.onsets_error = onsets_error
        self.heard_error = heard_error
        self.onset_calls = 0
        self.heard_calls = 0

    def describe(self):
        return u"speech path: test double"

    def speech_onsets(self, video, duration):
        self.onset_calls += 1
        if self.onsets_error:
            raise SPEECH.SpeechUnavailable(self.onsets_error)
        return list(self.onsets)

    def heard_windows(self, video, duration):
        self.heard_calls += 1
        if self.heard_error:
            raise SPEECH.SpeechUnavailable(self.heard_error)
        return self.heard(video, duration)


def _no_track_reader(duration=RUNTIME):
    def read(path):
        return CONTAINER.ContainerInfo(path=path, format="matroska",
                                       duration=duration, tracks=[])
    return read


@pytest.fixture()
def episode(tmp_path):
    u"""A video with NO subtitle track (its bytes are never read: the reader
    is injected) and the right subtitle, 2.0 s early."""
    video = tmp_path / u"Show S01E18.mkv"
    video.write_bytes(b"\x1aE\xdf\xa3" + b"\0" * 64)
    sub = _write(tmp_path / u"Show S01E18.ja.srt",
                 _srt([t - SHIFT for t in VIDEO_STARTS], LINES))
    return {"root": tmp_path, "video": str(video), "subtitle": sub}


def _sync(episode, speech, subtitle=None, vad=True, **kw):
    return PIPE.sync([(episode["video"], subtitle or episode["subtitle"])],
                     vad=vad, reader=_no_track_reader(), speech=speech,
                     results=False, **kw)


# ===========================================================================
# 1. the path is OFF unless asked for, and says how to turn it on
# ===========================================================================

def test_without_vad_a_no_track_video_is_refused_naming_the_switch(episode):
    speech = FakeSpeech()
    got = _sync(episode, speech, vad=False)
    assert got[0].outcome == V.ERROR
    assert u"--vad" in got[0].reason
    assert speech.onset_calls == 0 and speech.heard_calls == 0


# ===========================================================================
# 2. ⭐ the right subtitle: timing AND text agree -> CONFIDENT, capped `fair`
# ===========================================================================

def test_the_right_subtitle_is_confident_at_its_own_offset(episode):
    speech = FakeSpeech()
    got = _sync(episode, speech)
    r = got[0]
    assert r.outcome == V.CONFIDENT, r.reason
    assert r.reference_kind == V.SPEECH_MASK
    assert len(r.segments) == 1
    # ⚠ Within MR_TOL, not tighter: on a mask many onsets have no line, and
    # `_refine`'s plateau can sit on a stray onset's spike anywhere inside the
    # tolerance (`12-alignment.md` §5b). The lag's exact removal is pinned by
    # `test_the_reference_is_the_onsets_moved_earlier_by_the_lag`.
    assert abs(r.segments[0][1] - SHIFT) <= MR_TOL, r.segments
    # ⚠ Capped: a mask's multiple is not on the cue-vs-cue word scale.
    assert r.verdict_word == u"fair"
    assert any(u"text check" in n for n in r.notes)
    assert speech.heard_calls == 1


def test_the_reference_is_the_onsets_moved_earlier_by_the_lag():
    speech = FakeSpeech()
    ref, why = PIPE.speech_reference(u"/x/v.mkv", RUNTIME, speech=speech)
    assert why == u""
    assert ref.kind == V.SPEECH_MASK
    raw = [t0 for t0, _t1 in speech.onsets]
    assert ref.starts == [t - LAG for t in raw]
    assert ref.hearing is not None and speech.heard_calls == 0, (
        "the transcription must be lazy: only an accepted timing asks")


# ===========================================================================
# 3. 🚨 the hardest wrong pair: IDENTICAL timing, other words
# ===========================================================================

def test_identical_timing_with_other_words_is_REFUSED_by_the_witness(
        episode, tmp_path):
    u"""A recap, a re-dub, a wrong episode cut to the same rhythm: timing
    cannot tell. The witness can."""
    wrong = _write(tmp_path / u"Other S01E18.ja.srt",
                   _srt([t - SHIFT for t in VIDEO_STARTS], OTHER_LINES))
    speech = FakeSpeech()
    r = _sync(episode, speech, subtitle=wrong)[0]
    assert r.outcome == V.REFUSED
    assert speech.heard_calls == 1, "timing alone must have reached accept"
    assert u"does not match" in r.reason
    assert r.output_path is None


def test_a_witness_that_could_not_run_REFUSES_with_its_reason(episode):
    speech = FakeSpeech(heard_error=u"no whisper model was found")
    r = _sync(episode, speech)[0]
    assert r.outcome == V.REFUSED
    assert u"no whisper model was found" in r.reason


def test_a_subtitle_in_another_language_than_the_speech_is_not_called_wrong(
        episode, tmp_path):
    u"""⛔ An English subtitle on Japanese speech is not *"a different
    episode"*: the witness says it cannot compare, and why."""
    english = [u"Where are you going today", u"Beyond that mountain",
               u"Are you really all right", u"Wait a moment",
               u"There is no time left", u"Guess who came"]
    lines = [english[i % len(english)] for i in range(len(VIDEO_STARTS))]
    sub = _write(tmp_path / u"Show S01E18.en.srt",
                 _srt([t - SHIFT for t in VIDEO_STARTS], lines))
    r = _sync(episode, FakeSpeech(), subtitle=sub)[0]
    assert r.outcome == V.REFUSED
    assert u"language" in r.reason and u"Japanese" in r.reason


# ===========================================================================
# 4. ⭐ the cost guard -- a pair the timing refuses is never transcribed
# ===========================================================================

def test_a_pair_the_timing_refuses_never_pays_for_a_transcription(
        episode, tmp_path):
    wrong = _write(tmp_path / u"Show S01E19.ja.srt",
                   _srt(_starts(19), OTHER_LINES))
    speech = FakeSpeech()
    r = _sync(episode, speech, subtitle=wrong)[0]
    assert r.outcome == V.REFUSED
    assert speech.heard_calls == 0


@pytest.mark.parametrize("excess", [1.2, 1.9, 2.0, 2.3, 2.59, 2.6, 2.61, 4.0])
@pytest.mark.parametrize("holds", [True, False])
def test_the_cost_guard_agrees_with_the_verdict_everywhere(excess, holds):
    u"""⛔ `mask_would_accept` is not a second copy of the rule: wherever it
    says no, the verdict refuses even with a passing witness; wherever it
    says yes, a passing witness is what makes it CONFIDENT."""
    fit = make_fit(excess=excess, failing=() if holds else
                   [(0.0, 40, 0.30, +10.0, 0.62)])
    passing = W.Witness(True, [], u"")
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK, witness=passing)
    assert V.mask_would_accept(fit) == (v.outcome == V.CONFIDENT)


# ===========================================================================
# 5. ⛔ one offset on a mask
# ===========================================================================

def _cut_subtitle_starts():
    u"""A broadcast cut: the opening 3:40 wants +12 s more than the rest."""
    return [t - SHIFT - (12.0 if t < 220.0 else 0.0) for t in VIDEO_STARTS]


def test_a_cut_subtitle_is_SPLIT_against_a_cue_track_positive_control():
    u"""The positive control: the same cut IS found cue-vs-cue, so the next
    check's single offset is the mask rule, not this fixture."""
    fit = align(unique_starts(VIDEO_STARTS),
                unique_starts(_cut_subtitle_starts()), RUNTIME)
    assert fit.is_cut


def test_a_cut_subtitle_on_a_mask_gets_ONE_offset_and_is_refused(
        episode, tmp_path):
    cut = _write(tmp_path / u"Show S01E18 (TV).ja.srt",
                 _srt(_cut_subtitle_starts(), LINES))
    speech = FakeSpeech()
    r = _sync(episode, speech, subtitle=cut)[0]
    assert len(r.segments) == 1
    assert r.outcome == V.REFUSED
    assert r.output_path is None


# ===========================================================================
# 6. what the mask needs before its timing means anything
# ===========================================================================

def test_too_little_speech_is_refused_by_count(episode):
    thin = _onsets()[:PIPE.MIN_MASK_ONSETS - 1]
    speech = FakeSpeech(onsets=thin)
    r = _sync(episode, speech)[0]
    assert r.outcome == V.ERROR
    assert (u"%d" % (PIPE.MIN_MASK_ONSETS - 1)) in r.reason
    assert speech.heard_calls == 0


def test_the_onset_floor_sits_where_thinning_stopped_accepting_wrong_pairs():
    u"""🚨 `12-alignment.md` §5b: thinned real onsets accepted wrong episodes
    and controls at 60 (2 of 264), 40 (22) and 25 (49), and none from 80 up.
    The check above reads the constant, so this is what holds it there."""
    assert PIPE.MIN_MASK_ONSETS >= 80


def test_exactly_the_floor_is_measured(episode):
    u"""The boundary: `MIN_MASK_ONSETS` onsets are enough to be MEASURED."""
    ref, why = PIPE.speech_reference(
        u"/x/v.mkv", RUNTIME,
        speech=FakeSpeech(onsets=_onsets()[:PIPE.MIN_MASK_ONSETS]))
    assert ref is not None, why


def test_speech_that_cannot_be_read_is_an_ERROR_with_its_sentence(episode):
    speech = FakeSpeech(onsets_error=u"ffmpeg is not on this machine")
    r = _sync(episode, speech)[0]
    assert r.outcome == V.ERROR
    assert u"no subtitle track" in r.reason
    assert u"ffmpeg is not on this machine" in r.reason


# ===========================================================================
# 7. the verdict on a mask
# ===========================================================================

def test_timing_alone_never_makes_a_mask_pair_confident():
    for witness in (None, W.Witness.unavailable(u"no model")):
        v = V.verdict(make_fit(excess=4.0), reference_kind=V.SPEECH_MASK,
                      witness=witness)
        assert v.outcome == V.REFUSED
        assert u"Nothing is written" in v.reason


def test_a_coherent_cluster_lifts_a_CUE_pair_positive_control():
    v = V.verdict(make_fit(excess=2.0), cluster=Cluster(AGREEING))
    assert v.outcome == V.CONFIDENT


def test_a_coherent_cluster_lifts_nothing_on_a_mask():
    u"""Coherence was measured on cue-vs-cue offsets; nothing has measured it
    on a mask, and an unmeasured lift is Rule 2's confidently wrong answer."""
    refuse_below, accept_at = V.MASK_BAND
    excess = (refuse_below + accept_at) / 2.0
    v = V.verdict(make_fit(excess=excess), cluster=Cluster(AGREEING),
                  reference_kind=V.SPEECH_MASK,
                  witness=W.Witness(True, [], u""))
    assert v.outcome == V.REFUSED


def test_the_mask_band_refuses_the_measured_broadcast_cut():
    u"""🚨 `12-alignment.md` §5b: the shincaps AT-X cut holds throughout on
    this segmenter at 2.34x. Every right pair measured >= 2.71x."""
    refuse_below, accept_at = V.MASK_BAND
    assert 2.34 < accept_at <= 2.71
    assert 1.92 < refuse_below < accept_at


# ===========================================================================
# 8. the scan path carries `vad` all the way down
# ===========================================================================

def test_a_scan_with_vad_measures_the_no_track_video(episode):
    u"""⚠ `_durations_for` fills the same reference cache the alignment loop
    reads; without `vad` there it left a no-track refusal for the loop to
    find (#4)."""
    speech = FakeSpeech()
    got = PIPE.sync(API.scan(str(episode["root"])), vad=True,
                    reader=_no_track_reader(), speech=speech, results=False)
    assert got.confident, [(r.outcome, r.reason) for r in got]
    assert got.confident[0].reference_kind == V.SPEECH_MASK


def test_the_run_says_once_what_the_speech_path_uses(episode):
    got = _sync(episode, FakeSpeech())
    assert u"speech path: test double" in got.notes


def test_a_speech_module_that_cannot_describe_itself_does_not_fail_the_run(
        episode):
    class Broken(FakeSpeech):
        def describe(self):
            raise OSError("cannot list the folder")
    got = _sync(episode, Broken())
    assert got[0].outcome == V.CONFIDENT


# ===========================================================================
# 9. the witness itself -- pure string arithmetic
# ===========================================================================

def _cue(t, text):
    return CUES.Cue(t, t + 1.5, text)


def test_windows_cover_the_runtime_evenly_and_never_start_before_zero():
    starts = W.windows(1420.0)
    assert len(starts) == W.WINDOWS
    assert starts[0] >= 0.0 and starts[-1] + W.WINDOW_S <= 1420.0
    assert starts == sorted(starts)
    assert W.windows(0) == [] and W.windows(None) == []


def test_normalise_drops_markup_and_folds_full_width():
    assert W.normalise(u"{\\an8}ＡＢ\\Nｃ") == u"abc"
    assert W.normalise(u"<i>今日は、晴れ！</i>") == u"今日は晴れ"


def test_containment_is_what_was_heard_not_what_was_written():
    heard = u"今日はどこへ行くの"
    assert W.containment(heard, heard + u"兄さんみんな先生") == 1.0
    assert W.containment(heard, u"雨が降りそうだな") == 0.0
    assert W.containment(u"", u"何か") == 0.0


def test_the_script_of_japanese_chinese_and_english():
    assert W.script_of(u"今日はどこへ行くの") == u"kana"
    assert W.script_of(u"我们今天去哪里") == u"han"
    assert W.script_of(u"where are we going") == u"latin"
    assert W.script_of(u"1234") is None


def _rows_check(heard_texts, written_texts):
    heard = [(i * 40.0, h) for i, h in enumerate(heard_texts)]
    cues = [_cue(i * 40.0 + 5.0, w) for i, w in enumerate(written_texts)]
    return W.check(heard, cues, 0.0)


def test_quiet_and_unsubtitled_windows_are_not_scored():
    got = _rows_check([u"あ", LINES[1], LINES[2], LINES[3], LINES[4]],
                      [LINES[0], u"", LINES[2], LINES[3], LINES[4]])
    kinds = [v for _t, v in got.rows]
    assert kinds[0] == W.QUIET and kinds[1] == W.NO_SUB
    assert len(got.scored) == 3


def test_too_few_scored_windows_cannot_vouch():
    got = _rows_check(LINES[:W.MIN_SCORED - 1], LINES[:W.MIN_SCORED - 1])
    assert not got.passed and u"only" in got.reason


def test_a_right_pair_may_lose_a_window_and_says_where():
    n = 8
    heard = LINES[:n]
    written = LINES[:n - 2] + OTHER_LINES[:2]
    got = _rows_check(heard, written)
    assert got.passed            # 6 of 8 = 0.75, the share
    assert u"did not match at" in got.reason
    assert u"did not match" in got.summary()


def test_one_window_more_lost_fails_the_share():
    n = 8
    got = _rows_check(LINES[:n], LINES[:n - 3] + OTHER_LINES[:3])
    assert not got.passed        # 5 of 8 < 0.75
    assert u"does not match" in got.reason


def test_speech_in_a_script_the_check_was_not_measured_on_is_not_judged():
    u"""⛔ In the Latin alphabet a WRONG film matched windows at 0.28-0.47
    (`12-alignment.md` §5b) -- over `MATCH` -- so English speech is not judged
    on a line fitted on Japanese, even against a subtitle that says the same
    words."""
    said = [u"where are you going today my friend",
            u"beyond that mountain there is a village",
            u"are you really all right after that",
            u"wait a moment I will come with you",
            u"there is no time left for any of us"]
    got = _rows_check(said, said)
    assert not got.available and not got.passed
    assert u"measured only on Japanese" in got.reason


def test_japanese_speech_with_a_hebrew_subtitle_says_language_not_episode():
    u"""A real case: OpenSubtitles' `sintel.en` is written in Hebrew."""
    got = _rows_check(LINES[:6], [u"מוסד בלנדר מציג", u"הפקה של קרן בלנדר",
                                  u"סינטל", u"תרגום לעברית", u"שלום",
                                  u"להתראות"])
    assert not got.available
    assert u"Hebrew" in got.reason and u"own language" in got.reason


def test_an_unavailable_witness_never_reads_as_passed():
    w = W.Witness(True, [], u"x", available=False)
    assert not w.passed
    assert u"did not run" in W.Witness.unavailable(u"why").summary()


# ===========================================================================
# 10. ⛔ speech.py refuses a whisper.cpp it has not proven
# ===========================================================================

def _defaults_1_8_4():
    u"""whisper.cpp 1.8.4's own defaults, built in memory through our structs
    -- what `_Engine` reads back from the library on load."""
    vad = SPEECH._VadParams(0.5, 250, 100, 3.4e38, 30, 0.1)
    full = SPEECH._FullParams()
    full.strategy, full.n_threads, full.n_max_text_ctx = 0, 4, 16384
    full.thold_pt, full.thold_ptsum = 0.01, 0.01
    full.language = b"en"
    full.max_initial_ts, full.length_penalty = 1.0, -1.0
    full.temperature_inc, full.entropy_thold = 0.2, 2.4
    full.logprob_thold, full.no_speech_thold = -1.0, 0.6
    full.greedy.best_of = 5
    full.beam_search.beam_size, full.beam_search.patience = -1, -1.0
    full.grammar_penalty = 100.0
    full.vad_params = SPEECH._VadParams(0.5, 250, 100, 3.4e38, 30, 0.1)
    return vad, full


def test_the_known_defaults_read_back_as_the_known_layout():
    vad, full = _defaults_1_8_4()
    assert SPEECH._layout_problems(vad, full) == []


def test_a_shifted_field_is_NAMED_and_refuses_the_library():
    u"""A field inserted near the end shifts what we read as
    `grammar_penalty` -- the check names it rather than guessing on."""
    vad, full = _defaults_1_8_4()
    full.grammar_penalty = 0.0
    bad = SPEECH._layout_problems(vad, full)
    assert any(u"grammar_penalty" in b for b in bad)
    vad, full = _defaults_1_8_4()
    vad.min_silence_duration_ms = 250
    assert any(u"min_silence" in b for b in SPEECH._layout_problems(vad, full))


def test_the_vad_struct_is_the_size_whisper_h_1_8_4_gives_it():
    u"""⭐ Passed BY VALUE to `whisper_vad_segments_from_samples`, so its size
    is the calling convention: six 4-byte fields in whisper.h 1.8.4."""
    assert ctypes.sizeof(SPEECH._VadParams) == 24


@pytest.mark.parametrize("version", [u"1.8.5", u"1.8.40", u"1.8.4-rc1",
                                     u"1.9.0", u"1.7.6", u""])
def test_any_release_not_proven_is_refused_by_name(version):
    why = SPEECH.version_refusal(version, u"/lib/whisper.dll")
    assert why and u"1.8.4" in why and u"/lib/whisper.dll" in why


def test_the_proven_release_passes():
    assert SPEECH.version_refusal(u"1.8.4", u"/lib/whisper.dll") is None


@pytest.mark.parametrize("decoded,duration,refused", [
    (1420.0, 1420.0, False), (1380.0, 1420.0, False),
    (1370.0, 1420.0, True), (379.0, 1420.0, True),
    (100.0, None, False), (100.0, 0, False)])
def test_audio_short_of_the_container_is_refused(decoded, duration, refused):
    u"""⛔ RUNBOOK B6: more than 3% short. A real case: a 379 s decode of a
    23-minute DVD episode (the Probe F Naruto slice)."""
    assert bool(SPEECH.short_decode_reason(decoded, duration)) == refused


def test_speech_onsets_refuses_a_short_decode_and_caches_a_whole_one(
        tmp_path, monkeypatch):
    class Eng(object):
        version = u"1.8.4"
        calls = 0

        def vad_settings(self):
            return {u"threshold": 0.5}

        def vad_segments(self, model, samples):
            Eng.calls += 1
            return [(1.0, 2.0)]

    loc = SPEECH.Location(u"/lib/whisper.dll", str(tmp_path / u"vad.bin"),
                          None, [])
    monkeypatch.setattr(SPEECH, "engine", lambda need_asr=False: (Eng(), loc))
    video = tmp_path / u"v.mkv"
    video.write_bytes(b"\0" * 2048)
    from tsubasa.cache import Cache
    cache = Cache(root=tmp_path / u"cache")

    monkeypatch.setattr(SPEECH, "decode_audio",
                        lambda *_a, **_k: np.zeros(16000 * 50, np.float32))
    with pytest.raises(SPEECH.SpeechUnavailable) as e:
        SPEECH.speech_onsets(str(video), 100.0, cache=cache)
    assert u"short" in str(e.value)

    monkeypatch.setattr(SPEECH, "decode_audio",
                        lambda *_a, **_k: np.zeros(16000 * 100, np.float32))
    assert SPEECH.speech_onsets(str(video), 100.0, cache=cache) == [(1.0, 2.0)]
    assert SPEECH.speech_onsets(str(video), 100.0, cache=cache) == [(1.0, 2.0)]
    assert Eng.calls == 1, "the second call must come from the cache"


def test_locate_refuses_to_pick_between_two_models(tmp_path, monkeypatch):
    for name in (u"whisper.dll", u"libwhisper.so", u"libwhisper.dylib",
                 u"ggml-silero-v6.2.0.bin", u"ggml-small-q5_1.bin",
                 u"ggml-large-v3-q5_0.bin"):
        (tmp_path / name).write_bytes(b"\0")
    monkeypatch.setattr(SPEECH, "_OVERRIDE",
                        {"library": None, "vad_model": None,
                         "asr_model": None})
    for env in (SPEECH.ENV_VAD, SPEECH.ENV_ASR):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv(SPEECH.ENV_LIBRARY, str(tmp_path))
    loc = SPEECH.locate()
    assert loc.library and loc.vad_model.endswith(u"ggml-silero-v6.2.0.bin")
    assert loc.asr_model is None
    why = SPEECH.missing_reason(loc, need_asr=True)
    assert SPEECH.ENV_ASR in why and u"Nothing is downloaded" in why
    monkeypatch.setenv(SPEECH.ENV_ASR, str(tmp_path / u"ggml-small-q5_1.bin"))
    assert SPEECH.locate().asr_model.endswith(u"ggml-small-q5_1.bin")


def test_nothing_found_names_every_variable(tmp_path, monkeypatch):
    monkeypatch.setattr(SPEECH, "_OVERRIDE",
                        {"library": None, "vad_model": None,
                         "asr_model": None})
    for env in (SPEECH.ENV_LIBRARY, SPEECH.ENV_VAD, SPEECH.ENV_ASR):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(SPEECH, "_speech_dir", lambda: str(tmp_path))
    why = SPEECH.missing_reason(SPEECH.locate(), need_asr=True)
    for env in (SPEECH.ENV_LIBRARY, SPEECH.ENV_VAD, SPEECH.ENV_ASR):
        assert env in why


# ===========================================================================
# 11. the B6 adversarial pass's findings, each held by a check
# ===========================================================================

def test_a_late_audio_stream_decodes_from_container_time_zero(tmp_path):
    u"""🚨 Raw PCM keeps no timestamps: audio starting 2.0 s into the
    container decoded from 0.02 s, so every onset came out 2 s early -- under
    the 3% check and invisible to the band. Built with ffmpeg here."""
    import subprocess
    from tsubasa.container import ffmpeg as FF
    exe = FF.find("ffmpeg")
    if not exe:
        pytest.skip(u"SKIPPED, NOT PASSED: no ffmpeg to build the fixture")
    video = str(tmp_path / u"late.mkv")
    subprocess.run([exe, "-nostdin", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=32x32:d=10:r=10",
                    "-itsoffset", "2", "-f", "lavfi", "-i", "sine=f=440:d=8",
                    "-map", "0:v", "-map", "1:a", "-c:v", "ffv1",
                    "-c:a", "pcm_s16le", video], check=True,
                   **FF._no_window())
    x = SPEECH.decode_audio(video)
    loud = np.flatnonzero(np.abs(x) > 0.03)
    assert abs(len(x) / float(SPEECH.SAMPLE_RATE) - 10.0) < 0.1
    assert abs(loud[0] / float(SPEECH.SAMPLE_RATE) - 2.0) < 0.05


def test_a_changed_decode_is_measured_again_not_served_from_cache(
        tmp_path, monkeypatch):
    class Eng(object):
        version = u"1.8.4"
        calls = 0

        def vad_settings(self):
            return {u"threshold": 0.5}

        def vad_segments(self, model, samples):
            Eng.calls += 1
            return [(1.0, 2.0)]

    loc = SPEECH.Location(u"/lib/whisper.dll", str(tmp_path / u"vad.bin"),
                          None, [])
    monkeypatch.setattr(SPEECH, "engine", lambda need_asr=False: (Eng(), loc))
    monkeypatch.setattr(SPEECH, "decode_audio",
                        lambda *_a, **_k: np.zeros(16000 * 100, np.float32))
    video = tmp_path / u"v.mkv"
    video.write_bytes(b"\0" * 2048)
    from tsubasa.cache import Cache
    cache = Cache(root=tmp_path / u"cache")
    SPEECH.speech_onsets(str(video), 100.0, cache=cache)
    monkeypatch.setattr(SPEECH, "DECODE_RECIPE", u"some later decode")
    SPEECH.speech_onsets(str(video), 100.0, cache=cache)
    assert Eng.calls == 2


def _measured(kind, n, folder=u"/lib/Show"):
    sub = os.path.join(folder, u"[Grp] Show - %02d.ja.srt" % n)
    ref = PIPE.Reference([0.0], kind, u"x", RUNTIME)
    return PIPE._Measured(os.path.join(folder, u"Show - %02d.mkv" % n), sub,
                          fit=make_fit(excess=4.0), reference=ref)


def test_mask_pairs_do_not_vote_in_the_cluster_that_lifts_track_pairs():
    u"""🚨 Mask offsets could carry a release group's cluster to its quorum
    and LIFT a text-track pair: `vad=True` would change verdicts on videos
    that have a track. Positive control first: track pairs DO form one."""
    tracks = [_measured(V.TEXT_TRACK, n) for n in (1, 2, 3)]
    assert PIPE.clusters_for(tracks)
    masks = [_measured(V.SPEECH_MASK, n) for n in (1, 2, 3)]
    assert PIPE.clusters_for(masks) == {}
    mixed = PIPE.clusters_for(tracks[:1] + masks)
    assert all(c.size == 1 for c in mixed.values())


def test_a_path_the_windows_code_page_cannot_hold_is_refused_by_name():
    path = u"C:/Users/\U0001f642/ggml-small-q5_1.bin"
    if sys.platform != "win32":
        assert SPEECH._c_path(path) == path.encode(sys.getfilesystemencoding())
        return
    with pytest.raises(SPEECH.SpeechUnavailable) as e:
        SPEECH._c_path(path)
    assert u"code page" in str(e.value)
    assert SPEECH._c_path(u"C:/models/ggml-small.bin") == \
        b"C:/models/ggml-small.bin"


def test_the_refusal_only_promises_a_pairing_subtitle_when_one_could_pass():
    fit = make_fit(excess=4.0)
    could_not = V.verdict(fit, reference_kind=V.SPEECH_MASK,
                          witness=W.Witness.unavailable(u"no model here"))
    assert u"will pair" not in could_not.reason
    disagreed = V.verdict(fit, reference_kind=V.SPEECH_MASK,
                          witness=W.Witness(False, [(0.0, 0.05)], u"x"))
    assert u"will pair" in disagreed.reason
    assert u"--force" in could_not.reason and u"--force" in disagreed.reason


def test_anything_raised_reading_the_audio_is_a_refusal_not_a_crash():
    class Odd(FakeSpeech):
        def speech_onsets(self, video, duration):
            raise MemoryError("audio too long for memory")
    ref, why = PIPE.speech_reference(u"/x/v.mkv", RUNTIME, speech=Odd())
    assert ref is None and u"MemoryError" in why


def test_force_writes_a_pair_the_witness_refused_and_says_so(episode,
                                                           tmp_path):
    wrong = _write(tmp_path / u"Other S01E18.ja.srt",
                   _srt([t - SHIFT for t in VIDEO_STARTS], OTHER_LINES))
    # ⚠ A suffixed COPY: the right subtitle already holds the video's name,
    # and a forced write never destroys a file the run did not account for.
    r = _sync(episode, FakeSpeech(), subtitle=wrong, write=True, force=True,
              suffix=u"_rt", trash_root=str(tmp_path / u"trash"))[0]
    assert r.outcome == V.REFUSED and r.forced
    assert r.output_path and os.path.isfile(r.output_path)
