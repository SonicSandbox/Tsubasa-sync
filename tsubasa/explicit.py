# -*- coding: utf-8 -*-
"""
Explicit pairing -- the escape hatch. RUNBOOK step A11.
Authority: `05-interface.md` §*Explicit pairing -- the escape hatch*.

    tsubasa --pair VIDEO SUBTITLE
    tsubasa --pair A.mkv A.srt --pair B.mkv B.srt
    tsubasa --pairs pairs.json

Sonic's words: *"I would also want the option to explicitly match the subs as a
mode option... for anything that falls through the cracks."*

⭐ LIBRARY SIDE. This module is the entry point and its rules; the argparse
wiring is RUNBOOK 3c and is deliberately absent. Everything a CLI needs is a
`PairPlan`.

===========================================================================
🚨 IT SKIPS THE PAIRER. IT NEVER SKIPS THE VERDICT.
===========================================================================

The user is asserting *"these two files go together"*. They are **not**
asserting *"the alignment is findable"* -- a subtitle for a different cut of
the same film satisfies the first and fails the second.

`05-interface.md`: *"the whole value of the tool is that it will not produce a
confidently wrong file. An explicit-pair flag that bypassed the verdict would
be the one command capable of doing exactly that."*

⭐ SO THE VERDICT IS NOT A RULE ANYONE HAS TO REMEMBER. It is the shape of the
types, because `doctrine/robustness` says a rule that relies on remembering
will be forgotten. Five mechanisms, each closing one bypass:

  1. `ExplicitPair` carries **no output path, no write flag and no truthy
     "go"**. There is nothing on it to read instead of asking.
  2. The only call in this module that returns a write authorization is
     `ExplicitPair.decide(verdict, *, force=False)` -- the verdict is
     **required and positional**, `force` is keyword-only, and `force=True`
     with no verdict **raises**. *"Write anyway"* has no syntax without a
     verdict object in hand.
  3. `ExplicitPair` and `PairPlan` **refuse to be unpacked or iterated** into
     `(video, subtitle)` tuples. The bypass shape is
     `for v, s in pairs: write(...)`, and it is a `TypeError` here that names
     the correct route.
  4. `PairPlan.writable()` -- the list of things to write -- **does not exist
     until every accepted pair has been decided**, and it raises naming the
     ones that were not. A loop that `continue`s past a pair cannot produce a
     silently short write list.
  5. `Decision` -- the authorization itself -- **is minted only by `decide()`**
     (see `_MINTED`). Hand-constructing one is a permission slip with no
     verdict behind it, and it is refused.

⚠ What none of that can reach is a caller that never imports this module.
`sync()` at RUNBOOK 3b should turn its `[(video, subtitle), ...]` argument
into a plan by calling `explicit_pairs(pair_args=...)` rather than consuming
the tuples directly -- which also buys the tuple path every refusal below.

===========================================================================
FORCE OVERRIDES THE VERDICT. IT CANNOT OVERRIDE A BROKEN INPUT.
===========================================================================

`explicit_pairs()` **takes no force parameter at all**, and a `Refusal` has no
`decide()`. So an input that never became a pair can never be forced: not
because the code checks, but because `force` is not in scope at that layer.

⚠ And force does not override `ERROR`. `REFUSED` means *measured and
rejected* -- there is an offset the user is choosing to trust. `ERROR` means
*could not be measured*; there is no answer to trust, and writing one would be
the Rule 2 violation this flag exists beside. `LEDGER.md`: *"`measurable is
False` IS `ERROR`, NOT `REFUSED`; subsync shipped that confusion twice."*

===========================================================================
WHAT THIS MODULE DELIBERATELY DOES NOT DO
===========================================================================

⛔ **It does not apply discovery's junk filters.** `discover.is_junk` drops
`.synced.srt`, `sample.mkv` and `name.srt.bak`. The escape hatch exists *for
the files that fall through the cracks*, so re-running the filters it exists to
escape would defeat it. Explicit means explicit.

⛔ **It does not open the video.** That is `container.read()`, it is the
expensive half, and `sync()` does it anyway. An unknown video extension is
therefore a NOTE, not a refusal -- the container reader refuses it honestly and
by name if it truly cannot read it.
"""
import json
import os

from . import formats
from .cues import Outcome
# ⭐ Discovery's OWN classifier, not a second copy of the extension sets.
# `doctrine/architecture`: reuse the app's helpers -- a resolver rebuilt by
# hand stays wrong silently while the real one is fixed. This module bypasses
# discovery's PAIRER; it must not fork its idea of what a video is.
from .discover import classify

