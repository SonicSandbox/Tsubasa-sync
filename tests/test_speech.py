# -*- coding: utf-8 -*-
u"""
RUNBOOK B6 -- the speech path: a reference read from the audio when a video has
no subtitle track, and the text witness that has to agree before anything is
written.

Media-free. The speech module is INJECTED (`sync(speech=...)`, the same kind of
seam as `reader=`), so every rule the pipeline and the verdict apply to a
speech mask is driven here without whisper.cpp; `speech.py`'s own C-layout
check is driven on structs built in memory. What this suite CANNOT cover --
whether Silero and whisper hear what they should on real audio -- is
`12-alignment.md` §5b's measurement, and it is stated there with its population.

⚠ The subtitle text is JAPANESE and different on every line. An ASCII fixture
cannot test `normalise()`'s "letters in any script", and one repeated template
line would make every window match every other -- the witness would pass a
wrong episode and this suite would call that correct.
"""
import os
import random
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import cues as CUES                              # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa import speech as SPEECH                          # noqa: E402
from tsubasa import verdict as V                              # noqa: E402
from tsubasa import witness as W                              # noqa: E402
from tsubasa.arbitrate import Cluster                         # noqa: E402

from test_pipeline import (CUE_STARTS, RUNTIME, WRONG_STARTS,  # noqa: E402
                           _reader, _stamp, _track)
from test_verdict import make_fit                             # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

_KANA = (u"あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめも"
         u"やゆよらりるれろわをん漢字科学石神千空")


def _lines(n, seed):
    rng = random.Random(seed)
    return [u"".join(rng.choice(_KANA) for _ in range(14)) for _ in range(n)]


LINES = _lines(len(CUE_STARTS), seed=4)
OTHER_LINES = _lines(len(CUE_STARTS), seed=5)     # "a different episode"

#: The subtitle is this late; the right answer is -LATE.
LATE = 2.0


def _srt_text(starts, lines):
    out = []
    for i, (t, line) in enumerate(zip(starts, lines), 1):
        out.append(u"%d\n%s --> %s\n%s\n" % (i, _stamp(t), _stamp(t + 2.0),
                                             line))
    return u"\n".join(out)


def _write(path, text):
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return str(path)


def _heard(starts, lines):
    u"""What a perfect transcriber would hear in each witness window."""
    out = []
    for w0 in W.windows(RUNTIME):
        out.append((w0, u" ".join(l for t, l in zip(starts, lines)
                                  if w0 <= t <= w0 + W.WINDOW_S)))
    return out


class FakeSpeech(object):
    u"""The four names `pipeline.speech_reference` reads, and call counts."""

    SpeechUnavailable = SPEECH.SpeechUnavailable
    ONSET_LAG = SPEECH.ONSET_LAG

    def __init__(self, onsets=CUE_STARTS, heard=None, onsets_fail=None,
                 heard_fail=None):
        # Onsets TRAIL the line by ONSET_LAG, as measured on real audio.
        self.onsets = [(t + self.ONSET_LAG, t + self.ONSET_LAG + 1.5)
                       for t in onsets]
        self.heard = _heard(CUE_STARTS, LINES) if heard is None else heard
        self.onsets_fail = onsets_fail
        self.heard_fail = heard_fail
        self.onset_calls = 0
        self.heard_calls = 0

    def speech_onsets(self, video_path, duration):
        self.onset_calls += 1
        if self.onsets_fail:
            raise SPEECH.SpeechUnavailable(self.onsets_fail)
        return list(self.onsets)

    def heard_windows(self, video_path, duration):
        self.heard_calls += 1
        if self.heard_fail:
            raise SPEECH.SpeechUnavailable(self.heard_fail)
        return list(self.heard)

    def describe(self):
        return u"speech path: fake"


@pytest.fixture()
def pair(tmp_path):
    video = _write(tmp_path / u"石神 S01E04.mkv", u"not a real video")
    sub = _write(tmp_path / u"石神 S01E04.ja.srt",
                 _srt_text([t + LATE for t in CUE_STARTS], LINES))
    return video, sub


def _run(pair, speech, tracks=(), vad=True, sub=None):
    video, subtitle = pair
    return PIPE.sync([(video, sub or subtitle)], reader=_reader(list(tracks)),
                     vad=vad, speech=speech, results=False)


# ===========================================================================
# 1. THE WITNESS -- pure string arithmetic
# ===========================================================================

