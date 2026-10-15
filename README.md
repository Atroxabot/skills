> **Note:** These skills follow the open Agent Skills standard. For the format itself, see [agentskills.io](https://agentskills.io) and Anthropic's reference repository, [anthropics/skills](https://github.com/anthropics/skills).

# Atroxabot Skills

A curated set of skills for Claude from [atroxabot.com](https://atroxabot.com). Skills are folders of instructions, scripts and resources that Claude loads when a task calls for them, so it does that task the same reliable way every time.

For background on skills:
- [What are skills?](https://support.claude.com/en/articles/12512176-what-are-skills)
- [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude)
- [How to create custom skills](https://support.claude.com/en/articles/12512198-creating-custom-skills)
- [Equipping agents for the real world with Agent Skills](https://anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

# Skills

| Skill | Plugin | What it does |
|-------|--------|--------------|
| [humanizer](./skills/humanizer) | `writing-skills` | Edits text so it reads like a specific person wrote it. It finds the patterns that mark text as AI-written and fixes their causes (vagueness, puffery) instead of swapping synonyms, keeps the author's facts and voice, and never invents details. Includes a pattern scanner script. |

Each skill is self-contained in its own folder, with a `SKILL.md` holding the instructions and metadata Claude uses, plus any `references/` and `scripts/` it needs.

# Repository layout

- [./skills](./skills): the skills
- [./spec](./spec): the Agent Skills specification
- [./template](./template): a starting point for a new skill
- [./.claude-plugin/marketplace.json](./.claude-plugin/marketplace.json): the plugin marketplace that groups the skills into installable plugins

# Try in Claude Code, Claude.ai, and the API

## Claude Code

Register this repository as a Claude Code plugin marketplace:

```
/plugin marketplace add Atroxabot/skills
```

Then install a plugin:

```
/plugin install writing-skills@atroxabot-skills
```

Or pick one interactively: run `/plugin`, choose `Browse and install plugins`, then `atroxabot-skills`, and the plugin you want.

To use a single skill without a plugin, copy its folder into your skills directory:

```
cp -r skills/humanizer ~/.claude/skills/
```

Once installed, just ask, for example "humanize this" or "does this sound like AI?".

## Claude.ai

Zip a skill folder (for example `skills/humanizer/`) and upload it under Customize → Skills. See [Using skills in Claude](https://support.claude.com/en/articles/12512180-using-skills-in-claude#h_a4222fa77b).

## Claude API

Custom skills can be uploaded and used through the Claude API. See the [Skills API Quickstart](https://docs.claude.com/en/api/skills-guide#creating-a-skill).

# Creating a skill

A skill is a folder with a `SKILL.md` file that starts with YAML frontmatter. Start from [template/SKILL.md](./template/SKILL.md):

```markdown
---
name: my-skill-name
description: A clear description of what this skill does and when to use it
---

# My Skill Name

[Add your instructions here that Claude will follow when this skill is active]
```

The frontmatter requires only two fields:
- `name`: a unique identifier for the skill (lowercase, hyphens for spaces), matching the folder name
- `description`: what the skill does and when to use it, including the phrases users type

Optional fields include `license`, `allowed-tools`, `metadata` and `compatibility`. See the [specification](https://agentskills.io/specification).

To add a skill to this repository:
1. Create `skills/<skill-name>/` with a `SKILL.md`. If the skill reuses someone else's licensed material, add a `LICENSE.txt` and a `license` field, and keep the required attribution.
2. Keep `SKILL.md` focused on the workflow. Put long material in `references/` and helper code in `scripts/`, linked from `SKILL.md` with a note on when to use each.
3. Don't link to files outside the skill's own folder. A skill must work when copied or uploaded on its own.
4. Add the skill's path to a plugin in `.claude-plugin/marketplace.json`, and a row to the table above.
