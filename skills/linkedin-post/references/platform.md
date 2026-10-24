# How LinkedIn distributes posts (as of October 2026)

Read this when the user asks about reach, strategy, timing, links, hashtags or format, or why a rule in SKILL.md exists. When you cite something to the user, give its date: LinkedIn changes the feed often.

Evidence tags:
- **[Official]**: LinkedIn statements or its engineering blog.
- **[Data]**: large third-party datasets. They're correlational, so treat the numbers as directional.
- **[Contested]**: sources disagree.

## How ranking works

**Retrieval by meaning** [Official, LinkedIn Engineering, Mar 2026]
- The feed uses an LLM-based dual encoder to match posts to members by meaning, not keywords.
- It can show a post to people outside the author's network if the topic fits their interests.
- For writing, this means: be clear about what the post is about and who it's for. Vague, generic posts are hard to match to anyone.

**Ranking on history and predicted actions** [Official, Mar 2026]
- A sequential model reads a member's history of more than 1,000 interactions.
- It predicts clicks, skips, long dwell, likes, comments and shares.
- It also uses the viewer's profile, their past engagement with the author, and popularity percentiles.

**What LinkedIn is demoting** [Official, Newsroom, 12 Mar 2026]
- "Repetitive, low-substance posts and engagement bait," with "comment to agree" prompts as the example.
- "Recycled and click-driven posts."
- Engagement pods: LinkedIn is "working to make engagement pods ineffective."
- What it wants more of: "posts that offer genuine insight, actionable ideas, and thoughtful perspectives."

**Generic AI content** [Official, Laura Lorenzetti, VP, May 2026, via Social Media Today]
- "It's ok to use AI to help you write, but your posts and comments need to represent your voice and your perspectives."
- LinkedIn limits the reach of content that appears AI-generated and lacks a clear perspective.

**Automated comments** [Official, 2025–26]: comments posted by scripts or plugins are hidden from the default comment view.

**Dwell time** [Official, Engineering blog, 2020]
- Time on a post is measured once at least half of it is on screen.
- A skip model demotes posts people scroll past.
- No threshold is published.

**Which posts reach new people** [Official, LinkedIn's Director of Creator Products, quoted by Forbes, Jun 2026]
- Out of network: "topical, substantive, and actionable" posts.
- In network: personal updates.

**Things LinkedIn has said to avoid** [Official, 2024, via Search Engine Journal]
- asking for likes or comments without adding value
- reaction-vote polls
- tagging people for attention
- irrelevant hashtags
- copy-paste reshares
- purely salesy posts

## Writing that reads as AI [Data]

- **LigoSocial (134K posts, 2023–2026):** posts that read as AI-written got about 22% less engagement than the same author's other posts that year; clearly human posts got about 31% more. "It's not X, it's Y" rose from 1.2% to 5.9% of posts. (Seen via the study's published summary.)
- **Originality.ai (2024):** long posts flagged as likely AI got about 45% less engagement.

## Engagement signals [Data]

- **Saves.** One save is worth about 5× a like and about 2× a comment in reach (AuthoredUp).
- **Comments.** A comment is worth about 2× a like early on. Reply threads under comments go with up to 2.4× reach.
- **Author replies.** Replying to comments goes with about +30% engagement (Buffer, 72K posts). Replying within about 30 minutes goes with about 64% more comments (van der Blom).
- **Comment quality.** Substantive comments count for more than "Great post!" The exact multiplier is unproven.

## Format and length [Data]

- **The "see more" cut:** about 210 characters on desktop and about 140 on mobile (AuthoredUp, Aug 2026). About 72% of use is on mobile, and blank lines use up preview lines.
- **Hard limit:** 3,000 characters.
- **Length:**
  - The 1,301–2,500-character band gets about 27% more engagement than posts under 400 characters (AuthoredUp, 372K posts).
  - Once you normalize per author, no single length wins. Posts under 100 words are weakest in every format.
  - Working range: 900–1,800 characters.
