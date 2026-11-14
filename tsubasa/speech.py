# -*- coding: utf-8 -*-
u"""
The speech path: a reference for a video with NO subtitle track (RUNBOOK B6).
Based on Mattias's Tsubasa-sync #4 (rebuilt here, re-measured on this
project's own corpus; `12-alignment.md` §5b).

`00-INDEX.md` Rule 1: *the embedded subtitle track is an ACCELERATOR, never a
dependency.* When there is none, the reference is read from the audio:

  * **timing** -- Silero VAD speech ONSETS (`speech_onsets`), through
    whisper.cpp's ggml port of Silero.
  * **text** -- a whisper model transcribes a few short windows
    (`heard_windows`) for `witness.py`, the mask path's second signal.
    ⛔ Whisper's own segment times are not a reference: they come back to back
    on a ~1 s grid (#4 measured them at 1.21-1.90x, no better than a wrong
    episode). Transcription is used for WHAT is said, never WHEN.

⭐ WHY whisper.cpp AND NOT onnxruntime (`12-alignment.md` §5b, the engine
ruling). onnxruntime would be a new dependency for tsubasa AND for every
program that freezes it, and Silero through it measured ~21 s an episode
(§5). whisper.cpp's ggml Silero is already on a learner's machine when they
have Anki Miner's subtitle generation, it carries the text check too, and it
costs no dependency at all: it is FOUND, like ffmpeg, never bundled and never
downloaded.

🚨 THE PRICE IS COUPLING TO ANOTHER PROGRAM'S BINARY, and it is paid here:

  * whisper.cpp passes its parameter structs BY VALUE and their layout moves
    between releases. A struct passed with the wrong layout writes a setting
    into the wrong bytes -- garbage at best, a crash at worst. So the library
    is used ONLY at a release whose layout was checked (`PROVEN_VERSIONS`,
    exact, not a prefix), and even then its own defaults are read back
    through our structs and must come out as the known values.
  * Every function used is looked up BEFORE any is called; a missing one
    refuses by name.
  * Only ggml's CPU backend is loaded. Its GPU backends enumerate devices in
    native code at load time, which is where Anki Miner's own notes record
    C-level aborts; the CPU is all this path needs.

Any of these failing is `SpeechUnavailable` with the sentence that would fix
it -- a refusal of the pair, never an exception out of `sync()`.
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

#: How audio becomes samples (`decode_audio`), in every cache stamp: change
#: the decode and every cached onset and transcript is measured again.
DECODE_RECIPE = u"s16le/16000/mono/aresample-async1-first_pts0"

#: 🚨 Seconds a Silero ONSET trails the subtitle line it belongs to: captions
#: appear as speech starts or a little before, and Silero marks the first
#: voiced frame. Subtracted from every onset, so a fit against the corrected
#: reference reads the subtitle's own offset. ⭐ RE-MEASURED on this project's
#: corpus (`12-alignment.md` §5b): 8 right pairs whose truth is known (Yomi
#: 15/18/20 + ABEMA + Netflix, Gintama 201, One Piece 1121, 86 03), through
#: the real aligner, swept 0.24-0.39 s: 0.31 is the lag whose WORST residual
#: is smallest, 0.13 s -- inside §8's 0.15. #4's 0.27 (its own 9 episodes)
#: leaves ABEMA and One Piece at 0.16 here.
ONSET_LAG = 0.31

#: ⛔ RUNBOOK B6: refuse when the decoded audio is short of the container's
#: duration by more than this. A truncated decode makes a reference that ends
#: early, and the bucket walk would read the missing stretch as quiet.
MAX_SHORT_DECODE = 0.03

#: ⛔ whisper.cpp releases whose struct layout below was CHECKED, exactly.
#: Not a prefix: 1.8.5 may move a field. A new release is added here only
#: after `_layout_problems` passes on it AND a real episode is re-measured.
PROVEN_VERSIONS = (u"1.8.4",)

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
    u"""An embedding application's answer to *where is whisper.cpp?* --
    ahead of every other rung, as `ffmpeg.set_location` is."""
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
    picking one: the answer is None and the run names the variable to set.
    Which model heard the audio is part of the claim the witness makes."""
    dirs = []
    for d in (_OVERRIDE["library"], os.environ.get(ENV_LIBRARY),
              _speech_dir()):
        if d and d not in dirs:
            dirs.append(d)
    library = None
    for d in dirs:
        if os.path.isfile(d):
            library = d
            break
        for name in _library_names():
            if os.path.isfile(os.path.join(d, name)):
                library = os.path.join(d, name)
                break
        if library:
            break

    model_dirs = [d for d in dirs if os.path.isdir(d)]
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
        gaps.append(u"one Silero VAD model (ggml-silero-*.bin) -- set %s to "
                    u"its path" % ENV_VAD)
    if need_asr and not loc.asr_model:
        gaps.append(u"one whisper model (ggml-*.bin) for the text check -- "
                    u"set %s to its path" % ENV_ASR)
    if not gaps:
        return None
    return (u"the speech path needs %s. Looked in: %s. Nothing is downloaded."
            % (u"; and ".join(gaps), u", ".join(loc.searched) or u"(nowhere)"))


