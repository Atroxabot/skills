#!/usr/bin/env python3
"""Check a batch of repurposed pieces, each against its own platform.

Usage:
    python3 check_pieces.py pieces.txt
    python3 check_pieces.py pieces.txt --source source.txt
    pbpaste | python3 check_pieces.py

Put each piece under a header line naming its platform, optionally with a label:

    === linkedin ===
    === x-thread: the pricing thread ===

Separate the posts of a thread or the slides of a carousel with a line holding
only `---`. Platforms: linkedin, x, x-thread, x-premium, threads, bluesky,
instagram, carousel, video.

Per piece: length counted the way each platform counts it, the hook preview,
hashtags, links, leftovers from other platforms, engagement bait, markdown, and
signs of AI writing (via ai_signs.py; see references/ai-writing-signs.md).
Across pieces: reused hooks, closers and hashtag blocks, and sentences copied
word for word. With --source: numbers that aren't in the source, and quoted
text that isn't verbatim.

Warnings are prompts to look again, not automatic rewrites. Exits 1 if a piece
is over a hard limit or a header names an unknown platform.
"""

import os
import re
import sys
import unicodedata
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_signs import scan as scan_ai_signs  # noqa: E402  (same scanner as the humanizer skill)

# limit: hard limit per post; count: how the platform counts; tags: hashtag ceiling
# (per post on X, Threads and Bluesky, per piece elsewhere); preview: characters
# shown before the cut.
PLATFORMS = {
    "linkedin": dict(limit=3000, count="chars", tags=3, preview=140),
    "x": dict(limit=280, count="x", tags=1),
    "x-premium": dict(limit=25000, count="x", tags=1),
    "threads": dict(limit=500, count="threads", tags=1),
    "bluesky": dict(limit=300, count="bluesky", tags=2),
    "instagram": dict(limit=2200, count="chars", tags=5, preview=125),
    "carousel": dict(),
    "video": dict(),
}
ALIASES = {
    "li": "linkedin", "linkedin-post": "linkedin", "twitter": "x", "x-post": "x", "x-thread": "x",
    "tweet": "x", "thread": "x", "ig": "instagram", "instagram-caption": "instagram",
    "linkedin-carousel": "carousel", "instagram-carousel": "carousel", "slides": "carousel",
    "reel": "video", "reels": "video", "tiktok": "video", "shorts": "video", "short": "video",
    "short-video": "video", "script": "video",
}

# (pattern, platforms where it belongs, message). Everywhere else it's a leftover.
LEFTOVERS = [
    (r"\blink in (my |the )?bio\b", {"instagram", "video"}, "'link in bio' only works on Instagram and TikTok"),
    (r"\b(re-?tweet(s|ed)?|quote[- ]tweet|rt)\b|🧵", {"x", "x-premium"}, "X-only wording; say 'repost' or 'quote', or cut it"),
    (r"\bsee more\b", {"linkedin"}, "'see more' is LinkedIn's cut"),
    (r"\blink in (the )?(first )?comments?\b", {"linkedin"}, "'link in the comments' is a LinkedIn habit; link in the body (X, Bluesky) or the bio (Instagram)"),
    (r"\bswipe\b", {"carousel", "instagram", "linkedin"}, "'swipe' only makes sense on a carousel"),
    (r"\b(like and subscribe|hit (the )?subscribe|subscribe to (my|our|the) channel)\b", {"video"}, "a video call to action"),
]
BAIT = [
    r"\b(comment|reply)( with)? ['\"“]\w+['\"”]",
    r"\b(comment|reply) (yes|below)\b",
    r"\b(comment|reply)\b.{0,30}\band i'?ll (dm|send)\b",
    r"\b(like|repost|retweet|share) (this )?if\b",
    r"\brepost to\b",
    r"\btag (someone|a friend|\d)\b",
    r"\bfollow (me )?for more\b",
    r"^\s*(agree|thoughts|what do you think)\s*\??\s*(👇)?\s*$",
]
SPOKEN_LABEL = re.compile(r"^\s*(vo|v/o|voice ?over|narration|narrator|say|spoken|audio|host|speaker)\s*:", re.IGNORECASE)
NON_SPOKEN = re.compile(
    r"^\s*([\[(#]|(on[- ]screen|text|visual|b-?roll|shot|scene|caption|cut|sfx|music|overlay)\b[^:]{0,20}:|\d{1,2}:\d{2})",
    re.IGNORECASE)
