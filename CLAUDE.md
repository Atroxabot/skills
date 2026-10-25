# Atroxabot Skills: working in this repo

A curated collection of Agent Skills, laid out like [anthropics/skills](https://github.com/anthropics/skills). Keep it that way.

## Layout

```
skills/<skill-name>/
  SKILL.md        # frontmatter (name, description) + instructions
  LICENSE.txt     # only if the skill reuses licensed third-party material
  references/     # optional: long material, loaded only when needed
  scripts/        # optional: helper code the skill runs
  evals/          # optional: evals.json test prompts (skill-creator format)
spec/             # pointer to the Agent Skills spec
template/SKILL.md # starting point for a new skill
.claude-plugin/marketplace.json  # groups skills into installable plugins
```

## Adding a skill

1. Copy `template/SKILL.md` to `skills/<skill-name>/SKILL.md`. `name` must match the folder name (kebab-case, at most 64 characters).
2. Write the `description` so it triggers reliably: say what the skill does and list the phrases users type. At most 1024 characters, no angle brackets.
3. Add a `LICENSE.txt` and a `license:` line only when the skill reuses someone else's licensed material (copied text, code, fonts). Ideas and facts drawn from a source just need a credit.
4. Add the skill path to a plugin's `skills` array in `.claude-plugin/marketplace.json` (or a new plugin, grouped by theme), and a row to the table in `README.md`. Bump `metadata.version` in the marketplace.

## Rules

- **Self-contained skills.** A skill folder may be copied or uploaded on its own, so it never links to files outside itself.
- **Explain why.** Give the reason behind each rule instead of bare MUSTs. The model generalizes from reasons.
- **One catalog, several copies.** linkedin-post, repurpose and cold-outreach each carry a copy of the humanizer's `references/ai-writing-signs.md` and `scripts/ai_signs.py`, because their editing step and linters need them and a skill must work on its own. The humanizer's files are the originals: edit those, copy them over the other three, and check nothing has drifted with `for s in linkedin-post repurpose cold-outreach; do cmp skills/humanizer/references/ai-writing-signs.md skills/$s/references/ai-writing-signs.md; cmp skills/humanizer/scripts/ai_signs.py skills/$s/scripts/ai_signs.py; done` (no output means they match).
- **Date platform claims.** Writing skills that rely on how a platform ranks, counts or polices posts say when the research was done and list dated sources in their references, because platforms change these rules every few months.
- **Write in your own words.** Draw on sources for ideas, but don't paste their text: copied text brings its license with it (Wikipedia's CC BY-SA would put the whole file under share-alike terms). Name the main sources in a short note, as `skills/humanizer/references/ai-writing-signs.md` does, and cite specific studies where a claim relies on them.
