# Signs of AI writing: an editor's field guide

> **About this guide.** A working editor's list, compiled from several sources and our own editing practice. The main ones:
> - the patterns logged by Wikipedia's WikiProject AI Cleanup in [Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
> - studies of model style from 2023 to 2026, named where they're used (mainly section 9)
> - 2026 research on social posts (section 8)
>
> It's written for editing, not detection, so every sign comes with a fix. It's also incomplete by nature: each model generation drops some habits and picks up new ones, and no sign proves who wrote a text. Treat a hit as a reason to reread the sentence, not as a verdict. Last revised October 2026.

## Read this first

**Why AI text reads the way it does.** Language models predict the most statistically likely continuation, then get tuned toward the most broadly palatable prose. The result regresses to the mean:
- Specific, unusual facts (statistically rare) get replaced by generic, positive, important-sounding statements (statistically common).
- "Ran the town's only bike repair shop for 30 years" becomes "a beloved pillar of the local community."
- The text gets *less specific and more exaggerated* at the same time.

**Fix the cause, not the symptom.** Wikipedia's guide warns against treating the signs as the problems to fix, because that "could just make detection harder." The real problems are underneath:
- vagueness
- puffery
- unsupported claims
- statements nobody would bother to make

A sentence like "This underscores the enduring importance of community" isn't fixed by swapping "underscores" for "shows." Fix it by replacing it with the specific fact it gestures at, or by deleting it. If no specific fact exists, the sentence had nothing to say.

**Signs cluster.**
- One "crucial" is a coincidence. Ten AI-vocabulary words, two negative parallelisms and a rule-of-three list in 200 words is a pattern.
- Look for density, not single words.
- Read words literally. A word on the list doesn't make its synonyms suspicious, and context matters ("underscore" can be a literal underline).

**Signs change over time.**
- Each model generation has its own tics: "delve" peaked in 2023 and has nearly vanished.
- As of October 2026, the newest models avoid em dashes and write uniform 8–20-word sentences.
- Word lists turn over with every model release. Structural and rhythmic habits persist. Weight those (sections 1, 2.3–2.6, 9) over individual words.
- Check the era table in 2.1 and the historical list in section 6.

**Humans write like this too.** Models learned from human writing: press releases, blogs, editorials. A sign is not proof. Never accuse someone of using AI on style alone. In 2025 studies:
- most people detected AI text at about chance
- only frequent LLM users did well

---

## 1. Content: what the text claims

These matter most. They are the deeper problems the surface signs point to.

### 1.1 Inflated significance, legacy and broader trends
**Watch for:**
- stands/serves as
- is a testament/reminder
- a pivotal/crucial/vital/key role/moment
- underscores/highlights its importance
- reflects broader
- symbolizing its enduring/lasting
- setting the stage for
- marking/shaping the
- represents a shift
- key turning point
- evolving landscape
- focal point
- indelible mark
- deeply rooted
- "[distinction] matters because"

Arbitrary details get tied to a bigger story, even for mundane subjects. Sometimes the text admits the subject is minor and then claims importance anyway ("Although few people used it, the tool remains part of the wider story of...").

> The county library opened its second branch in 1994, *marking a pivotal moment* in the region's commitment to literacy.

**Fix:** state what happened and stop. If the significance is real, show it with a fact ("It was the first library within 20 miles of the eastern villages"). Otherwise cut the sentence.

### 1.2 Canned emphasis on coverage and recognition
**Watch for:**
- featured/profiled/cited in
- independent coverage
- leading expert
- media outlets
- "maintains an active social media presence"
- "Awards and recognition" as a header

The text tries to prove importance by listing where the subject was mentioned, often describing the *sources* rather than what they said.

**Fix:** if a mention matters, say what was said or done ("Wired named it one of 2025's best tools"). Otherwise drop it.

### 1.3 Superficial "-ing" analysis
**Watch for:**
- a trailing participle phrase: highlighting…, underscoring…, emphasizing…, ensuring…, reflecting…, symbolizing…, contributing to…, fostering…, cultivating…, showcasing…
- valuable insights
- align/resonate with

> ...a population of approximately 56,998, *creating a lively community within its borders.*

The trailing clause interprets the fact for the reader, usually with an unsupported claim.

**Fix:** delete the trailing clause. If the interpretation is real and yours, make it its own sentence with its own evidence.

### 1.4 Promotional, ad-like tone
**Watch for:**
- boasts
- vibrant
- rich (heritage, history)
- profound
- showcasing
- exemplifies
- commitment to
- natural beauty
- nestled
- in the heart of
- groundbreaking
- renowned
- diverse array
- seamless
- breathtaking