def test_normalise_keeps_letters_in_ANY_script_and_drops_markup():
    assert W.normalise(u"{\\an8}千空、科学の\\N力だ！ 100億") == u"千空科学の力だ100億"
    assert W.normalise(u"<i>Hello</i>, world") == u"Helloworld"


def test_containment_is_what_was_HEARD_that_the_subtitle_also_says():
    u"""The subtitle may say MORE (speaker names, a line whisper missed);
    that is not evidence against it."""
    assert W.containment(u"科学の力", u"千空科学の力だ") == 1.0
    assert W.containment(u"科学の力", u"まったく別の台詞") == 0.0
    assert W.containment(u"", u"千空") == 0.0


def test_the_right_subtitle_at_the_right_offset_passes():
    cues = [CUES.Cue(t + LATE, t + LATE + 2, l) for t, l in zip(CUE_STARTS, LINES)]
    got = W.check(_heard(CUE_STARTS, LINES), cues, -LATE)
    assert got.passed, got.reason
    assert len(got.scored) >= W.MIN_SCORED


def test_the_same_subtitle_at_a_WRONG_offset_fails_and_says_where():
    u"""The witness checks the subtitle where the timing would PUT it."""
    cues = [CUES.Cue(t + LATE, t + LATE + 2, l) for t, l in zip(CUE_STARTS, LINES)]
    got = W.check(_heard(CUE_STARTS, LINES), cues, -LATE + 40.0)
    assert not got.passed
    assert u"does not match" in got.reason and u":" in got.reason


def test_a_different_episode_fails_even_with_identical_timing():
    cues = [CUES.Cue(t, t + 2, l) for t, l in zip(CUE_STARTS, OTHER_LINES)]
    got = W.check(_heard(CUE_STARTS, LINES), cues, 0.0)
    assert not got.passed
    assert all(v < W.MATCH for _t, v in got.scored)


def test_speech_with_no_subtitle_line_is_NOT_a_mismatch():
    u"""An opening song, a preview: the audio speaks, the subtitle is silent.
    Those windows are `no-sub` and neither help nor hurt."""
    heard = _heard(CUE_STARTS, LINES)
    heard[0] = (heard[0][0], u"ラララ主題歌の歌詞がここに流れる")
    first_window_end = heard[0][0] + W.WINDOW_S + W.MARGIN_S
    cues = [CUES.Cue(t, t + 2, l) for t, l in zip(CUE_STARTS, LINES)
            if t > first_window_end]
    got = W.check(heard, cues, 0.0)
    assert got.passed, got.reason
    assert got.rows[0][1] == W.NO_SUB


def test_too_few_comparable_windows_is_not_a_pass():
    u"""A short or mostly-musical video: the witness has not seen enough of
    it to vouch for it, so it says so instead of passing on two windows."""
    heard = [(t, u"") for t, _ in _heard(CUE_STARTS, LINES)]
    heard[2] = _heard(CUE_STARTS, LINES)[2]
    cues = [CUES.Cue(t, t + 2, l) for t, l in zip(CUE_STARTS, LINES)]
    got = W.check(heard, cues, 0.0)
    assert not got.passed
    assert u"only 1 window" in got.reason


def test_the_match_thresholds_sit_in_their_measured_empty_bands():
    u"""`witness.py`, 2026-11-14: per window, wrong max 0.20 / right min 0.26;
    per pair, wrong 0.0 / right >= 7 of 8."""
    assert 0.20 < W.MATCH < 0.26
    assert 0.0 < W.MIN_SHARE < 7 / 8.0


def test_ONE_misheard_window_does_not_refuse_a_right_pair_and_is_NAMED():
    u"""🚨 Gachiakuta 02 at 5:47: shouting, whisper heard `ブーブー言っmeme`,
    26% of it in the right subtitle. The every-window rule refused that
    correct pair."""
    heard = _heard(CUE_STARTS, LINES)
    heard[3] = (heard[3][0], u"ブーブー言っmeme今後お前らもいい加減全だよ")
    cues = [CUES.Cue(t, t + 2, l) for t, l in zip(CUE_STARTS, LINES)]
    got = W.check(heard, cues, 0.0)
    assert got.passed, got.reason
    assert u"did not match at" in got.summary()