FILLERS = {"um", "uh", "erm", "er", "ah", "uhm", "hmm", "mm"}
HASHTAG_RE = re.compile(r"(?<![\w&#])#\w*[A-Za-z]\w*")
URL_RE = re.compile(
    r"https?://\S+|\b(?:www\.)?[a-z0-9-]+\.(?:com|org|net|io|co|ai|dev|app|xyz|me|so|gg|ly|news)\b(?:/\S*)?",
    re.IGNORECASE)

# Character counting. X follows twitter-text v3: most characters count 1, emoji and
# CJK count 2, every URL counts 23.
LIGHT_RANGES = [(0, 4351), (8192, 8205), (8208, 8223), (8242, 8247)]
EMOJI_BASE = "[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌀-⏿]"
EMOJI_MOD = "[️⃣\U0001F3FB-\U0001F3FF\U000E0020-\U000E007F]*"
EMOJI_RE = re.compile(
    "[\U0001F1E6-\U0001F1FF]{2}|" + EMOJI_BASE + EMOJI_MOD + "(?:‍" + EMOJI_BASE + EMOJI_MOD + ")*")


def x_length(text):
    text = unicodedata.normalize("NFC", text)
    spans = sorted([(m.start(), m.end(), 23) for m in URL_RE.finditer(text)]
                   + [(m.start(), m.end(), 2) for m in EMOJI_RE.finditer(text)])
    total, i = 0, 0
    weight = lambda s: sum(1 if any(lo <= ord(c) <= hi for lo, hi in LIGHT_RANGES) else 2 for c in s)
    for start, end, w in spans:
        if start < i:
            continue
        total += weight(text[i:start]) + w
        i = end
    return total + weight(text[i:])


def threads_length(text):
    """Threads API rule: emoji count as their UTF-8 bytes; everything else counts 1."""
    total, i = 0, 0
    for m in EMOJI_RE.finditer(text):
        total += len(text[i:m.start()]) + len(m.group(0).encode("utf-8"))
        i = m.end()
    return total + len(text[i:])


def graphemes(text):
    """Approximate count of user-perceived characters (joins marks, ZWJ sequences, flags)."""
    count, prev_zwj, pending_ri = 0, False, False
    for ch in unicodedata.normalize("NFC", text):
        cp = ord(ch)
        joins = (unicodedata.category(ch) in ("Mn", "Me", "Mc") or cp in (0xFE0E, 0xFE0F, 0x20E3, 0x200D)
                 or 0x1F3FB <= cp <= 0x1F3FF or 0xE0020 <= cp <= 0xE007F or prev_zwj)
        if 0x1F1E6 <= cp <= 0x1F1FF:
            joins = joins or pending_ri
            pending_ri = not pending_ri if not joins else False
        else:
            pending_ri = False
        count += not joins
        prev_zwj = cp == 0x200D
    return count


def bluesky_length(text):
    """The Bluesky app shortens links to host + up to 13 path characters + '...'."""
    def short(m):
        try:
            u = urlsplit(m.group(0))
        except ValueError:
            return m.group(0)
        path = ("" if u.path == "/" else u.path) + ("?" + u.query if u.query else "") + ("#" + u.fragment if u.fragment else "")
        return u.netloc + (path[:13] + "..." if len(path) > 15 else path)
    return graphemes(re.sub(r"https?://\S+", short, text))


COUNTERS = {"chars": len, "x": x_length, "threads": threads_length, "bluesky": bluesky_length}
UNITS = {"chars": "characters", "x": "weighted characters", "threads": "characters (emoji as bytes)",
         "bluesky": "graphemes"}


def norm(text):
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[^\w\s']", " ", text)
    return " ".join(w for w in text.split() if w not in FILLERS)


def first_line(text):
    return next((ln.strip() for ln in text.splitlines() if ln.strip()), "")


def last_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not re.fullmatch(r"(#\w+\s*)+", ln.strip())]
    return lines[-1] if lines else ""


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def numbers(text):
    """Numeric values in text, as floats, ignoring timestamps and thread counters like 2/5."""
    text = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b|\b\d+/\d*(?=\s|$)", " ", text)
    found = []
    for m in re.finditer(r"(?<![\w.])[$€£]?(\d[\d,]*(?:\.\d+)?)\s?(k|m|bn|b|million|billion|thousand)?\b", text, re.IGNORECASE):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}
        found.append((m.group(0).strip(), value * mult.get((m.group(2) or "").lower(), 1)))
    return found