# ---------------------------------------------------------------------------
# the outcome vocabulary
# ---------------------------------------------------------------------------
# ⚠ These three names are `05-interface.md`'s, fixed by the spec -- an
# ENUMERATION, not a derivation. Nothing here decides which one a pair gets;
# `decide()` consumes a verdict that already carries one, because
# `doctrine/architecture` rule 4 says a derived value needs ONE writer and the
# band rule (>= 2.5x accept / 1.5-2.5x escalate / < 1.5x refuse) belongs to the
# verdict, not to its consumer.
#
# ⭐ SO THEY ARE IMPORTED FROM THERE, not declared here (RUNBOOK B8). They were
# literals in this file while `verdict.py` did not exist yet, which made two
# copies of one enumeration -- the drift shape rule 4 describes. Re-exported so
# `explicit.CONFIDENT` keeps working for every caller that already reads it.

from .verdict import CONFIDENT, ERROR, OUTCOMES, REFUSED  # noqa: E402

#: 🚨 THE MINT. A `Decision` is a write authorization, so the only way to hold
#: one is to have been given it by `ExplicitPair.decide(verdict)`. Without this
#: token `Decision(pair, CONFIDENT, u"")` is a hand-written permission slip with
#: no verdict behind it -- the last constructible route to `write is True`, and
#: closing it is what makes *"the only route is decide()"* literally true rather
#: than approximately true.
_MINTED = object()

#: Above this, a file is not a subtitle and we will not read it into memory to
#: find out. A Blu-ray PGS track for a long film reaches tens of megabytes; a
#: WEB-DL video starts around a gigabyte. The ceiling sits in the gap, and it
#: exists so `--pair A.mkv B.iso` cannot make the content sniff read 8 GB.
MAX_SUBTITLE_BYTES = 256 * 1024 * 1024


# ---------------------------------------------------------------------------
# faults
# ---------------------------------------------------------------------------

class ExplicitPairError(ValueError):
    """The caller's request could not be understood at all.

    A USER fault: the CLI catches this and prints it. Distinct from a
    `Refusal`, which is a well-understood request that must not proceed.
    """


class ManifestError(ExplicitPairError):
    """The manifest as a WHOLE is unusable -- absent, not JSON, not a list.

    ⚠ Deliberately different from a bad ENTRY. A single entry with a missing
    path is data, and is returned as a `Refusal` so the other forty entries
    still run. A manifest that will not parse has no entries to attribute
    anything to, and nothing in it can be trusted.
    """


class VerdictRequired(RuntimeError):
    """Something asked whether a pair may be written without supplying a
    verdict.

    ⛔ NEVER CATCH THIS, never suppress it, never make it non-fatal. It is a
    PROGRAMMING fault, not a user one, and it announces the single bug this
    feature is capable of causing. `doctrine/robustness`: *a guard that
    announces a tooling fault is never caught* -- one such guard was swallowed
    by a bare `.catch(() => {})` and produced a bug hunt into nothing.

    It is not an `ExplicitPairError` on purpose, so a CLI's
    `except ExplicitPairError` cannot swallow it by accident.
    """


# ---------------------------------------------------------------------------
# what came back
# ---------------------------------------------------------------------------

class Refusal(object):
    """An explicit pairing that will not proceed, and why.

    🚨 THERE IS NO `decide()` HERE AND THERE IS NO `force`. Force overrides the
    verdict; it can never override a broken input, and the reason it can never
    is that a broken input never becomes an `ExplicitPair` -- so there is no
    object on which forcing could be expressed.

    `outcome` is `ERROR` throughout: every case below is *the request could not
    be carried out*, never *the alignment was measured and rejected*. Those are
    different results and this project has shipped them conflated twice.
    """

    __slots__ = ("index", "source", "video", "subtitle", "kind", "outcome",
                 "reason")

    def __init__(self, index, source, video, subtitle, kind, reason):
        self.index = index
        self.source = source
        self.video = video              # as the user gave it, not resolved
        self.subtitle = subtitle
        self.kind = kind
        self.outcome = ERROR
        self.reason = reason

    def __repr__(self):
        return "Refusal(%s, %s, %r)" % (self.source, self.kind,
                                        self.reason[:60])