def test_a_QUARTER_of_the_windows_not_matching_is_a_refusal():
    heard = _heard(CUE_STARTS, LINES)
    for i in (1, 4, 7):
        heard[i] = (heard[i][0], OTHER_LINES[i] + OTHER_LINES[i + 1])
    cues = [CUES.Cue(t, t + 2, l) for t, l in zip(CUE_STARTS, LINES)]
    got = W.check(heard, cues, 0.0)
    assert not got.passed
    assert u"3 of 10 windows" in got.reason


# ===========================================================================
# 2. THE VERDICT ON A SPEECH MASK
# ===========================================================================

#: `12-alignment.md` §5b's population. ⛔ A constant moved outside it is a
#: threshold set by taste, and this is what says so.
RIGHT_MIN, WRONG_MAX = 2.71, 1.73


def _passing():
    return W.Witness(True, [(0.0, 0.9)] * 5, u"")


def test_the_mask_band_sits_inside_the_measured_empty_band():
    refuse_below, accept_at = V.MASK_BAND
    assert WRONG_MAX < refuse_below < accept_at < RIGHT_MIN


def test_timing_AND_text_both_passing_is_confident_but_only_FAIR():
    u"""`strong` and `locked` are floors on the CUE-VS-CUE scale."""
    v = V.verdict(make_fit(excess=3.6), reference_kind=V.SPEECH_MASK,
                  witness=_passing())
    assert v.outcome == V.CONFIDENT
    assert v.word == u"fair"
    assert v.reference_kind == V.SPEECH_MASK


def test_timing_alone_is_NOT_enough_on_a_mask():
    v = V.verdict(make_fit(excess=3.6), reference_kind=V.SPEECH_MASK)
    assert v.outcome == V.REFUSED
    assert u"no text check" in v.reason


def test_a_failed_text_check_refuses_and_carries_its_reason():
    failed = W.Witness(False, [], u"what is said in the video does not match "
                                  u"the subtitle at 4:12 (3%)")
    v = V.verdict(make_fit(excess=3.6), reference_kind=V.SPEECH_MASK,
                  witness=failed)
    assert v.outcome == V.REFUSED
    assert u"4:12" in v.reason
    assert v.band == u"escalate"


def test_a_text_check_that_could_not_run_refuses_rather_than_waving_through():
    v = V.verdict(make_fit(excess=3.6), reference_kind=V.SPEECH_MASK,
                  witness=W.Witness.unavailable(u"no whisper model was found"))
    assert v.outcome == V.REFUSED
    assert u"could not run" in v.reason and u"whisper model" in v.reason


@pytest.mark.parametrize("excess", [1.5, 1.9, 2.1])
def test_below_the_mask_accept_line_a_passing_text_check_cannot_lift_it(excess):
    v = V.verdict(make_fit(excess=excess), reference_kind=V.SPEECH_MASK,
                  witness=_passing())
    assert v.outcome == V.REFUSED


def test_a_coherent_cluster_does_not_lift_a_mask_pair_either():
    u"""Coherence was measured on cue-vs-cue offsets; nothing measured it on a
    mask (`verdict._mask_band_of`)."""
    from test_verdict import AGREEING
    # ⭐ Positive control first: the SAME cluster lifts a cue-vs-cue pair, so
    # the refusal below is the mask rule and not a cluster that lifts nothing.
    assert V.verdict(make_fit(excess=2.0),
                     cluster=Cluster(AGREEING)).outcome == V.CONFIDENT
    v = V.verdict(make_fit(excess=2.0), cluster=Cluster(AGREEING),
                  reference_kind=V.SPEECH_MASK, witness=_passing())
    assert v.outcome == V.REFUSED


@pytest.mark.parametrize("excess", [1.2, 1.74, 2.19, 2.2, 2.21, 3.0, 4.5])
def test_the_pipelines_cost_guard_agrees_with_the_verdict(excess):
    u"""`mask_would_accept` decides whether a transcription is paid for. If it
    disagreed with `verdict()`, a pair could be refused for want of a witness
    nobody ran -- or a witness run for a pair already refused."""
    fit = make_fit(excess=excess)
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK, witness=_passing())
    assert V.mask_would_accept(fit) == (v.outcome == V.CONFIDENT)


def test_a_mask_pair_that_does_not_hold_throughout_is_refused_first():
    fit = make_fit(excess=3.6, failing=[(0.0, 40, 0.1, 10.0, 0.5)])
    assert not V.mask_would_accept(fit)
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK, witness=_passing())
    assert v.outcome == V.REFUSED