def parse(raw):
    pieces, current = [], None
    for line in raw.splitlines():
        m = re.match(r"^\s*===\s*([\w-]+)\s*(?::\s*(.*?))?\s*===\s*$", line)
        if m:
            current = {"name": m.group(1).lower(), "label": m.group(2) or "", "lines": []}
            pieces.append(current)
        elif current is not None:
            current["lines"].append(line)
    if not pieces and raw.strip():
        sys.exit("No '=== platform ===' header found. Put each piece under a header line, e.g. '=== linkedin ==='.")
    for p in pieces:
        p["platform"] = ALIASES.get(p["name"], p["name"])
        body = "\n".join(p["lines"]).strip("\n")
        p["parts"] = [s.strip("\n") for s in re.split(r"^\s*---\s*$", body, flags=re.MULTILINE) if s.strip()]
        p["text"] = "\n\n".join(p["parts"])
    return pieces


def check_piece(p):
    errors, warnings, info = [], [], []
    plat, text, parts = p["platform"], p["text"], p["parts"]
    spec = PLATFORMS[plat]
    lowered = text.lower()
    summary = ""

    if "limit" in spec:
        counter = COUNTERS[spec["count"]]
        posts = parts if plat in ("x", "x-premium", "threads", "bluesky") else ["\n\n".join(parts)]
        lengths = [counter(t) for t in posts]
        for i, n in enumerate(lengths, 1):
            where = f"post {i}: " if len(posts) > 1 else ""
            if n > spec["limit"]:
                hint = " (use x-premium if this is a Premium long post)" if plat == "x" else ""
                errors.append(f"{where}{n} {UNITS[spec['count']]}: over the {spec['limit']:,} limit{hint}")
            tags = HASHTAG_RE.findall(posts[i - 1])
            if plat != "instagram" and len(tags) > spec["tags"]:
                warnings.append(f"{where}{len(tags)} hashtags: {spec['tags']} at most on {plat}")
        summary = (f"{len(posts)} posts, longest {max(lengths):,}/{spec['limit']:,} {UNITS[spec['count']]}"
                   if len(posts) > 1 else f"{lengths[0]:,}/{spec['limit']:,} {UNITS[spec['count']]}")
        if plat == "x-premium" and lengths[0] > 280:
            info.append("long post: only the first ~280 characters show before 'Show more'; they must stand alone")
        if plat in ("x", "x-premium") and len(posts) > 1 and URL_RE.search(posts[0]):
            info.append("link in the first post of a thread: links usually go in the last post")
        if plat == "bluesky":
            info.append("Bluesky posts can't be edited after posting: proofread")

    if plat == "linkedin":
        hook = first_line(text)
        if len(hook) > spec["preview"]:
            warnings.append(f"first line is {len(hook)} characters: the mobile preview shows about {spec['preview']}")
        if len(re.findall(r"[\w'’-]+", text)) < 100:
            info.append("under 100 words: LinkedIn posts this short underperform unless the point is very sharp")
        if URL_RE.search(text):
            info.append("link in the body: if reach matters, put it in the first comment")
    if plat == "instagram":
        hook = first_line(text)
        if len(hook) > spec["preview"]:
            info.append(f"first line is {len(hook)} characters: about {spec['preview']} show before 'more'")
        tags = HASHTAG_RE.findall(text)
        if len(tags) > 5:
            errors.append(f"{len(tags)} hashtags: Instagram caps a post at 5 (caption and comments together)")
        if URL_RE.search(text):
            warnings.append("link in the caption: Instagram captions don't link; point to the bio or a DM")
    if plat == "carousel":
        n = len(parts)
        summary = f"{n} slides"
        if n > 20:
            warnings.append(f"{n} slides: Instagram carousels hold 20 (LinkedIn documents allow more)")
        elif not 5 <= n <= 15:
            info.append(f"{n} slides: 8-12 is the usual sweet spot")
        for i, s in enumerate(parts, 1):
            wc = len(re.findall(r"[\w'’-]+", s))
            if wc > 50:
                info.append(f"slide {i}: {wc} words; keep slides under ~50 so they read on a phone")
        if URL_RE.search(text):
            info.append("link on a slide: links inside a PDF carousel don't work")
    if plat == "video":
        lines = [ln for ln in text.splitlines() if ln.strip()]
        labeled = [SPOKEN_LABEL.sub("", ln) for ln in lines if SPOKEN_LABEL.match(ln)]
        spoken = labeled or [ln for ln in lines if not NON_SPOKEN.match(ln)]
        wc = len(re.findall(r"[\w'’-]+", " ".join(spoken)))
        lo, hi = wc / 3.0, wc / 2.5
        summary = f"~{wc} spoken words, about {lo:.0f}-{hi:.0f} s at 150-180 words a minute"
        if lo > 180:
            warnings.append("over 3 minutes: Reels and Shorts are recommended only up to 3 minutes")
        elif hi > 60:
            info.append("over 60 s: under a minute fits every short-video platform")

    for pattern, home, message in LEFTOVERS:
        if plat in home:
            continue
        for m in re.finditer(pattern, lowered):
            warnings.append(f"'{text[m.start():m.end()]}': leftover from another platform ({message})")
    bait_spans = []
    for pattern in BAIT:
        for m in re.finditer(pattern, lowered, flags=re.MULTILINE):
            if any(s <= m.start() < e or m.start() <= s < m.end() for s, e in bait_spans):
                continue  # the same phrase caught by an overlapping pattern
            bait_spans.append((m.start(), m.end()))
            warnings.append(f"'{text[m.start():m.end()].strip()[:60]}': engagement bait; platforms demote it")
    if plat not in ("carousel", "video"):
        if re.search(r"\*\*[^*\n]+\*\*|__[^_\n]+__|^#{1,6}\s|\[[^\]]+\]\(https?://", text, flags=re.MULTILINE):
            warnings.append("markdown (bold, heading or link syntax): social platforms show the symbols literally")
    handles = sorted(set(re.findall(r"(?<![\w.])@\w{2,}", text)))
    if handles:
        info.append(f"handles {', '.join(handles)}: check each one exists on {plat} and is the right account")

    prose = re.sub(r"^[ \t]*(#\w+[ \t]*)+$", "", text, flags=re.MULTILINE)
    weak = 0
    for f in scan_ai_signs(prose, exclude={"formatting"}):
        if f.severity == "warn":
            warnings.append(f"'{f.excerpt}': {f.label} (ai-writing-signs §{f.section}): {f.note}")
        else:
            weak += 1
    if weak:
        info.append(f"{weak} weak AI-writing signal(s): run scripts/ai_signs.py on this piece to see them")
    return summary, errors, warnings, info


