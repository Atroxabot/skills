---
name: repurpose
description: Turns one source (a blog post, newsletter, podcast or video transcript, talk, webinar, long thread, case study or report) into a set of platform-native pieces, such as LinkedIn posts and carousels, X posts and threads, Threads and Bluesky posts, Instagram captions and carousels, and short-video scripts. It finds the source's thesis and its strongest standalone ideas, matches each to the format that fits it, adapts every element per platform instead of copy-pasting, and plans the schedule. It follows the 2025–2026 platform originality rules and quotes guests accurately. Use whenever the user wants to repurpose, atomize, chop up, cross-post or "get more mileage" from content, turn a podcast, video, webinar, article or newsletter into social posts, build a content calendar from one piece, or adapt a post from one platform to another.
---

# Repurpose

Turn one strong source into several pieces that each work natively on their platform and each deliver one complete idea without a click. This isn't copying the same text everywhere.

The platform research behind this skill was done in October 2026. [references/adaptation.md](references/adaptation.md) and [references/policies.md](references/policies.md) have the details with dated sources.

## The rules that shape everything

- **Repurposing your own material is safe; copying isn't.**
  - Instagram, Facebook, YouTube and TikTok all define "original" as work you made, or that carries your own perspective. No platform penalizes the same *idea* appearing on several platforms.
  - What loses reach (mostly reach to non-followers, which is the point of repurposing):
    - another app's watermark on a video
    - re-uploading the same asset to the same platform
    - templated, mass-produced batches
    - other people's material with only cosmetic edits
- **Cosmetic changes don't count.** Platforms reject borders, subtitles, speed changes, your own watermark and a caption credit as "changes." Commentary, analysis, storytelling and new information count.
- **Adapt every element, not just the length:** hook, structure, tone, links, @handles, hashtags, call to action and format. Strip the leftovers: "link in bio" off anything but Instagram, "retweet" and 🧵 off anything but X, dead handles everywhere.
- **One complete idea per piece, delivered without a click.** This is Amanda Natividad's "zero-click content": platforms keep people in the app, so a piece that only teases a link reaches few people and helps fewer. The link, if any, is a bonus.
- **The source decides how many pieces,** not a quota. Ideas that already got a reaction deserve the most versions.

## Workflow

### 1. Read the source and the author

- Read the whole source. For transcripts, note who said what, and keep the timestamps.
- Check for a voice card or style guide (a `voice-profile.md` in the working directory, or one the user pastes). If one exists, every piece must sound like it. Either way, keep the author's signature phrases and real examples from the source: a distinctive speaker flattened into generic "content voice" is the most common repurposing failure.
- Ask which platforms the user actually uses, if they haven't said. Two or three done well beat six done badly.
- Know which account each piece posts from: the person's own profile or a brand account. It decides the pronouns ("I" or "we") and whose story it is. If the user hasn't said, default to the voice the source is written in, and state the assumption in the notes so they can swap it.

### 2. Find the thesis

Write the source's point in one sentence before cutting anything. Every piece should serve it, or at least not contradict it.

### 3. Take inventory of the atoms

List the standalone ideas in the source by type:

| Atom | Look for |
|---|---|
| Claims and opinions | especially contrarian ones, with the reasoning |
| Stories | who, when, where, what changed |
| Frameworks, steps, lists | anything with a sequence |
| Data points | with their original source |
| Quotable lines | verbatim, with a timestamp and the speaker |
| Mistakes and lessons | with the cost |
| Audience questions | what people asked, or will ask |
| Moments with energy | for video: a demo, a laugh, a reaction |

Test each atom:
- It stands alone: one idea, with a beginning, middle and end.
- It needs no "as I said earlier."
- It needs no context the reader lacks.

Rank the atoms by specificity, evidence, novelty and response (questions asked, comments, the moment the room reacted). Drop the weak ones.

### 4. Map atoms to formats