# ---------------------------------------------------------------------------
# whisper.h at 1.8.4, the parts used here
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


#: Every whisper.cpp function this module calls. Looked up before any call.
_FUNCTIONS = (
    "whisper_version", "whisper_vad_default_params",
    "whisper_vad_default_context_params",
    "whisper_vad_init_from_file_with_params",
    "whisper_vad_segments_from_samples", "whisper_vad_segments_n_segments",
    "whisper_vad_segments_get_segment_t0",
    "whisper_vad_segments_get_segment_t1", "whisper_vad_free_segments",
    "whisper_vad_free", "whisper_context_default_params_by_ref",
    "whisper_full_default_params_by_ref", "whisper_free_params",
    "whisper_free_context_params", "whisper_init_from_file_with_params",
    "whisper_full", "whisper_full_n_segments",
    "whisper_full_get_segment_text",
)

_LOG_CB = C.CFUNCTYPE(None, C.c_int, C.c_char_p, C.c_void_p)


@_LOG_CB
def _quiet(_level, _text, _user):
    u"""whisper.cpp and ggml log every model load to stderr. Under `--json`
    stderr carries the run summary, so the noise is dropped here."""


def _close(a, b, tol=1e-4):
    return abs(float(a) - float(b)) <= tol


def _layout_problems(vad, full):
    u"""The library's defaults, read back through OUR structs. -> [str]

    Each line is a field that came out other than whisper.cpp 1.8.4 sets it,
    which means the layout is not the one written above."""
    want = [("vad.threshold", vad.threshold, 0.5),
            ("vad.min_speech_duration_ms", vad.min_speech_duration_ms, 250),
            ("vad.min_silence_duration_ms", vad.min_silence_duration_ms, 100),
            ("vad.speech_pad_ms", vad.speech_pad_ms, 30),
            ("vad.samples_overlap", vad.samples_overlap, 0.1),
            ("full.strategy", full.strategy, 0),
            ("full.n_max_text_ctx", full.n_max_text_ctx, 16384),
            ("full.thold_pt", full.thold_pt, 0.01),
            ("full.temperature_inc", full.temperature_inc, 0.2),
            ("full.entropy_thold", full.entropy_thold, 2.4),
            ("full.logprob_thold", full.logprob_thold, -1.0),
            ("full.no_speech_thold", full.no_speech_thold, 0.6),
            ("full.max_initial_ts", full.max_initial_ts, 1.0),
            ("full.length_penalty", full.length_penalty, -1.0),
            ("full.greedy.best_of", full.greedy.best_of, 5),
            ("full.beam_search.beam_size", full.beam_search.beam_size, -1),
            # ⭐ the LAST fields before `vad`: a field inserted anywhere above
            # shifts these, so they witness the whole struct's length.
            ("full.grammar_penalty", full.grammar_penalty, 100.0),
            ("full.vad_params.threshold", full.vad_params.threshold, 0.5),
            ("full.vad_params.min_speech_duration_ms",
             full.vad_params.min_speech_duration_ms, 250),
            ("full.vad_params.speech_pad_ms",
             full.vad_params.speech_pad_ms, 30)]
    bad = [u"%s=%r (expected %r)" % (n, got, exp)
           for n, got, exp in want if not _close(got, exp)]
    if full.language != b"en":
        bad.append(u"full.language=%r (expected 'en')" % (full.language,))
    return bad


