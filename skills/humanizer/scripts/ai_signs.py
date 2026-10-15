#!/usr/bin/env python3
"""Scan text for signs of AI writing.

The patterns follow references/ai-writing-signs.md, the skill's field guide to
AI writing signs. Section numbers in the output point into that guide.

Usage:
    python3 ai_signs.py draft.txt
    pbpaste | python3 ai_signs.py

As a library:
    from ai_signs import scan, rhythm

This is an editing aid, not an AI detector. A finding means "look at this
sentence again". It is not proof of anything, and the guide explains why
fixing the underlying problem matters more than deleting the flagged words.
"""

import re
import statistics
import sys
from dataclasses import dataclass

# (category, guide section, label, regex, note[, severity]). Matched case-insensitively.
# Severity defaults to "warn"; "info" marks patterns that are weak on their own.
PATTERNS = [
    # 1. Content
    ("content", "1.1", "inflated significance",
     r"\b(stands|serves) as (a|an) (testament|reminder|symbol)|\bis a testament\b|\b(a |an )?(pivotal|crucial|vital|significant|key) (role|moment|turning point)\b|\b(underscor|highlight)(es|ing|ed) (its|the|their) (importance|significance)\b|\breflects? (a )?broader\b|\b(enduring|lasting|indelible) (legacy|mark|impact)\b|\bsetting the stage for\b|\bevolving landscape\b|\bfocal point\b|\bdeeply rooted\b",
     "state the specific fact or cut the sentence"),
    ("content", "1.2", "canned coverage claim",
     r"\b(featured|profiled) in\b|\bindependent coverage\b|\bleading expert\b|\b(active|strong) (social media|digital) presence\b|\bmedia outlets\b",
     "say what was said or done, or drop it"),
    ("content", "1.3", "superficial -ing analysis",
     r",\s+(highlighting|underscoring|emphasizing|showcasing|reflecting|symbolizing|ensuring|fostering|cultivating|contributing to|solidifying|cementing|enhancing)\b",
     "delete the trailing clause; make a real point its own sentence"),
    ("content", "1.4", "promotional tone",
     r"\b(boasts?|vibrant|nestled|groundbreaking|renowned|breathtaking|diverse array|in the heart of|natural beauty|rich (cultural )?(heritage|history|tapestry)|commitment to|seamless(ly)?|world-class|cutting-edge)\b",
     "describe plainly; replace adjectives with facts"),
    ("content", "1.5", "vague association",
     r"\b(associated with|connected (to|with)|in connection (to|with)|in association with)\b",
     "state the actual relationship"),
    ("content", "1.6", "vague attribution",
     r"\b(experts|observers|critics|researchers|analysts|scholars) (argue|agree|say|suggest|believe|warn|recommend|note|have (cited|noted))\b|\bindustry reports\b|\bstudies (show|suggest)\b|\bdescribed in scholarship\b|\bseveral (sources|publications)\b",
     "name the source, own the claim, or cut it"),
    ("content", "1.7", "challenges formula",
     r"\bdespite (its|these|the) [^.]{0,60}\bchallenges\b|\bfaces? (several|many|numerous) challenges\b|\bfuture (outlook|prospects)\b",
     "name the real problem or end on the last substantive point"),
    ("content", "1.8", "hedging disclaimer",
     r"\b(while )?specific details are (limited|scarce)\b|\bnot widely (documented|available|disclosed)\b|\bbased on (the )?available information\b|\bshould be (treated|seen|read|understood) as\b[^.]{0,80}\brather than\b|\bdoes not by itself (establish|prove|mean)\b|\bmaintains a low profile\b",
     "delete; state what you know or leave it out"),

    # 2. Language
    ("parallelism", "2.3", "not just X, but Y",
     r"\bnot (only|just|merely|simply)\b[^.!?\n]{1,80}\bbut( also)?\b",
     "state the positive claim directly"),
    ("parallelism", "2.3", "it's not X, it's Y",
     r"\b(it'?s|this is|that'?s|they'?re|we'?re|he'?s|she'?s)\s+not\s+[^.!?\n]{1,60}?[,;:.—–-]+\s*(it'?s|this is|that'?s|they'?re|we'?re|he'?s|she'?s|but)\b",
     "the most recognised tic in social posts; say what it is"),
    ("parallelism", "2.3", "X isn't Y. It's Z.",
     r"\b(is|are|was|were)n'?t\s+[^.!?\n]{1,60}\.\s+(it|this|that|they)('s| is| are| was| were)\b",
     "say what it is"),
    ("parallelism", "2.3", "X isn't (just) Y, it's Z",
     r"\b(is|are|was|were)n'?t\s+(just |only |merely |simply )?[^.!?\n]{1,60}?[,;:\u2014\u2013-]+\s*(it'?s|it is|they'?re|this is|that'?s)\b",
     "say what it is"),
    ("parallelism", "2.3", "not a X but a Y",
     r"\bnot (a|an|the) [^.!?\n,]{1,30}\bbut (a|an|the)\b",
     "say what it is"),
    ("parallelism", "2.3", "no X, no Y, just Z",
     r"\b(no|not)\s+[^,.\n]{1,30},\s*(no|not)\s+[^,.\n]{1,30}[,;:—–-]+\s*(just|only)\b",
     "say what it is"),
    ("copula", "2.2", "avoiding is/has",
     r"\b(serves|served|stands|stood|functions|functioned|operates) as (a|an|the)\b|\b(represents|marks|marked|signals) (a|an) (\w+ )?(shift|moment|milestone|turning point|departure|step)\b",
     "use is / has"),

    # 4. Chatbot residue
    ("residue", "4.1", "talking to the user",
     r"\b(certainly|of course|absolutely)!|\bhere(?:'s| is) (a|an|the) (revised|rewritten|more|polished|updated|draft)\b|\bi hope this helps\b|\bwould you like (me )?to\b|\blet me know if\b|\byou'?re absolutely right\b|\bin this (section|article|post),? (we|i) will\b",
     "delete; it was meant for the person prompting"),
    ("residue", "4.2", "placeholder",
     r"\[(your|insert|add|company|name)[^\]]{0,40}\]|\((if available|insert [^)]*)\)|\b20\d\d-xx-xx\b",
     "fill or remove before publishing"),
    ("residue", "6", "didactic disclaimer",
     r"\bit'?s (important|worth|crucial|critical|essential) (to )?(note|noting|remember|mention|consider)\b|\bworth noting\b|\bmay vary\b",
     "cut it, or state the specific caveat"),
    ("residue", "6", "summary tag",
     r"(^|[.!?]\s+|\n)\s*(in summary|in conclusion|to sum up|in short),",
     "end on the last substantive point"),
    ("residue", "6", "summary opener",
     r"(^|[.!?]\s+|\n)\s*(overall|ultimately),",
     "fine in moderation; cut if it only restates", "info"),
    ("residue", "6", "AI self-reference",
     r"\bas an ai( language model)?\b|\bas of my (last )?(knowledge|training) (update|cutoff)\b",
     "delete"),

    # 9. Newer structural tells (2025-2026 research)
    ("structure", "9.1", "'matters' framing",
     r"\b(this|that|it) matters\b|\bwhy (this|it|that|\w+) matters\b|\bmatters because\b|\bis more than (just )?(a|an) [^.!?\n]{1,40}[;,:\u2014-]\s*it\b|\bis not simply\b",
     "delete the frame; let the fact carry the weight"),
    ("structure", "9.3", "explaining after showing",
     r"\bthis (shows|proves|tells us|reminds us) that\b|\bthe (lesson|takeaway|moral)\?|\bwhat this (means|tells us)\b",
     "if the example made the point, cut the explanation", "info"),
    ("structure", "9.4", "nominalization",
     r"\bthe (implementation|optimization|utilization|facilitation|enhancement|establishment|leveraging) of\b",
     "use a verb with a subject", "info"),

    # 8. Social-post patterns
    ("social", "8", "stock line",
     r"\bhere'?s the thing\b|\blet that sink in\b|\bread that again\b|\bthe result\?|\bspoiler( alert)?:|\bno fluff\b|\blet'?s dive in\b|\bgame[- ]?changer\b|\bbut that'?s not all\b|\bhere'?s where it gets interesting\b|\bat the end of the day\b|\bin today'?s (fast[- ]paced|ever[- ]changing|digital) (world|landscape|age)\b",
     "cut or replace with a specific"),
    ("social", "8", "announcement opener",
     r"\b(humbled|thrilled|excited|delighted) to (announce|share)\b",
     "lead with the news itself"),
]

