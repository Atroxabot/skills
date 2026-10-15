#!/usr/bin/env python3
"""Lint a markdown spec for the things that make executors guess.

Flags vague words, hedges, deferred decisions, lowercase "should" in
requirements, placeholders, shouting, missing sections, unnumbered
requirements, and acceptance criteria with nothing observable in them.

Usage:
    python3 spec_lint.py spec.md
    cat spec.md | python3 spec_lint.py
    python3 spec_lint.py spec.md --strict     # warnings count as errors
    python3 spec_lint.py spec.md --json

Severity depends on the section: the same vague word is a warning in
Requirements or Acceptance criteria and only a note in Background.
Hedges and TBDs are expected under Open questions and Assumptions.

A finding means "read this sentence again", not "this is wrong". Leave
a finding on purpose when the looser wording is deliberate.
"""

import argparse
import json
import re
import sys

VAGUE = {
    r"robust(ly|ness)?": "against which failures, and what happens then?",
    r"graceful(ly)?": "name the exact behavior for each error",
    r"user[- ]friendly|intuitive(ly)?|easy to use": "name the behaviors that make it so",
    r"fast(er)?|quick(ly)?|performant|snappy|responsive": "give a number: latency, percentile, load",
    r"scalab(le|ility)": "to what load, keeping what constant?",
    r"efficient(ly)?|optimi[sz]ed?|optimal(ly)?": "by what measure, from what to what?",
    r"flexib(le|ility)|extensib(le|ility)": "for which future change, specifically?",
    r"seamless(ly)?|smooth(ly)?": "describe what the user sees",
    r"appropriate(ly)?|reasonabl[ey]|sensibl[ey]|proper(ly)?|suitabl[ey]": "state the rule this word hides",
    r"as needed|as necessary|if necessary|if needed|where possible|when possible|as appropriate": "state the condition, or make it a requirement",
    r"etc\.?|and so on|and so forth|and more": "finish the list, or say 'only the items listed'",
    r"various|several|numerous|a number of|a lot of|lots of|many|few|some": "give the number or the list",
    r"large|huge|small|tiny|big|massive|high[- ]volume|heavy": "give the number",
    r"minimal(ly)?|minimi[sz]e|maximi[sz]e": "minimal by what measure? give a bound",
    r"secure(ly)?|safe(ly)?": "against which threat, by which rule?",
    r"reliab(le|ly|ility)|resilien(t|ce)|stable": "which failures, what availability, what happens on failure?",
    r"modern|clean|nice|elegant|beautiful|polished": "describe the concrete properties",
    r"real[- ]time|instant(ly|aneous(ly)?)?|immediately": "within what latency?",
    r"up[- ]to[- ]date|fresh": "how stale is acceptable?",
    r"improve[ds]?|enhance[ds]?|better": "from what to what?",
    r"similar to|something like|kind of|sort of|like the": "say which properties to copy",
    r"support(s|ed|ing)?": "read, write, both? which versions, fields, limits?",
    r"handle[ds]?|handling": "handle how? name the behavior",
    r"simpl[ey]|just|easily|straightforward(ly)?|obvious(ly)?": "hides work; say what's needed",
}

HEDGES = r"\b(should probably|probably|might|may want to|could|consider(ing)?|ideally|try to|attempt to|hopefully|maybe|perhaps|possibly|if possible|preferably|tbd|tbc|todo|fixme|xxx|\?\?+|or something|or similar|to be decided|to be determined|we'll see|later)\b"
DEFERRED = r"\b(either\b[^.]{1,80}\bor\b|up to (you|the (developer|implementer|executor|agent))|at (your|the developer's|the implementer's) discretion|feel free|your call|whichever you prefer|whatever works|your choice|decide (later|during implementation)|(we|you) can decide)\b"
PLACEHOLDER = r"(<[A-Za-z][^<>\n]{0,60}>|\{\{[^}]*\}\}|\[(TODO|TBD|insert|placeholder)[^\]]*\]|lorem ipsum)"
SHOUT_WORDS = r"\b(IMPORTANT|CRITICAL|NEVER|ALWAYS|ABSOLUTELY|URGENT|WARNING|NOTE|MANDATORY|DO NOT|DON'T|YOU MUST|UNDER NO CIRCUMSTANCES)\b"
PASSIVE = r"\b(is|are|be|been|being|will be|must be|should be|gets?|got)\s+(\w+ed|sent|done|shown|made|built|written|run|kept|set|taken|given|thrown|hidden)\b(?![^.]*\bby\b)"
OBSERVABLE = r"(\d|`|\"|'|\breturns?\b|\bresponds?\b|\bstatus\b|\bshows?\b|\bdisplays?\b|\bexits?\b|\bcontains?\b|\bequals?\b|\bexists?\b|\bpasses\b|\bfails\b|\berror\b|\bno (new )?\w+ (is|are) (created|sent|written)|\bmatches\b|\bwithin\b|\bbelow\b|\babove\b|\bat most\b|\bat least\b|\blogged\b|\bemail(ed)?\b|\bredirect)"
KEYWORDS_UPPER = r"\b(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY|SHALL NOT|SHALL|REQUIRED|RECOMMENDED|OPTIONAL)\b"

