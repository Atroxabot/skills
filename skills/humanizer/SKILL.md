---
name: humanizer
description: Edits text so it reads like a specific person wrote it. Finds and fixes the patterns that mark writing as AI-generated, using a field guide to the common signs (inflated significance, vague attributions, promotional tone, AI vocabulary, "it's not X, it's Y" parallelisms, rule-of-three lists, monotone rhythm, bold-header bullets, chatbot residue), while keeping the author's facts and voice. Use whenever the user asks to humanize text, make it sound less like AI, ChatGPT, robotic or generic, remove AI tells or "AI slop", asks whether a draft sounds AI-written, or wants a final human pass on a post, email, bio, newsletter, landing page or blog draft. Use it also as the last step for drafts produced by other writing skills. Never adds invented details.
---

# Humanizer

Edit text so it reads like a particular person wrote it: specific, plainly worded, uneven in the way real writing is, and free of the patterns readers now recognize as machine-written.

The catalog behind this skill is [references/ai-writing-signs.md](references/ai-writing-signs.md). It's compiled from Wikipedia's "Signs of AI writing" project, 2023–2026 research on model style, and editing practice. It isn't exhaustive, because the signs change with each model generation. Read it before your first edit in a conversation. It's organized by section number, and the scanner's output points to those numbers.

## The principle: fix causes, not symptoms

AI text regresses to the mean. Specific, unusual facts get smoothed into generic, positive, important-sounding statements, so the text becomes less specific and more exaggerated at the same time. Every surface sign (the vocabulary, the parallelisms, the triplets) is a symptom of that.

So the job is not swapping words. "This underscores the enduring importance of community" is not fixed by "This shows the lasting importance of community." It's fixed by replacing the sentence with the fact it was gesturing at ("Forty neighbours turned up to rebuild the fence"), or by deleting it. Wikipedia's editors warn that only treating the surface signs "could just make detection harder." It also leaves the writing just as empty.

This skill is about writing quality and the author's voice. It isn't a tool for beating AI detectors. Those detectors are unreliable in both directions, and their verdicts are not the target.

## Workflow

### 1. Read for what's real

Before changing anything, find the parts worth keeping:
- **Facts:** names, numbers, dates, events, quotes.
- **The author's actual opinions.**
- **Their voice markers:** pet phrases, humor, how long or short they write, whether they swear, their punctuation habits.

If there's a voice card or style guide (for example a `voice-profile.md` in the working directory, or one the user pastes), read it. It's the best voice reference you'll have. If it lists catalog patterns the author really uses, leave those signs alone. If the user has shared other writing of theirs, use that too. **The author's own sample beats every rule in the catalog.** A sample means text the author wrote themselves. The draft you're fixing doesn't count if a model wrote it, so its em dashes or triplets aren't "their style." Two more points about samples:
- **Copy the voice, not the stock moves.** Copy their rhythm, punctuation, humor and vocabulary. If the sample itself leans on a catalog tic ("here's what nobody tells you:"), the author may keep their habit, but don't multiply it.
- **Facts in the author's own sample are real.** You can draw on them, for example with a callback to an earlier story, as long as you use them accurately. Flag the callback if you're unsure it fits. If they use em dashes, rhetorical questions or long sentences, so does the revision.

Also protect the things that look odd but are the most human parts of the text. Don't "fix" these:
- a strangely specific detail
- mixed or unresolved feelings
- a dated or niche reference
- a genuine aside
- a deliberately rough phrase
- technical precision

Make it plainer only where it was vague, never less accurate.

These must survive the edit.

### 2. Diagnose

Go through the text against the catalog, in this order of importance:

1. **Content** (catalog section 1): inflated significance, coverage-bragging, trailing "-ing" analysis, promotional tone, vague association, vague attribution, the "despite challenges" formula, hedging disclaimers. These are the real problems.
2. **Language** (section 2): AI vocabulary density, avoiding "is"/"has," negative parallelisms, rule-of-three lists, elegant variation, monotone rhythm.
3. **Formatting** (section 3): Title Case headings, bold everywhere, `**Label:**` bullets, emoji bullets, needless tables, em-dash habits, markdown where it won't render.
4. **Residue** (sections 4 and 6): "Certainly!", "I hope this helps," unfilled placeholders, "It's important to note," "In conclusion."
5. **Social patterns** (section 8), if it's a post: stock lines, broetry, engagement bait.

If you can run code, `python3 scripts/ai_signs.py draft.txt` gives you a first pass with line numbers. Pipe the text on stdin if it isn't in a file. The scanner catches word- and pattern-level signs. It cannot judge content signs well, so read for those yourself.

Look for clusters, not single words. One "crucial" is fine; a paragraph with five catalog hits is the problem. Weight structure over vocabulary. Word habits change with every model release, while the shapes persist:
- the not-X-but-Y frame
- the "this matters" frame
- the triplet
- the tidy announce-list-recap structure
- the quotable closer
- the even beat

