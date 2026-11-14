# -*- coding: utf-8 -*-
u"""
The speech path: a reference for a video with NO subtitle track (RUNBOOK B6).

`00-INDEX.md` Rule 1: *the embedded subtitle track is an ACCELERATOR, never a
dependency.* When it is absent, the reference is read from the audio:

  * **timing** -- Silero VAD speech ONSETS, through whisper.cpp's ggml port of
    Silero (`speech_onsets`). ~2 s per 24-minute episode on a CPU, against ~21 s
    for onnxruntime Silero in `12-alignment.md` §5.
  * **text** -- a whisper model transcribes a few short windows
    (`heard_windows`) for `witness.py`, the mask path's second signal.

🚨 WHISPER'S OWN SEGMENT TIMES ARE NOT A REFERENCE, AND THAT WAS MEASURED, not
assumed (`12-alignment.md` §5b). Dr. Stone Stone Wars 04 against its subtitle:
whisper large-v3 segments 1.21x (no VAD) and 1.90x (with VAD) -- no better than
the WRONG episodes at 1.24-1.53x -- because whisper emits segments back to back
on a ~1 s grid (478 of 594 exactly 2 s long), so a segment start is the end of
the previous one, not a moment anyone started speaking. Silero onsets on the
same pair: 3.54x. ⛔ So transcription is used for WHAT is said, never WHEN.

⛔ NOTHING HERE DOWNLOADS ANYTHING, and nothing is bundled. whisper.cpp and its
models are found where the user or an embedding application put them -- the
same posture as ffmpeg (`container/ffmpeg.py`):

    set_location(library=, vad_model=, asr_model=)   an application's answer
    $TSUBASA_WHISPER      folder holding whisper.dll / libwhisper.so / .dylib
    $TSUBASA_VAD_MODEL    ggml-silero-*.bin
    $TSUBASA_ASR_MODEL    a ggml whisper model (ggml-*.bin), for the text check
    <cache>/speech/       the per-user cache directory, last

🚨 THE C LAYOUT IS CHECKED, NOT TRUSTED. whisper.cpp passes its parameter
structs BY VALUE and their layout changes between releases. The structs below
are whisper.h at v1.8.4; on load, the library's OWN defaults are read back
through them and must come out as the known values (VAD threshold 0.5, 250 ms,
entropy 2.4, language "en", ...). A library whose defaults read differently is
refused by name -- writing a parameter into the wrong bytes is exactly the
confidently wrong answer Rule 2 forbids, one layer down.
"""
import ctypes as C
import glob
import os
import subprocess
import sys
import threading

import numpy as np

from .container import ffmpeg as _ffmpeg

SAMPLE_RATE = 16000

#: 🚨 Seconds the speech ONSET trails the subtitle line it belongs to. Captions
#: are timed to appear as speech starts or a little before; Silero marks the
#: first voiced frame. Measured 2026-11-14 on 9 episodes whose own embedded
#: caption track is the truth (offset 0), Silero onsets as the reference:
#:
#:     Gachiakuta 01-03          +0.27 +0.23 +0.29
#:     Kusuriya S2 01-03         +0.51 +0.52 +0.49
#:     Spy x Family S3 01-03     +0.14 +0.23 +0.27
#:
#: The median is subtracted from every onset, so a fit against the corrected
#: reference reads the subtitle's own offset. ⚠ The residual is per-SHOW --
#: -0.13 to +0.25 s after correction -- and that is stated wherever a mask
#: offset is reported (`12-alignment.md` §5b), not hidden in this number.
ONSET_LAG = 0.27

#: ⛔ RUNBOOK B6: refuse when the decoded audio is short of the container's
#: duration by more than this. A truncated decode makes a reference that ends
#: early, and the bucket walk would read the missing stretch as quiet.
MAX_SHORT_DECODE = 0.03

