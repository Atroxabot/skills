---
name: linkedin-post
description: Writes, rewrites and critiques LinkedIn feed posts (text posts, optionally with one image) using researched hooks, proven post structures and LinkedIn's 2026 ranking rules, so the post earns the "see more" click, holds attention and draws real comments. Use whenever the user wants a LinkedIn post, whether they say "write a LinkedIn post about...", "turn this into a LinkedIn post", "make this LinkedIn-ready", "punch up my post", "give me hooks for LinkedIn", or just shares a win, lesson, story, announcement, article or notes they want to share professionally. Also use it to review a draft before it's posted. Not for LinkedIn articles, newsletters, profile About sections or DMs (use cold-outreach for those).
---

# LinkedIn Post Writer

Write LinkedIn feed posts that sound like a specific professional with something real to say, and that are built around how the feed decides who sees them.

The platform research behind this skill was done in October 2026. [references/platform.md](references/platform.md) has the data and dated sources. Platform mechanics change every few months; the writing principles below change much more slowly, so when the two conflict in a newer source, trust the newer source on mechanics and this skill on writing.

## What a post has to do

A LinkedIn post has three jobs, in order:

1. **Earn the "see more" click.** Only about 140 characters show on mobile (about 210 on desktop) before the cut, and most reading is on mobile. Everything the click depends on has to happen in the first one or two lines.
2. **Hold attention.** LinkedIn measures time spent on a post and demotes posts people scroll past. A post that pays off its hook keeps people reading; one that doesn't gets skipped and buried.
3. **Give people something to answer or keep.** Saves and thoughtful comments (and the author's replies to them) carry far more weight than likes.

Since March 2026 the feed matches posts to readers by meaning, using LLM embeddings, and LinkedIn says it is demoting engagement bait, recycled "click-driven" posts, and AI-sounding content that "lacks clear perspective." So the strategy that keeps working is a clear, specific, substantive post in the author's own voice, on a topic they post about consistently. Tricks lose value every quarter; substance gains it.

## Workflow

### 1. Get the raw material

Good posts are made of specifics: what happened, the numbers, who was involved, what the author believes and why. Before drafting, check that you have:

- **The one point** the post makes. If there are three points, there are three posts.
- **The proof:** the story, result, example, data or observation behind the point.
- **The reader:** who should stop scrolling for this ("first-time engineering managers", "B2B founders before Series A").
- **The goal:** reach new people (lean topical and actionable), deepen trust with the existing network (personal stories do well here), or point people at something (a launch, a hire, an event).
- **A voice card or style guide**, if one exists: a `voice-profile.md` in the working directory, or one the user pastes. Read it before drafting. It overrides generic style defaults (length, punctuation, emoji, sign-offs), but not platform limits or the honesty rules below. Facts it lists about the author are true material you can use.
- **Voice samples**, if there's no card but the user has past posts. Match their rhythm and vocabulary over any generic "LinkedIn style."

If something important is missing, ask one short round of questions. If the user wants a draft right away, write it and leave clearly marked `[placeholders]` for the missing facts. Keep placeholders to the two or three facts the post can't work without, because a draft that is mostly brackets isn't a draft. If more is missing, write the strongest version the real material supports and list the questions whose answers would improve it.

**Never invent the author's experience.** Don't make up anecdotes, clients, numbers, dialogue or results and present them as true. Invented stories are what LinkedIn readers mock most, they can embarrass the user in public, and LinkedIn demotes inauthentic content. Opinions, analysis and general knowledge are fair game. What must not be invented is personal fact: events, numbers, quotes, causes, other people's reactions. When you interpret the user's material ("that was the warning sign"), stay close to what they said and flag the line in your notes so they can check it. If the user gives only a topic, choose a structure that doesn't depend on personal claims (a framework, how-to, observation or contrarian take), or use placeholders like `[the client's result]`.

### 2. Choose the structure

Pick the archetype that fits the material and the goal. Skeletons and annotated examples for each are in [references/archetypes.md](references/archetypes.md). Read it when drafting.

| Material the user has | Archetype |
|---|---|
| Something happened that taught them something | Story → lesson |
| They disagree with common advice, with reasons | Contrarian take |
| A repeatable process or set of steps | How-to / listicle |
| A result after sustained effort | "I did X, here's what I learned" |
| A clear before and after | Transformation |
| Something went wrong | Mistake / failure |
| How their team actually does something | Behind the scenes |
| A mental model or method they use | Framework breakdown |
| A pattern they keep noticing | Observation |
| Numbers from their own work or research | Data / result |
| Someone else did something great | Celebrate others |
| An industry change they have a view on | News + take |

Topical, actionable posts (how-to, framework, data, contrarian, news + take) travel furthest to new audiences. Personal posts (story, failure, transformation) build trust with people who already follow the author. LinkedIn's own product team described the split this way in 2026.

When the material fits more than one archetype, pick the one that serves the goal. Archetypes also combine: an announcement (a raise, a launch, a new job) lands best inside a story → lesson or "I did X" post, so the news reaches the author's network and the lesson gives strangers a reason to read.

### 3. Write the hook

The hook is everything before "see more." Write it last if that helps, but give it the most effort, because it decides whether anything else gets read. Formulas with examples are in [references/hooks.md](references/hooks.md).

- **Finish the hook within about 140 characters.** That's what mobile shows: roughly two or three lines, and each blank line uses one of them. Check that the hook and the second line both land before the cut.
- **Keep line one short.** First lines under about 40 characters outperform long ones in large datasets.
- **Make a claim, not a question.** Story and contrarian openers beat question openers. Turn "Ever wonder why most startups fail at LinkedIn?" into "Most startups fail at LinkedIn for one reason."
- **Be specific.** A number, a name, a timeframe, an amount, a real stake. "I lost our biggest client in 11 minutes" beats "I learned a hard lesson about client relationships."
- **Open a loop, then raise it.** Line one creates tension; line two adds the context or stakes that make the click worth it.
- **Pay it off.** A hook the post doesn't deliver on wins the click, then loses the reading time and the reader's trust.

Write three hook options from different formulas, and lead with the strongest.

### 4. Write the body

- **One idea.** Everything in the post serves the single point.
- **Length:** about 900–1,800 characters (150–300 words) for most posts. Sharp observations can be 400–800. Posts under 100 words underperform in every format. The hard limit is 3,000. Never pad to hit a number: reading time only helps when the reading is worth it.
- **Short paragraphs** of one to three lines, with a blank line between them. Phone screens are narrow, and walls of text get skipped.
- **Vary the rhythm.** Mix one-line paragraphs with two- and three-sentence ones. A single sentence on every line ("broetry") reads as fake-deep, and it's one of the strongest machine tells.
- **Plain words.** Aim for roughly a 3rd–6th grade reading level and an average sentence under about 15 words. Write the way the author talks. Short on average, but not uniform: a run of same-length sentences is its own tell (current models write in a steady 8–20-word band).
- **Specifics over abstractions.** At least three concrete details: numbers, names, dates, tools, exact quotes, what it cost. Specifics make a post credible and memorable.
- **Show the cost.** What didn't work, what it took, the tradeoff. A post with no friction reads like a humblebrag or an ad. If the user hasn't told you the cost, ask for it in the notes instead of making one up.
- **Lists:** number steps that happen in order. Each item should be a concrete action or fact, not an abstract noun.

### 5. End well

- **Land the point in one line:** a takeaway, a TL;DR, or "Remember: ...".
- **Then, optionally, ask a specific question** readers can answer from their own experience. "What's the one question you always ask in reference checks?" earns comments. "Thoughts?" and "Agree?" don't: generic closing questions perform no better than no question.
- **Never ask for engagement.** No "comment YES," "like if you agree," "repost to help," or tagging people for attention. LinkedIn names these as engagement bait and demotes them.
- A **P.S.** line gets read. It's a good place for the question, a soft offer, or "link in the comments."

### 6. Edit like a person wrote it

Readers and LinkedIn's classifiers both punish posts that sound machine-written. In one 134K-post study, posts that read as AI-written got 22% less engagement than the same authors' other posts that year. Cut these on sight:

- **Reframe tics:** "It's not X, it's Y." / "X isn't about Y. It's about Z." This shape went from about 1% to about 6% of LinkedIn posts between 2023 and 2026, and readers now spot it.
- **Stock phrases:** "Here's the thing," "Let that sink in," "Read that again," "The result?", "Spoiler:", "game-changer," "unlock," "delve," "navigate the landscape," "in today's fast-paced world," "I'm humbled/thrilled to announce."
- **Triads of abstractions:** "clarity, focus, and impact." One concrete thing beats three vague ones.
- **Emoji bullets** (🚀 ✅ 💡) and decorative emoji. Zero or one emoji in total.
- **Symmetrical lists** where every item is the same length and none contains a specific.
- **Em-dash habits.** One is fine; a habit of them reads as AI. Don't swap them all for periods, though: the newest models avoid dashes entirely, and an all-comma-and-period monotone is now its own tell. If the author uses dashes, keep them.
- **LinkedIn tropes:** invented dialogues ("A janitor taught me..."), life events turned into B2B lessons, a moral tacked onto an unrelated story.

For the full pass, read [references/ai-writing-signs.md](references/ai-writing-signs.md), a field guide to the patterns that make text read as machine-written (inflated significance, vague attribution, promotional tone, avoiding "is"/"has", rhythm and more), with a fix for each. Fix the cause, not the symptom: a vague, inflated sentence needs a specific fact from the user, or deletion. A synonym doesn't fix it. If the humanizer skill is installed, it does this pass in more depth.

These apply to the user's own lines too. If their draft's core idea is phrased as a tic ("Customers don't care about your roadmap. They care about outcomes."), keep the idea, phrase it more concretely, and say why in the diagnosis.

Then read it aloud as the author. If a sentence is something they'd never say out loud, rewrite it.

## Formatting

LinkedIn doesn't render markdown. `**bold**`, `# headings` and `[links](url)` show up as literal symbols, so hand over plain text ready to paste.