def check_batch(pieces):
    warnings, info = [], []
    if len(pieces) < 2:
        return warnings, info

    def groups(key):
        seen = {}
        for i, p in enumerate(pieces, 1):
            k = key(p)
            if k:
                seen.setdefault(k, []).append(i)
        return {k: v for k, v in seen.items() if len(v) > 1}

    for k, idx in groups(lambda p: norm(first_line(p["parts"][0]))).items():
        warnings.append(f"pieces {', '.join(map(str, idx))} open with the same line ('{k[:50]}'): write a new hook for each platform")
    for k, idx in groups(lambda p: " ".join(norm(first_line(p["parts"][0])).split()[:3])).items():
        if len(idx) >= 3:
            info.append(f"pieces {', '.join(map(str, idx))} open with the same words ('{k}'): vary the openers")
    for k, idx in groups(lambda p: norm(last_line(p["parts"][-1]))).items():
        warnings.append(f"pieces {', '.join(map(str, idx))} end with the same line ('{k[:50]}'): vary the endings")
    closers = [last_line(p["parts"][-1]) for p in pieces if p["platform"] not in ("carousel", "video")]
    if len(closers) >= 3 and all(c.endswith("?") for c in closers):
        info.append("every piece ends on a question: one template repeated across the batch reads as mass-produced")
    for k, idx in groups(lambda p: " ".join(sorted(t.lower() for t in HASHTAG_RE.findall(p["text"])))
                         if len(HASHTAG_RE.findall(p["text"])) >= 2 else "").items():
        warnings.append(f"pieces {', '.join(map(str, idx))} share a hashtag block ({k}): never carry one platform's tags to another")
    copies = {}
    for i, p in enumerate(pieces, 1):
        for s in {norm(s) for s in sentences(p["text"]) if len(s.split()) >= 10}:
            copies.setdefault(s, set()).add(i)
    for s, idx in copies.items():
        if len(idx) > 1:
            info.append(f"sentence copied word for word into pieces {', '.join(map(str, sorted(idx)))} "
                        f"('{s[:60]}...'): adapt it to each platform rather than pasting")
    return warnings, info