class ExplicitPair(object):
    """One pairing the user asserted, validated as an INPUT and nothing more.

    ⭐ Read the slots: there is no `output_path`, no `write`, no `ok`. Reaching
    this object means the two files exist and are the kind of thing they were
    claimed to be. It says nothing whatever about the alignment, and there is
    nothing on it to mistake for that claim.
    """

    __slots__ = ("index", "source", "video", "subtitle", "notes",
                 "subtitle_parse", "_plan")

    def __init__(self, index, source, video, subtitle, notes=None,
                 subtitle_parse=None, plan=None):
        self.index = index
        self.source = source
        self.video = video
        self.subtitle = subtitle
        self.notes = list(notes) if notes else []
        #: The `ParseResult` the content check already produced. Carried so the
        #: file is read ONCE -- `00-INDEX.md` Rule 4 asked of an instrument
        #: rather than of the product.
        self.subtitle_parse = subtitle_parse
        self._plan = plan

    def decide(self, verdict, *, force=False):
        """The ONLY route from a pairing to permission to write.

        `verdict` is any object carrying an `outcome` of `CONFIDENT`,
        `REFUSED` or `ERROR` -- a `Result` at RUNBOOK 3b.

        🚨 `verdict` is REQUIRED and POSITIONAL and `force` is KEYWORD-ONLY, so
        `decide(force=True)` is a `TypeError` before any of this runs. That is
        the point: the accident this guards against is somebody reaching for
        the override and getting a write, and the override is not a verdict.

        | verdict  | force | writes | reported as |
        | CONFIDENT|  any  |  yes   | CONFIDENT   |
        | REFUSED  | False |  no    | REFUSED     |
        | REFUSED  | True  | ⚠ yes  | REFUSED, forced -- never "confident" |
        | ERROR    |  any  |  no    | ERROR       |

        ⚠ The forced row still reports REFUSED. `LEDGER.md` §Interface: the GUI
        painted a run containing refusals green because *"11 confident, 1
        refused"* contains the word "confident". A forced write is the most
        dangerous thing this feature can do and it may never be relabelled as
        a success.

        ⚠ Deciding the same pair twice is allowed and the LAST answer stands.
        A retry after a transient read fault is a real case, and making the
        caller track which pairs it had already decided would put the
        book-keeping back where this design just took it from. It is not a
        bypass: every call still costs a verdict object.
        """
        outcome = _outcome_of(verdict, force)
        reason = _reason_of(verdict, outcome, force)
        decision = Decision(_MINTED, self, outcome, reason,
                            forced=bool(force))
        if self._plan is not None:
            self._plan._record(self, decision)
        return decision

    def __iter__(self):
        """⛔ Not unpackable, on purpose -- and this says what to do instead.

        `for video, subtitle in pairs:` is the exact shape that walks past the
        verdict, so it raises here rather than working. `doctrine/architecture`:
        *instruction, not refusal* -- an unavailable path renders what would
        make it available.
        """
        raise TypeError(
            "an ExplicitPair does not unpack into (video, subtitle): that is "
            "the shape that skips the verdict. Read .video and .subtitle "
            "explicitly, and call pair.decide(verdict) -- the only route to a "
            "write. See tsubasa/explicit.py and 05-interface.md.")

    def __repr__(self):
        return "ExplicitPair(%s, %s <- %s)" % (
            self.source, os.path.basename(self.video),
            os.path.basename(self.subtitle))


class Decision(object):
    """A verdict applied to an explicit pairing. The write authorization.

    `write` is a read-only property computed from the outcome and the force
    flag. There is no setter and no slot behind it, so it cannot be assigned
    to -- `doctrine/architecture` rule 4: a derived value needs one writer.
    """

    __slots__ = ("pair", "_outcome", "_reason", "_forced")

    def __init__(self, token, pair, outcome, reason, forced=False):
        if token is not _MINTED:
            raise VerdictRequired(
                "a Decision is minted by ExplicitPair.decide(verdict) and "
                "cannot be constructed directly: doing so would be a write "
                "authorization with no verdict behind it, which is exactly "
                "what explicit pairing must never produce "
                "(05-interface.md).")
        self.pair = pair
        self._outcome = outcome
        self._reason = reason
        self._forced = bool(forced)

    @property
    def outcome(self):
        return self._outcome

    @property
    def forced(self):
        return self._forced

    @property
    def reason(self):
        """🚨 Never empty on a non-confident outcome (`03-permissions.md`
        §hand-back). A refusal whose reason is blank is indistinguishable from
        a success at every surface that reads it."""
        return self._reason

    @property
    def write(self):
        """May this be written?

        CONFIDENT always. REFUSED only when forced. ERROR never -- there is no
        measured offset to apply, so *"write it anyway"* would mean writing a
        number the tool has just said means nothing.
        """
        if self._outcome == CONFIDENT:
            return True
        if self._outcome == REFUSED:
            return self._forced
        return False

    def __repr__(self):
        return "Decision(%s%s, write=%s)" % (
            self._outcome, ", FORCED" if self._forced else "", self.write)