def _c_path(path):
    u"""A file path as the bytes whisper.cpp / ggml open with a NARROW call.

    ⚠ On Windows that is the ANSI code page, not UTF-8: a model under a
    Japanese user name, encoded as UTF-8, is a file that does not exist. A path
    the code page cannot hold is refused by name rather than reported as a
    model that "could not be loaded"."""
    if sys.platform != "win32":
        return path.encode(sys.getfilesystemencoding())
    try:
        return path.encode("mbcs", "strict")
    except UnicodeEncodeError:
        raise SpeechUnavailable(
            u"the path %s has characters this Windows code page cannot hold, "
            u"and whisper.cpp opens files by that code page. Put it in a "
            u"folder whose path is plain letters" % path)


def version_refusal(version, library):
    u"""The refusal for a whisper.cpp release not in `PROVEN_VERSIONS`, or
    None. ⛔ Exact: `1.8.40` and `1.8.4-rc` are not `1.8.4`."""
    if version in PROVEN_VERSIONS:
        return None
    return (u"whisper.cpp %s at %s is a release whose parameter layout "
            u"tsubasa has not checked (checked: %s). Its structs passed blind "
            u"could put a setting in the wrong bytes, so it is not used."
            % (version or u"(no version)", library,
               u", ".join(PROVEN_VERSIONS)))


def _load_cpu_backend(folder):
    u"""Quiet ggml's log and register its CPU backend, and only that one.

    ⚠ ggml loads its compute backends as separate libraries, from the
    EXECUTABLE's folder unless told; without one registered, whisper.cpp
    aborts inside ggml (#4 measured it in a frozen tsubasa.exe).
    ⛔ `ggml_backend_load_all_from_path` would also load the Vulkan / CUDA
    backends, which enumerate devices in native code at load time."""
    for name in ("ggml-base.dll", "libggml-base.so", "libggml-base.dylib"):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            base = C.CDLL(path)
            if hasattr(base, "ggml_log_set"):
                base.ggml_log_set(_quiet, None)
            break
    for name in ("ggml.dll", "libggml.so", "libggml.dylib"):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ggml = C.CDLL(path)
        if not (hasattr(ggml, "ggml_backend_reg_count")
                and hasattr(ggml, "ggml_backend_load")):
            raise SpeechUnavailable(u"ggml at %s has no backend registry "
                                    u"tsubasa knows how to use" % path)
        ggml.ggml_backend_reg_count.restype = C.c_size_t
        ggml.ggml_backend_load.restype = C.c_void_p
        ggml.ggml_backend_load.argtypes = [C.c_char_p]
        # ⭐ A build with its backends linked in has one registered already;
        # only a build that loads them as libraries needs the CPU one loaded.
        if ggml.ggml_backend_reg_count() == 0:
            cpu = [os.path.join(folder, n) for n in
                   ("ggml-cpu.dll", "libggml-cpu.so", "libggml-cpu.dylib")]
            cpu = [p for p in cpu if os.path.isfile(p)]
            if cpu:
                ggml.ggml_backend_load(_c_path(cpu[0]))
        # ⛔ Still none: whisper.cpp would abort inside ggml, a crash rather
        # than a refusal. A build that ships only per-CPU variants
        # (ggml-cpu-haswell, ...) lands here too: picking a variant this CPU
        # cannot run is an illegal instruction, so it is not guessed at.
        if ggml.ggml_backend_reg_count() == 0:
            raise SpeechUnavailable(
                u"ggml at %s has no CPU backend tsubasa can load (it looks "
                u"for ggml-cpu beside it), and whisper.cpp cannot run "
                u"without one" % folder)
        return