- **First line.** First lines under 40 characters: 2.61% median engagement. Over 200 characters: 2.08% (AuthoredUp, 771K posts).
- **Hook type.** Median engagement: story 2.60%, contrarian 2.31%, question 2.16% (AuthoredUp, 309K posts, Dec 2025–May 2026).
- **Hook length.** Hooks under 10 words got about 40% more "see more" clicks in a smaller study (ConnectSafely, about 1K posts).
- **Readability.** A reading grade under 4 is the strongest bucket. Grade 10 or above underperforms (AuthoredUp).
- **Emoji.** Going from 0 to 1 emoji goes with about +22% median reach. More than one adds nothing (AuthoredUp).
- **Hashtags.** Posts with no hashtags beat posts with hashtags by 5–10%. Three or more do much worse. Hashtag following was removed in 2024.
- **Format multipliers on reach** (AuthoredUp 2025, personal profiles):

  | Format | Reach multiplier |
  |---|---|
  | Polls | 1.64× |
  | Documents / carousels | 1.45× |
  | Images | 1.18× |
  | Video | 1.10× |
  | Text only | 0.88× |

  Richard van der Blom's 2026 report says text-only posts do well only for exceptional writers, and recommends text plus an image.
- **Closing questions.** A specific closing question gives a small lift. A generic one ("Thoughts?") does slightly worse than no question.

## Contested questions

- **Link penalty.**
  - Studies range from −36% to +43%. Most find single-link posts underperform (Ordinal; van der Blom −18.8% median reach).
  - One study finds the penalty mostly on company pages.
  - LinkedIn has never confirmed a penalty.
  - Safe default: make the post valuable without the link, and offer "link in the first comment" when reach matters.
- **"Golden hour."** Early traction plausibly matters, but no thresholds are published. The real lever is being around to reply.
- **Editing after posting.** No measured penalty. Small edits are fine.
- **"Comment [word] to get the PDF."** This is close to the bait LinkedIn named. Avoid it.
- **The "360Brew" model.** It was a research paper. It isn't confirmed as the production ranker.

## Cadence and timing [Data]

- **Frequency:** 2–4 posts a week.
  - Buffer finds 2–5 posts a week performs best.
  - Daily posting cuts reach per post by about 26% (van der Blom 2026).
  - Leave at least 24 hours between posts.
- **Topic focus.** One main topic for about 80% of posts. Staying on 2–3 topics for 90 days goes with about +27% reach (van der Blom).
- **Timing.** Studies conflict, and timing matters less than replying to comments.
  - Tuesday to Thursday, late morning to afternoon, in the audience's time zone.
  - Weekends are weakest.
- **Overall reach** fell roughly 50–60% across 2024–2026 for most creators (van der Blom 2025 and 2026). Low numbers are often the platform, not the post.

## Sources

Accessed October 2026. Richard van der Blom's reports are paywalled; his figures come from the write-ups listed.

**LinkedIn**
- Engineering, next-generation feed (2026-03-12): https://www.linkedin.com/blog/engineering/feed/engineering-the-next-generation-of-linkedins-feed
- Newsroom, Improving the Feed (2026-03-12): https://news.linkedin.com/2026/ImprovingTheFeed
- Engineering, dwell time (2020): https://www.linkedin.com/blog/engineering/feed/understanding-feed-dwell-time

**Coverage of LinkedIn statements**
- Social Media Today, AI content (2026-05-21): https://www.socialmediatoday.com/news/linkedin-wants-to-limit-the-reach-of-ai-generated-content/820935/
- TNW (2026-05-20): https://thenextweb.com/news/linkedin-ai-slop-crackdown-generic-content
- Search Engine Journal, LinkedIn dos and don'ts (2024-11-28): https://www.searchenginejournal.com/linkedin-shares-dos-donts-for-better-post-visibility/533571/

**Data studies**
- AuthoredUp, algorithm: https://authoredup.com/blog/linkedin-algorithm
- AuthoredUp, character limit and truncation: https://authoredup.com/blog/linkedin-character-limit
- AuthoredUp, writing tips: https://authoredup.com/blog/tips-to-write-a-post-on-linkedin
- Buffer, posting frequency: https://buffer.com/resources/how-often-to-post-on-linkedin/
- Ordinal, link penalty study: https://www.tryordinal.com/blog/linkedin-link-penalty-study
- LigoSocial, AI-written posts: https://ligosocial.com/research/ai-linkedin-posts
- Originality.ai, AI posts and engagement: https://originality.ai/blog/linkedin-ai-study-engagement
- ConnectSafely, hook length (secondhand): https://connectsafely.ai/articles/how-to-write-like-matt-barker-linkedin

**Van der Blom write-ups**
- https://newsletter.kararedman.com/p/i-binged-6-linkedin-algorithm-reports
- https://melaniegoodmanlinkedinconsultant.substack.com/p/linkedin-algorithm-2026-reach-topic-authority