class PairPlan(object):
    """Everything the user asserted: what survived validation, and what did not.

    ⭐ `pairs` and `refusals` sit side by side and the plan is NOT iterable, so
    there is no `for x in plan` that quietly walks the accepted half and loses
    the other one.
    """

    __slots__ = ("pairs", "refusals", "sources", "_decisions")

    def __init__(self, pairs, refusals, sources):
        self.pairs = pairs
        self.refusals = refusals
        self.sources = sources          # ["--pair", "pairs.json"], for reports
        self._decisions = {}            # pair index -> Decision

    # -- counts ------------------------------------------------------------

    @property
    def ok(self):
        """True only when NOTHING was refused. ⚠ A boolean a caller cannot
        misread, because the interface ledger's defect was a string match."""
        return not self.refusals

    @property
    def accepted(self):
        return len(self.pairs)

    @property
    def refused(self):
        return len(self.refusals)

    # -- deciding ----------------------------------------------------------

    def _record(self, pair, decision):
        self._decisions[pair.index] = decision

    def decisions(self):
        """Decisions so far, in input order."""
        return [self._decisions[p.index] for p in self.pairs
                if p.index in self._decisions]

    def undecided(self):
        """Accepted pairs that have not been given a verdict."""
        return [p for p in self.pairs if p.index not in self._decisions]

    def writable(self):
        """The decisions that authorize a write.

        🚨 THIS LIST DOES NOT EXIST UNTIL EVERY ACCEPTED PAIR HAS A VERDICT.
        A caller whose loop skipped one -- an exception, a `continue`, an early
        `break` -- gets a `VerdictRequired` naming the pairs, not a silently
        short list. `doctrine/robustness`: refuse loudly, never drop silently.
        """
        missing = self.undecided()
        if missing:
            raise VerdictRequired(
                "%d of %d explicit pairs have no verdict, so there is no list "
                "of things to write: %s. Explicit pairing skips the pairer, "
                "never the verdict (05-interface.md)."
                % (len(missing), len(self.pairs),
                   u", ".join(u"%s %s" % (p.source,
                                          os.path.basename(p.subtitle))
                              for p in missing[:6])
                   + (u", ..." if len(missing) > 6 else u"")))
        return [d for d in self.decisions() if d.write]

    # -- reporting ---------------------------------------------------------

    def summary(self):
        """One line about VALIDATION. A refusal leads it, always.

        ⚠ `LEDGER.md` §Interface: *"11 confident, 1 refused"* was painted green
        because the bare word "confident" was matched. So when anything was
        refused, the refusal count is the first thing in the string and no
        positive word precedes it.
        """
        if self.refusals:
            return u"%d REFUSED · %d accepted" % (self.refused,
                                                       self.accepted)
        return u"%d accepted" % self.accepted

    def decision_summary(self):
        """One line about the VERDICTS. Refusals first, forced writes named.

        ⚠ A forced write is reported in its own right. It is the only way this
        tool writes a file it did not stand behind, and it must never be
        readable as an ordinary success.
        """
        decided = self.decisions()
        refused = [d for d in decided if d.outcome == REFUSED]
        errored = [d for d in decided if d.outcome == ERROR]
        forced = [d for d in decided if d.forced and d.write]
        confident = [d for d in decided if d.outcome == CONFIDENT]

        head = []
        if forced:
            head.append(u"%d FORCED" % len(forced))
        if refused:
            head.append(u"%d REFUSED" % len(refused))
        if errored:
            head.append(u"%d ERROR" % len(errored))
        tail = [u"%d confident" % len(confident)]
        if self.undecided():
            tail.append(u"%d not yet decided" % len(self.undecided()))
        return u" · ".join(head + tail)

    def __iter__(self):
        raise TypeError(
            "a PairPlan is not iterable: iterating it would walk the accepted "
            "pairs and silently lose plan.refusals. Read .pairs and .refusals "
            "explicitly, and .summary() for the line a person sees.")

    def __repr__(self):
        return "PairPlan(%s)" % self.summary()


# ---------------------------------------------------------------------------
# the entry point
# ---------------------------------------------------------------------------