def check_source(pieces, source):
    warnings, info = [], []
    known = [v for _, v in numbers(source)]
    src = norm(source)
    for i, p in enumerate(pieces, 1):
        missing = []
        for shown, value in numbers(p["text"]):
            if not any(abs(value - k) <= 1e-9 * max(1.0, abs(k)) for k in known) and shown not in missing:
                missing.append(shown)
        big = [s for s in missing if numbers(s) and numbers(s)[0][1] > 10]
        small = [s for s in missing if s not in big]
        if big:
            warnings.append(f"piece {i}: numbers not in the source: {', '.join(big)}; check each is in it or derived correctly")
        if small:
            info.append(f"piece {i}: small numbers not in the source: {', '.join(small)} (fine for counts like '3 lessons')")
        for m in re.finditer(r"[\"“]([^\"”\n]+)[\"”]", p["text"]):
            quote = m.group(1)
            if len(quote.split()) < 4:
                continue
            segments = [norm(s) for s in re.split(r"\.\.\.|…", quote) if len(norm(s).split()) >= 3]
            pos, ok = 0, True
            for seg in segments:
                at = src.find(seg, pos)
                if at < 0:
                    ok = False
                    break
                pos = at + len(seg)
            if segments and not ok:
                warnings.append(f"piece {i}: quoted text isn't verbatim in the source: \"{quote[:70]}\"; "
                                "quote exactly (minus filler) or paraphrase without quotation marks")
    return warnings, info


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source_path = None
    if "--source" in sys.argv:
        i = sys.argv.index("--source")
        if i + 1 >= len(sys.argv):
            sys.exit("--source needs a file path")
        source_path = sys.argv[i + 1]
        args = [a for a in args if a != source_path]
    raw = open(args[0], encoding="utf-8").read() if args else sys.stdin.read()
    pieces = parse(raw)

    any_error = False
    names = ", ".join(p["name"] for p in pieces)
    print(f"== Repurpose batch check: {len(pieces)} piece(s) ({names}) ==")
    for i, p in enumerate(pieces, 1):
        title = f"{i}. {p['name']}" + (f": {p['label']}" if p["label"] else "")
        if p["platform"] not in PLATFORMS:
            any_error = True
            print(f"\n-- {title} --\n  ERROR: unknown platform '{p['name']}' (use one of: {', '.join(PLATFORMS)}, x-thread)")
            continue
        if not p["parts"]:
            print(f"\n-- {title} --\n  WARN: empty piece")
            continue
        summary, errors, warnings, info = check_piece(p)
        any_error = any_error or bool(errors)
        print(f"\n-- {title}" + (f" | {summary}" if summary else "") + " --")
        for tag, items in (("ERROR", errors), ("WARN", warnings), ("INFO", info)):
            for item in items:
                print(f"  {tag}: {item}")
        if not (errors or warnings or info):
            print("  ok")

    valid = [p for p in pieces if p["platform"] in PLATFORMS and p["parts"]]
    sections = [("across the batch", check_batch(valid))]
    if source_path:
        with open(source_path, encoding="utf-8") as fh:
            sections.append(("against the source", check_source(valid, fh.read())))
    for title, (warnings, info) in sections:
        print(f"\n-- {title} --")
        for tag, items in (("WARN", warnings), ("INFO", info)):
            for item in items:
                print(f"  {tag}: {item}")
        if not (warnings or info):
            print("  ok")

    placeholders = sorted(set(re.findall(r"\[[^\]\n]{2,150}\]", raw)))
    if placeholders:
        print(f"\nplaceholders to fill or check: {', '.join(placeholders)}")
    return 1 if any_error else 0


if __name__ == "__main__":
    sys.exit(main())
