# -*- coding: utf-8 -*-
u"""
The text witness: does the subtitle SAY what the video says, where it says it?
RUNBOOK B6; based on Mattias's Tsubasa-sync #4, re-measured on this project's
corpus (`12-alignment.md` §5b).

On a speech mask the timing evidence is thinner than cue-vs-cue (§5), so a
mask verdict needs a second, INDEPENDENT signal before anything is written. A
few windows of the audio are transcribed (`speech.heard_windows`), and each is
compared with the subtitle's lines at the offset the timing found.

⭐ A DIFFERENT SIGNAL, NOT THE SAME ONE TWICE. The timing reads WHEN speech
starts; this reads WHAT is said. A wrong episode of the same show has the same
rhythm of dialogue; it shares almost no words.

🚨 A RIGHT PAIR CAN LOSE A WINDOW -- a shout whisper mis-hears, a song the
subtitle only describes as （歌声）. So a pair passes on a SHARE of its windows,
and the windows that did not match are named on the result (#4 measured an
every-window rule refusing four correct pairs).

⭐ A WINDOW CAN SAY NOTHING. An opening song, a preview: speech or singing in
the audio and no line in the subtitle. That is `no-sub`, and silence is
`quiet`; neither helps nor hurts. Only windows with both are SCORED.

⛔ THE WITNESS CAN ONLY VOUCH FOR A SUBTITLE IN THE AUDIO'S OWN LANGUAGE.
Whisper writes what it hears; an English subtitle on Japanese speech shares no
letters with it, and calling that *"a different episode"* would be a false
sentence. When the subtitle and what was heard are written in different
scripts the witness is `unavailable` and says why.

⛔ Nothing here reads audio or runs a model: it is string arithmetic over what
`speech` heard and what the subtitle says, so the suite drives every rule
without media.
"""
import re
import unicodedata

#: Windows spread evenly over the runtime, each this long.
WINDOWS = 10
WINDOW_S = 30.0

#: Subtitle lines are taken from the window widened by this much on each side:
#: a line that starts 2 s before the window may be the one being heard.
MARGIN_S = 3.0

#: Fewer heard characters than this: the window is `quiet`, not scored.
QUIET_CHARS = 8

#: Fewer subtitle characters than this in the window: `no-sub`, not scored.
NO_SUB_CHARS = 4

#: ⭐ A scored window MATCHES when at least this share of what was heard
#: (character bigrams) is also in the subtitle there. Re-measured
#: (`12-alignment.md` §5b).
MATCH = 0.23

#: ⭐ A pair passes when at least this share of its scored windows match.
#: Set high: a false refusal costs a click, a false accept a wrong card.
MIN_SHARE = 0.75

#: ⛔ At least this many scored windows, or the witness has not seen enough of
#: the episode to vouch for it.
MIN_SCORED = 4

#: ⛔ The writing systems `MATCH` was measured on (`12-alignment.md` §5b).
#: Character bigrams separate Japanese because there are thousands of them;
#: in the Latin alphabet a WRONG film's windows matched at 0.28-0.47 (Tears
#: of Steel against Sintel's English speech), over `MATCH`. Speech in any
#: other script is `unavailable` until it is measured -- a refusal, never a
#: guess.
MEASURED_SCRIPTS = (u"kana",)

QUIET, NO_SUB = u"quiet", u"no-sub"

_TAG = re.compile(u"\\{[^}]*\\}|\\\\[Nnh]|<[^>]*>")


def windows(duration):
    u"""Window START times for a video of `duration` seconds. -> [float]"""
    duration = float(duration or 0.0)
    if duration <= 0:
        return []
    return [max(0.0, duration * (i + 0.5) / WINDOWS - WINDOW_S / 2.0)
            for i in range(WINDOWS)]


def normalise(text):
    u"""Letters and digits only, any script, NFKC-folded (full-width `ＡＢ`
    and `AB` are one thing). Markup goes first, so `{\\an8}` does not become
    the word `an8`."""
    text = unicodedata.normalize(u"NFKC", _TAG.sub(u"", text or u""))
    return u"".join(ch for ch in text if ch.isalnum()).lower()


def script_of(text):
    u"""The writing system most of `text`'s letters are in. -> str or None

    `kana` (Japanese: any kana among CJK letters), `han` (CJK without kana),
    `hangul`, or the first word of the Unicode name otherwise (`latin`,
    `cyrillic`, `arabic`, ...). None for text with no letters."""
    counts = {}
    for ch in text:
        if not ch.isalpha():
            continue
        name = unicodedata.name(ch, u"")
        if name.startswith((u"HIRAGANA", u"KATAKANA")):
            key = u"kana"
        elif name.startswith(u"CJK"):
            key = u"han"
        elif name.startswith(u"HANGUL"):
            key = u"hangul"
        else:
            key = (name.split(u" ", 1)[0] or u"other").lower()
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    cjk = counts.get(u"kana", 0) + counts.get(u"han", 0)
    if cjk * 2 >= sum(counts.values()):
        # ⚠ Japanese is mostly kanji in places; a share of kana marks it.
        return u"kana" if counts.get(u"kana", 0) * 10 >= cjk else u"han"
    return max(counts, key=counts.get)