Models drift into travel-brochure or press-release voice even when asked for neutral text. They even "remove promotional tone" while adding it. Newer models are subtler than older ones: fewer "the best," more steady positive gloss.

> *Nestled* among the *breathtaking* hills of the valley, Millbrook *stands as a charming village with a rich cultural heritage.*

**Fix:** describe plainly. Replace adjectives with facts: what it has, what it does, numbers, names.

### 1.5 Vague connection or association
**Watch for:**
- associated with
- connected to/with
- in connection with
- in association with
- "ventured into X as"
- "began his career as" (where "was" would do)

**Fix:** state the actual relationship: "was CEO of," "taught at," "founded."

### 1.6 Vague attributions and overgeneralized opinion
**Watch for:**
- experts argue
- industry reports
- observers have cited
- some critics argue
- researchers and conservationists
- described in scholarship
- several sources (when there are one or two)
- "such as" before a list that is actually complete

**Fix:** name the source and what it said, or own the claim as the author's view. If neither is possible, cut it. Never invent a source to fill the gap.

### 1.7 Formulaic challenges-and-outlook endings
**Watch for:**
- "Despite its [praise], [subject] faces several challenges..."
- "Despite these challenges"
- future outlook / future prospects
- ending on a vaguely hopeful forecast

This is about the rigid formula. Mentioning real problems is fine.

**Fix:** name the actual problem specifically, or end on the last substantive point.

### 1.8 Hedging disclaimers about information and interpretation
**Watch for:**
- "While specific details are limited/scarce"
- not widely documented/available
- based on available information
- "[claim] should be treated as [interpretive] rather than [definitive]"
- "does not by itself establish"
- "maintains a low profile"

These are common in chatbots that browse the web, especially by mid-2026. When the model can't find something it says so, then often speculates anyway.

**Fix:** delete. Either you know the fact (state it) or you don't (leave it out, or ask).

---

## 2. Language and grammar

### 2.1 "AI vocabulary"

These words appear far more often in post-2022 text. They co-occur: where there's one there are usually several. Density is the tell.

| Era (approx.) | Overused words |
|---|---|
| 2023 to mid-2024 (GPT-4) | additionally, boasts, bolstered, crucial, delve, emphasizing, enduring, garner, intricate/intricacies, interplay, key (adj.), landscape (abstract), meticulously, pivotal, underscore, tapestry, testament, valuable, vibrant |
| Mid-2024 to mid-2025 (GPT-4o) | align with, bolstered, crucial, emphasizing, enhance, enduring, fostering, highlighting, pivotal, showcasing, underscore, vibrant |
| Mid-2025 to mid-2026 (GPT-5) | emphasizing, enhance, highlighting, showcasing, plus the coverage words in 1.2 |
| Mid-2026 on (GPT-6) | challenge, clearer, dependable, echoed, foster, leverage, matters, multifaceted, practical, prioritize, quietly, steady, universally, plus uniform 8–20-word sentences built only from periods and commas |

Grok also overuses pseudo-scientific words ("causal," "empirical," "correlate") and still uses "underscore" in 2026.

**Fix:** use the plain word, or none. Usually the sentence is better with the word gone and a fact in its place. Don't swap one fancy word for another ("delve" → "dig deep into" everywhere is the same tic).

### 2.2 Avoiding plain "is" and "has"
**Watch for:**
- serves as / stands as / functions as / represents / marks (instead of *is*)
- boasts / features / offers / maintains (instead of *has*)
- refers to

One study found *is* and *are* fell more than 10% in academic writing in 2023. AI copyedits "improve" text by making exactly this change.

> *Gallery 825 serves as* LAAA's exhibition space... *The gallery features* four separate spaces.
> → Gallery 825 *is* LAAA's exhibition space. *It has* four gallery spaces.

**Fix:** use *is*, *are* and *has*. They're not weak words.

### 2.3 Negative parallelisms
These are constructions that correct a misconception nobody had:
- **Not just X, but also Y:** "not only dismissive but also unnecessarily harsh"
- **Not X, but Y / It's not X, it's Y:** "not a mirror but a portal"
- **No X, no Y, just Z:** "No roadmap, no budget, no owner — just a slide deck."
- **Y rather than X:** more common in recent output ("prioritizing consolidation rather than ideological purity")
- **The multi-sentence version:** "X. Y, however, ..."

Humans use these in myth-busting pieces. AI uses them everywhere, and in social posts they are now the most recognized tic.

**Fix:** state the positive claim directly ("The portrait is a portal..."). Keep a contrast only when the reader really holds the misconception, and then name it concretely.

