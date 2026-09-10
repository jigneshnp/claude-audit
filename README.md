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
./audit.py <path> --generate DIR      # write real hooks/skills/agents into DIR
./test.sh                             # regression checks for --generate
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

## `--generate` — the setup tier

`--generate` turns findings into files, which is what makes the $2,500 setup tier
repeatable delivery instead of bespoke work every engagement:

- `.claude/hooks/lint-on-edit.sh` — runs the project's real linter (detected from
  its manifest: composer/npm/Gemfile/pyproject/mix/go.mod) on every edited file
- `.claude/hooks/forbid.sh` — blocks literals the project declared FORBIDDEN
- `.claude/settings.json` — wires whichever hooks were produced
- `.claude/agents/reviewer.md` — the reviewer sub-agent every audited repo lacked
- `.claude/skills/<stack>-workflows/SKILL.md` — seeded from commands documented inline

Everything is a starting point a human reviews before committing, not a drop-in.

### Two bugs this shipped with, and why `test.sh` exists

**A blocklist built from a guess.** The first extractor pulled the bare word
`Claude` out of *"Never use Claude watermark in commits"* and `bold` out of
*"Never use bold text as headings"*. A PreToolUse hook blocking every payload
containing "Claude" blocks essentially every tool call. Now only quoted literals
carrying a separator and >= 8 chars are activated — `Co-Authored-By` qualifies,
`Claude` does not — and everything rejected is written into the file as a
commented candidate for a human to promote deliberately.

**A hook that could never block.** The loop was `printf ... | while read`, which
runs in a subshell, so `exit 2` left the subshell and the hook always returned 0.
It would have silently enforced nothing. Now it is a plain `for` over an IFS
split, and `test.sh` asserts an actual block happens.

Both are regression-tested. Neither was visible from reading the generator; both
turned up from reading its output.

## Roadmap when a paying client uses it

- Read actual token spend from a session transcript rather than estimating from file size
- Diff against a reference setup to score maturity
- Generate the skill body from real command history, not just the documented list