# 2.1 AI vocabulary, all eras. Matched literally as whole words.
VOCAB = [
    "additionally", "align with", "aligns with", "bolstered", "crucial", "delve", "delves", "delving",
    "emphasizing", "enduring", "enhance", "enhances", "enhancing", "fostering", "foster", "garner",
    "garnered", "highlighting", "interplay", "intricate", "intricacies", "landscape", "meticulous",
    "meticulously", "pivotal", "robust", "showcase", "showcases", "showcasing", "tapestry",
    "testament", "underscore", "underscores", "underscoring", "valuable", "vibrant", "leverage",
    "leveraging", "multifaceted", "prioritize", "quietly", "universally", "dependable", "echoed",
    "realm", "nuanced", "moreover", "synergy", "synergies", "holistic", "paramount", "seamless", "elevate", "empower", "unlock",
    "unlocking", "navigate", "navigating",
]

EMOJI = "[\U0001F300-\U0001FAFF☀-➿⬀-⯿]"


@dataclass
class Finding:
    category: str
    section: str
    label: str
    excerpt: str
    note: str
    line: int
    severity: str = "warn"  # "warn" = look again; "info" = weak signal on its own


def _line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in parts if len(re.findall(r"[A-Za-z0-9]+", s)) >= 2]


def rhythm(text):
    """Sentence-length and punctuation statistics (guide 2.6 and 3.6)."""
    lengths = [len(re.findall(r"[\w'’-]+", s)) for s in sentences(text)]
    words = len(re.findall(r"[\w'’-]+", text))
    stats = {"sentences": len(lengths), "words": words}
    if len(lengths) >= 2:
        mean = statistics.mean(lengths)
        stats.update(
            mean=mean,
            stdev=statistics.pstdev(lengths),
            cv=statistics.pstdev(lengths) / mean if mean else 0.0,
            in_band=sum(8 <= n <= 20 for n in lengths) / len(lengths),
            shortest=min(lengths),
            longest=max(lengths),
        )
    stats.update(
        em_dashes=text.count("—"),
        other_punct=sum(text.count(c) for c in ":;()?"),
        curly_quotes=sum(text.count(c) for c in "“”‘’"),
    )
    return stats


