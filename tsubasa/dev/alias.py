# -*- coding: utf-8 -*-
"""
RUNBOOK step A7 — the alias table: harvest it, derive it, grade it.

    python -m tsubasa.dev alias --harvest   Wikidata -> <corpus>/_work/, SLOW, network
    python -m tsubasa.dev alias --derive    the harvest -> tsubasa/data/aliases.json
    python -m tsubasa.dev alias --grade     coverage against the answer key

⭐ WHY ENUMERATE RATHER THAN SEARCH

Probe G2 measured coverage by asking Wikidata one `wbsearchentities` question
per show: 400 titles in 231 s, i.e. **~2 hours for the 12,120-row key**, which
is most of `D6`'s one-day box spent on I/O. `00-INDEX.md` Rule 4, asked at the
I/O level: *is searching the right shape at all?* It is not. The table is
bundled data — it does not need to know which shows anyone owns — so it is
built by **enumerating** the work classes once and keeping every row.

⛔ AND ENUMERATING IS THE ONLY PROVENANCE-CLEAN BUILD.

`02-data-model.md`: the answer key is AniList-derived and **never ships**; a
table mined from jimaku filenames **never ships**. Seeding the queries FROM the
key would make the key the selection function, and the row set would be
AniList-derived even though every field came from Wikidata (CC0). Enumerating
from Wikidata's own P31 classes has no such thread — the key is then used only
as the ANSWER KEY, to grade coverage, which is the role
`09-corpus-strategy.md` reserves for it.

🚨 A PART 1 DEFECT, FOUND BY PROBE A7/1 AND RECORDED HERE

`02-data-model.md` and `09-corpus-strategy.md` both describe this as a
**three-way table: romaji ↔ Japanese ↔ English**. ⛔ **Wikidata has no romaji
field.** Measured on 40 anime-television-series rows: a `ja` label on 100%, an
`en` label on 100%, a `mul` label on 0%, and English ALIASES on 90% — and the
romaji lives *inside those aliases*, mixed with:

    新世紀エヴァンゲリオン   en: Neon Genesis Evangelion
                       ~ Shin Seiki Evangelion   <- the romaji
                       ~ Evangelion, Eva, NGE    <- abbreviations
    宇宙戦艦ヤマト        en: Space Battleship Yamato
                       ~ Uchū Senkan Yamato      <- the romaji, with macrons
                       ~ Star Blazers            <- a DIFFERENT English title
    科学救助隊テクノボイジャー en: Thunderbirds 2086
                       ~ Kagaku Kyūjo Tai Techno Voyager

⭐ **So a three-column row cannot be built, and the right shape is better than
the one the spec asked for:** one entity, N names, each tagged by script. That
covers `Star Blazers` — a real alternative name a filename can carry, which no
romaji column would have held — and it is exactly what `D6`'s **ranking-only**
ruling wants. The spec parts are amended where they live; this is the record.

⚠ AND JAPANESE ALIASES MATTER TOO — `エヴァ`, `グレンラガン`, `ブラッドプラス`.
A filename can use any of them, so the ja side is a SET, not a single title.

🔒 The harvest writes only inside `<corpus>/_work/`. The derived table is the
only thing that reaches the package, and it is CC0 throughout.
"""
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

from ..paths import atomic_write_text, corpus_root, load_config, repo_root

SPARQL = "https://query.wikidata.org/sparql"
ACTION = "https://www.wikidata.org/w/api.php"
UA = ("tsubasa/0.1 alias-table build (subtitle pairing, offline tool; "
      "CC0 data only; https://github.com/ - see spec/09-corpus-strategy.md)")

RAW = "a7_wikidata_raw.jsonl"          # inside <corpus>/_work/ — never ships
BUNDLED = "aliases.json"               # inside tsubasa/data/ — ships

# ⚠ SPARQL is throttled harder than the action API, and the two have different
# budgets. Measured on probe A7/1: `wbgetentities`-style pacing at 0.12 s was
# fine for 430 calls, while three SPARQL calls in a row drew a 429.
SPARQL_PAUSE = 1.5
ACTION_PAUSE = 0.12
BATCH = 50                             # wbgetentities' documented ceiling

# ⭐ The work classes, DIRECT `wdt:P31` — not the `wdt:P279*` subclass closure.
# The closure timed out on `film` at 504 and, worse, would enumerate a
# different population from the one graded. `LEDGER.md` records two headline
# numbers already lost to comparing a probe against a population it never
# covered; measure and build over the same set.
#
# ⚠ Narrower than probe G2's whitelist ON PURPOSE. G2 was measuring COVERAGE,
# where a false reject understates the number and biases the gate towards CUT —
# the safe direction for a gate. Building is the other way round: a false
# accept puts a fish cake in a shipped table.
CLASSES = [
    ("Q63952888", "anime television series"),
    ("Q117467246", "anime television series season"),
    ("Q20650540", "anime film"),
    ("Q220898", "original video animation"),
    ("Q21198342", "manga series"),
    ("Q8274", "manga"),
    ("Q100269041", "light novel"),
    ("Q5398426", "television series"),
    ("Q3464665", "television series season"),
    ("Q11424", "film"),
    ("Q24856", "film series"),
    ("Q7889", "video game"),
    ("Q7058673", "video game series"),
]