| Atom | Best fit |
|---|---|
| Sharp one-line claim | X post, Threads, Bluesky |
| Personal story with a lesson | LinkedIn post, Instagram caption |
| Framework, steps, checklist | LinkedIn carousel, Instagram carousel, X thread |
| Data point or chart | Image post with a one-line takeaway, a carousel slide (cite the source) |
| Moment with energy or a demo | Short-video clip or script |
| Strong quote | Quote card, Threads, X (verbatim, in the speaker's own words) |
| Contrarian argument with reasoning | LinkedIn post, X thread |

Skip any platform the source has nothing good for. Ten mediocre fragments from one template is exactly the "mass-produced" pattern platforms demote.

### 5. Write each piece natively

Apply each platform's rules. If the linkedin-post skill is installed (it shows in your list of available skills), follow its workflow for LinkedIn posts; it goes deeper on hooks and structure. For every other format, use the condensed per-platform guide in [references/adaptation.md](references/adaptation.md). Either way:

- **Write a new hook for each platform.** Never reuse one hook everywhere.
- **Cut, don't compress.** Pick fewer points rather than squeezing all of them in.
- **Match the platform's length, tone, links, hashtags and call to action** (the element-by-element table is in adaptation.md).
- **Keep the author's real details.** Never add claims, numbers or stories the source doesn't contain. Before pairing a "before" and an "after" number, check they measure the same thing ("400 orders to the wrong address" and "mis-picks down to 1 in 500" may not); if you can't tell, keep them apart and ask in the notes.
- **Write the parts the format needs.** A carousel caption frames slides, and a Reel caption frames a video. If those don't exist yet, write the slide copy or the script too, and list them under the visuals that still need making.
- **Video scripts:** label every spoken line with who says it (`VO:`, `PRIYA:`, `HOST (00:12:33):`) and every direction with what it is (`ON-SCREEN:`, `VISUAL:`, `B-ROLL:`), so the editor (and the checker below) can tell speech from directions. A script to record is timed by its words, at about 150–180 a minute; a clip cut from existing footage is timed by its in and out points.
- **Edit like a person wrote it.** Read [references/ai-writing-signs.md](references/ai-writing-signs.md) and fix causes, not words. A batch of pieces is especially prone to one template repeated across all of them (the same opener shape, the same closing question), so vary them on purpose. If the humanizer skill is installed, it does this pass in more depth.

### 6. Handle transcripts and other people's words

- **The author's own speech:** rewrite freely into prose in their voice. Keep distinctive phrasing; cut filler, repetition and tangents.
- **Guests and other speakers:** anything in quotation marks must be what they said. Removing "um" and false starts is fine; changing words, merging moments or reordering isn't. Quoting only part of a line with an ellipsis is fine when the meaning stays the same. Otherwise paraphrase without quotation marks and attribute by name.
- **Never present a guest's story or result as the author's.**
- **Permission:** a credit isn't permission. Clips and quote cards of another person's face, voice or words need it (a signed guest release, for example). You can draft them, but put the permission check first in the notes and say not to post until the user has confirmed it.
- **Garbled transcript at the key moment:** flag `[unclear at 14:32]`. Don't guess, and don't quote across the gap.
- **For every quote and clip,** give HH:MM:SS start and end times so it can be checked and cut. When the transcript has only start times, use the next line's start as the end and say so; when a clip starts partway through a line, give that line's time and the first words to cut in on.

### 7. Plan the schedule

- **Two orders both work:**
  - **Long first, then the pieces:** publish the source on a channel the author owns, then release the pieces over the following days.
  - **Small first, then expand:** test angles as short posts, then build the long version from what got traction.
- **Spread the pieces out.** Don't release everything on one day; pieces on the same platform compete with each other. LinkedIn does best at 2–4 posts a week, never more than one a day. For the hour, go by the user's own analytics; spacing matters more than the time of day, so don't invent precise "best times."
- **Later re-runs on the same platform:** rewrite the piece, don't repost it. LinkedIn demotes "recycled" posts, X limits copypasta, and Instagram demotes Reels it has already seen.
- **Video:** export clean files without another app's watermark. A Short downloaded from YouTube Studio carries one.

### 8. Check the batch

If you can run code, save the pieces in one file, each under a header line naming its platform (add a label after a colon when a platform has several pieces: `=== linkedin: post 2 ===`), and run:

```
python3 scripts/check_pieces.py pieces.txt --source source.txt
```

The file looks like this. Separate the posts of an X thread, a Threads chain or a Bluesky thread, or the slides of a carousel, with a line holding only `---`:

```
=== linkedin ===
[the post]
=== x-thread ===
[post 1]
---
[post 2]
=== instagram ===
[the caption]
```

Platform names: `linkedin`, `x` (`x-thread`, or `x-premium` for long posts), `threads`, `bluesky`, `instagram`, `carousel`, `video`.

It checks each piece against its platform's limit (counting characters the way each platform does), hashtag caps, links and leftovers from other platforms, and AI-writing signs outside quotations. For a video script it estimates the spoken length. Across the batch it flags reused hooks, closers and hashtag blocks, and sentences copied word for word between pieces. With `--source`, it lists numbers that don't appear in the source, quoted text that isn't verbatim or that joins separate moments, and, for a transcript, who said each quote and when, so you can check the attribution. These are the most common ways a repurposed piece drifts from the truth. It doesn't judge hooks or the first seconds of a video; read those yourself. Treat every hit as a reason to look again, not an automatic rewrite: a derived number ("doubled") can be fine.

## Output

Return:

1. **The thesis**, in one line.
2. **An atom inventory:** a short ranked list showing which atoms you used and which you skipped, with one-line reasons.
3. **The pieces,** grouped by platform. Each is ready to paste, in a code block, with its format and character or word count.
4. **A schedule:** a simple table of day, platform, piece and why.
5. **Notes:**
   - permissions to confirm, first, when the pieces use someone else's words, voice or face
   - quotes and clips with timestamps
   - `[placeholders]`
   - pieces that need visuals (carousel design, a video shoot)
   - the account assumption, if the user didn't say

If the user asks for one adaptation (for example "turn this LinkedIn post into a tweet"), skip the inventory and the schedule. Adapt the piece, and say what changed and why in two or three bullets.

## Final check

- [ ] Every piece delivers one complete idea without a click
- [ ] Every piece has its own hook, length, tone, call to action and tags for its platform
- [ ] No platform leftovers: "link in bio", "retweet", 🧵, dead @handles, the wrong hashtag block
- [ ] Nothing invented; guest quotes verbatim with timestamps; permissions flagged
- [ ] The pieces don't share one template, and the voice matches the author
- [ ] Spread out over time; no same-platform reposts

## References

- [references/adaptation.md](references/adaptation.md): platform limits, element-by-element adaptation rules, a condensed writing guide for each platform, and transcript handling. Read when writing the pieces.
- [references/policies.md](references/policies.md): each platform's originality, reuse and attribution rules, with dated sources (October 2026). Read when the source includes other people's material, or for policy questions.
- [references/ai-writing-signs.md](references/ai-writing-signs.md): the catalog of AI-writing patterns, with fixes. Read during the editing pass.
- `scripts/check_pieces.py`: the batch checker. It imports `scripts/ai_signs.py`, the AI-writing scanner, which also runs on its own.