# ===========================================================================
# 3. THE PIPELINE -- the speech module injected
# ===========================================================================

def test_without_vad_a_trackless_video_is_refused_and_names_the_switch(pair):
    fake = FakeSpeech()
    got = _run(pair, fake, vad=False)
    assert got[0].outcome == V.ERROR
    assert u"--vad" in got[0].reason
    assert fake.onset_calls == 0


def test_with_vad_the_right_subtitle_is_confident_at_its_own_offset(pair):
    fake = FakeSpeech()
    got = _run(pair, fake)
    r = got[0]
    assert r.outcome == V.CONFIDENT, r.reason
    assert r.reference_kind == V.SPEECH_MASK
    assert r.verdict_word == u"fair"
    # ⭐ The onset lag is taken out: the subtitle's OWN offset, not +0.27.
    assert len(r.segments) == 1
    assert abs(r.segments[0][1] - (-LATE)) <= 0.05, r.segments
    assert any(n.startswith(u"text check:") for n in r.notes), r.notes
    assert fake.heard_calls == 1


def test_a_different_episode_with_the_same_rhythm_is_refused_by_the_TEXT(
        tmp_path, pair):
    u"""The hardest wrong pair there is: identical timing, other words. Only
    the witness can refuse it -- and it must."""
    other = _write(tmp_path / u"石神 S01E05.ja.srt",
                   _srt_text([t + LATE for t in CUE_STARTS], OTHER_LINES))
    got = _run(pair, FakeSpeech(), sub=other)
    assert got[0].outcome == V.REFUSED
    assert u"does not match" in got[0].reason


def test_wrong_timing_is_refused_WITHOUT_paying_for_a_transcription(
        tmp_path, pair):
    wrong = _write(tmp_path / u"石神 S01E06.ja.srt",
                   _srt_text(WRONG_STARTS, OTHER_LINES))
    fake = FakeSpeech()
    got = _run(pair, fake, sub=wrong)
    assert got[0].outcome != V.CONFIDENT
    assert fake.heard_calls == 0


def test_no_whisper_model_means_refused_with_the_reason_not_confident(pair):
    fake = FakeSpeech(heard_fail=u"a whisper model (ggml-*.bin) for the text "
                                 u"check -- set TSUBASA_ASR_MODEL")
    got = _run(pair, fake)
    assert got[0].outcome == V.REFUSED
    assert u"TSUBASA_ASR_MODEL" in got[0].reason


def test_audio_that_cannot_be_measured_is_an_ERROR_with_both_reasons(pair):
    fake = FakeSpeech(onsets_fail=u"ffmpeg could not decode the audio")
    got = _run(pair, fake)
    assert got[0].outcome == V.ERROR
    assert u"no subtitle track" in got[0].reason
    assert u"ffmpeg could not decode the audio" in got[0].reason


def test_too_little_speech_is_an_ERROR_not_a_guess(pair):
    got = _run(pair, FakeSpeech(onsets=CUE_STARTS[:3]))
    assert got[0].outcome == V.ERROR
    assert u"only 3 stretches" in got[0].reason


def test_a_video_WITH_a_track_never_touches_the_speech_path(pair):
    fake = FakeSpeech()
    got = _run(pair, fake, tracks=[_track(0, CUE_STARTS)])
    assert got[0].reference_kind == V.TEXT_TRACK
    assert fake.onset_calls == 0 and fake.heard_calls == 0


def test_a_cut_subtitle_is_ONE_offset_and_refused_never_split(tmp_path, pair):
    u"""`12-alignment.md` §5 ruling 1: the mask path fits one offset and
    refuses when the bucket walk fails. Split detection on a mask is
    evolution -- this fails if `max_segments=1` is dropped."""
    starts = [t + LATE if t < 400 else t + LATE + 12.0 for t in CUE_STARTS]
    cut = _write(tmp_path / u"石神 S01E04.cut.ja.srt", _srt_text(starts, LINES))
    got = _run(pair, FakeSpeech(), sub=cut)
    assert got[0].outcome != V.CONFIDENT
    assert len(got[0].segments) <= 1


def test_the_run_says_once_what_the_speech_path_will_use(pair):
    got = _run(pair, FakeSpeech())
    assert u"speech path: fake" in got.notes