- **Hashtags:** none by default; two or three at most, and only ones people actually follow. LinkedIn removed hashtag following in 2024, and posts without hashtags do slightly better than posts with them.
- **Emoji:** zero or one, used for meaning, not decoration.
- **Tags:** only people who are part of the story and likely to reply. Mass-tagging is named engagement bait.
- **Links:** make the post fully valuable without the link. The evidence on a link penalty conflicts, but if reach matters, suggest putting the link in the first comment and writing "link in comments" in the post.
- **Bold:** LinkedIn has no native bold. Unicode "bold" letters exist, but screen readers can't read them. Skip them, or use them for at most one phrase if the user asks.

## Output

Unless the user asks for something else, return:

1. **The post**, plain text, ready to paste. In a chat reply, put it in its own code block so the line breaks survive and it copies in one click.
2. **Two alternative hooks** from different formulas (for example a story hook and a data hook), so the user can swap the opener.
3. **Short notes**, three to five bullets at most:
   - the archetype used and the character count. If placeholders remain, give the count without them and an estimate once they're filled.
   - any `[placeholders]` the user must fill in
   - one optional improvement (an image idea, link placement, or a posting tip)

If the user asks for several versions, make each a different archetype or angle, not near-copies.

**When critiquing or rewriting a user's draft:** give a short diagnosis first, covering the hook, then one idea, then specificity, then voice, then the ending, and quote the lines that need work. Then give the rewrite, keeping the user's voice and every true detail they gave; don't swap their real specifics for generic ones. Include alternative hooks only when the hook was a main problem, and finish with the usual short notes. Keep the diagnosis in proportion: a strong draft needs a few notes, not an essay.

