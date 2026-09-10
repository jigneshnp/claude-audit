# claude-audit

Finds what's silently broken in a repo's Claude Code setup.

Not a linter for your code — a linter for the layer your agent runs on. Most of
what it finds looks fine in review and does nothing at runtime.

```console
$ ./audit.py your-org/your-repo

# Claude Code audit — your-org/your-repo

Instructions file: `CLAUDE.md` (~2,856 tokens, loaded every turn)
Tooling present: none
Tooling missing: skills, sub-agents, hooks, slash commands, shared settings, MCP servers

## Findings: 4 high, 1 medium

### 1. [HIGH] CLAUDE.md is ~2,856 tokens and loads on every single turn.
**Why it costs you:** At ~2,856 tokens per turn, a 40-turn session pays ~114,240
tokens just re-reading instructions — before any of your code is read.
```

Zero dependencies. Python 3, plus `gh` if you point it at a GitHub repo.

## Install

```console
git clone https://github.com/YOUR_USERNAME/claude-audit
cd claude-audit && ./audit.py --help
```

## Use

```console
./audit.py .                      # this repo
./audit.py ~/code/some-project    # a local checkout
./audit.py owner/repo             # any public GitHub repo (needs `gh auth login`)
./audit.py . --json               # machine-readable
./audit.py . --generate ./out     # write the fixes, don't just name them
./test.sh                         # the regression suite
```

## What it catches

The interesting checks are the silent ones — configuration that is present,
committed, reviewed, and inert.

| Check | Why it's silent |
| --- | --- |
| **`.claude/` in `.gitignore`** | Skills, agents and hooks are the shareable part. Ignored, every engineer rebuilds them privately and none of it survives someone leaving. |
| **Hooks pointing at a missing script** | A hook whose command doesn't exist fails *open*. The rule isn't enforced and nothing reports it. |
| **Skills with no `description:`** | The description is what the model matches a task against. Without one the skill is committed, present, and never fires. |
| **Unparseable `settings.json`** | Every hook in it is inactive. No warning. |
| **Rules written as prose** | `ALWAYS lint before committing` holds early in a session and slips late in one. |
| **Instructions-file token cost** | It loads on *every* turn, including the ones that never use it. |
| **Inline command lists** | Procedural knowledge billed as context on turns that never run it. Belongs in a skill. |

It also reports **git-layer enforcement** (`.husky`, `.githooks`, pre-commit,
lefthook) as a *strength*, not a gap — a team running Husky already believes in
mechanical enforcement; it just stops before the agent.

## `--generate` writes the fix

```console
./audit.py . --generate ./out
```

Emits a `lint-on-edit` hook wired to your actual linter (detected from
`composer.json` / `package.json` / `Gemfile` / `pyproject.toml` / `mix.exs` /
`go.mod`), a `forbid` hook built from literals your own instructions file
declares forbidden, the `settings.json` that wires them, a reviewer sub-agent,
and a skill seeded from the commands you documented inline.

All of it is a reviewed starting point, never a drop-in.

## A correct setup reports nothing

That property is enforced by `test.sh`, because it's the one that decides whether
the tool is worth running. Four of its cases are regressions of bugs this tool
actually shipped:

- **A blocklist built from a guess.** The first extractor pulled the bare word
  `Claude` out of *"Never use Claude watermark in commits"*. A PreToolUse hook
  blocking every payload containing "Claude" blocks essentially every tool call.
- **A hook that could never block.** The loop piped into `while read`, which runs
  in a subshell, so `exit 2` left the subshell and the hook always returned 0. It
  would have enforced nothing while looking correct in review.
- **Flagging correct practice.** It reported `.claude/settings.local.json` being
  gitignored as a problem — while its own remediation text said to keep exactly
  that ignored.
- **`.lstrip("./")`.** Strips every leading `.` and `/` *character*, so
  `.claude/hooks/lint.sh` became `claude/hooks/lint.sh` and every configured hook
  reported as missing.

None of the four were visible reading the code. All four came from reading the
output. That's the habit the tool is trying to encode.

## Contributing

New checks are welcome, with one rule: a check must not fire on a correct setup.
Add the passing case to `test.sh` alongside the failing one.

## License

MIT
