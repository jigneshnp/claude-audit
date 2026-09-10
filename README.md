# claude-audit

Inspects a repo's Claude Code setup and reports what's missing, why it costs
them, and what to build first.

This is the deliverable behind the **$500 audit tier** in the consulting offer —
and, run against a prospect's *public* repo, it's the attachment that turns a
cold email from "can we talk?" into "here are three specific things, attached."

## Usage

```console
./audit.py ~/some/local/checkout      # local
./audit.py owner/repo                 # public GitHub repo (needs `gh auth login`)
./audit.py owner/repo --json          # machine-readable
```

Zero dependencies. Python 3, plus `gh` for the GitHub path.

## What it checks

| Check | Why it matters |
| --- | --- |
| `CLAUDE.md` / `AGENTS.md` present and its token size | The file loads on **every turn**. Over ~2k tokens it is a standing tax paid on turns that never use it. |
| Imperative rules (ALWAYS / NEVER / MUST / CRITICAL …) | Each one is a hook candidate. A prose rule holds early in a session and slips late in one. |
| Inline shell commands | Procedural knowledge billed as context every turn. Belongs in a skill, loaded on demand. |
| `.claude/skills`, `agents`, `hooks`, `commands`, `settings.json`, `.mcp.json` | The actual tooling surface. Missing = "installed it and stopped." |
| `.husky`, `.githooks`, `.pre-commit-config.yaml`, `lefthook.yml` | Reported as a **strength**, not a gap — see below. |

## The git-hooks check exists to stop you being wrong

A team running Husky already believes in mechanical enforcement; their standards
just stop at the git layer and never reach the agent. Telling them "you have no
hooks" gets you contradicted in the first reply and ends the conversation.

So git-layer enforcement is detected separately and reported as a strength, and
the framing becomes: *the instinct is right, it just stops before the agent.*

That check caught a real bug in this tool during development. `gh api contents/<dir>`
returns an **array** for a directory and an **object** for a file; a jq of
`.name // .[0].name` errors on the array, `gh` exits non-zero, and every directory
silently reported as absent — producing a false "no git hooks" on a repo that
ships `.githooks/`. Fixed by branching on `type == "array"`. Regression-checked
in both directions: a repo with hooks reports them, a repo without still reports
none.

## Sample output

`reports/` holds real reports generated against public repos. They are also the
proof that the tool says something specific rather than generic — it quotes the
target's own rules back to them.

## Roadmap when a paying client uses it

- Read actual token spend from a session transcript rather than estimating from file size
- Generate the hook files, not just the recommendation
- Diff against a reference setup to score maturity
