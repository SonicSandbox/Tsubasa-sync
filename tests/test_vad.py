# -*- coding: utf-8 -*-
u"""
RUNBOOK B6 on REAL audio -- `12-alignment.md` §8's `test_vad.py`: the Yomi no
Tsugai ep18 set (`video-derived/yomi18/`), through whisper.cpp's ggml Silero
and a whisper model, exactly as `sync(vad=True)` runs them.

  * uncut -> one offset within 0.15 s of the track-derived truth, CONFIDENT
  * cut   -> REFUSED (both AT-X files; shincaps is the one #4's 2.2 accepted)
  * wrong episode -> REFUSED
  * an English subtitle on Japanese speech -> REFUSED, saying it is language
  * audio decoded short of its container -> not measured (RUNBOOK B6's 3%)

⛔ NOT HERMETIC. It needs the corpus AND whisper.cpp with its two models
(`TSUBASA_WHISPER`, `TSUBASA_VAD_MODEL`, `TSUBASA_ASR_MODEL`), and each check
that cannot run SKIPS AND SAYS SO -- it never passes. The first run transcribes
ten windows (~2 minutes on a CPU with the small model); its cache is a temp
directory, so nothing outside the test is written.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tsubasa import formats as F                              # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa import speech as SPEECH                          # noqa: E402
from tsubasa import verdict as V                              # noqa: E402
from tsubasa import witness as W                              # noqa: E402
from tsubasa.align import align, unique_starts                # noqa: E402
from tsubasa.cache import Cache                               # noqa: E402
from tsubasa.paths import corpus_root                         # noqa: E402

#: `track_2.mkv`'s container duration (`yomi18/README.md`), which a real
#: video of this audio would report.
DURATION = 1420.01
#: `12-alignment.md` §8: an uncut pair lands within this of the truth.
TRUTH_TOL = 0.15


def _skip(why):
    pytest.skip(u"SKIPPED, NOT PASSED: %s" % why)


@pytest.fixture(scope="module")
def yomi():
    try:
        root = os.path.join(str(corpus_root()), u"video-derived", u"yomi18")
    except Exception as exc:
        _skip(u"no corpus (%s)" % exc)
    audio = os.path.join(root, u"audio16k.opus")
    if not os.path.isfile(audio):
        _skip(u"no %s" % audio)
    return root


@pytest.fixture(scope="module")
def speech_cache(tmp_path_factory):
    u"""The speech products cached in a temp directory for this module only."""
    cache = Cache(root=tmp_path_factory.mktemp(u"speech-cache"))
    real = SPEECH._cache
    SPEECH._cache = lambda: cache
    yield cache
    SPEECH._cache = real


def _need(asr):
    why = SPEECH.missing_reason(SPEECH.locate(), need_asr=asr)
    if why:
        _skip(why)


@pytest.fixture(scope="module")
def reference(yomi, speech_cache):
    _need(asr=False)
    ref, why = PIPE.speech_reference(os.path.join(yomi, u"audio16k.opus"),
                                     DURATION)
    assert ref is not None, why
    return ref


def _cues(path):
    parsed = F.read_file(path)
    assert parsed.ok, parsed.reason
    return parsed.cues


def _truth(yomi, name):
    u"""The subtitle's offset against the video's OWN track, cue-vs-cue --
    measured here, never pinned."""
    own = [c.start for c in _cues(os.path.join(yomi, u"track_2.ass"))]
    sub = [c.start for c in _cues(os.path.join(yomi, name))]
    fit = align(unique_starts(own), unique_starts(sub), DURATION)
    assert not fit.is_cut
    return fit.segments[0][1]


def _timing(yomi, reference, name):
    u"""`measure()` with the witness held back: the timing's own answer."""
    keep = reference.hearing
    reference.hearing = None
    try:
        m = PIPE.measure(os.path.join(yomi, u"audio16k.opus"),
                         os.path.join(yomi, name), reference)
    finally:
        reference.hearing = keep
    return m.fit


# ===========================================================================
# timing alone -- needs the VAD model only
# ===========================================================================

@pytest.mark.parametrize("name", [u"track_2.ass", u"abema.streaming.ja.srt",
                                  u"netflix.streaming.ja.srt"])