SECTION_KINDS = [
    ("requirements", r"requirement|functional|behaviou?r|rules?\b|^r\d|error|edge case|non-functional|constraints?|interfaces?|api\b|security|performance"),
    ("acceptance", r"acceptance|done when|definition of done|success criteria|verification|test plan|checks?\b"),
    ("open", r"open question|question|assumption|risks?|unknowns?|future|later|parking"),
    ("scope", r"non-goals?|out of scope|scope|goals?"),
    ("background", r"background|context|summary|overview|motivation|problem|why|history|introduction|notes?|reference|appendix|glossary|definitions"),
]

EXPECTED_SECTIONS = {
    "goal or summary": r"summary|goal|objective|problem|overview|purpose",
    "non-goals or out of scope": r"non-goals?|out of scope|not in scope|scope",
    "requirements": r"requirement|behaviou?r|functional|what to build|must",
    "acceptance criteria": r"acceptance|done when|definition of done|success criteria",
    "errors or edge cases": r"error|edge case|failure|unhappy|exception",
    "verification": r"verification|verify|test plan|how to test|testing|done when",
    "open questions or assumptions": r"open question|assumption|unknown",
}


def classify(heading):
    h = heading.lower()
    for kind, pattern in SECTION_KINDS:
        if re.search(pattern, h):
            return kind
    return "other"


def severity(base, kind):
    """Scale a finding by where it appears."""
    if kind in ("requirements", "acceptance"):
        return base
    if kind in ("background", "other", "scope"):
        return "note" if base == "warn" else base
    return base