### 3. Rewrite

Work sentence by sentence, fixing the cause:

| Sign | Fix |
|---|---|
| Inflated significance, legacy, "pivotal moment" | State what happened. Show significance with a fact, or cut. |
| Trailing "-ing" analysis | Delete the clause. A real interpretation becomes its own sentence. |
| Promotional adjectives | Replace with what the thing has, does or costs. |
| Vague attribution ("experts say") | Name the source the user gave, own the opinion, or cut. Never invent a source. |
| "Serves as," "boasts," "features" | Use "is" and "has." |
| "It's not X, it's Y" and its family | Say what it is. Keep a contrast only if readers really believe X, and name that belief. |
| Rule-of-three lists | Keep the item that matters, or make the items concrete and uneven. |
| AI vocabulary | Use a plain word, or better, a fact. Don't swap in a fancier synonym. |
| Monotone rhythm | Vary sentence length on purpose. Allow a fragment, a long sentence, a question, a colon. |
| Bold, bold-label bullets, emoji bullets | Use prose, or a plain list. Emphasis comes from the sentence. |
| Chatbot residue, summaries, disclaimers | Delete. |

If the draft has almost no real content (pure filler around one or two facts), say so plainly. A short, true draft plus two or three questions that would unlock the real story is better than a lively version built on invented experiences. In testing, a version without this skill invented a whole year of mishaps for the author. It read well, and it was fiction.

When removing vagueness leaves a hole (the sentence said "a pivotal moment" and you don't know why it mattered), don't fill it with an invented detail. Ask the user, or leave a clearly marked `[what changed after this?]` placeholder. Use at most two or three placeholders. If more are needed, cut the sentences instead and list your questions.

### 4. Don't over-correct

Over-polished text is its own tell, and so is a new uniform habit. A 2026 public blind test of a popular Wikipedia-based humanizer found it removed AI vocabulary and dashes but made rhythm more uniform and added *more* aphoristic one-line closers. Every tell left in its output was rhythmic. Watch for:

- **Swapping one tic for another.** Replacing every em dash with a period gives a comma-and-period monotone, which is the newest AI signature. Turning every "delve" into "dig into" is the same tic.
- **Stripping the author's voice.** Keep their quirks, their slang, a long sentence that works, an occasional "very" or "in order to." Human writing isn't perfectly concise.
- **Flattening everything to short sentences.** Short isn't the goal; variety is.
- **Cutting real contrast or real lists.** If a list genuinely has three items, it can stay.
- **"Fixing" things that aren't signs.** Perfect grammar, formality, mixed registers and plain transition words are not evidence of AI (catalog section 7).
- **Faking human cues.** Don't add "I", feelings, family mentions or an anecdote to make text seem human. Readers do take these as signs of a human author, which is exactly why adding them misleads. An opinion or reaction the author actually holds is fine; a fact they didn't give is not (catalog 9.6).

### 5. Check

- Re-run the scanner, or re-read against the catalog. Make sure you haven't introduced new patterns.
- Check the two things rewrites most often add: a **uniform beat** (sentences or paragraphs of similar length, one after another) and **quotable closers** (a short, deep-sounding last line on a paragraph or the piece).
- Compare meaning with the original: same facts, same claims, nothing added.
- Read it aloud. It should sound like the author talking to someone they respect, with no metronome beat.
- Length usually shrinks. If it grew, you probably added filler.

## Output

Return:

1. **The revised text**, ready to use, in the format of its destination (plain text for social posts and email; markdown only where it renders). Put it in a code block when the line breaks matter.
2. **What changed**, in three to six bullets grouped by pattern, quoting a before → after for the most important ones. Keep it short. The user wants the text, not an essay.
3. **Questions or placeholders**, if any facts are missing.

For text that matters (a post under the author's name, an important email), suggest the author make the last pass in their own words. Studies of AI-assisted writing find that edited drafts stay closer to the model's style than people realize. The author's own final touches are what make it theirs.

If the user only asks "does this sound like AI?", give a diagnosis:
- the patterns found, quoting the lines, with the most important first
- an honest overall read

Then offer to revise. Don't claim certainty either way: style alone can't prove authorship.

For long documents, revise in sections. Keep the author's structure unless the structure itself is the problem (for example, bold-header bullets that should be prose).

## Working with other writing skills

Platform writing skills often run a short tell checklist in their own editing step. Use this skill when:
- the user asks for a humanizing pass on its own
- the text isn't a social post (emails, bios, blog drafts, newsletters, product copy)
- the user wants a deeper edit than another skill's checklist

## References

- [references/ai-writing-signs.md](references/ai-writing-signs.md): the full catalog, with what to watch for, examples and fixes. Read it before editing.
- `scripts/ai_signs.py`: the pattern scanner. Run it on any text file or on stdin.