def explicit_pairs(pair_args=None, manifest_path=None):
    """Validate explicitly asserted pairings. -> `PairPlan`

    ⛔ THERE IS NO `force` PARAMETER, and its absence is the mechanism. Force
    overrides the VERDICT and can never override a broken input; the way that
    is guaranteed is that force is not in scope at this layer at all. A path
    that does not exist cannot be forced into a pair because there is nothing
    here to force.

    `pair_args`   an iterable of 2-sequences, exactly what argparse produces
                  from `--pair VIDEO SUBTITLE` with `action="append",
                  nargs=2`. Relative paths resolve against the CWD, because
                  that is what a shell already means.
    `manifest_path`  a JSON file: `[["video", "subtitle"], ...]` or
                  `[{"video": ..., "subtitle": ...}, ...]`.
                  ⭐ Relative paths inside it resolve against THE MANIFEST'S
                  OWN DIRECTORY -- a manifest generated beside the media and
                  run from elsewhere is the normal case, and resolving against
                  the CWD would turn every entry into "not found".

    Both may be given at once; a manifest plus one extra pair is a real case.
    Duplicate detection runs across the union.
    """
    entries = []
    sources = []

    if pair_args is not None:
        entries.extend(_entries_from_args(pair_args))
        sources.append(u"--pair")
    if manifest_path is not None:
        entries.extend(_entries_from_manifest(manifest_path))
        sources.append(os.path.basename(str(manifest_path)))

    if not entries:
        # ⛔ Refuse loudly rather than hand back an empty plan. A caller that
        # asked for explicit pairing and got a silent no-op believes it ran.
        raise ExplicitPairError(
            "explicit pairing was requested with nothing to pair. Give "
            "pair_args=[(video, subtitle), ...] or manifest_path=... "
            "(both may be given).")

    pairs, refusals = [], []
    for index, entry in enumerate(entries):
        source, video, subtitle, fault = entry
        if fault is not None:
            kind, reason = fault
            refusals.append(Refusal(index, source, video, subtitle, kind,
                                    reason))
            continue
        result = _validate(index, source, video, subtitle)
        (pairs if isinstance(result, ExplicitPair) else refusals).append(result)

    pairs, extra = _resolve_collisions(pairs)
    refusals.extend(extra)
    refusals.sort(key=lambda r: r.index)

    plan = PairPlan(pairs, refusals, sources)
    for pair in pairs:
        pair._plan = plan
    return plan


# ---------------------------------------------------------------------------
# reading what the caller gave us
# ---------------------------------------------------------------------------

def _entries_from_args(pair_args):
    """`--pair` arguments -> [(source, video, subtitle, fault)].

    `fault` is None or `(kind, reason)` -- a malformed entry is a refusal with
    its position named, never a crash that loses the other nine.
    """
    if isinstance(pair_args, (str, bytes)):
        # ⚠ A bare string iterates into CHARACTERS. Catching it here turns a
        # baffling forty-refusal report into one sentence.
        raise ExplicitPairError(
            "pair_args must be a list OF pairs, not a single path: got %r. "
            "Did you mean pair_args=[(video, subtitle)]?" % (pair_args,))

    items = list(pair_args)
    if len(items) == 2 and all(isinstance(i, (str, bytes)) for i in items):
        # ⚠ `("a.mkv", "a.srt")` is one flat pair, not two malformed entries,
        # and guessing either way would be wrong. Say so.
        raise ExplicitPairError(
            "pair_args looks like ONE flat pair, %r, but it must be a list of "
            "pairs. Did you mean pair_args=[(%r, %r)]?"
            % (items, items[0], items[1]))

    out = []
    for n, item in enumerate(items):
        source = u"--pair #%d" % (n + 1)
        out.append(_normalise_entry(source, item, base=None))
    return out