def _bigrams(text):
    return set(text[i:i + 2] for i in range(len(text) - 1))


def containment(heard, written):
    u"""Share of what was HEARD that the subtitle also says. -> 0..1

    ⚠ Containment, not similarity: the subtitle may say MORE than whisper
    heard (speaker names, sound cues, a line whisper missed), and that is not
    evidence against it."""
    h = _bigrams(heard)
    if not h:
        return 0.0
    return len(h & _bigrams(written)) / float(len(h))


class Witness(object):
    u"""What the text check concluded. `passed` is the only field a decision
    may read; `rows` and `reason` are for the person."""

    __slots__ = ("passed", "rows", "reason", "available")

    def __init__(self, passed, rows, reason, available=True):
        self.passed = bool(passed) and bool(available)
        #: [(window start s, QUIET | NO_SUB | score)]
        self.rows = list(rows)
        self.reason = reason
        self.available = available

    @classmethod
    def unavailable(cls, reason):
        return cls(False, [], reason, available=False)

    @property
    def scored(self):
        return [(t, v) for t, v in self.rows if not isinstance(v, str)]

    def summary(self):
        u"""One line for the result's notes."""
        if not self.available:
            return u"text check: did not run -- %s" % self.reason
        scored = self.scored
        hits = sum(1 for _t, v in scored if v >= MATCH)
        skipped = len(self.rows) - len(scored)
        line = (u"text check: %d of %d windows say the same thing as the "
                u"subtitle" % (hits, len(scored)))
        if self.passed and self.reason:
            line += u"; %s" % self.reason
        if skipped:
            line += (u" (%d with nothing to compare: quiet, or speech the "
                     u"subtitle has no line for)" % skipped)
        return line


def check(heard, cues, offset):
    u"""Judge one subtitle against what was heard. -> `Witness`

    `heard`   [(window start, text)] from `speech.heard_windows`
    `cues`    the subtitle's `cues.Cue`s, in the subtitle's own time
    `offset`  seconds ADDED to the subtitle to land on the video -- the timing
              fit's answer; the witness reads the subtitle where it WOULD BE
    """
    said_all = u"".join(normalise(t) for _s, t in heard)
    written_all = u"".join(normalise(c.text) for c in cues)
    heard_script, written_script = script_of(said_all), script_of(written_all)
    if heard_script and heard_script not in MEASURED_SCRIPTS:
        return Witness.unavailable(
            u"whisper wrote the speech down in %s, and the text check is "
            u"measured only on Japanese speech so far"
            % _SCRIPT_WORDS.get(heard_script, heard_script))
    if heard_script and written_script and heard_script != written_script:
        return Witness.unavailable(
            u"whisper wrote the speech down in %s and the subtitle is written "
            u"in %s, and the text check can only compare a subtitle in the "
            u"audio's own language" % (_SCRIPT_WORDS.get(heard_script,
                                                         heard_script),
                           _SCRIPT_WORDS.get(written_script, written_script)))

    lines = [(c.start + offset, normalise(c.text)) for c in cues]
    rows = []
    for start, text in heard:
        said = normalise(text)
        lo, hi = start - MARGIN_S, start + WINDOW_S + MARGIN_S
        written = u"".join(t for (at, t) in lines if lo <= at <= hi)
        if len(said) < QUIET_CHARS:
            rows.append((start, QUIET))
        elif len(written) < NO_SUB_CHARS:
            rows.append((start, NO_SUB))
        else:
            rows.append((start, containment(said, written)))

    scored = [(t, v) for t, v in rows if not isinstance(v, str)]
    misses = [(t, v) for t, v in scored if v < MATCH]
    where = u", ".join(u"%s (%d%%)" % (_clock(t), int(round(v * 100)))
                       for t, v in misses[:4])
    if len(scored) < MIN_SCORED:
        return Witness(False, rows, (
            u"the text check could compare only %d window%s of the episode "
            u"with the subtitle (at least %d are needed): the rest were quiet "
            u"or had speech the subtitle has no line for"
            % (len(scored), u"" if len(scored) == 1 else u"s", MIN_SCORED)))
    if len(scored) - len(misses) < MIN_SHARE * len(scored):
        return Witness(False, rows, (
            u"what is said in the video does not match the subtitle at %s -- "
            u"%d of %d windows checked. A different episode, a different cut, "
            u"a subtitle that drifts there, or one in another language"
            % (where, len(misses), len(scored))))
    # ⭐ Passed with stragglers: said, not hidden. A mis-heard shout and a
    # stretch where the subtitle drifts look the same from one window.
    return Witness(True, rows, (u"did not match at %s" % where) if misses
                   else u"")


_SCRIPT_WORDS = {u"kana": u"Japanese", u"han": u"Chinese characters",
                 u"hangul": u"Korean", u"latin": u"the Latin alphabet",
                 u"cyrillic": u"Cyrillic", u"hebrew": u"Hebrew"}


def _clock(seconds):
    s = int(max(0, seconds))
    return u"%d:%02d" % (s // 60, s % 60)