#: whisper.cpp releases whose struct layout is the one written below.
KNOWN_VERSIONS = (u"1.8.",)

ENV_LIBRARY = "TSUBASA_WHISPER"
ENV_VAD = "TSUBASA_VAD_MODEL"
ENV_ASR = "TSUBASA_ASR_MODEL"

_OVERRIDE = {"library": None, "vad_model": None, "asr_model": None}


class SpeechUnavailable(Exception):
    u"""The speech path cannot run here. Carries the sentence a person can act
    on: what is missing, and where it was looked for."""


# ---------------------------------------------------------------------------
# where whisper.cpp and its models are
# ---------------------------------------------------------------------------

def set_location(library=None, vad_model=None, asr_model=None):
    u"""An embedding application's answer to *where is whisper.cpp?*. ⭐ Ahead
    of every other rung, for the same reason as `ffmpeg.set_location`: an
    application that said where it is has answered the question."""
    _OVERRIDE.update(library=library, vad_model=vad_model,
                     asr_model=asr_model)


def _speech_dir():
    from .paths import cache_root
    return os.path.join(str(cache_root()), "speech")


def _library_names():
    if sys.platform == "win32":
        return ("whisper.dll",)
    if sys.platform == "darwin":
        return ("libwhisper.dylib",)
    return ("libwhisper.so", "libwhisper.so.1")


class Location(object):
    __slots__ = ("library", "vad_model", "asr_model", "searched")

    def __init__(self, library, vad_model, asr_model, searched):
        self.library = library
        self.vad_model = vad_model
        self.asr_model = asr_model
        self.searched = searched


def locate():
    u"""Find whisper.cpp and its two models. -> `Location` (fields may be None)

    ⛔ A folder holding TWO candidate models of one kind is not resolved by
    picking one: the answer is `None`, and the reason names both. Which model
    measured the witness is part of the claim it makes."""
    dirs = []
    for d in (_OVERRIDE["library"], os.environ.get(ENV_LIBRARY), _speech_dir()):
        if d and d not in dirs:
            dirs.append(d)
    library = None
    for d in dirs:
        if os.path.isfile(d) and os.path.basename(d).lower().startswith(
                ("whisper", "libwhisper")):
            library = d
            break
        for name in _library_names():
            if os.path.isfile(os.path.join(d, name)):
                library = os.path.join(d, name)
                break
        if library:
            break

    model_dirs = list(dirs)
    if library and os.path.dirname(library) not in model_dirs:
        model_dirs.insert(0, os.path.dirname(library))

    def pick(explicit, env, want_vad):
        given = explicit or os.environ.get(env)
        if given:
            return given if os.path.isfile(given) else None
        found = []
        for d in model_dirs:
            for p in sorted(glob.glob(os.path.join(d, "ggml-*.bin"))):
                is_vad = u"silero" in os.path.basename(p).lower()
                if is_vad == want_vad and p not in found:
                    found.append(p)
        return found[0] if len(found) == 1 else None

    return Location(library,
                    pick(_OVERRIDE["vad_model"], ENV_VAD, True),
                    pick(_OVERRIDE["asr_model"], ENV_ASR, False),
                    dirs)


def missing_reason(loc, need_asr=False):
    u"""The sentence for whatever `locate()` did not find, or None."""
    gaps = []
    if not loc.library:
        gaps.append(u"the whisper.cpp library (%s) -- set %s to the folder "
                    u"holding it" % (u" / ".join(_library_names()),
                                     ENV_LIBRARY))
    if not loc.vad_model:
        gaps.append(u"the Silero VAD model (ggml-silero-*.bin) -- set %s to "
                    u"its path" % ENV_VAD)
    if need_asr and not loc.asr_model:
        gaps.append(u"a whisper model (ggml-*.bin) for the text check -- set "
                    u"%s to its path" % ENV_ASR)
    if not gaps:
        return None
    return (u"the speech path needs %s. Looked in: %s. Nothing is downloaded."
            % (u"; and ".join(gaps), u", ".join(loc.searched) or u"(nowhere)"))