# ===========================================================================
# 4. speech.py -- finding whisper.cpp, and the C layout check
# ===========================================================================

@pytest.fixture()
def clean_location(monkeypatch):
    for env in (SPEECH.ENV_LIBRARY, SPEECH.ENV_VAD, SPEECH.ENV_ASR):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(SPEECH, "_speech_dir", lambda: u"/nowhere/speech")
    yield
    SPEECH.set_location()


def _touch(path):
    with open(str(path), "wb") as fh:
        fh.write(b"x")
    return str(path)


def test_nothing_found_names_every_switch_and_downloads_nothing(clean_location):
    why = SPEECH.missing_reason(SPEECH.locate(), need_asr=True)
    for name in (SPEECH.ENV_LIBRARY, SPEECH.ENV_VAD, SPEECH.ENV_ASR):
        assert name in why
    assert u"Nothing is downloaded" in why


def test_a_folder_with_the_library_and_one_model_of_each_kind_resolves(
        tmp_path, clean_location):
    lib = _touch(tmp_path / SPEECH._library_names()[0])
    vad = _touch(tmp_path / u"ggml-silero-v6.2.0.bin")
    asr = _touch(tmp_path / u"ggml-large-v3-q5_0.bin")
    SPEECH.set_location(library=str(tmp_path))
    loc = SPEECH.locate()
    assert (loc.library, loc.vad_model, loc.asr_model) == (lib, vad, asr)
    assert SPEECH.missing_reason(loc, need_asr=True) is None


def test_TWO_whisper_models_are_not_resolved_by_picking_one(
        tmp_path, clean_location):
    u"""Which model measured the witness is part of what it claims."""
    _touch(tmp_path / SPEECH._library_names()[0])
    _touch(tmp_path / u"ggml-silero-v6.2.0.bin")
    _touch(tmp_path / u"ggml-tiny.bin")
    _touch(tmp_path / u"ggml-large-v3.bin")
    SPEECH.set_location(library=str(tmp_path))
    loc = SPEECH.locate()
    assert loc.asr_model is None
    assert SPEECH.ENV_ASR in SPEECH.missing_reason(loc, need_asr=True)


def _known_defaults():
    vad = SPEECH._VadParams(0.5, 250, 100, 3.4e38, 30, 0.1)
    full = SPEECH._FullParams()
    full.strategy = 0
    full.entropy_thold, full.logprob_thold = 2.4, -1.0
    full.no_speech_thold = 0.6
    full.greedy.best_of = 5
    full.vad_params = SPEECH._VadParams(0.5, 250, 100, 3.4e38, 30, 0.1)
    full.language = b"en"
    return vad, full


def test_the_layout_check_accepts_the_known_defaults():
    assert SPEECH._layout_problems(*_known_defaults()) == []


@pytest.mark.parametrize("field,value", [
    ("entropy_thold", 0.0), ("no_speech_thold", 2.4), ("language", b"ja")])
def test_the_layout_check_refuses_a_struct_that_reads_differently(field, value):
    u"""A shifted field reads as the wrong number. That is the signal that
    the library's layout is not the one written in `speech.py`."""
    vad, full = _known_defaults()
    setattr(full, field, value)
    bad = SPEECH._layout_problems(vad, full)
    assert bad and field in bad[0]


def test_the_onset_lag_is_the_median_of_its_recorded_population():
    measured = [0.27, 0.23, 0.29, 0.51, 0.52, 0.49, 0.14, 0.23, 0.27]
    assert SPEECH.ONSET_LAG == sorted(measured)[len(measured) // 2]


def test_the_SCAN_path_takes_the_speech_path_too(tmp_path):
    u"""The explicit path and the discovery path thread `vad` separately
    (`_sync_plan` / `_sync_scan`, and `_durations_for` shares their cache)."""
    from tsubasa import api as API
    _write(tmp_path / u"石神 S01E04.mkv", u"not a real video")
    _write(tmp_path / u"石神 S01E04.ja.srt",
           _srt_text([t + LATE for t in CUE_STARTS], LINES))
    got = PIPE.sync(API.scan(str(tmp_path)), reader=_reader([]), vad=True,
                    speech=FakeSpeech(), results=False)
    assert [r.outcome for r in got] == [V.CONFIDENT], [r.reason for r in got]
    assert got[0].reference_kind == V.SPEECH_MASK
