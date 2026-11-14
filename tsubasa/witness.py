# -*- coding: utf-8 -*-
u"""
The text witness: does the subtitle SAY what the video says, where it says it?

RUNBOOK B6. On a speech mask the timing evidence is thinner than cue-vs-cue
(`12-alignment.md` §5), so a mask verdict needs a second, INDEPENDENT signal
before anything is written. This is it: a few windows of the video's audio are
transcribed (`speech.heard_windows`), and each is compared with the subtitle's
lines at the offset the timing found.

⭐ WHY THIS IS A DIFFERENT SIGNAL AND NOT THE SAME ONE TWICE. The timing fit
reads WHEN speech starts; this reads WHAT is said. A wrong episode of the same
show has the same rhythm of dialogue and scores 1.4-1.7x on timing; it shares
almost no words. Measured 2026-11-14 through this module and `speech.py`
(`spec/12-alignment.md` §5b), 9 episodes of 3 shows whose own caption track is
the truth, every wrong pair judged at the RIGHT pair's offset -- identical
timing, the hardest case the text has to settle alone:

                       windows   per window            per pair
    right subtitle        73     min 0.26, p5 0.54     >= 7 of 8 windows match
    wrong episode        579     max 0.20              0 windows match (72 pairs)

🚨 A RIGHT PAIR CAN LOSE A WINDOW. Gachiakuta 02 at 5:47 is shouting, and
whisper heard `ブーブー言っmeme...`: 26% of it is in the right subtitle. An
every-window rule refused that correct pair -- and three Dr. Stone episodes,
where a character SINGS and the subtitle says only （リリアンの歌声）: compared,
0%. The first version had that rule, from a 24-window sample that never saw a
miss. So a pair passes on a SHARE of its
windows, and the windows that did not match are named on the result.

⭐ AND WHY A WINDOW CAN SAY NOTHING. An opening song, an ending, a preview: the
audio has speech or singing and the subtitle has no line there. That is not a
mismatch -- it is a window with nothing to compare -- so it is reported as
`no-sub` and neither helps nor hurts. Silence is `quiet`. Only windows with
both are SCORED.

⛔ Nothing here reads audio or runs a model. It is pure string arithmetic over
what `speech` heard and what the subtitle says, so the suite drives every rule
without media.
"""
import re

#: Windows spread evenly over the runtime, each this long. 10 x 30 s is what
#: was measured; it costs 5-12 s on a GPU with large-v3 (`speech`).
WINDOWS = 10
WINDOW_S = 30.0

#: Subtitle lines are taken from the window widened by this much on each side,
#: because a line that starts 2 s before the window may be the one being heard.
MARGIN_S = 3.0

#: Fewer heard characters than this: the window is `quiet`, not scored.
QUIET_CHARS = 8

#: Fewer subtitle characters than this in the window: `no-sub`, not scored.
NO_SUB_CHARS = 4

#: ⭐ A scored window MATCHES when at least this share of what was heard
#: (character bigrams) is also in the subtitle there. Sits in the measured
#: per-window empty band 0.20-0.26 above.
MATCH = 0.23

#: ⭐ A pair passes when at least this share of its scored windows match.
#: Measured empty band: wrong pairs 0.0, right pairs >= 0.875 (7 of 8). Set
#: high in it, because a false refusal costs a click and a false accept costs
#: a wrong card.
MIN_SHARE = 0.75

#: ⛔ At least this many scored windows, or the witness has not seen enough of
#: the episode to vouch for it -- a short or mostly-musical video is refused,
#: not passed on two windows.
MIN_SCORED = 4

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
    u"""Letters and digits only, any script. Markup (ASS override tags, `\\N`,
    HTML-ish tags) goes first so `{\\an8}` does not become the word `an8`."""
    return u"".join(ch for ch in _TAG.sub(u"", text or u"") if ch.isalnum())


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
        self.passed = bool(passed)
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
        stragglers = (u"; %s" % self.reason) if self.passed and self.reason             else u""
        return (u"text check: %d of %d windows say the same thing as the "
                u"subtitle%s%s" % (hits, len(scored), stragglers,
                                 u" (%d with nothing to compare: quiet, or "
                                 u"speech the subtitle has no line for)"
                                 % skipped if skipped else u""))


def check(heard, cues, offset):
    u"""Judge one subtitle against what was heard. -> `Witness`

    `heard`   [(window start, text)] from `speech.heard_windows`
    `cues`    the subtitle's `cues.Cue`s, in the subtitle's own time
    `offset`  seconds ADDED to the subtitle to land on the video -- the timing
              fit's answer; the witness checks the subtitle where it WOULD BE
    """
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
            u"or a subtitle that drifts there"
            % (where, len(misses), len(scored))))
    # ⭐ Passed with stragglers: said, not hidden. A mis-heard shout and a
    # stretch where the subtitle drifts look the same from one window.
    return Witness(True, rows, (u"did not match at %s" % where) if misses
                   else u"")


def _clock(seconds):
    s = int(max(0, seconds))
    return u"%d:%02d" % (s // 60, s % 60)