### 2.4 The rule of three
Triplets of adjectives or short phrases make shallow analysis look thorough. Examples: "innovation, collaboration, and growth"; "clarity, focus, and impact."

**Fix:** keep the one item that matters. Or, if all three are real and concrete, make them uneven: different lengths, different shapes. Real lists rarely come in neat threes.

### 2.5 Elegant variation
Older models avoided repeating a noun, so one subject got renamed again and again: "non-conformist artists," "these artists," "like-minded artists," "the Russian avant-garde artists."

**Fix:** repeat the noun, or use a pronoun. Clarity beats variety. (Non-native writers taught to avoid repetition do this too.)

### 2.6 Monotone rhythm
Sentences all land in the same length band (about 8–20 words), with the same structure and punctuation. The newest models (late 2026), hard-coded away from em dashes, lean on periods and commas more than humans do. Every paragraph is the same size.

**Fix:** vary on purpose:
- a three-word sentence, then a long one that carries a whole thought
- a fragment
- a question that's actually asked
- a parenthetical
- a colon
- paragraphs of different sizes

Read it aloud. If it has a metronome beat, break it.

---

## 3. Style and formatting

### 3.1 Title Case in headings
Chatbots capitalize every main word in headings. **Fix:** use sentence case unless the venue requires Title Case.

### 3.2 Boldface everywhere
Chatbots bold key phrases mechanically, "key takeaways" style, often every instance of a term. **Fix:** remove almost all bold. Emphasis should come from the sentence.

### 3.3 Inline-header lists
`- **Header:** description` bullets, often in threes, where prose would read better. **Fix:** write a paragraph, or a plain list without bold labels.

### 3.4 Emoji as formatting
Emoji placed before headings or bullets (🚀 ✅ 💡). **Fix:** remove them. Use at most one emoji, and only where it carries meaning.

### 3.5 Tables for trivial content
Small tables that hold two or three facts. **Fix:** use a sentence.

### 3.6 Punctuation
- **Em dashes (—):** a historical sign (2022–September 2026). Older models overused them, usually with spaces around them and in punched-up, sales-like spots where a person would use a comma, colon or parentheses. Wikipedia cites a July 2026 study in which Claude was the only current model above professional writers. Graphite's October 2026 data shows Claude Opus 5.5 and Gemini 3.1 Pro now use almost none (about 0.015 per 1,000 words, against about 3 for humans), while GPT-5-era models still use about 7. So too many dashes and none at all are both signals. Fix the formulaic ones. Don't strip every dash and replace it with a period: that creates the monotone rhythm in 2.6. If the author's own writing uses dashes, keep them.
- **Curly quotes and apostrophes:** typical of ChatGPT and DeepSeek output, and often mixed with straight quotes in one text. They're weak on their own, since Word and macOS produce them too.

### 3.7 Markdown in places that don't render it
Asterisks, `#` headings and `[text](url)` links pasted into LinkedIn, X, email or a CMS. **Fix:** convert to plain text that suits the destination.

---

## 4. Chatbot residue

### 4.1 Talking to the user inside the text
**Watch for:**
- "Certainly!"
- "Of course!"
- "Here is a..."
- "I hope this helps"
- "Would you like me to..."
- "Let me know if..."
- "You're absolutely right"
- "In this section, we will discuss..."

**Fix:** delete it all. It was meant for the person prompting, not the reader.

### 4.2 Unfilled placeholders and template text
`[Your Name]`, "(If available)", `2025-xx-xx`, "Insert statistic here". **Fix:** fill them with real information, or remove them before publishing.

### 4.3 Meta-commentary about the edit
A rewrite that announces itself, such as "Here's a more human version:" or "I've removed the jargon." **Fix:** keep notes to the user outside the deliverable.

---

## 5. What human writing tends to do

### 5.1 Observed by Wikipedia editors

Wikipedia editors have observed that human-written text uses certain constructions *more* than AI text. Over-polished prose is itself a tell. Human writing tends to use:

- **Simple is/has phrases:** "there is a," "it has a."
- **Plain verbs over stiff synonyms:** *wrote* (not authored), *moved* (relocated), *used* (utilized), *tried* (attempted), *died* (passed away).
- **Definite statements and superlatives, when true:** "the only," "the first," "one of the best."
- **Some qualifiers and intensifiers:** "very," "perhaps," "tends to." Humans hedge naturally in small doses.
- **A little wordiness:** "in order to," "the fact that," "all of the." People aren't perfectly concise.

### 5.2 The author's own details

These are also human, and missing from most AI text:

- **Specific first-hand detail:** a date, a price, a name, what someone actually said, what went wrong.
- **An opinion with a reason**, stated without throat-clearing.
- **Uneven structure:** a point that gets one line, and another that gets a paragraph.
- **Tone that fits the person:** humor, irritation, enthusiasm.

**Don't over-correct.** Leave the author's quirks, an occasional "very," a long sentence that works, a repeated word that's clearer than a synonym.

---

## 6. Historical signs (older models)

These were common in older output and are rarer now. They still show up because many people use older or cheaper models.

- **Knowledge-cutoff disclaimers (2022–2023):** "As of my last knowledge update..."
- **Didactic disclaimers (2022–2024):** "It's important to note," "it's worth noting," "may vary." Mid-2026 models have a successor: the "should be treated as X rather than Y" disclaimer (1.8).
- **Section summaries:** "In summary," "In conclusion," "Overall," or a paragraph that restates its own point at the end.
- **Refusal residue:** "As an AI language model..."
- **Em-dash overuse (2022–September 2026):** see 3.6.
- **Elegant variation:** see 2.5.

---

## 7. Not reliable signs

Don't "fix" these. They are not evidence of AI and may indicate the opposite:

- **Perfect grammar.** Many people write well.
- **Mixed casual and formal registers.** Common in technical people, younger writers and neurodivergent writers.
- **"Bland" or "robotic" prose in general.** AI's actual traits are specific (above). Blandness alone isn't one.
- **Formal, academic or "fancy" prose in general.** Only specific words are overused, not formality itself.
- **Transition words on their own:** "Additionally" or "Consequently" by themselves. Only a few transitions are overused, and essays use them legitimately.

---

## 8. Social-post patterns

These come from 2026 research on how LinkedIn and X posts read and rank. They're common enough in AI-written posts to check for in any social copy.

- **Stock lines:** "Here's the thing," "Let that sink in," "Read that again," "The result?", "Spoiler:", "No fluff," "Let's dive in."
- **Broetry:** every sentence on its own line, all the same length.
- **Engagement bait:** "Agree?", "Comment YES," "Thoughts? 👇", "Like if...". Platforms demote these.
- **Emoji bullets and hashtag clusters.**
- **A moral appended to an unrelated story**, and invented anecdotes or dialogue.
- **"I'm humbled/thrilled to announce."**

---

## 9. Newer structural tells

These come from 2025–2026 studies. The main ones are Graphite's AI Tells corpus (2026), Reinhart et al. (PNAS 2025), Antislop (ICLR 2026), and a 2026 public blind test of a Wikipedia-based humanizer.

### 9.1 "Matters" framing
**Watch for:**
- "this matters"
- "why X matters"
- "matters because"
- "here's why this matters"
- "is more than a X; it's..."
- "the X is not simply..."

Each runs about 90–580× the human rate in 2026 models. They announce importance instead of showing it, which is the same root problem as 1.1.

**Fix:** delete the frame and let the fact carry the weight.

### 9.2 Aphoristic one-line closers
A paragraph or post that ends on a short, quotable, deep-sounding line ("And that changes everything." "Clarity is kindness." "That's the real lesson."). In the blind test, humanizer rewrites *increased* these, from 38 to 61. They're the easiest tic to add while removing others.

**Fix:** end on the last concrete point. Keep a closing line only if it adds information.

### 9.3 Explaining the point after showing it
The text shows something, then explains what it meant ("This shows that..." "The lesson? ..."). AI stories and posts over-explain their themes and have a tidy, self-announcing shape: announce, list, recap. Structure-level detectors catch this even after word-level rewording.

**Fix:** trust the reader. If the example makes the point, cut the explanation. Let the shape be a little untidy where the material is.

### 9.4 Participle and noun-heavy syntax
Instruction-tuned models use present-participle clauses at 2–5× the human rate, and nominalizations ("the implementation of," "the optimization of") at 1.5–2×.

**Fix:** use verbs with subjects: "we implemented," "it got faster."

### 9.5 Missing human texture
Compared with human writers, models use fewer exclamation marks, parenthetical asides and rhetorical questions. Their paragraphs are all about the same size.

**Fix:** don't sprinkle these in mechanically. That is just another uniform habit. Do allow them where the author would: a real aside, a real question, one exclamation when something is surprising.

### 9.6 Never fake the human cues
Readers wrongly treat first-person pronouns, contractions, family mentions and anecdotes as proof of a human author (Jakesch et al., PNAS 2023). Adding "I", feelings or a story to seem human misleads readers. When it invents facts, it is fabrication.

**Fix:** keep the author's real experiences, opinions and reactions. A reaction the author actually has is fine. A fact they didn't give is not.