# ---------------------------------------------------------------------------
# whisper.h v1.8.4, the parts used here
# ---------------------------------------------------------------------------

class _VadParams(C.Structure):
    _fields_ = [("threshold", C.c_float),
                ("min_speech_duration_ms", C.c_int),
                ("min_silence_duration_ms", C.c_int),
                ("max_speech_duration_s", C.c_float),
                ("speech_pad_ms", C.c_int),
                ("samples_overlap", C.c_float)]


class _VadContextParams(C.Structure):
    _fields_ = [("n_threads", C.c_int), ("use_gpu", C.c_bool),
                ("gpu_device", C.c_int)]


class _Aheads(C.Structure):
    _fields_ = [("n_heads", C.c_size_t), ("heads", C.c_void_p)]


class _ContextParams(C.Structure):
    _fields_ = [("use_gpu", C.c_bool), ("flash_attn", C.c_bool),
                ("gpu_device", C.c_int), ("dtw_token_timestamps", C.c_bool),
                ("dtw_aheads_preset", C.c_int), ("dtw_n_top", C.c_int),
                ("dtw_aheads", _Aheads), ("dtw_mem_size", C.c_size_t)]


class _Greedy(C.Structure):
    _fields_ = [("best_of", C.c_int)]


class _Beam(C.Structure):
    _fields_ = [("beam_size", C.c_int), ("patience", C.c_float)]


class _FullParams(C.Structure):
    _fields_ = [
        ("strategy", C.c_int), ("n_threads", C.c_int),
        ("n_max_text_ctx", C.c_int), ("offset_ms", C.c_int),
        ("duration_ms", C.c_int),
        ("translate", C.c_bool), ("no_context", C.c_bool),
        ("no_timestamps", C.c_bool), ("single_segment", C.c_bool),
        ("print_special", C.c_bool), ("print_progress", C.c_bool),
        ("print_realtime", C.c_bool), ("print_timestamps", C.c_bool),
        ("token_timestamps", C.c_bool), ("thold_pt", C.c_float),
        ("thold_ptsum", C.c_float), ("max_len", C.c_int),
        ("split_on_word", C.c_bool), ("max_tokens", C.c_int),
        ("debug_mode", C.c_bool), ("audio_ctx", C.c_int),
        ("tdrz_enable", C.c_bool),
        ("suppress_regex", C.c_char_p), ("initial_prompt", C.c_char_p),
        ("carry_initial_prompt", C.c_bool),
        ("prompt_tokens", C.c_void_p), ("prompt_n_tokens", C.c_int),
        ("language", C.c_char_p), ("detect_language", C.c_bool),
        ("suppress_blank", C.c_bool), ("suppress_nst", C.c_bool),
        ("temperature", C.c_float), ("max_initial_ts", C.c_float),
        ("length_penalty", C.c_float),
        ("temperature_inc", C.c_float), ("entropy_thold", C.c_float),
        ("logprob_thold", C.c_float), ("no_speech_thold", C.c_float),
        ("greedy", _Greedy), ("beam_search", _Beam),
        ("new_segment_callback", C.c_void_p),
        ("new_segment_callback_user_data", C.c_void_p),
        ("progress_callback", C.c_void_p),
        ("progress_callback_user_data", C.c_void_p),
        ("encoder_begin_callback", C.c_void_p),
        ("encoder_begin_callback_user_data", C.c_void_p),
        ("abort_callback", C.c_void_p),
        ("abort_callback_user_data", C.c_void_p),
        ("logits_filter_callback", C.c_void_p),
        ("logits_filter_callback_user_data", C.c_void_p),
        ("grammar_rules", C.c_void_p), ("n_grammar_rules", C.c_size_t),
        ("i_start_rule", C.c_size_t), ("grammar_penalty", C.c_float),
        ("vad", C.c_bool), ("vad_model_path", C.c_char_p),
        ("vad_params", _VadParams),
    ]


_LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p, C.c_void_p)


@_LOG_CB
def _quiet(_level, _text, _user):
    u"""whisper.cpp and ggml log every model load to stderr. Under `--json`
    stderr is the run summary, so the noise is dropped here."""


def _close(a, b, tol=1e-4):
    return abs(float(a) - float(b)) <= tol


def _layout_problems(vad, full):
    u"""Read the library's defaults back through OUR structs. -> [str]

    Each line is a field that came out wrong, which means the layout is not
    the one written above."""
    want = [("vad.threshold", vad.threshold, 0.5),
            ("vad.min_speech_duration_ms", vad.min_speech_duration_ms, 250),
            ("vad.min_silence_duration_ms", vad.min_silence_duration_ms, 100),
            ("vad.speech_pad_ms", vad.speech_pad_ms, 30),
            ("full.strategy", full.strategy, 0),
            ("full.entropy_thold", full.entropy_thold, 2.4),
            ("full.logprob_thold", full.logprob_thold, -1.0),
            ("full.no_speech_thold", full.no_speech_thold, 0.6),
            ("full.greedy.best_of", full.greedy.best_of, 5),
            ("full.vad_params.threshold", full.vad_params.threshold, 0.5),
            ("full.vad_params.min_speech_duration_ms",
             full.vad_params.min_speech_duration_ms, 250)]
    bad = [u"%s=%r (expected %r)" % (n, got, exp)
           for n, got, exp in want if not _close(got, exp)]
    if full.language != b"en":
        bad.append(u"full.language=%r (expected 'en')" % (full.language,))
    return bad


