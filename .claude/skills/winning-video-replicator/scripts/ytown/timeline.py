"""The join schema: one per-second-readable timeline per video, and the metrics read off it.

A join file (analytics/join/<video id>.json) holds:
  sections  [{name, kind, t0, t1}]           kind in SECTION_KINDS
  sentences [{i, text, t0, t1, words, section}]
  beats     [{t0, t1, kind, label, moving, text}]   the shots; kind in BEAT_KINDS
  spans     [{t0, t1, type, label}]          cards, recordings, music, sfx, takes, narration, tags
  words     [{w, s, e}]
  attrs     {...}                            adapter facts (takes, bed, host share, hook words...)
Every adapter returns these five lists plus attrs; make_join() fills the rest.
"""
from __future__ import annotations

import re
import statistics as st

from .util import median, pct, words_to_sentences, wtext

SECTION_KINDS = ("hook", "item", "cta", "payoff", "outro", "end", "other")
BEAT_KINDS = ("clip", "still", "card", "hero", "grid", "recording", "host", "text", "montage", "flat", "beat")
SPAN_TYPES = ("card", "price_flash", "recording", "music", "sfx", "take", "narration", "tag", "host")


def classify_section(name: str, index: int | None = None) -> str:
    n = (name or "").upper()
    if any(k in n for k in ("HOOK", "OPEN", "COLD", "INTRO")):
        return "hook"
    if "CTA" in n or "SUBSCRIBE" in n:
        return "cta"
    if "PAYOFF" in n or "BACK TO" in n:
        return "payoff"
    if n.strip() == "END" or n.startswith("END ") or "END LINE" in n:
        return "end"
    if "OUTRO" in n or "CLOSE" in n:
        return "outro"
    if index == 0:
        return "hook"
    return "item"


def _at(items: list[dict], t: float, k0="t0", k1="t1"):
    for it in items:
        if it[k0] <= t < it[k1]:
            return it
    return None


def section_at(sections, t):
    return _at(sections, t)


def sentence_at(sentences, t):
    return _at(sentences, t)


def beats_in(beats, t0, t1):
    return [b for b in beats if b["t1"] > t0 and b["t0"] < t1]


def make_join(video_id: str | None, episode: str, duration: float | None, sections, sentences, beats, spans, words, attrs,
              adapter: str) -> dict:
    sections = sorted(sections, key=lambda s: s["t0"])
    for s in sections:
        s.setdefault("kind", classify_section(s.get("name", "")))
    beats = sorted(beats, key=lambda b: b["t0"])
    spans = sorted(spans, key=lambda s: s["t0"])
    if not sentences and words:
        sentences = words_to_sentences(words, section_of=lambda t: (section_at(sections, t) or {}).get("name"))
    if duration is None:
        ends = [x["t1"] for x in sections + beats + spans] + [w["e"] for w in words]
        duration = max(ends) if ends else None
    j = {"video_id": video_id, "episode": episode, "adapter": adapter, "duration": duration,
         "sections": sections, "sentences": sentences, "beats": beats, "spans": spans, "words": words, "attrs": attrs or {}}
    j["metrics"] = {**script_metrics(j), **visual_metrics(j)}
    return j


# ------------------------------------------------------------------ script metrics
_CONTRACTION = re.compile(r"\b(\w+n't|\w+'re|\w+'ve|\w+'ll|\w+'d|(?:it|that|there|he|she|what|where|who|here|let|how|why|when)'s)\b", re.I)
_NUMBER_WORDS = {"zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                 "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
                 "forty", "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million", "billion", "trillion"}
_MONEY = re.compile(r"\$|\bdollars?\b|\bbucks?\b|\bcents?\b|\bworth\b|\bcost\b|\bprice\b|\bsold\b|\bauction\b", re.I)
_SECOND_PERSON = re.compile(r"\b(you|your|you're|you'd|you'll|you've|yourself)\b", re.I)
_PRON = r"(?:it|that|this|he|she|they|we|you|there|these|those|i)"
_NOT_X_ITS_Y = re.compile(
    rf"\b{_PRON}(?:'s|'re|'m| is| was| were| are| isn't| wasn't| aren't| weren't|'d| had| has| have)?\s+(?:not|never)\b"
    rf"[^.!?;]{{1,80}}?[,.;:]\s*{_PRON}(?:'s|'re|'m| is| was| were| are)\b", re.I)
_FRAGMENT_NOT = re.compile(r"(?:^|[.!?]\s+)Not\s+(?:a|an|the|just)\b[^.!?]{1,60}[.!?]\s+(?:A|An|The|Just)\b", re.M)