If you can run code, check the final draft mechanically:

```
python3 scripts/lint_post.py draft.txt
```

or pipe the text on stdin. It reports the character count, the approximate mobile and desktop previews, engagement bait, AI-writing signs, hashtags, emoji, markdown leftovers and rhythm. It's a check, not a judge: a warning means look again, not rewrite automatically.

## Final check

Before handing over, confirm:

- [ ] The hook is complete within ~140 characters, and a stranger in the target audience would click "see more"
- [ ] The post makes one point, and the body pays off the hook
- [ ] Every claim, number and story came from the user, or is a marked `[placeholder]`
- [ ] It has at least three concrete specifics
- [ ] None of the AI tells or engagement bait above
- [ ] It reads aloud like the author talking
- [ ] It's in the length range, plain text, with at most one emoji and three hashtags
- [ ] It ends on a clean takeaway and, optionally, a specific question

## Beyond the text

Bring these up only when relevant, or when the user asks about strategy. The data behind them is in [references/platform.md](references/platform.md).

- **Frequency:** 2–4 posts a week, never more than one a day. Daily posting lowers reach per post.
- **Consistency:** one main topic plus a few subtopics. Staying on topic goes with higher reach.
- **Timing:** Tuesday to Thursday, during the audience's working hours. Timing matters less than being around to reply to comments in the first hour.
- **Format:** a relevant image (a real photo, screenshot or artifact) is a cheap reach upgrade over text alone. Frameworks and step-by-step guides often work better still as a document (carousel) post.
- **Editing after posting:** small edits have no measured penalty. Fix the typo.

## References

- [references/hooks.md](references/hooks.md): hook formulas with examples and the data behind them. Read when writing or improving hooks.
- [references/archetypes.md](references/archetypes.md): twelve post structures with skeletons and annotated examples. Read when drafting.
- [references/ai-writing-signs.md](references/ai-writing-signs.md): the catalog of AI-writing patterns, with fixes. Read during the editing pass.
- [references/platform.md](references/platform.md): how the feed ranks posts, plus format, length, timing and link data, with dated sources. Read when the user asks about reach or strategy, or why a rule exists.
- `scripts/lint_post.py`: the draft checker. It imports `scripts/ai_signs.py`, the AI-writing scanner, which also runs on its own.
