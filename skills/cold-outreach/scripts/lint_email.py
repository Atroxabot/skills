#!/usr/bin/env python3
"""Mechanical checks for cold outreach drafts.

Usage:
    python3 lint_email.py email.txt                  # one email
    python3 lint_email.py sequence.txt --sequence    # several emails separated by a line '---'
    python3 lint_email.py note.txt --linkedin-note   # connection request note (200 chars)
    pbpaste | python3 lint_email.py

An email may start with a line "Subject: ...". Reports word count, subject
length, links, attachments, calendar links, worn-out openers and follow-ups,
fake Re:/Fwd:, urgency, missing opt-out, and signs of AI writing (via
ai_signs.py; see references/ai-writing-signs.md). Warnings are prompts to
look again, not automatic rewrites. Exits 1 if a LinkedIn note is over the limit.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_signs import scan as scan_ai_signs  # noqa: E402  (same scanner as the humanizer skill)

NOTE_LIMIT = 200

WORN_OPENERS = [
    r"\bhope (this|you)('re| are)? (email )?(finds you|doing) well\b", r"\bmy name is\b", r"\bi came across your\b",
    r"\bi wanted to reach out\b", r"\bi know you'?re busy\b", r"\bi'?m reaching out\b", r"\bquick question\b",
    r"\bi noticed that \w+ is\b", r"\bwe are a leading\b", r"\bi'?m the (founder|ceo|head) of\b",
]
WORN_FOLLOWUPS = [
    r"\bjust (checking|following) (in|up)\b", r"\bbump(ing)? this\b", r"\bcircling back\b", r"\btop of your inbox\b",
    r"\bdid (my|this) (last )?(email|note) get buried\b", r"\b(fall|fell) off a cliff\b", r"\bclose (your|the) file\b",
    r"\bi'?ll assume you'?re not interested\b", r"\bany update\??\b",
]
URGENCY = [r"\b(only|just) \d+ (spots?|seats?|slots?) left\b", r"\b(offer|deal) ends\b", r"\blast chance\b", r"\bact now\b",
           r"\burgent\b", r"\basap\b", r"\blimited time\b"]
SALESY = [r"\brevolutionary\b", r"\bbest[- ]in[- ]class\b", r"\bgame[- ]chang", r"\bsynerg", r"\bcutting[- ]edge\b",
          r"\bstreamline\b", r"\bseamless(ly)?\b", r"\bturnkey\b", r"\bworld[- ]class\b", r"\bindustry[- ]leading\b",
          r"\b\d+x roi\b", r"\bguaranteed\b"]
OPT_OUT = r"\b(reply|respond|just say) ['\"“]?(no|not interested|stop|unsubscribe)|unsubscribe|opt[- ]out|won'?t (follow up|reach out|email) again|not relevant.{0,40}(let me know|reply)"


def split_email(text):
    m = re.match(r"\s*subject:\s*(.+)\n", text, re.IGNORECASE)
    if m:
        return m.group(1).strip(), text[m.end():].strip()
    return None, text.strip()


def words(s):
    return len(re.findall(r"[\w'’-]+", s))


def check_email(text, step, total):
    errors, warnings, info = [], [], []
    subject, body = split_email(text)
    lowered = body.lower()
    # Word count for the message itself: stop at the sign-off, and skip opt-out and placeholder lines.
    message_lines = []
    for ln in body.splitlines():
        if re.match(r"^\s*(best|thanks|thank you|cheers|regards|warmly|talk soon)\b[^.?!]{0,20}[,!]?\s*$", ln, re.IGNORECASE):
            break
        if re.search(OPT_OUT, ln.lower()) or re.match(r"^\s*\[[^\]]*\]\s*$", ln):
            continue
        message_lines.append(ln)
    lines_nonempty = [ln for ln in message_lines if ln.strip()]
    # drop a trailing name/company signature (short lines after the last sentence-ending line)
    while lines_nonempty and len(lines_nonempty[-1].split()) <= 4 and not re.search(r"[.?!]$", lines_nonempty[-1].strip()):
        lines_nonempty.pop()
    wc = words("\n".join(lines_nonempty))
    first = next((ln for ln in body.splitlines() if ln.strip() and not re.match(r"^(hi|hey|hello|dear)\b[^.!?]{0,30}[,!]?$", ln.strip(), re.I)), "")

    if subject is not None:
        sw = words(subject)
        if re.match(r"^(re|fwd?):", subject, re.IGNORECASE) and step == 1:
            errors.append(f"subject '{subject}': fake Re:/Fwd: on a first email is deceptive (and a CAN-SPAM problem)")
        if sw > 7:
            warnings.append(f"subject is {sw} words: 2-5 words open and get replies best")
        if subject.isupper() or re.search(r"!|\$\$|free\b", subject, re.IGNORECASE):
            warnings.append(f"subject '{subject}': caps, '!' or 'free' read as spam")
        if re.search(r"quick question", subject, re.IGNORECASE):
            warnings.append("'Quick question' subjects underperform (Hunter)")
    elif step == 1:
        info.append("no 'Subject:' line found; add one to check it")

    limit = 100 if step == 1 else 60
    if wc > limit + 20:
        warnings.append(f"{wc} words: aim for {'50-100' if step == 1 else '1-3 sentences'} ({'first email' if step == 1 else 'follow-up'})")
    elif step == 1 and wc > 100:
        info.append(f"{wc} words: under ~80-100 performs best, especially for senior readers")

    if first and re.match(r"^\s*(i|we|my|our)\b", first, re.IGNORECASE):
        warnings.append(f"first line starts with '{first.split()[0]}': make it about them, not you")
    for pat in WORN_OPENERS:
        for m in re.finditer(pat, lowered):
            warnings.append(f"'{body[m.start():m.end()]}': worn-out opener; spend the first line on them")
    if step > 1:
        for pat in WORN_FOLLOWUPS:
            for m in re.finditer(pat, lowered):
                warnings.append(f"'{body[m.start():m.end()]}': empty or guilt-trip follow-up; add a new angle instead")
    for pat in URGENCY:
        for m in re.finditer(pat, lowered):
            warnings.append(f"'{body[m.start():m.end()]}': false urgency")
    for pat in SALESY:
        for m in re.finditer(pat, lowered):
            warnings.append(f"'{body[m.start():m.end()]}': salesy/buzzword language cuts replies")

    links = re.findall(r"https?://\S+|www\.\S+", body)
    if len(links) > 1:
        warnings.append(f"{len(links)} links: at most one, ideally none in a first email")
    elif links and step == 1:
        info.append("link in first email: consider offering the resource instead ('Want me to send it?')")
    if re.search(r"calendly|cal\.com|hubspot\.com/meetings|savvycal|book a (time|slot|call)|grab (a|some) time on my calendar", lowered):
        warnings.append("calendar link or booking ask: presumes interest; ask an interest question first")
    if re.search(r"\battach(ed|ment)\b|\bsee (the )?attached\b", lowered):
        warnings.append("attachment: skip attachments in cold email (filters and trust)")
    if re.search(r"bit\.ly|tinyurl|t\.co/|ow\.ly", lowered):
        warnings.append("link shortener: hurts deliverability")
    if re.search(r"<img|\.png\b|\.jpg\b|!\[", body, re.IGNORECASE):
        warnings.append("image: plain text performs better")
    asks = len(re.findall(r"\?", body))
    if asks > 2:
        info.append(f"{asks} question marks: make sure there's one clear ask")

    if not re.search(OPT_OUT, lowered):
        (warnings if step == 1 else info).append("no opt-out line: add a plain one ('reply \"no\" and I won't follow up'); CAN-SPAM and others apply to every message, follow-ups included")

    for f in scan_ai_signs(body, exclude={"formatting", "rhythm"}):
        (warnings if f.severity == "warn" else info).append(
            f"'{f.excerpt}': {f.label} (ai-writing-signs §{f.section}): {f.note}")

    return subject, wc, errors, warnings, info


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    raw = open(args[0], encoding="utf-8").read() if args else sys.stdin.read()

    if "--linkedin-note" in sys.argv:
        note = raw.strip()
        n = len(note)
        print(f"== LinkedIn connection note: {n}/{NOTE_LIMIT} characters ==")
        problems = []
        if n > NOTE_LIMIT:
            problems.append(f"ERROR: over {NOTE_LIMIT} characters (free accounts)")
        if re.search(r"https?://|www\.", note):
            problems.append("WARN: no links in a connection note")
        if re.search(r"\b(demo|pricing|our (product|platform|solution)|book a call|15 minutes)\b", note, re.IGNORECASE):
            problems.append("WARN: reads like a pitch; give one reason to connect that's about them")
        print("\n".join("  " + p for p in problems) or "  ok")
        return 1 if n > NOTE_LIMIT else 0

    parts = [p.strip() for p in re.split(r"^\s*---\s*$", raw, flags=re.MULTILINE) if p.strip()] if "--sequence" in sys.argv else [raw]
    any_error = False
    print(f"== Outreach check ({'sequence of ' + str(len(parts)) if len(parts) > 1 else 'single email'}) ==")
    if len(parts) > 5:
        print("  WARN: more than 5 touches sharply raises unsubscribes and complaints")
    for i, part in enumerate(parts, 1):
        subject, wc, errors, warnings, info = check_email(part, i, len(parts))
        any_error = any_error or bool(errors)
        label = f"email {i}" if len(parts) > 1 else "email"
        print(f"\n-- {label}: {wc} words in the message (sign-off and footer excluded)" + (f" | subject: '{subject}' ({words(subject)} words)" if subject else "") + " --")
        for tag, items in (("ERROR", errors), ("WARN", warnings), ("INFO", info)):
            for item in items:
                print(f"  {tag}: {item}")
        if not (errors or warnings or info):
            print("  ok")
    placeholders = re.findall(r"\[[^\]\n]{2,150}\]", raw)
    if placeholders:
        print(f"\nplaceholders to verify: {', '.join(sorted(set(placeholders)))}")
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