class _Engine(object):
    u"""whisper.cpp, loaded once per process. ⚠ One whisper context at a time:
    `whisper_full` is not re-entrant on a context, so calls are serialised."""

    def __init__(self, library):
        folder = os.path.dirname(os.path.abspath(library))
        if sys.platform == "win32":
            os.add_dll_directory(folder)
        # ⚠ ggml loads its compute backends (CPU, Vulkan, CUDA ...) as separate
        # libraries, and only from the EXECUTABLE's folder unless told. Without
        # this a frozen tsubasa.exe aborts inside ggml with GGML_ASSERT(device)
        # -- measured, not imagined: it is the first thing that happened.
        # ⚠ The log hook lives in ggml-BASE, which every backend shares; set on
        # ggml.dll it left the Vulkan banner on stderr, which under `--json` is
        # where the run summary goes.
        for name in ("ggml-base.dll", "libggml-base.so", "libggml-base.dylib"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                base = C.CDLL(path)
                if hasattr(base, "ggml_log_set"):
                    base.ggml_log_set(_quiet, None)
                break
        for name in ("ggml.dll", "libggml.so", "libggml.dylib"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                ggml = C.CDLL(path)
                if hasattr(ggml, "ggml_backend_load_all_from_path"):
                    ggml.ggml_backend_load_all_from_path(
                        folder.encode(sys.getfilesystemencoding()))
                break
        try:
            w = C.CDLL(library)
        except OSError as exc:
            raise SpeechUnavailable(u"whisper.cpp at %s could not be loaded: "
                                    u"%s" % (library, exc))
        self.lib = w
        self.library = library
        self.lock = threading.Lock()
        self._asr = {}

        w.whisper_version.restype = C.c_char_p
        self.version = (w.whisper_version() or b"").decode("ascii", "replace")
        if not self.version.startswith(KNOWN_VERSIONS):
            raise SpeechUnavailable(
                u"whisper.cpp %s at %s is a release tsubasa has not checked "
                u"the parameter layout of (known: %s). Passing its structs "
                u"blind could write a setting into the wrong bytes, so it is "
                u"not used." % (self.version, library,
                                u", ".join(v + u"x" for v in KNOWN_VERSIONS)))
        if hasattr(w, "whisper_log_set"):
            w.whisper_log_set(_quiet, None)

        w.whisper_vad_default_params.restype = _VadParams
        w.whisper_vad_default_context_params.restype = _VadContextParams
        w.whisper_vad_init_from_file_with_params.restype = C.c_void_p
        w.whisper_vad_init_from_file_with_params.argtypes = [
            C.c_char_p, _VadContextParams]
        w.whisper_vad_segments_from_samples.restype = C.c_void_p
        w.whisper_vad_segments_from_samples.argtypes = [
            C.c_void_p, _VadParams, C.POINTER(C.c_float), C.c_int]
        w.whisper_vad_segments_n_segments.argtypes = [C.c_void_p]
        for f in ("whisper_vad_segments_get_segment_t0",
                  "whisper_vad_segments_get_segment_t1"):
            getattr(w, f).restype = C.c_float
            getattr(w, f).argtypes = [C.c_void_p, C.c_int]
        w.whisper_vad_free_segments.argtypes = [C.c_void_p]
        w.whisper_vad_free.argtypes = [C.c_void_p]

        w.whisper_context_default_params_by_ref.restype = \
            C.POINTER(_ContextParams)
        w.whisper_full_default_params_by_ref.restype = C.POINTER(_FullParams)
        w.whisper_full_default_params_by_ref.argtypes = [C.c_int]
        w.whisper_free_params.argtypes = [C.c_void_p]
        w.whisper_free_context_params.argtypes = [C.c_void_p]
        w.whisper_init_from_file_with_params.restype = C.c_void_p
        w.whisper_init_from_file_with_params.argtypes = [C.c_char_p,
                                                         _ContextParams]
        w.whisper_full.restype = C.c_int
        w.whisper_full.argtypes = [C.c_void_p, _FullParams,
                                   C.POINTER(C.c_float), C.c_int]
        w.whisper_full_n_segments.argtypes = [C.c_void_p]
        w.whisper_full_get_segment_text.restype = C.c_void_p
        w.whisper_full_get_segment_text.argtypes = [C.c_void_p, C.c_int]

        full_p = w.whisper_full_default_params_by_ref(0)
        try:
            self.full_defaults = _FullParams.from_buffer_copy(full_p.contents)
        finally:
            w.whisper_free_params(full_p)
        self.vad_defaults = w.whisper_vad_default_params()
        bad = _layout_problems(self.vad_defaults, self.full_defaults)
        if bad:
            raise SpeechUnavailable(
                u"whisper.cpp %s at %s does not lay out its parameters the way "
                u"tsubasa reads them (%s), so it is not used: a setting written "
                u"into the wrong bytes is a guess, not a measurement."
                % (self.version, library, u"; ".join(bad[:3])))

    # -- timing -----------------------------------------------------------
    def vad_segments(self, model, samples):
        u"""[(t0, t1)] seconds of speech. CPU: ~2 s per 24-minute episode."""
        w = self.lib
        cp = w.whisper_vad_default_context_params()
        cp.use_gpu = False
        with self.lock:
            ctx = w.whisper_vad_init_from_file_with_params(
                model.encode(sys.getfilesystemencoding()), cp)
            if not ctx:
                raise SpeechUnavailable(u"the Silero VAD model %s could not "
                                        u"be loaded" % model)
            try:
                segs = w.whisper_vad_segments_from_samples(
                    ctx, self.vad_defaults,
                    samples.ctypes.data_as(C.POINTER(C.c_float)), len(samples))
                if not segs:
                    raise SpeechUnavailable(u"Silero VAD failed on this audio")
                try:
                    n = w.whisper_vad_segments_n_segments(segs)
                    # ⚠ centiseconds, despite the float.
                    return [(w.whisper_vad_segments_get_segment_t0(segs, i)
                             / 100.0,
                             w.whisper_vad_segments_get_segment_t1(segs, i)
                             / 100.0) for i in range(n)]
                finally:
                    w.whisper_vad_free_segments(segs)
            finally:
                w.whisper_vad_free(ctx)

    def vad_settings(self):
        v = self.vad_defaults
        return {f: round(float(getattr(v, f)), 4) if f != "max_speech_duration_s"
                else None for f, _t in _VadParams._fields_}

    # -- text -------------------------------------------------------------
    def transcribe(self, model, samples):
        u"""All the text whisper hears in `samples`. ⛔ Its timestamps are not
        read -- see the module note."""
        w = self.lib
        with self.lock:
            ctx = self._asr.get(model)
            if ctx is None:
                cp_p = w.whisper_context_default_params_by_ref()
                try:
                    cp = _ContextParams.from_buffer_copy(cp_p.contents)
                finally:
                    w.whisper_free_context_params(cp_p)
                ctx = w.whisper_init_from_file_with_params(
                    model.encode(sys.getfilesystemencoding()), cp)
                if not ctx:
                    raise SpeechUnavailable(u"the whisper model %s could not "
                                            u"be loaded" % model)
                self._asr[model] = ctx
            params = _FullParams.from_buffer_copy(self.full_defaults)
            # The language is DETECTED, not assumed: tsubasa is not a Japanese
            # tool, and the witness compares letters in any script.
            language = C.c_char_p(b"auto")
            params.language = language
            params.detect_language = False
            params.no_context = True
            params.print_progress = False
            params.print_realtime = False
            params.print_timestamps = False
            if w.whisper_full(ctx, params,
                              samples.ctypes.data_as(C.POINTER(C.c_float)),
                              len(samples)) != 0:
                raise SpeechUnavailable(u"whisper could not transcribe this "
                                        u"audio")
            # ⚠ Joined as BYTES, decoded once: a segment can end inside a
            # multi-byte character, and decoding per segment turned Japanese
            # into U+FFFD at every join.
            raw = b"".join(
                C.string_at(w.whisper_full_get_segment_text(ctx, i))
                for i in range(w.whisper_full_n_segments(ctx)))
        return raw.decode("utf-8", "replace")


_ENGINES = {}


def engine(need_asr=False):
    u"""-> (`_Engine`, `Location`). Raises `SpeechUnavailable` with the
    sentence that would fix it."""
    loc = locate()
    why = missing_reason(loc, need_asr=need_asr)
    if why:
        raise SpeechUnavailable(why)
    if loc.library not in _ENGINES:
        _ENGINES[loc.library] = _Engine(loc.library)
    return _ENGINES[loc.library], loc


# ---------------------------------------------------------------------------
# audio
# ---------------------------------------------------------------------------

def decode_audio(video_path, start=None, length=None, timeout=900):
    u"""The video's first audio stream as 16 kHz mono float32. -> ndarray

    ⚠ Through ffmpeg, the one dependency `10-deployment.md` says cannot be
    replaced on this path. `start`/`length` seek, for the witness windows."""
    exe = _ffmpeg.find("ffmpeg")
    if not exe:
        raise SpeechUnavailable(_ffmpeg.missing_reason(
            u"reading a video's audio"))
    argv = [exe, "-nostdin", "-v", "error"]
    if start is not None:
        argv += ["-ss", "%.3f" % max(0.0, start)]
    argv += ["-i", str(video_path)]
    if length is not None:
        argv += ["-t", "%.3f" % length]
    argv += ["-map", "0:a:0", "-ac", "1", "-ar", str(SAMPLE_RATE),
             "-f", "s16le", "-"]
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout,
                              **_ffmpeg._no_window())
    except subprocess.TimeoutExpired:
        raise SpeechUnavailable(u"ffmpeg did not finish decoding the audio "
                                u"within %d s" % timeout)
    except OSError as exc:
        raise SpeechUnavailable(u"could not run ffmpeg: %s" % exc)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise SpeechUnavailable(u"ffmpeg could not decode the audio: %s"
                                % (u" ".join(err[-2:]) or u"(no output)"))
    pcm = np.frombuffer(proc.stdout, dtype=np.int16)
    return pcm.astype(np.float32) / 32768.0


# ---------------------------------------------------------------------------
# the two products, cached per video
# ---------------------------------------------------------------------------

def _fingerprint(path):
    try:
        return u"%s:%d" % (os.path.basename(path), os.path.getsize(path))
    except OSError:
        return os.path.basename(path)


def _cache():
    from .cache import Cache
    return Cache()


def speech_onsets(video_path, duration, cache=None):
    u"""Speech segments [(t0, t1)] of the video, RAW (no `ONSET_LAG`). Cached
    per video content and per VAD model + settings; ~2 s plus the decode.

    ⛔ Raises `SpeechUnavailable` -- including when the decode came back more
    than `MAX_SHORT_DECODE` short of `duration` (RUNBOOK B6)."""
    from .cache import content_key
    eng, loc = engine()
    stamp = {"engine": eng.version, "model": _fingerprint(loc.vad_model),
             "settings": eng.vad_settings()}
    cache = cache if cache is not None else _cache()
    key = None
    try:
        key = content_key(video_path)
        hit = cache.get(key, "speech-onsets")
        if hit and hit.get("stamp") == stamp:
            return [tuple(s) for s in hit["segments"]]
    except (IOError, OSError):
        key = None

    samples = decode_audio(video_path)
    decoded = len(samples) / float(SAMPLE_RATE)
    if duration and decoded < float(duration) * (1.0 - MAX_SHORT_DECODE):
        raise SpeechUnavailable(
            u"its audio decoded to %.0f s of a %.0f s video -- more than %d%% "
            u"short -- so a reference built from it would end early and the "
            u"missing stretch would read as silence"
            % (decoded, float(duration), int(MAX_SHORT_DECODE * 100)))
    segments = eng.vad_segments(loc.vad_model, samples)
    if key is not None:
        try:
            cache.put(key, "speech-onsets",
                      {"stamp": stamp, "segments": [list(s) for s in segments]})
        except (IOError, OSError):
            pass
    return segments


def heard_windows(video_path, duration, cache=None):
    u"""[(window start, text)] for `witness.windows(duration)`. Cached per video
    and per whisper model. Raises `SpeechUnavailable`."""
    from .cache import content_key
    from . import witness as _witness
    eng, loc = engine(need_asr=True)
    starts = _witness.windows(duration)
    stamp = {"engine": eng.version, "model": _fingerprint(loc.asr_model),
             "windows": [round(s, 3) for s in starts],
             "length": _witness.WINDOW_S}
    cache = cache if cache is not None else _cache()
    key = None
    try:
        key = content_key(video_path)
        hit = cache.get(key, "speech-heard")
        if hit and hit.get("stamp") == stamp:
            return [tuple(h) for h in hit["heard"]]
    except (IOError, OSError):
        key = None

    heard = []
    for start in starts:
        clip = decode_audio(video_path, start=start, length=_witness.WINDOW_S)
        heard.append((start, eng.transcribe(loc.asr_model, clip)
                      if len(clip) else u""))
    if key is not None:
        try:
            cache.put(key, "speech-heard",
                      {"stamp": stamp, "heard": [list(h) for h in heard]})
        except (IOError, OSError):
            pass
    return heard


def describe():
    u"""One line naming what the speech path would use, for a run's notes."""
    loc = locate()
    why = missing_reason(loc, need_asr=True)
    if why:
        return why
    return (u"speech path: whisper.cpp at %s, VAD %s, text check %s"
            % (os.path.dirname(loc.library), os.path.basename(loc.vad_model),
               os.path.basename(loc.asr_model)))