def _entries_from_manifest(manifest_path):
    """`--pairs manifest.json` -> [(source, video, subtitle, fault)]."""
    path = str(manifest_path)
    label = os.path.basename(path)

    if not os.path.exists(path):
        raise ManifestError("the pair manifest does not exist: %s" % path)
    if os.path.isdir(path):
        raise ManifestError("the pair manifest is a directory, not a file: %s"
                            % path)
    try:
        # ⚠ Explicit encoding, always (LEDGER-HOT). `utf-8-sig` because a
        # manifest written by Notepad or PowerShell's Out-File carries a BOM,
        # and json.load on a BOM raises "Expecting value: line 1 column 1",
        # which names the wrong problem entirely.
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ManifestError("%s is not valid JSON: %s (line %d, column %d)"
                            % (path, exc.msg, exc.lineno, exc.colno)) from exc
    except (IOError, OSError) as exc:
        raise ManifestError("could not read %s: %s" % (path, exc)) from exc
    except UnicodeDecodeError as exc:
        raise ManifestError("%s is not UTF-8 text: %s" % (path, exc)) from exc

    if not isinstance(data, list):
        raise ManifestError(
            "%s must hold a JSON list of pairs; found %s. Expected "
            '[["video", "subtitle"], ...] or '
            '[{"video": ..., "subtitle": ...}, ...].'
            % (path, type(data).__name__))
    if not data:
        # An empty manifest is a request that would do nothing while looking
        # like work. Same argument as the empty call above.
        raise ManifestError("%s holds no pairs." % path)

    base = os.path.dirname(os.path.abspath(path))
    out = []
    for n, item in enumerate(data):
        source = u"%s #%d" % (label, n + 1)
        out.append(_normalise_entry(source, item, base=base))
    return out


def _normalise_entry(source, item, base):
    """One raw entry -> `(source, video, subtitle, fault)`.

    Accepts a 2-sequence or an object with exactly `video` and `subtitle`.
    ⛔ An unlisted key fails CLOSED and LOUDLY -- `doctrine/robustness`: a
    machine writer meeting an unlisted field must not accept silently, because
    `{"video": ..., "sub": ...}` would otherwise read as *"the subtitle is
    missing"* and hide the typo that caused it.
    """
    video = subtitle = None

    if isinstance(item, dict):
        unknown = sorted(set(item) - {"video", "subtitle"})
        if unknown:
            return (source, None, None,
                    ("entry", u"unknown key%s %s; an entry takes exactly "
                              u"'video' and 'subtitle'"
                     % ("" if len(unknown) == 1 else "s",
                        u", ".join(repr(k) for k in unknown))))
        missing = sorted({"video", "subtitle"} - set(item))
        if missing:
            return (source, item.get("video"), item.get("subtitle"),
                    ("entry", u"the entry has no %s"
                     % u" and no ".join(repr(k) for k in missing)))
        video, subtitle = item["video"], item["subtitle"]
    elif isinstance(item, (list, tuple)):
        if len(item) != 2:
            return (source, None, None,
                    ("entry", u"an entry must hold exactly 2 paths; this one "
                              u"holds %d: %r" % (len(item), item)))
        video, subtitle = item[0], item[1]
    else:
        return (source, None, None,
                ("entry", u"an entry must be [video, subtitle] or "
                          u"{'video': ..., 'subtitle': ...}; found %s: %r"
                 % (type(item).__name__, item)))

    for label, value in ((u"video", video), (u"subtitle", subtitle)):
        if not isinstance(value, str):
            return (source, video, subtitle,
                    ("entry", u"the %s path must be text; found %s: %r"
                     % (label, type(value).__name__, value)))
        if not value.strip():
            return (source, video, subtitle,
                    ("entry", u"the %s path is empty" % label))

    return (source, _resolve(video, base), _resolve(subtitle, base), None)


def _resolve(path, base):
    """Resolve a path against `base`, or the CWD when `base` is None."""
    path = os.path.expanduser(str(path))
    if base is not None and not os.path.isabs(path):
        path = os.path.join(base, path)
    return os.path.abspath(path)


# ---------------------------------------------------------------------------
# validating one pairing
# ---------------------------------------------------------------------------