# Every id-bearing query requires a Japanese label. An entity with no Japanese
# title cannot bridge a Japanese filename to anything, so it is not a row.
IDS_Q = u"""
SELECT ?item WHERE {
  ?item wdt:P31 wd:%s .
  ?item rdfs:label ?ja . FILTER(LANG(?ja) = "ja")
}
"""

IDS_PAGED_Q = u"""
SELECT ?item WHERE {
  ?item wdt:P31 wd:%s .
  ?item rdfs:label ?ja . FILTER(LANG(?ja) = "ja")
}
ORDER BY ?item
LIMIT %d OFFSET %d
"""

STATS = {"sparql": 0, "action": 0, "retries": 0, "unanswered": 0}


class Unanswered(object):
    """Not a result.

    ⛔ Never falsy-checked into the same branch as an empty answer. That
    conflation is what made probe G report 55.2%, then 19.3%, then 22.5% for
    the same question (`LEDGER.md` §Harness): *"Wikidata has nothing"* and
    *"I never got an answer"* were the same number, and under rate limiting the
    second grew while the figure fell smoothly and plausibly.
    """
    __slots__ = ("why",)

    def __init__(self, why):
        self.why = why

    def __repr__(self):
        return "Unanswered(%s)" % self.why


def _ssl_context():
    """⛔ Never fall back to an unverified context.

    `LEDGER.md` §Environment: every HTTPS host failed identically with
    CERTIFICATE_VERIFY_FAILED and it was not the network. Downgrading turns a
    loud, correct refusal into a silent one that ships.
    """
    try:
        import certifi
        import ssl
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


SSLCTX = _ssl_context()


def _request(url, data=None, tries=4, timeout=180):
    req = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": UA,
                 "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded"})
    kw = {"timeout": timeout}
    if SSLCTX is not None:
        kw["context"] = SSLCTX
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, **kw) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                          # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
            if attempt < tries - 1:
                STATS["retries"] += 1
                # ⚠ 429, 502 and 504 are all LOAD, and WDQS returns them
                # interchangeably. Probe A7/1 saw a HEAVIER query answer in
                # 0.4 s straight after a lighter one drew a 429 — which is the
                # tell that you are diagnosing query cost when the cause is
                # throttling. Back off hard rather than simplify the query.
                time.sleep(4.0 * (attempt + 1))
    STATS["unanswered"] += 1
    return Unanswered(last)


def sparql(query):
    STATS["sparql"] += 1
    # ⚠ POST, not GET: WDQS truncates a long GET and the failure then arrives
    # as a parse error about the RESULT rather than about the request.
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    data = _request(SPARQL, data=body)
    if isinstance(data, Unanswered):
        return data
    return [row["item"]["value"].rsplit("/", 1)[-1]
            for row in data.get("results", {}).get("bindings", [])]


def class_ids(qid, label, log):
    """Every entity id in one class. Unpaged first, paged only if that fails.

    ⚠ OFFSET without ORDER BY is not stable paging — the same row can appear
    in two pages and another in none, silently. So the paged fallback orders by
    `?item`, and the unpaged form is tried first precisely because ordering
    50,000 rows is the expensive part.
    """
    ids = sparql(IDS_Q % qid)
    if not isinstance(ids, Unanswered):
        log(u"  %-12s %-34s %8s  (one query)"
            % (qid, label, "{:,}".format(len(ids))))
        return ids

    log(u"  %-12s %-34s unpaged failed: %s" % (qid, label, ids.why[:34]))
    out, page, offset = [], 20000, 0
    while True:
        time.sleep(SPARQL_PAUSE)
        chunk = sparql(IDS_PAGED_Q % (qid, page, offset))
        if isinstance(chunk, Unanswered):
            log(u"  %-12s %-34s ⛔ UNANSWERED at offset %d: %s"
                % (qid, label, offset, chunk.why[:30]))
            # ⛔ A partial class is reported as partial, never returned as if
            # it were the whole thing. A silently short harvest becomes a
            # silently thin table, and nothing downstream can tell.
            return Unanswered("partial at offset %d (%d collected)"
                              % (offset, len(out)))
        out.extend(chunk)
        if len(chunk) < page:
            break
        offset += page
    log(u"  %-12s %-34s %8s  (paged)"
        % (qid, label, "{:,}".format(len(out))))
    return out