def script_metrics(j: dict) -> dict:
    words, sents, sections, dur = j["words"], j["sentences"], j["sections"], j["duration"]
    if not words:
        return {"words": 0}
    texts = [wtext(w) for w in words]
    n = len(texts)
    full = " ".join(texts)
    speech_s = sum(max(0.0, w["e"] - w["s"]) for w in words)
    first_word, last_word = words[0]["s"], words[-1]["e"]
    gaps = [b["s"] - a["e"] for a, b in zip(words, words[1:])]
    pauses = [g for g in gaps if g >= 0.5]
    sl = [s["words"] for s in sents] if sents else []
    items = [s for s in sections if s["kind"] == "item"]
    hook = next((s for s in sections if s["kind"] == "hook"), None)
    cta = next((s for s in sections if s["kind"] == "cta"), None)
    first_item_t = items[0]["t0"] if items else None
    m = {
        "words": n,
        "wpm_gross": round(n / ((last_word - first_word) / 60.0), 1) if last_word > first_word else None,
        "wpm_speech": round(n / (speech_s / 60.0), 1) if speech_s else None,
        "sentences": len(sents),
        "sent_median": median(sl), "sent_mean": round(st.mean(sl), 1) if sl else None,
        "sent_p90": sorted(sl)[int(0.9 * (len(sl) - 1))] if sl else None,
        "sent_over20_pct": pct(sum(1 for x in sl if x >= 20), len(sl)) if sl else None,
        "sent_under6_pct": pct(sum(1 for x in sl if x <= 5), len(sl)) if sl else None,
        "questions_per100": round(100.0 * sum(1 for s in sents if s["text"].rstrip().endswith("?")) / max(1, len(sents)), 1) if sents else None,
        "contractions_per100": round(100.0 * len(_CONTRACTION.findall(full)) / n, 2),
        "numbers_per100": round(100.0 * sum(1 for t in texts if re.search(r"\d", t) or t.lower().strip(".,!?") in _NUMBER_WORDS) / n, 2),
        "money_per100": round(100.0 * len(_MONEY.findall(full)) / n, 2),
        "you_per100": round(100.0 * len(_SECOND_PERSON.findall(full)) / n, 2),
        "its_not_its": len(_NOT_X_ITS_Y.findall(full)) + len(_FRAGMENT_NOT.findall(full)),
        "pauses_per_min": round(len(pauses) / ((last_word - first_word) / 60.0), 1) if last_word > first_word else None,
        "pause_median_s": round(median(pauses), 2) if pauses else None,
        "words_first_30s": sum(1 for w in words if w["s"] < 30),
        "hook_seconds": round(hook["t1"] - hook["t0"], 1) if hook else (round(first_item_t, 1) if first_item_t else None),
        "time_to_item1_s": round(first_item_t, 1) if first_item_t is not None else None,
        "items": len(items),
        "words_per_item": round(st.mean([sum(1 for w in words if s["t0"] <= w["s"] < s["t1"]) for s in items]), 1) if items else None,
        "seconds_per_item": round(st.mean([s["t1"] - s["t0"] for s in items]), 1) if items else None,
        "cta_at_pct": round(100.0 * cta["t0"] / dur, 1) if cta and dur else None,
        "has_payoff": any(s["kind"] == "payoff" for s in sections),
        "has_end_line": any(s["kind"] == "end" for s in sections),
    }
    return m


# ------------------------------------------------------------------ visual metrics
def visual_metrics(j: dict) -> dict:
    beats, spans, dur = j["beats"], j["spans"], j["duration"] or 0
    m = {}
    if beats and dur:
        lens = sorted(b["t1"] - b["t0"] for b in beats if b["t1"] > b["t0"])
        cuts = max(0, len(beats) - 1)
        m.update({
            "beats": len(beats),
            "cuts_per_min": round(cuts / (dur / 60.0), 1),
            "shot_median_s": round(median(lens), 2) if lens else None,
            "shot_p10_s": round(lens[int(0.1 * (len(lens) - 1))], 2) if lens else None,
            "shot_p90_s": round(lens[int(0.9 * (len(lens) - 1))], 2) if lens else None,
            "holds_over_8s": sum(1 for x in lens if x > 8),
            "flashes_under_1s": sum(1 for x in lens if x < 1),
            "cuts_first_30s": sum(1 for b in beats if 0 < b["t0"] < 30),
        })
        tot = sum(lens) or dur
        kinds = {}
        for b in beats:
            kinds[b["kind"]] = kinds.get(b["kind"], 0.0) + (b["t1"] - b["t0"])
        for k, v in kinds.items():
            m[f"share_{k}"] = round(100.0 * v / tot, 1)
        moving = [b for b in beats if b.get("moving") is not None]
        if moving:
            m["moving_share"] = round(100.0 * sum(b["t1"] - b["t0"] for b in moving if b["moving"]) / tot, 1)
        text = [b for b in beats if b.get("text") is not None]
        if text:
            m["text_beats_pct"] = round(100.0 * sum(1 for b in text if b["text"]) / len(beats), 1)
        m["host_beats_pct"] = round(100.0 * sum(1 for b in beats if b.get("host")) / len(beats), 1) if any("host" in b for b in beats) else None
    if spans and dur:
        by = {}
        for s in spans:
            by.setdefault(s["type"], []).append(s)
        for t, ss in by.items():
            m[f"{t}_count"] = len(ss)
            m[f"{t}_seconds"] = round(sum(x["t1"] - x["t0"] for x in ss), 1)
        if "recording" in by:
            m["recording_share"] = round(100.0 * m["recording_seconds"] / dur, 1)
            m["recording_median_s"] = round(median([x["t1"] - x["t0"] for x in by["recording"]]), 1)
        if "card" in by:
            m["cards_per_min"] = round(len(by["card"]) / (dur / 60.0), 2)
        m["has_music"] = "music" in by
    return m