def scan(text, exclude=()):
    """Return a list of Findings. `exclude` is a set of categories to skip."""
    findings = []
    for category, section, label, pattern, note, *sev in PATTERNS:
        if category in exclude:
            continue
        for m in re.finditer(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            excerpt = text[m.start():m.end()].strip().replace("\n", " ")
            findings.append(Finding(category, section, label, excerpt[:70], note,
                                    _line_of(text, m.start()), sev[0] if sev else "warn"))

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if "structure" not in exclude and len(paragraphs) >= 4:
        last = paragraphs[-1]
        last_words = len(re.findall(r"[\w'’-]+", last))
        if len(sentences(last)) == 1 and last_words <= 8 and not last.rstrip().endswith("?"):
            findings.append(Finding(
                "structure", "9.2", "short closing line", last[:60],
                "keep it only if it adds information, not just a quotable beat",
                _line_of(text, text.rfind(last)), "info"))
        sizes = [len(re.findall(r"[\w'’-]+", p)) for p in paragraphs]
        if len(paragraphs) >= 5 and statistics.mean(sizes) and statistics.pstdev(sizes) / statistics.mean(sizes) < 0.25:
            findings.append(Finding(
                "structure", "9.5", "uniform paragraph size", f"{len(paragraphs)} paragraphs, similar length",
                "let paragraph size follow the material", 1, "info"))

    if "vocabulary" not in exclude:
        hits = []
        for word in VOCAB:
            for m in re.finditer(r"\b" + re.escape(word) + r"\b", text, flags=re.IGNORECASE):
                hits.append((m.start(), m.group(0)))
        words = max(len(re.findall(r"[\w'’-]+", text)), 1)
        if hits:
            distinct = sorted({h[1].lower() for h in hits})
            # A cluster needs several hits; one word is never a cluster, however short the text.
            dense = len(hits) >= 3 or (len(hits) >= 2 and len(hits) / words > 0.01)
            findings.append(Finding(
                "vocabulary", "2.1",
                "AI vocabulary cluster" if dense else "AI vocabulary",
                ", ".join(distinct)[:70],
                "these co-occur; replace with plain words or facts" if dense
                else "one or two can be coincidence; check each",
                _line_of(text, hits[0][0]), "warn" if dense else "info"))

    if "triad" not in exclude:
        triads = list(re.finditer(
            r"\b(\w+(?: \w+){0,3}), (\w+(?: \w+){0,3}),? and (\w+(?: \w+){0,3})\b", text))
        if triads:
            findings.append(Finding(
                "triad", "2.4", "rule of three",
                f"{len(triads)} three-item list(s), first: '{triads[0].group(0)[:40]}'",
                "keep the one that matters, or make them concrete and uneven",
                _line_of(text, triads[0].start()), "warn" if len(triads) >= 2 else "info"))

    if "rhythm" not in exclude:
        r = rhythm(text)
        flat = r.get("cv", 1) < 0.35
        banded = r.get("in_band", 0) > 0.85
        if r["sentences"] >= 6 and (flat or banded):
            # Plenty of human sentences fall in 8-20 words; only both together is a strong signal.
            findings.append(Finding(
                "rhythm", "2.6", "monotone sentence length",
                f"mean {r['mean']:.0f} words, spread {r['cv']:.2f}, {r['in_band']:.0%} in the 8-20 band",
                "vary: a very short sentence, a long one, a fragment", 1,
                "warn" if (flat and banded) or r.get("cv", 1) < 0.25 else "info"))
        if r["em_dashes"] >= 2 and r["em_dashes"] / max(r["words"], 1) > 1 / 150:
            findings.append(Finding(
                "rhythm", "3.6", "em-dash habit", f"{r['em_dashes']} em dashes",
                "keep the ones that earn it; use commas, colons or parentheses for the rest", 1))
        if r["sentences"] >= 8 and r["em_dashes"] == 0 and r["other_punct"] == 0:
            findings.append(Finding(
                "rhythm", "2.6", "only commas and periods", "no colons, questions or parentheses",
                "a little punctuation variety reads as human", 1, "info"))

    if "formatting" not in exclude:
        bold = list(re.finditer(r"\*\*[^*\n]+\*\*", text))
        if len(bold) >= 3:
            findings.append(Finding("formatting", "3.2", "boldface overuse", f"{len(bold)} bold phrases",
                                    "emphasis should come from the sentence", _line_of(text, bold[0].start())))
        for m in re.finditer(r"^[ \t]*([-*•]|\d+\.)\s*\*\*[^*\n]+?(:\*\*|\*\*\s*:)", text, flags=re.MULTILINE):
            findings.append(Finding("formatting", "3.3", "inline-header list item", m.group(0).strip()[:50],
                                    "prose, or a plain list without bold labels", _line_of(text, m.start())))
        for m in re.finditer(r"^[ \t]*" + EMOJI, text, flags=re.MULTILINE):
            findings.append(Finding("formatting", "3.4", "emoji as bullet/heading", m.group(0).strip(),
                                    "remove", _line_of(text, m.start())))
        for m in re.finditer(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE):
            words = [w for w in m.group(1).split() if len(w) > 3]
            if len(words) >= 2 and all(w[0].isupper() for w in words):
                findings.append(Finding("formatting", "3.1", "Title Case heading", m.group(1)[:50],
                                        "use sentence case", _line_of(text, m.start())))

    findings.sort(key=lambda f: (f.line, f.section))
    return findings


def report(text, exclude=()):
    findings = scan(text, exclude)
    r = rhythm(text)
    lines = [f"sentences: {r['sentences']} | words: {r['words']}"]
    if "mean" in r:
        lines[0] += (f" | sentence length: mean {r['mean']:.1f}, range {r['shortest']}-{r['longest']},"
                     f" {r['in_band']:.0%} in 8-20 band")
    lines[0] += f" | em dashes: {r['em_dashes']}"
    if not findings:
        lines.append("No signs found. Still read it aloud: the guide's content signs need judgment.")
    by_cat = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)
    for cat, items in by_cat.items():
        lines.append(f"\n[{cat}]")
        for f in items:
            tag = "" if f.severity == "warn" else " [weak]"
            lines.append(f"  line {f.line} (§{f.section}) {f.label}{tag}: '{f.excerpt}' -> {f.note}")
    return "\n".join(lines)


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()
    print("== Signs of AI writing (see references/ai-writing-signs.md) ==")
    print(report(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
