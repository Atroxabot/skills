#!/usr/bin/env python3
"""Mechanical checks for a LinkedIn post draft.

Usage:
    python3 lint_post.py draft.txt
    pbpaste | python3 lint_post.py

Reports length, the approximate "see more" preview, and warnings for
signs of AI writing (via ai_signs.py; see references/ai-writing-signs.md),
engagement bait, markdown leftovers, hashtags, emoji and
rhythm. Warnings are prompts to look again, not automatic rewrites.
Exits 1 only if the post exceeds LinkedIn's 3,000-character limit.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_signs import scan as scan_ai_signs  # noqa: E402  (same scanner as the humanizer skill)

MAX_CHARS = 3000
MOBILE_PREVIEW_CHARS, MOBILE_PREVIEW_LINES = 140, 3
DESKTOP_PREVIEW_CHARS, DESKTOP_PREVIEW_LINES = 210, 5
TARGET_CHARS = (900, 1800)

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF\U00002B00-\U00002BFF]"
)

ENGAGEMENT_BAIT = [
    r"\bcomment( with)? ['\"\u201c]\w+['\"\u201d]",
    r"\bcomment (yes|below)\b",
    r"\bcomment\b.{0,30}\band i'?ll (dm|send)\b",
    r"\b(like|repost|share) (this )?if\b",
    r"\brepost to\b",
    r"\btag (someone|a friend|3)\b",
    r"\bfollow (me )?for more\b",
    r"^\s*(agree|thoughts|what do you think)\s*\??\s*$",
]


def split_paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s.strip() for s in parts if re.search(r"[A-Za-z0-9]", s)]


def syllables(word):
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and count > 1 and not word.endswith("le"):
        count -= 1
    return max(count, 1)


def reading_grade(text):
    sentences = split_sentences(text)
    words = re.findall(r"[A-Za-z']+", text)
    if not sentences or not words:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return 0.39 * len(words) / len(sentences) + 11.8 * syl / len(words) - 15.59


def preview(text, max_chars, max_lines):
    lines = text.split("\n")
    shown = "\n".join(lines[:max_lines])
    if len(shown) > max_chars:
        shown = shown[:max_chars]
    return shown


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()
    text = text.strip("\n")

    errors, warnings, info = [], [], []
    chars = len(text)
    words = re.findall(r"\b[\w'’-]+\b", text)
    paragraphs = split_paragraphs(text)
    sentences = split_sentences(text)
    first_line = text.split("\n", 1)[0].strip()

    # Length
    if chars > MAX_CHARS:
        errors.append(f"{chars} characters: over LinkedIn's {MAX_CHARS} limit")
    elif len(words) < 100:
        warnings.append(f"only {len(words)} words: posts under 100 words underperform in every format")
    elif not TARGET_CHARS[0] <= chars <= TARGET_CHARS[1]:
        info.append(f"{chars} characters: outside the usual {TARGET_CHARS[0]}-{TARGET_CHARS[1]} range (fine if intentional)")

    # Hook
    if len(first_line) > MOBILE_PREVIEW_CHARS:
        warnings.append(f"first line is {len(first_line)} chars: it won't fit the ~{MOBILE_PREVIEW_CHARS}-char mobile preview")
    elif len(first_line) > 60:
        info.append(f"first line is {len(first_line)} chars: first lines under ~40 chars perform best")
    if first_line.endswith("?"):
        info.append("hook is a question: claims and story openers outperform question hooks")
    mobile = preview(text, MOBILE_PREVIEW_CHARS, MOBILE_PREVIEW_LINES)
    if mobile.count("\n\n") >= 1 and len(mobile.replace("\n", "")) < 80:
        info.append("blank lines use most of the mobile preview: consider tightening the first lines")

    # Voice
    lowered = text.lower()
    # Blank out hashtag-only lines (keeping line numbers) so a hashtag block isn't read as a closing line.
    prose = re.sub(r"^[ \t]*(#\w+[ \t]*)+$", "", text, flags=re.MULTILINE)
    for f in scan_ai_signs(prose, exclude={"formatting"}):
        (warnings if f.severity == "warn" else info).append(
            f"line {f.line}: '{f.excerpt}': {f.label} (ai-writing-signs §{f.section}): {f.note}")
    for pattern in ENGAGEMENT_BAIT:
        for m in re.finditer(pattern, lowered, flags=re.MULTILINE):
            warnings.append(f"'{text[m.start():m.end()].strip()[:60]}': engagement bait (LinkedIn demotes this)")

    # Rhythm
    if len(paragraphs) >= 8:
        single = sum(1 for p in paragraphs if len(split_sentences(p)) == 1)
        if single / len(paragraphs) > 0.8:
            warnings.append(f"{single}/{len(paragraphs)} paragraphs are single sentences: vary the rhythm (broetry reads as fake-deep and AI)")
    for p in paragraphs:
        if len(p) > 350:
            info.append(f"long paragraph ({len(p)} chars) starting '{p[:40]}...': split for mobile")
    long_sents = [s for s in sentences if len(s.split()) > 25]
    for s in long_sents:
        info.append(f"long sentence ({len(s.split())} words): '{s[:50]}...'")
    grade = reading_grade(text)
    if grade > 8:
        warnings.append(f"reading grade ~{grade:.1f}: aim for 3-6; shorter sentences and plainer words")

    # Formatting
    if re.search(r"\*\*[^*]+\*\*|__[^_]+__", text):
        warnings.append("markdown bold (** or __): LinkedIn shows the symbols literally")
    if re.search(r"^#{1,6}\s", text, flags=re.MULTILINE):
        warnings.append("markdown heading (#): LinkedIn shows the symbols literally")
    if re.search(r"\[[^\]]+\]\(https?://", text):
        warnings.append("markdown link: paste the bare URL (or put it in the first comment)")
    hashtags = re.findall(r"(?<!\w)#\w+", text)
    if len(hashtags) > 3:
        warnings.append(f"{len(hashtags)} hashtags: use 0-3; posts without hashtags do slightly better")
    elif hashtags:
        info.append(f"{len(hashtags)} hashtag(s): optional; zero is the default")
    emoji = EMOJI_RE.findall(text)
    if len(emoji) > 1:
        warnings.append(f"{len(emoji)} emoji: one at most; more adds nothing and reads as decoration")
    if re.search(r"^\s*" + EMOJI_RE.pattern, text, flags=re.MULTILINE):
        warnings.append("emoji used as bullets: reads as template/AI; use numbers or plain lines")
    links = re.findall(r"https?://\S+", text)
    if links:
        info.append(f"{len(links)} link(s) in the body: evidence on link penalties is mixed; consider the first comment")
    mentions = re.findall(r"(?<!\w)@\w+", text)
    if len(mentions) > 3:
        warnings.append(f"{len(mentions)} tags: only tag people who are part of the story")

    placeholders = re.findall(r"\[[^\]\n]{2,150}\]", text)

    # Report
    print("== LinkedIn post check ==")
    print(f"characters: {chars}/{MAX_CHARS} | words: {len(words)} | paragraphs: {len(paragraphs)} | reading grade: ~{grade:.1f}")
    print(f"first line: {len(first_line)} chars")
    print("\n-- mobile preview (approx., before 'see more') --")
    print(mobile + " ...see more")
    print("\n-- desktop preview (approx.) --")
    print(preview(text, DESKTOP_PREVIEW_CHARS, DESKTOP_PREVIEW_LINES) + " ...see more")
    if placeholders:
        print(f"\nplaceholders to fill: {', '.join(placeholders)}")
    for label, items in (("ERROR", errors), ("WARN", warnings), ("INFO", info)):
        if items:
            print(f"\n{label}:")
            for item in items:
                print(f"  - {item}")
    if not (errors or warnings):
        print("\nNo warnings.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