def entities(ids):
    """{qid: record} for up to BATCH ids, via one wbgetentities call."""
    STATS["action"] += 1
    params = {"action": "wbgetentities", "ids": "|".join(ids),
              "props": "labels|aliases|claims", "languages": "en|ja|mul",
              "format": "json", "formatversion": "2"}
    data = _request(ACTION + "?" + urllib.parse.urlencode(params))
    if isinstance(data, Unanswered):
        return data

    out = {}
    for qid, ent in (data.get("entities") or {}).items():
        labels = {}
        for lang, lab in (ent.get("labels") or {}).items():
            value = lab.get("value") if isinstance(lab, dict) else lab
            if value:
                labels[lang] = value
        aliases = {}
        for lang, rows in (ent.get("aliases") or {}).items():
            values = [a.get("value") if isinstance(a, dict) else a
                      for a in (rows or [])]
            values = [v for v in values if v]
            if values:
                aliases[lang] = values
        classes = []
        for claim in (ent.get("claims") or {}).get("P31", []) or []:
            try:
                classes.append(
                    claim["mainsnak"]["datavalue"]["value"]["id"])
            except (KeyError, TypeError):
                continue
        out[qid] = {"qid": qid, "labels": labels, "aliases": aliases,
                    "classes": classes}
    return out


# --------------------------------------------------------------------------
# --harvest
# --------------------------------------------------------------------------