def _validate(index, source, video, subtitle):
    """-> `ExplicitPair` or `Refusal`. The whole refusal surface lives here."""
    notes = []

    # -- the swap, FIRST, because two complaints hide one cause -------------
    #
    # `--pair A.srt A.mkv` is the commonest mistake this flag can attract and
    # the two independent messages ("not a video" / "not a subtitle") describe
    # it far worse than one does. `doctrine/architecture`: instruction, not
    # refusal -- print what would make it work.
    if classify(video) == "subtitle" and classify(subtitle) == "video":
        return Refusal(
            index, source, video, subtitle, "swapped",
            u"these look swapped: %s is a subtitle and %s is a video. Did you "
            u"mean --pair %s %s?"
            % (os.path.basename(video), os.path.basename(subtitle),
               os.path.basename(subtitle), os.path.basename(video)))

    # -- both sides must be a real file -------------------------------------
    for label, path in ((u"video", video), (u"subtitle", subtitle)):
        if not os.path.exists(path):
            return Refusal(index, source, video, subtitle, "missing",
                           u"the %s does not exist: %s" % (label, path))
        if os.path.isdir(path):
            return Refusal(index, source, video, subtitle, "not-a-file",
                           u"the %s is a directory, not a file: %s"
                           % (label, path))
        if not os.path.isfile(path):
            return Refusal(index, source, video, subtitle, "not-a-file",
                           u"the %s is not a regular file: %s" % (label, path))

    # -- one file cannot be both sides of its own pair ----------------------
    if _identity(video) == _identity(subtitle):
        return Refusal(index, source, video, subtitle, "same-file",
                       u"the video and the subtitle are the same file: %s"
                       % video)

    # -- the video side: extension only, never a container read -------------
    video_kind = classify(video)
    if video_kind == "subtitle":
        return Refusal(
            index, source, video, subtitle, "not-a-video",
            u"%s is a subtitle, not a video -- it was given where the video "
            u"goes (--pair VIDEO SUBTITLE)" % os.path.basename(video))
    if video_kind is None:
        # ⭐ NOT a refusal. The escape hatch exists for what falls through the
        # cracks, and an unrecognised container extension is exactly that; the
        # container reader will refuse it by name if it truly cannot read it.
        notes.append(u"%s is not a recognised video extension; the container "
                     u"reader will decide" % (os.path.splitext(video)[1]
                                              or u"(no extension)"))

    # -- the subtitle side: extension, then CONTENT -------------------------
    if classify(subtitle) == "video":
        return Refusal(
            index, source, video, subtitle, "not-a-subtitle",
            u"%s is a video, not a subtitle -- it was given where the "
            u"subtitle goes (--pair VIDEO SUBTITLE)"
            % os.path.basename(subtitle))

    try:
        size = os.path.getsize(subtitle)
    except (IOError, OSError) as exc:
        return Refusal(index, source, video, subtitle, "unreadable",
                       u"could not stat the subtitle %s: %s" % (subtitle, exc))
    if size > MAX_SUBTITLE_BYTES:
        return Refusal(
            index, source, video, subtitle, "not-a-subtitle",
            u"%s is %.1f MB, far larger than any subtitle; it was not read"
            % (os.path.basename(subtitle), size / (1024.0 * 1024.0)))

    parsed = formats.read_file(subtitle)
    if parsed.outcome == Outcome.ERROR:
        # ⚠ The reason comes from the reader verbatim. It already names the
        # rung of the ladder that failed -- "no reader recognised this file.
        # Tried -- srt: ...", or "ttml is not implemented yet".
        return Refusal(index, source, video, subtitle, "unreadable",
                       u"%s could not be read as a subtitle: %s"
                       % (os.path.basename(subtitle), parsed.reason))

    if classify(subtitle) is None:
        # ⭐ A subtitle with the wrong extension is the escape hatch's own use
        # case: discovery's `classify` would never have looked at it. It parsed
        # into cues, so it IS a subtitle -- accept it and say why.
        notes.append(u"%s is not a subtitle extension, but the file parses as "
                     u"%s with %d cues" % (os.path.splitext(subtitle)[1]
                                           or u"(no extension)",
                                           parsed.format, len(parsed.cues)))

    if not parsed.cues:
        # 🚨 OK-with-zero-cues is NOT an error, and calling it one here would
        # be the conflation `formats/__init__.py` exists to prevent and that
        # subsync shipped twice. The pairing is accepted; the VERDICT will
        # refuse it, because there is nothing to align. That is the whole
        # design of this feature in one case.
        notes.append(u"%s read cleanly but contains no cues; the verdict will "
                     u"have nothing to measure"
                     % os.path.basename(subtitle))

    return ExplicitPair(index, source, video, subtitle, notes=notes,
                        subtitle_parse=parsed)


def _identity(path):
    """A key two paths share only when they are the same file.

    `realpath` resolves `..` and symlinks; `normcase` folds the case, which
    matters because `A.SRT` and `a.srt` are one file on Windows and two strings
    everywhere.

    ⚠ Known gap, and it is deliberate: two HARD LINKS to one file compare as
    different. The stat-based identity that would catch them returns `st_ino`
    0 on some network filesystems, where it would collide every file into one
    and refuse a whole correct manifest. A missed duplicate costs a wasted
    alignment; a false one costs the user their run.
    """
    return os.path.normcase(os.path.realpath(str(path)))