class _Engine(object):
    u"""whisper.cpp, loaded once per process. ⚠ `whisper_full` is not
    re-entrant on a context, so every call is serialised."""

    def __init__(self, library):
        folder = os.path.dirname(os.path.abspath(library))
        try:
            if sys.platform == "win32":
                os.add_dll_directory(folder)
            _load_cpu_backend(folder)
            w = C.CDLL(library)
        except OSError as exc:
            raise SpeechUnavailable(u"whisper.cpp at %s could not be loaded: "
                                    u"%s" % (library, exc))
        missing = [f for f in _FUNCTIONS if not hasattr(w, f)]
        if missing:
            raise SpeechUnavailable(
                u"whisper.cpp at %s lacks %s, so it is not a release tsubasa "
                u"can use" % (library, u", ".join(missing[:3])))
        self.lib = w
        self.library = library
        self.lock = threading.Lock()
        self._asr = {}

        w.whisper_version.restype = C.c_char_p
        self.version = (w.whisper_version() or b"").decode("ascii", "replace")
        why = version_refusal(self.version, library)
        if why:
            raise SpeechUnavailable(why)
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

        # ⭐ By REFERENCE first: the library allocates the struct at its own
        # size and we copy ours out of it. ⚠ That stays inside its allocation
        # only while our struct is no LARGER than the library's -- which the
        # exact version gate above is what guarantees; the read-back then
        # proves the fields are where we think.
        full_p = w.whisper_full_default_params_by_ref(0)
        if not full_p:
            raise SpeechUnavailable(u"whisper.cpp at %s returned no default "
                                    u"parameters" % library)
        try:
            self.full_defaults = _FullParams.from_buffer_copy(full_p.contents)
        finally:
            w.whisper_free_params(full_p)
        self.vad_defaults = w.whisper_vad_default_params()
        bad = _layout_problems(self.vad_defaults, self.full_defaults)
        if bad:
            raise SpeechUnavailable(
                u"whisper.cpp %s at %s does not lay out its parameters the way "
                u"tsubasa reads them (%s), so it is not used: a setting in the "
                u"wrong bytes is a guess, not a measurement."
                % (self.version, library, u"; ".join(bad[:3])))

    # -- timing -----------------------------------------------------------
    def vad_segments(self, model, samples):
        u"""[(t0, t1)] seconds of speech, from Silero on the CPU."""
        w = self.lib
        cp = w.whisper_vad_default_context_params()
        cp.use_gpu = False
        with self.lock:
            ctx = w.whisper_vad_init_from_file_with_params(
                _c_path(model), cp)
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
                    # ⚠ Centiseconds, despite the float (checked against the
                    # decoded length in `12-alignment.md` §5b).
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
        return dict((f, round(float(getattr(v, f)), 4))
                    for f, _t in _VadParams._fields_)

    # -- text -------------------------------------------------------------
    def transcribe(self, model, samples):
        u"""All the text whisper hears in `samples`, on the CPU. ⛔ Its
        timestamps are not read -- see the module note."""
        w = self.lib
        with self.lock:
            ctx = self._asr.get(model)
            if ctx is None:
                cp_p = w.whisper_context_default_params_by_ref()
                try:
                    cp = _ContextParams.from_buffer_copy(cp_p.contents)
                finally:
                    w.whisper_free_context_params(cp_p)
                cp.use_gpu = False
                ctx = w.whisper_init_from_file_with_params(
                    _c_path(model), cp)
                if not ctx:
                    raise SpeechUnavailable(u"the whisper model %s could not "
                                            u"be loaded" % model)
                self._asr[model] = ctx
            params = _FullParams.from_buffer_copy(self.full_defaults)
            # The language is DETECTED, not assumed: tsubasa is not a Japanese
            # tool, and the witness compares letters in any script.
            language = C.c_char_p(b"auto")
            params.language = language
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
            # multi-byte character (#4: per-segment decoding turned Japanese
            # into U+FFFD at every join).
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

    Through ffmpeg -- `10-deployment.md`: audio is the one thing on this path
    the native reader cannot replace. `start`/`length` seek, for the witness
    windows."""
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
    # 🚨 `aresample=async=1:first_pts=0` IS LOAD-BEARING. Raw PCM keeps no
    # timestamps, so an audio stream that starts late (a broadcast or TS-born
    # raw: a few hundred ms is common) or has a hole decoded SHORTER, and every
    # onset came out early by the delay -- under the 3% check, constant over
    # the episode, so the band could not see it and the pair was written off
    # by that much. The filter pads from container time zero and fills holes
    # (found by the B6 adversarial pass: audio at 2.000 s read as 0.023 s).
    argv += ["-map", "0:a:0", "-af", "aresample=async=1:first_pts=0",
             "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"]
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, **_ffmpeg._no_window())
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


def short_decode_reason(decoded_s, duration):
    u"""The refusal when the decoded audio is short of the container, or None.

    ⛔ RUNBOOK B6. Only a KNOWN duration can be short; an unknown one is not
    a pass of this check and not a failure of it."""
    if not duration or duration <= 0:
        return None
    if decoded_s >= float(duration) * (1.0 - MAX_SHORT_DECODE):
        return None
    return (u"its audio decoded to %.0f s of a %.0f s video -- more than %d%% "
            u"short -- so a reference built from it would end early and the "
            u"missing stretch would read as silence"
            % (decoded_s, float(duration), int(round(MAX_SHORT_DECODE * 100))))


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


def _cached(video_path, kind, stamp, cache):
    u"""-> (key or None, payload or None). A cache that cannot be read is a
    miss, never a failure (`cache.Cache.get`)."""
    from .cache import content_key
    try:
        key = content_key(video_path)
        hit = cache.get(key, kind)
    except Exception:       # a regenerable cache: see LEDGER-HOT's zlib entry
        return None, None
    if hit and hit.get("stamp") == stamp:
        return key, hit
    return key, None


def _store(cache, key, kind, payload):
    if key is None:
        return
    try:
        cache.put(key, kind, payload)
    except Exception:       # a cache that cannot be written costs a re-run
        pass


def speech_onsets(video_path, duration, cache=None):
    u"""Speech segments [(t0, t1)] of the video, RAW (no `ONSET_LAG`). Cached
    per video content and per VAD model + settings.

    ⛔ Raises `SpeechUnavailable` -- including when the decode came back more
    than `MAX_SHORT_DECODE` short of `duration` (RUNBOOK B6)."""
    eng, loc = engine()
    stamp = {"engine": eng.version, "model": _fingerprint(loc.vad_model),
             "settings": eng.vad_settings(), "duration": duration,
             "decode": DECODE_RECIPE}
    cache = cache if cache is not None else _cache()
    key, hit = _cached(video_path, "speech-onsets", stamp, cache)
    if hit is not None:
        return [tuple(s) for s in hit["segments"]]

    samples = decode_audio(video_path)
    why = short_decode_reason(len(samples) / float(SAMPLE_RATE), duration)
    if why:
        raise SpeechUnavailable(why)
    segments = eng.vad_segments(loc.vad_model, samples)
    _store(cache, key, "speech-onsets",
           {"stamp": stamp, "segments": [list(s) for s in segments]})
    return segments


def heard_windows(video_path, duration, cache=None):
    u"""[(window start, text)] for `witness.windows(duration)`. Cached per
    video and per whisper model. Raises `SpeechUnavailable`."""
    from . import witness as _witness
    eng, loc = engine(need_asr=True)
    starts = _witness.windows(duration)
    stamp = {"engine": eng.version, "model": _fingerprint(loc.asr_model),
             "windows": [round(s, 3) for s in starts],
             "length": _witness.WINDOW_S, "decode": DECODE_RECIPE}
    cache = cache if cache is not None else _cache()
    key, hit = _cached(video_path, "speech-heard", stamp, cache)
    if hit is not None:
        return [tuple(h) for h in hit["heard"]]

    heard = []
    for start in starts:
        clip = decode_audio(video_path, start=start, length=_witness.WINDOW_S)
        heard.append((start, eng.transcribe(loc.asr_model, clip)
                      if len(clip) else u""))
    _store(cache, key, "speech-heard",
           {"stamp": stamp, "heard": [list(h) for h in heard]})
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