def cmd_harvest(cfg, args):
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2
    work = root / "_work"
    work.mkdir(parents=True, exist_ok=True)
    target = work / RAW

    def log(line):
        # ⚠ flush every line. A network-bound run whose stream block-buffers
        # prints nothing for minutes, and a job that is stuck then looks
        # exactly like one that is working (`LEDGER-HOT.md`).
        sys.stdout.write(line + u"\n")
        sys.stdout.flush()

    # ⭐ Resumable, because a 20-minute network job WILL be interrupted, and
    # re-running it from zero is how a one-day box becomes a two-day one.
    # ⚠ Append mode, never "w": `open(path, "w")` truncates the moment it opens
    # and a raise after that leaves zero bytes (`LEDGER-HOT.md`, bitten three
    # times). Appending cannot destroy what is already there.
    seen = set()
    if target.is_file():
        with io.open(str(target), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    seen.add(json.loads(line)["qid"])
                except (ValueError, KeyError):
                    continue
        log(u"  resuming: %s already holds %s entities"
            % (RAW, "{:,}".format(len(seen))))

    log(u"")
    log(u"  CLASSES -- entities with a Japanese label")
    wanted, partial = [], []
    for qid, label in CLASSES:
        ids = class_ids(qid, label, log)
        if isinstance(ids, Unanswered):
            partial.append((qid, label, ids.why))
            continue
        wanted.extend(ids)
        time.sleep(SPARQL_PAUSE)

    # ⚠ Overlapping by construction: one entity is often several classes. The
    # union is the population, and the per-class numbers above do NOT sum to it.
    wanted = list(dict.fromkeys(wanted))
    todo = [q for q in wanted if q not in seen]
    log(u"")
    log(u"  union %s entities · already have %s · fetching %s"
        % ("{:,}".format(len(wanted)), "{:,}".format(len(wanted) - len(todo)),
           "{:,}".format(len(todo))))
    if partial:
        log(u"  ⚠ %d class(es) returned PARTIAL and were skipped whole:"
            % len(partial))
        for qid, label, why in partial:
            log(u"      %-12s %-34s %s" % (qid, label, why))

    started = time.time()
    written = failed = 0
    with io.open(str(target), "a", encoding="utf-8", newline="\n") as fh:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            got = entities(chunk)
            if isinstance(got, Unanswered):
                failed += len(chunk)
                log(u"  ⛔ batch at %d UNANSWERED: %s" % (i, got.why[:60]))
                time.sleep(ACTION_PAUSE * 10)
                continue
            for record in got.values():
                fh.write(json.dumps(record, ensure_ascii=False) + u"\n")
                written += 1
            fh.flush()
            if (i // BATCH) % 20 == 0:
                done = i + len(chunk)
                rate = done / max(0.001, time.time() - started)
                log(u"  ...%s/%s  %.0f/s  eta %.0f min  (%d unanswered)"
                    % ("{:,}".format(done), "{:,}".format(len(todo)), rate,
                       (len(todo) - done) / max(0.001, rate) / 60.0, failed))
            time.sleep(ACTION_PAUSE)

    log(u"")
    log(u"  wrote %s new entity rows to %s in %.0f s"
        % ("{:,}".format(written), target, time.time() - started))
    log(u"  sparql %d · action %d · retries %d · UNANSWERED %d"
        % (STATS["sparql"], STATS["action"], STATS["retries"],
           STATS["unanswered"]))
    if failed:
        log(u"  ⚠ %s ids were never answered. Re-run to fill them in — the "
            u"harvest is resumable and append-only." % "{:,}".format(failed))
    # 🚨 An append-only log's line count is not the size of the thing it builds
    # (`LEDGER.md`: titles.jsonl 12,589 vs titles.json 12,259). This file can
    # hold the same qid twice across resumed runs; `--derive` dedupes on qid
    # and prints both numbers.
    log(u"  ⚠ %s is an append-only LOG and may hold a qid twice across "
        u"resumed runs. `--derive` dedupes and prints both counts." % RAW)
    return 0 if not partial else 1


# --------------------------------------------------------------------------
# --derive
# --------------------------------------------------------------------------

# ⭐ Rule 4, asked of the DERIVATION: an entity that cannot bridge is not a
# row. The bridge needs a title on BOTH sides of the script divide reaching one
# entity, so an entity whose names are all Japanese -- or all Latin -- can
# never fire it, whatever anyone looks up. Dropping them is provably lossless
# for this table's one job, and it is most of the file.
def _is_cjk(text):
    for ch in text or u"":
        code = ord(ch)
        if (0x3040 <= code <= 0x30FF or 0x4E00 <= code <= 0x9FFF
                or 0x3400 <= code <= 0x4DBF or 0xFF66 <= code <= 0xFF9F):
            return True
    return False


def _is_latin(text):
    return any(("a" <= ch <= "z") or ("A" <= ch <= "Z") for ch in text or u"")


def _names_of(record):
    """Every name an entity is known by, in any of the three languages."""
    out = []
    for value in (record.get("labels") or {}).values():
        if value:
            out.append(value)
    for values in (record.get("aliases") or {}).values():
        out.extend(v for v in (values or []) if v)
    return out


# ⭐ A MIXED-SCRIPT LABEL CAN CARRY THE TITLE TWICE, AND INDEXING IT WHOLE
# REACHES NEITHER HALF.
#
# Wikidata stores several of the largest anime under a stylised label that
# stacks both scripts into one string:
#
#     NARUTO -ナルト-            シン・ゴジラ Shin Godzilla
#
# `normalize()` keeps CJK, so that whole label folds to `narutoナルト` — which
# a filename saying `ナルト` never matches, and neither does one saying
# `Naruto`. The bundled table failed to bridge `ナルト` / `Naruto`, one of the
# four positive controls probe G2 gates its own run on.
#
# 🚨 THE FIRST FIX SPLIT EVERY MIXED LABEL INTO ITS SCRIPT RUNS, AND IT WAS
# UNSOUND. Found by the adversarial pass (`_work/probe_adj16_aliasadversary.py`),
# and it produced TWO shipping defects from one cause, because **a run of a
# compound title is a FRAGMENT, not a name**:
#
#     NARUTO -ナルト- 疾風伝   ->  `ナルト` became a name of *Shippuuden*, so
#                                `ナルト` / `Naruto Shippuuden` bridged to SAME
#     不思議の国のアリス OVA     ->  `ova` became a key naming 12 entities, and
#                                `A.bridge("OVA", "1988")` returned SAME
#
# ⚠ The second is the worse one: `OVA/`, `Specials/`, `劇場版/`, `1st` are
# ordinary DIRECTORY names, so it is reachable from real input. It is probe G's
# fish cake in a new form — the intersection rule firing correctly on input
# that names nothing, because the premise *"reaching an entity means being a
# name of it"* had quietly stopped being true.
#
# ⭐ THE RULE THAT IS SOUND: split a mixed label ONLY when it is **one title
# written twice** — exactly two runs that are phonetic equivalents of each
# other. That is what `NARUTO -ナルト-` is and what `NARUTO -ナルト- 疾風伝`
# is not.
#
# ⚠ Equivalence is decided by `kana.skeleton`, the bridge A3b already ships and
# measured. A kanji run has no skeleton without a dictionary, so it folds to
# empty — and an unverifiable pair is **not split**, which is the Rule 2
# direction.
_RUN_RE = re.compile(u"[぀-ゟ゠-ヿ一-鿿㐀-䶿ｦ-ﾟ]+|[0-9A-Za-z][0-9A-Za-z '&!.:-]*")


def _name_keys(name, normalize):
    """The keys one name contributes.

    The whole name always. Its two halves only when the name is provably the
    same title rendered in two scripts.
    """
    from ..naming import kana as K

    keys = set()
    whole = normalize(name).key
    if whole:
        keys.add(whole)
    if not (_is_cjk(name) and _is_latin(name)):
        return keys

    runs = [r.strip() for r in _RUN_RE.findall(name)]
    runs = [r for r in runs if r]
    # ⛔ EXACTLY TWO. Three runs means the label says something the two halves
    # do not both say -- a season, a subtitle, a year -- and splitting it
    # manufactures a fragment key.
    if len(runs) != 2:
        return keys

    left, right = (K.skeleton(runs[0]) or u""), (K.skeleton(runs[1]) or u"")
    # ⚠ An empty skeleton is "I cannot tell", never "they match". Kanji has no
    # phonetic form here, so a kanji+Latin label is left whole.
    if not left or not right or left != right:
        return keys

    for run in runs:
        key = normalize(run).key
        if key:
            keys.add(key)
    return keys


def cmd_derive(cfg, args):
    from ..naming import alias as A
    from ..naming.normalize import normalize

    root = corpus_root(cfg)
    source = root / "_work" / RAW
    if not source.is_file():
        sys.stderr.write(
            "no harvest at %s -- run `alias --harvest` first\n" % source)
        return 2

    started = time.time()
    # 🚨 An append-only log's line count is not the size of the thing it
    # builds. `titles.jsonl` read 12,589 against a 12,259-row key and the
    # difference was 330 tombstones; the same shape here is a qid written
    # twice by two resumed runs. Both counts are printed.
    lines = 0
    records = {}
    with io.open(str(source), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            lines += 1
            try:
                record = json.loads(line)
            except ValueError:
                continue
            records[record["qid"]] = record

    keys = {}
    display = {}
    bridging = 0
    for qid, record in records.items():
        names = _names_of(record)
        if not any(_is_cjk(n) for n in names):
            continue
        if not any(_is_latin(n) for n in names):
            continue
        bridging += 1

        folded = set()
        for name in names:
            folded |= _name_keys(name, normalize)
        for key in folded:
            keys.setdefault(key, set()).add(qid)

        # One display name for the reason string: prefer the English label,
        # because it is what a person reading a report will recognise.
        labels = record.get("labels") or {}
        display[qid] = labels.get("en") or labels.get("ja") or qid

    # ⭐ THE DISTRIBUTION, so `MAX_ENTITIES_PER_KEY` is FITTED and not chosen.
    # `LEDGER-HOT.md`: every threshold in this pack sits in a measured band; a
    # threshold set by taste breaks the whole value proposition.
    sizes = sorted(len(v) for v in keys.values())
    total = len(sizes)

    def share_at_most(n):
        lo, hi = 0, total
        while lo < hi:
            mid = (lo + hi) // 2
            if sizes[mid] <= n:
                lo = mid + 1
            else:
                hi = mid
        return lo

    print("")
    print("  source        %s" % source)
    print("  lines         %s  (append-only log)" % "{:,}".format(lines))
    print("  entities      %s  distinct qids  %s"
          % ("{:,}".format(len(records)),
             ("⚠ %s duplicate line(s) across resumed runs"
              % "{:,}".format(lines - len(records))) if lines != len(records)
             else ""))
    print("  ⭐ bridging    %s  carry BOTH a CJK and a Latin name"
          % "{:,}".format(bridging))
    print("     the other %s can never fire the bridge whatever is looked up,"
          % "{:,}".format(len(records) - bridging))
    print("     so they are not rows. `00-INDEX.md` Rule 4.")
    print("  keys          %s" % "{:,}".format(total))
    print("")
    print("  ⭐ ENTITIES PER KEY -- the fan-out that MAX_ENTITIES_PER_KEY caps")
    for n in (1, 2, 3, 4, 5, 8, 16, 64):
        print("    <= %-3d  %8s  %5.1f%%"
              % (n, "{:,}".format(share_at_most(n)),
                 100.0 * share_at_most(n) / total if total else 0.0))
    print("    max     %8d" % (sizes[-1] if sizes else 0))
    # 🚨 A key at STORE_CAP is a SILENT DROP: truncating its entity list can
    # remove the very entity the other side would have intersected with, and
    # nothing downstream can tell. It must stay zero.
    at_store_cap = sum(1 for n in sizes if n >= A.STORE_CAP)
    print("    ⛔ at the STORE cap (%d) -- a silent drop if non-zero:  %d"
          % (A.STORE_CAP, at_store_cap))
    print("    ⚠ A key naming many entities is not identifying. The")
    print("      intersection rule already makes a ONE-SIDED hit harmless;")
    print("      the cap is what stops two unrelated titles meeting on a")
    print("      coincidence, which is the one way intersection is fooled.")

    # ⚠ THE STORE CAP AND THE LOOKUP CAP ARE DIFFERENT NUMBERS, and the first
    # version conflated them by truncating at `MAX_ENTITIES_PER_KEY + 1`.
    #
    # That made the artefact unable to answer a question anyone would want to
    # ask of it: *what would a different cap buy?* A sweep could only ever
    # reach the value it was built with, which is a table that can only
    # confirm its own setting. `LEDGER.md`: a tier that cannot be reached
    # cannot be tested.
    #
    # ⭐ So the file stores up to STORE_CAP entities per key -- measured max is
    # 13, so in practice all of them -- and `MAX_ENTITIES_PER_KEY` stays a pure
    # LOOKUP POLICY that can be re-fitted without re-harvesting. Costs nothing:
    # 0.1% of keys carry more than four.
    cap = A.MAX_ENTITIES_PER_KEY
    payload_keys = {}
    for key, qids in keys.items():
        payload_keys[key] = sorted(qids)[:A.STORE_CAP]

    payload = {
        "//": ("RUNBOOK A7 -- the alias table. Enumerated from Wikidata (CC0) "
               "by P31 work class, NOT seeded from the AniList-derived answer "
               "key, which never ships (02-data-model.md). Re-derive with: "
               "python -m tsubasa.dev alias --harvest && --derive. ⛔ Never "
               "mine this from jimaku filenames."),
        # ⚠ FLAT, not nested under a "meta" key. The first shape put every
        # field one level down, so `Table.meta` was the whole envelope and
        # `meta["derived"]` was missing -- `repr(table)` printed `derived ?`
        # and the provenance check would have failed on the shipped artefact.
        # ⭐ Caught by looking at the repr while timing the load, not by any
        # assertion: the timing run printed the table and the `?` was visible.
        "format": A._FORMAT,
        "source": "wikidata",
        "licence": "CC0-1.0",
        "harvestLines": lines,
        "entities": len(records),
        "bridgingEntities": bridging,
        "keys": total,
        "storeCap": A.STORE_CAP,
        "maxEntitiesPerKey": cap,
        "keysOverCap": total - share_at_most(cap),
        "keysAtStoreCap": at_store_cap,
        "maxEntitiesSeen": sizes[-1] if sizes else 0,
        "classes": [q for q, _ in CLASSES],
        "derived": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - started, 1),
    }

    # ⭐ THE LINE FORMAT, not JSON, and the reason is in `naming/alias.py`:
    # parsing this as JSON cost **1.55 s of a 1.708 s load**, against a
    # remaining B5 budget of ~2.9 s. One metadata line, then `key\tQ1 Q2`,
    # then `##`, then `qid\tname`.
    out = io.StringIO()
    out.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    out.write(u"\n")
    for key in sorted(payload_keys):
        out.write(key)
        out.write(u"\t")
        out.write(u" ".join(payload_keys[key]))
        out.write(u"\n")
    out.write(A._SECTION)
    out.write(u"\n")
    for qid in sorted(display):
        out.write(qid)
        out.write(u"\t")
        out.write(display[qid].replace(u"\t", u" ").replace(u"\n", u" "))
        out.write(u"\n")
    text = out.getvalue()

    data_dir = repo_root() / "tsubasa" / "data"
    plain = data_dir / "aliases.tsv"
    packed = data_dir / "aliases.tsv.gz"
    # ⚠ Both legacy names are removed. `doctrine/architecture`: edit in place,
    # never accrete `v2 / v3` layers -- a stale artefact three files down is
    # what survives every override above it.
    for stale in ("aliases.json", "aliases.json.gz"):
        old = data_dir / stale
        if old.is_file():
            old.unlink()

    raw_mb = len(text.encode("utf-8")) / 1048576.0
    if raw_mb <= 1.0:
        atomic_write_text(plain, text)
        if packed.is_file():
            packed.unlink()
        print("")
        print("  wrote %s  (%.2f MB)" % (plain.name, raw_mb))
    else:
        # ⛔ Atomic, never `open(path, "w")`: it truncates the moment it opens,
        # and a raise after that leaves zero bytes (`LEDGER-HOT.md`, bitten
        # three times). Temp file plus os.replace, the same shape as
        # `paths.atomic_write_text`.
        import tempfile
        data_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(data_dir), prefix=".aliases.",
                                   suffix=".tmp")
        os.close(fd)
        try:
            with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, str(packed))
            tmp = None
        finally:
            if tmp is not None and os.path.exists(tmp):
                os.unlink(tmp)
        if plain.is_file():
            plain.unlink()
        packed_mb = packed.stat().st_size / 1048576.0
        print("")
        print("  wrote %s  (%.2f MB gzipped, %.2f MB raw)"
              % (packed.name, packed_mb, raw_mb))

    # ⭐ THE LOAD COST IS PART OF THE ARTEFACT, so it is measured here rather
    # than discovered at B5. A table nobody can afford to open is not a table.
    A.reset_cache()
    t0 = time.time()
    reloaded = A.load()
    load_s = time.time() - t0
    print("  load          %.3f s   %s keys, %s names"
          % (load_s, "{:,}".format(len(reloaded)),
             "{:,}".format(len(reloaded._names))))
    if len(reloaded) != total:
        print("  ⛔ WROTE %s KEYS AND READ BACK %s. The artefact does not "
              "round-trip." % ("{:,}".format(total),
                               "{:,}".format(len(reloaded))))
        return 1
    print("  %.1fs" % (time.time() - started))
    return 0