def _resolve_collisions(pairs):
    """One subtitle claimed for two videos, and exact repeats.

    🚨 A subtitle file belongs to ONE video. Claiming it for two is a
    contradiction inside the user's own assertion, and there is no basis to
    prefer either -- so BOTH are refused, each naming the other. ⚠ Refusing
    only the second would be ORDER-DEPENDENT, which is a defect that hides
    until somebody reorders a manifest.

    ⚠ The reverse is NOT a collision: one video with several subtitles is two
    languages, which `05-interface.md` §Naming and dedupe expects and handles.

    An exact repeat -- the same subtitle for the same video, twice -- is not a
    contradiction. It is the same instruction said twice, so it is collapsed
    to one with a note rather than refused.
    """
    by_subtitle = {}
    for pair in pairs:
        by_subtitle.setdefault(_identity(pair.subtitle), []).append(pair)

    kept, refusals = [], []
    for group in by_subtitle.values():
        videos = {_identity(p.video) for p in group}
        if len(videos) > 1:
            for pair in group:
                others = [os.path.basename(o.video) for o in group
                          if o is not pair]
                refusals.append(Refusal(
                    pair.index, pair.source, pair.video, pair.subtitle,
                    "duplicate-subtitle",
                    u"%s is claimed for %d different videos (%s and %s); one "
                    u"subtitle file belongs to one video, so none of them can "
                    u"be trusted"
                    % (os.path.basename(pair.subtitle), len(videos),
                       os.path.basename(pair.video), u", ".join(others))))
            continue
        first = group[0]
        if len(group) > 1:
            first.notes.append(
                u"the same pairing was given %d times (%s); the repeats were "
                u"collapsed" % (len(group),
                                u", ".join(p.source for p in group[1:])))
        kept.append(first)

    kept.sort(key=lambda p: p.index)
    return kept, refusals


# ---------------------------------------------------------------------------
# the verdict gate
# ---------------------------------------------------------------------------

def _outcome_of(verdict, force):
    """The verdict's outcome, or a loud fault. There is no third answer.

    🚨 This is the structural gate. `force` is accepted here ONLY so the fault
    message can name it, because *"I passed --force, why did it not write"* is
    the confusion that would otherwise follow.
    """
    if verdict is None:
        raise VerdictRequired(
            "an explicit pair was decided with no verdict%s. Explicit pairing "
            "skips the PAIRER, never the VERDICT (05-interface.md): the user "
            "asserted that these two files go together, not that the "
            "alignment is findable. Align the pair and pass the result."
            % (" -- and force=True is not a verdict" if force else ""))

    raw = getattr(verdict, "outcome", None)
    if raw is None:
        raise VerdictRequired(
            "an explicit pair was decided with %r, which carries no `outcome`%s"
            ". A verdict is the aligner's result, not a flag: nothing that is "
            "merely truthy may authorize a write."
            % (verdict, " (force=True does not substitute for one)"
               if force else ""))

    # An enum is fine; `str(SomeEnum.CONFIDENT)` is not, so read the members
    # rather than stringifying the object.
    for value in (raw, getattr(raw, "value", None), getattr(raw, "name", None)):
        if isinstance(value, str) and value.upper() in OUTCOMES:
            return value.upper()

    raise VerdictRequired(
        "an explicit pair was decided with outcome %r, which is not one of "
        "%s (05-interface.md). An unrecognised outcome is never treated as a "
        "success." % (raw, u", ".join(sorted(OUTCOMES))))


def _reason_of(verdict, outcome, force):
    """The sentence a person reads. Never empty unless CONFIDENT and unforced.

    `03-permissions.md` §hand-back: *`reason` is never empty on a non-confident
    outcome*. A blank refusal reads as a success at every surface downstream.
    """
    reason = getattr(verdict, "reason", u"") or u""
    reason = reason.strip() if isinstance(reason, str) else u""

    if outcome == CONFIDENT:
        return reason

    if not reason:
        reason = (u"the alignment was refused and the verdict gave no reason"
                  if outcome == REFUSED else
                  u"the alignment could not be measured")

    if outcome == REFUSED and force:
        return (u"WRITTEN UNDER --force. The pairing was accepted; the "
                u"alignment was NOT: %s" % reason)
    if outcome == ERROR and force:
        # ⚠ Say why force did not help, or the flag reads as broken.
        return (u"%s. --force does not apply: ERROR means the alignment could "
                u"not be MEASURED, so there is no offset to stand behind -- "
                u"force overrides a refusal, not a missing answer" % reason)
    return reason


__all__ = [
    "CONFIDENT", "REFUSED", "ERROR", "OUTCOMES", "MAX_SUBTITLE_BYTES",
    "ExplicitPairError", "ManifestError", "VerdictRequired",
    "Refusal", "ExplicitPair", "Decision", "PairPlan",
    "explicit_pairs",
]