def lint(text):
    findings = []
    lines = text.splitlines()
    headings = []
    kind = "other"
    in_code = False
    uses_upper_keywords = bool(re.search(KEYWORDS_UPPER, re.sub(r"```.*?```", "", text, flags=re.S)))
    has_preamble = bool(re.search(r"RFC\s*2119|RFC\s*8174", text))
    req_bullets = 0
    req_with_ids = 0

    def add(level, line_no, category, excerpt, hint):
        findings.append({"level": level, "line": line_no, "category": category, "text": excerpt.strip()[:140], "hint": hint})

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if line.strip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append(m.group(2))
            kind = classify(m.group(2))
            continue
        if not line.strip() or line.strip().startswith("|---"):
            continue
        # Strip inline code so `examples` aren't linted as prose.
        prose = re.sub(r"`[^`]*`", "``", line)

        if kind != "open":
            for hit in re.finditer(PLACEHOLDER, prose, re.I):
                add("error", i, "placeholder", line, f"unfilled placeholder {hit.group(0)!r}")
            for hit in re.finditer(HEDGES, prose, re.I):
                word = hit.group(0)
                if word.lower() in ("tbd", "tbc", "todo", "fixme", "xxx", "to be decided", "to be determined") or word.startswith("??"):
                    add("error", i, "undecided", line, f"'{word}' outside Open questions: move it there with an owner and a default")
                elif word.lower() == "could" and kind not in ("requirements", "acceptance"):
                    continue
                elif word.lower() == "later" and kind not in ("requirements", "acceptance"):
                    continue
                else:
                    add(severity("warn", kind), i, "hedge", line, f"'{word}': is it required? use MUST, SHOULD with an exception, or cut it")
            for hit in re.finditer(DEFERRED, prose, re.I):
                if re.search(r"executor'?s choice", prose, re.I):
                    continue
                add(severity("warn", kind), i, "deferred decision", line,
                    f"'{hit.group(0).strip()}' hands a decision to the executor: decide, or write 'executor's choice' explicitly")

        if kind in ("requirements", "acceptance", "scope", "other"):
            for pattern, hint in VAGUE.items():
                for hit in re.finditer(r"\b(" + pattern + r")\b", prose, re.I):
                    word = hit.group(0)
                    # "support" and "handle" are vague as verbs of capability, fine in nouns like "support team".
                    if word.lower().startswith(("support", "handl")) and kind not in ("requirements", "acceptance"):
                        continue
                    if word.lower() in ("some", "many", "few", "just", "better", "simple", "simply") and kind not in ("requirements", "acceptance"):
                        continue
                    add(severity("warn", kind), i, "vague", line, f"'{word}': {hint}")

        if kind in ("requirements", "acceptance") and re.search(r"\b(should|shall|will|must|may)\b", prose) and not re.search(r"\b(SHOULD|SHALL|MUST|MAY)\b", prose):
            word = re.search(r"\b(should|shall|will|must|may)\b", prose).group(0)
            if word in ("should", "may") or uses_upper_keywords:
                add("warn", i, "keyword", line, f"lowercase '{word}' in a requirement: use MUST / SHOULD / MAY in capitals so strength is unambiguous")
        if re.search(r"\bSHALL\b", prose) and uses_upper_keywords and re.search(r"\bMUST\b", text):
            add("note", i, "keyword", line, "SHALL and MUST both used: pick one so readers don't assume different strengths")

        caps = [w for w in re.findall(SHOUT_WORDS, prose) if not re.fullmatch(KEYWORDS_UPPER, w)]
        if caps or re.search(r"!!+", prose):
            add("note", i, "shouting", line, "state the rule once, calmly, with its reason; capitals make executors over-apply rules")

        if kind == "requirements" and re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            req_bullets += 1
            if re.match(r"^\s*([-*+]|\d+[.)])\s+\**(R|NFR|FR|REQ|[A-Z]{1,4})-?\d+[a-z]?\b", line):
                req_with_ids += 1
            if len(prose.split()) > 60:
                add("note", i, "long requirement", line, "over 60 words: split into singular requirements")
            if re.search(PASSIVE, prose, re.I):
                add("note", i, "passive", line, "passive voice without an actor: say which component does it")

        if kind == "acceptance" and re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            if not re.search(OBSERVABLE, prose, re.I):
                add("warn", i, "unverifiable", line, "no observable result (status, output, command, number, text): how would someone check this?")

    # Document-level checks
    joined = "\n".join(headings).lower()
    for name, pattern in EXPECTED_SECTIONS.items():
        if not re.search(pattern, joined):
            level = "error" if name in ("requirements", "acceptance criteria") else "warn"
            add(level, 0, "missing section", "", f"no '{name}' section: add it, even if the answer is one line")
    if uses_upper_keywords and not has_preamble:
        add("note", 0, "keyword", "", "MUST/SHOULD used without the RFC 2119 preamble defining them")
    if req_bullets >= 3 and req_with_ids < req_bullets / 2:
        add("warn", 0, "traceability", "", f"{req_bullets - req_with_ids} of {req_bullets} requirements have no ID (R1, R2...): acceptance criteria can't reference them")
    ac_refs = set(re.findall(r"\b(R\d+[a-z]?)\b", "\n".join(l for l in lines if re.search(r"\bAC\d*\b", l))))
    req_ids = set(re.findall(r"^\s*(?:[-*+]|\d+[.)])\s+\**(R\d+[a-z]?)\b", text, re.M))
    uncovered = sorted(req_ids - ac_refs, key=lambda r: int(re.sub(r"\D", "", r) or 0))
    if req_ids and ac_refs and uncovered:
        add("warn", 0, "traceability", "", f"requirements with no acceptance criterion referencing them: {', '.join(uncovered)}")
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", nargs="?", help="markdown spec (default: stdin)")
    ap.add_argument("--strict", action="store_true", help="exit non-zero on warnings too")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-notes", action="store_true", help="hide note-level findings")
    args = ap.parse_args()
    text = open(args.file, encoding="utf-8").read() if args.file else sys.stdin.read()
    findings = lint(text)
    if args.no_notes:
        findings = [f for f in findings if f["level"] != "note"]
    order = {"error": 0, "warn": 1, "note": 2}
    findings.sort(key=lambda f: (order[f["level"]], f["line"]))
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            where = f"line {f['line']}" if f["line"] else "document"
            print(f"{f['level']:<5} {where:<10} {f['category']}: {f['hint']}")
            if f["text"]:
                print(f"{'':16}> {f['text']}")
        counts = {k: sum(1 for f in findings if f["level"] == k) for k in order}
        print(f"\n{counts['error']} errors, {counts['warn']} warnings, {counts['note']} notes")
    bad = any(f["level"] == "error" for f in findings) or (args.strict and any(f["level"] == "warn" for f in findings))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