# --------------------------------------------------------------------------
# --grade
# --------------------------------------------------------------------------

def cmd_grade(cfg, args):
    """Coverage against the answer key. ⚠ The key NEVER ships; it grades.

    ⛔ NOT DIRECTLY COMPARABLE TO PROBE G's 38.8%, and saying so is the whole
    point of this docstring. Probe G asked Wikidata 400 live `wbsearchentities`
    questions; this asks a bundled table 12,120 offline ones. Same population,
    different instrument. `LEDGER.md` records two headline numbers already lost
    to being diffed against a figure that never measured the same thing --
    the parser gate's 97.38% and probe G's own 55.2%. **State the population
    and the instrument beside the number, every time.**
    """
    from ..naming import alias as A
    from . import corpus as C

    root = corpus_root(cfg)
    key_path = root / "naming" / "titles.json"
    if not key_path.is_file():
        sys.stderr.write("no answer key at %s\n" % key_path)
        return 2

    table = A.load()
    if not len(table):
        sys.stderr.write(
            "the alias table is EMPTY -- run `alias --derive` first. "
            "⚠ Grading an empty table reports 0.0%% and reads as a "
            "catastrophic regression rather than as a missing file.\n")
        return 2

    with io.open(str(key_path), encoding="utf-8") as fh:
        rows = json.load(fh)

    try:
        manifest = C.load_manifest(cfg)
        sealed = {C.split_key(show)
                  for scope in manifest.get("scopes", {}).values()
                  for show in scope.get("sealed", [])}
    except Exception:                                    # noqa: BLE001
        sealed = set()

    # 🔒 The seal, on the romaji side -- the same exclusion probe G2 applied,
    # so the two cover the same population even though the instruments differ.
    pool = [r for r in rows
            if r.get("japanese") and r.get("romaji")
            and C.split_key(r["romaji"]) not in sealed]

    def recall(field):
        """Rows whose OWN two titles bridge. Correct by construction."""
        eligible = [r for r in pool if r.get(field)]
        hit = 0
        misses = []
        for row in eligible:
            verdict, _score, _reason = A.bridge(row["japanese"], row[field],
                                                table=table)
            if verdict == A.SAME:
                hit += 1
            elif len(misses) < 6:
                misses.append((row["japanese"], row[field]))
        return len(eligible), hit, misses

    def false_positives(n=4000, seed=20260908):
        """🚨 THE CONTROL PROBE G DID NOT HAVE.

        Recall alone is trivially satisfiable: a table bridging everything to
        everything scores 100%. This scores the Japanese title of one row
        against the ROMAJI OF A DIFFERENT ROW — pairs that should almost never
        bridge — and counts the ones that do.

        ⚠ *Almost* never, and the exception is real: the answer key holds a
        franchise as several rows, so `Gintama` and `Gintama'` are two rows of
        one show. Those are excluded by `split_key`, the corpus split's own
        folding, which **over-merges on purpose** — the safe direction here,
        because over-excluding weakens the control rather than manufacturing
        an accusation.

        ⭐ The examples are PRINTED, not just counted. A number here is only
        as good as a look at what produced it.
        """
        import random
        rng = random.Random(seed)
        eligible = [r for r in pool if r.get("romaji")]
        hits = []
        tried = 0
        for _ in range(n):
            a, b = rng.sample(eligible, 2)
            if C.split_key(a["romaji"]) == C.split_key(b["romaji"]):
                continue
            tried += 1
            if A.bridge(a["japanese"], b["romaji"], table=table)[0] == A.SAME:
                hits.append((a["japanese"], b["romaji"]))
        return tried, hits

    def hard_false_positives():
        """🚨 THE CONTROL THE UNIFORM ONE STRUCTURALLY CANNOT BE.

        `false_positives` draws two rows at random. The adversarial pass
        measured what that actually samples: of 3,999 scored pairs, **3 were
        even a containment pair** -- 0.08%. So *"0 of 4,000 false positives"*
        was true and measured almost nothing: **if every sequel pair bridged
        wrongly, the number would still have read 0.**

        ⭐ This draws the failure shape ON PURPOSE -- a show's Japanese title
        against a DIFFERENT row whose romaji strictly contains its own. That is
        `Naruto` against `Naruto Shippuuden`, and the adversary measured the
        old build at **127 of 3,085 (4.1%)** on it.

        ⚠ Same instrument fault `series.py` already records against
        `seriesgate` ("deliberately hard negatives that were not hard"),
        recurring in the next gate. It is in `--grade` rather than a probe so
        it cannot be forgotten again.
        """
        from ..naming.normalize import normalize

        rows = [r for r in pool if r.get("romaji")]
        by_key = {}
        for row in rows:
            key = normalize(row["romaji"]).key
            if key:
                by_key.setdefault(key, []).append(row)

        pairs = []
        keys = sorted(by_key)
        for key in keys:
            if len(key) < 4:
                continue                     # too short to contain meaningfully
            for other in keys:
                if other == key or key not in other:
                    continue
                for a in by_key[key][:1]:
                    for b in by_key[other][:1]:
                        if C.split_key(a["romaji"]) == C.split_key(b["romaji"]):
                            continue
                        pairs.append((a, b))
        # ⚠ BOTH PATHS, because they are different claims and the first
        # version measured only the weaker one. `bridge()` is the raw table;
        # `same_series()` is what a user actually gets, and the containment
        # guard lives there. Reporting only the table would overstate the
        # defect; reporting only the verdict would hide how much of the table
        # is being saved by a guard downstream.
        from ..naming.series import SAME as S_SAME
        from ..naming.series import same_series

        raw, shipped = [], []
        for a, b in pairs:
            if A.bridge(a["japanese"], b["romaji"], table=table)[0] == A.SAME:
                raw.append((a["japanese"], b["romaji"]))
            if same_series(a["japanese"], b["romaji"])[0] == S_SAME:
                shipped.append((a["japanese"], b["romaji"]))
        return len(pairs), raw, shipped

    print("")
    print("  table         %r" % table)
    print("  answer key    %s rows · %s eligible (both titles, sealed out)"
          % ("{:,}".format(len(rows)), "{:,}".format(len(pool))))
    print("  ⚠ instrument: a BUNDLED TABLE, offline. Probe G's 38.8% came")
    print("    from 400 LIVE searches. Same population, different instrument;")
    print("    a difference is information, not a regression.")

    if not args.sweep:
        print("")
        for field in ("romaji", "english"):
            n, hit, misses = recall(field)
            print("  Japanese -> %-8s %6s / %-6s  %5.1f%%"
                  % (field, "{:,}".format(hit), "{:,}".format(n),
                     100.0 * hit / n if n else 0.0))
            for ja, other in misses[:3]:
                print("      miss  %-26s %s" % (ja[:26], other[:34]))

        tried, wrong = false_positives()
        print("")
        print("  🚨 NEGATIVE CONTROL -- one row's Japanese title against"
              " ANOTHER row's romaji")
        print("     %s cross-row pairs · %d bridged  %.2f%%"
              % ("{:,}".format(tried), len(wrong),
                 100.0 * len(wrong) / tried if tried else 0.0))
        for ja, other in wrong[:8]:
            print("       %-30s | %s" % (ja[:30], other[:36]))
        if not wrong:
            print("       none. ⭐ Recall alone is trivially satisfiable -- a")
            print("       table bridging everything scores 100%. This is what")
            print("       makes the recall number mean something.")
        print("       ⚠ UNIFORM RANDOM, so it draws the containment shape ~0.1%")
        print("         of the time. A 0 here is nearly free. The number that")
        print("         costs something is the next one.")

        tried, raw, shipped = hard_false_positives()
        print("")
        print("  🚨 HARD NEGATIVE CONTROL -- a title against a DIFFERENT row")
        print("     whose romaji CONTAINS it (`Naruto` vs `Naruto Shippuuden`)")
        print("     %s constructed pairs" % "{:,}".format(tried))
        print("       raw table   `bridge()`      %4d  %5.2f%%"
              % (len(raw), 100.0 * len(raw) / tried if tried else 0.0))
        print("       ⭐ SHIPPED  `same_series()`  %4d  %5.2f%%   <- what a "
              "user gets" % (len(shipped),
                             100.0 * len(shipped) / tried if tried else 0.0))
        print("       the gap is what `one_contains_the_other` is buying")
        for ja, other in shipped[:8]:
            print("       %-30s | %s" % (ja[:30], other[:36]))
        if not shipped:
            print("       none through the shipped path. ⭐ This is the shape")
            print("       the uniform control cannot see, and it is where every")
            print("       real defect in this feature has been.")
        return 0

    # ⭐ THE SWEEP -- fit MAX_ENTITIES_PER_KEY on measured recall against
    # measured false positives, rather than on the key-size distribution,
    # which cannot tell a generic word from a big franchise.
    print("")
    print("  ⭐ SWEEP -- the lookup cap against what it costs and buys")
    print("     ⚠ A tight cap refuses the BIGGEST franchises: `ワンピース` /")
    print("       `One Piece` is a manga, an anime, a film series and a game,")
    print("       four entities carrying the same two names. From the key-size")
    print("       distribution alone that looks exactly like a generic word.")
    print("")
    print("     %-6s %-22s %-22s %s"
          % ("cap", "ja->romaji recall", "ja->english recall",
             "cross-row false SAME"))
    original = A.MAX_ENTITIES_PER_KEY
    try:
        for cap in (1, 2, 4, 8, 16, 24, 32, 64, 128, A.STORE_CAP):
            A.MAX_ENTITIES_PER_KEY = cap
            n1, h1, _m = recall("romaji")
            n2, h2, _m = recall("english")
            tried, wrong = false_positives()
            print("     %-6d %7s / %-6s %5.1f%%  %7s / %-6s %5.1f%%  %4d / %-6s %5.2f%%"
                  % (cap, "{:,}".format(h1), "{:,}".format(n1),
                     100.0 * h1 / n1 if n1 else 0.0,
                     "{:,}".format(h2), "{:,}".format(n2),
                     100.0 * h2 / n2 if n2 else 0.0,
                     len(wrong), "{:,}".format(tried),
                     100.0 * len(wrong) / tried if tried else 0.0))
    finally:
        # ⛔ Restored in a `finally`. A sweep interrupted between two values
        # would otherwise leave the process running on an arbitrary cap, and
        # every number measured after it would be about a config nobody chose.
        A.MAX_ENTITIES_PER_KEY = original
    print("")
    print("     ⭐ Pick from the trade-off, not from the distribution. The cap")
    print("        is worth having only where recall stops rising and the")
    print("        false-positive rate starts.")
    return 0


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev alias")
    parser.add_argument("--harvest", action="store_true",
                        help="enumerate Wikidata into <corpus>/_work/ (slow, "
                             "network, resumable)")
    parser.add_argument("--derive", action="store_true",
                        help="the harvest -> tsubasa/data/aliases.json")
    parser.add_argument("--grade", action="store_true",
                        help="coverage against the answer key")
    parser.add_argument("--sweep", action="store_true",
                        help="with --grade: fit MAX_ENTITIES_PER_KEY on "
                             "measured recall against false positives")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.harvest:
        rc = cmd_harvest(cfg, args)
        if rc or not (args.derive or args.grade):
            return rc
    if args.derive:
        rc = cmd_derive(cfg, args)
        if rc or not args.grade:
            return rc
    if args.grade:
        return cmd_grade(cfg, args)
    parser.error("give --harvest, --derive or --grade")