def test_an_uncut_subtitle_lands_on_its_truth(yomi, reference, name):
    fit = _timing(yomi, reference, name)
    assert V.mask_would_accept(fit), (fit.excess, fit.failing)
    got, truth = fit.segments[0][1], _truth(yomi, name)
    assert abs(got - truth) <= TRUTH_TOL, (got, truth)


@pytest.mark.parametrize("name", [u"nanakoraws.atx.cut.srt",
                                  u"shincaps.atx.cut.srt"])
def test_a_broadcast_cut_is_refused_on_timing(yomi, reference, name):
    u"""🚨 shincaps HOLDS THROUGHOUT on this segmenter (2.34x): only the band
    refuses it. #4's accept line, 2.2, wrote it with its opening 3:42 out."""
    fit = _timing(yomi, reference, name)
    assert len(fit.segments) == 1
    assert not V.mask_would_accept(fit), fit.excess
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK,
                  witness=W.Witness(True, [], u""))
    assert v.outcome == V.REFUSED


def test_the_wrong_episode_is_refused_on_timing(yomi, reference):
    fit = _timing(yomi, reference, u"wrong-episode.s01e15.srt")
    assert not V.mask_would_accept(fit)


def test_audio_short_of_its_container_is_not_measured(speech_cache):
    u"""A real slice: Probe F's Naruto 113 audio is 379 s of a 1,388 s DVD
    episode (its `probe.json`)."""
    _need(asr=False)
    folder = os.path.join(str(corpus_root()), u"video-derived",
                          u"(SB-RAW)NARUTO 113 (R2DVD 960x728 x264 AC3)")
    if not os.path.isdir(folder):
        _skip(u"no %s" % folder)
    with open(os.path.join(folder, u"probe.json")) as fh:
        duration = float(json.load(fh)["format"]["duration"])
    ref, why = PIPE.speech_reference(os.path.join(folder, u"audio16k.opus"),
                                     duration)
    assert ref is None and u"short" in why, why


# ===========================================================================
# the text witness -- needs the whisper model too
# ===========================================================================

@pytest.fixture(scope="module")
def heard(yomi, reference):
    _need(asr=True)
    return reference.hearing()


@pytest.mark.parametrize("name", [u"abema.streaming.ja.srt",
                                  u"netflix.streaming.ja.srt"])
def test_a_japanese_subtitle_is_confirmed_by_what_is_said(yomi, reference,
                                                          heard, name):
    fit = _timing(yomi, reference, name)
    w = W.check(heard, _cues(os.path.join(yomi, name)), fit.segments[0][1])
    assert w.passed, w.summary()
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK, witness=w)
    assert (v.outcome, v.word) == (V.CONFIDENT, u"fair")


def test_the_wrong_episode_is_refused_even_at_the_right_offset(yomi, reference,
                                                              heard):
    u"""⭐ The hardest case for the witness: the wrong episode's lines read at
    the RIGHT pair's offset, so the timing cannot help it."""
    right = _timing(yomi, reference, u"abema.streaming.ja.srt")
    w = W.check(heard, _cues(os.path.join(yomi, u"wrong-episode.s01e15.srt")),
                right.segments[0][1])
    assert w.available and not w.passed, w.summary()


def test_an_english_subtitle_on_japanese_speech_says_it_is_the_language(
        yomi, reference, heard):
    fit = _timing(yomi, reference, u"track_2.ass")
    w = W.check(heard, _cues(os.path.join(yomi, u"track_2.ass")),
                fit.segments[0][1])
    assert not w.available and u"own language" in w.reason
    v = V.verdict(fit, reference_kind=V.SPEECH_MASK, witness=w)
    assert v.outcome == V.REFUSED


def test_the_installed_whisper_cpp_reads_back_as_the_proven_layout():
    u"""⭐ The one check that proves the struct layout against a REAL library:
    `test_speech.py`'s builds the defaults through our own structs, so it can
    name a shifted field but cannot discover one."""
    _need(asr=False)
    eng, _loc = SPEECH.engine()
    assert eng.version in SPEECH.PROVEN_VERSIONS
    assert SPEECH._layout_problems(eng.vad_defaults, eng.full_defaults) == []
