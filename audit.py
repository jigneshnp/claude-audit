#!/usr/bin/env python3
"""
claude-audit — inspect a repo's Claude Code setup and report what's missing.

The paid deliverable behind the $500 audit tier, and the asset that makes a cold
email concrete: run it against a prospect's PUBLIC repo and you have findings to
attach instead of a call to request.

Usage:
    ./audit.py <path>                  audit a local checkout
    ./audit.py owner/repo              audit a public GitHub repo (needs gh)
    ./audit.py owner/repo --json       machine-readable
    ./audit.py <path> --generate DIR   write real hooks/skills/agents into DIR

Zero dependencies. Uses `gh` only for the GitHub path.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# Rules phrased as instructions to the model are hook candidates: a hook enforces
# them mechanically instead of hoping the model remembers on turn 40.
IMPERATIVE = re.compile(
    r"^\s*[-*>\d.]*\s*(?:\*\*)?"
    r"(ALWAYS|NEVER|MUST|DO NOT|DON'T|CRITICAL|IMPORTANT|REQUIRED|ENSURE|MAKE SURE)"
    r"\b(?:\*\*)?[:\s]",
    re.I,
)
# A run of shell commands in prose is repeated setup knowledge — that is a skill,
# loaded on demand, not context paid for on every single turn.
CMD_LINE = re.compile(r"^\s*(?:\$|>)?\s*(npm|npx|yarn|pnpm|bun|make|docker|ddev|php|python|pytest|go|cargo|rails|bundle|composer|terraform|kubectl)\s+\S")


def sh(args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


class Repo:
    """Uniform read interface over a local checkout or a public GitHub repo."""

    def __init__(self, target):
        self.target = target
        self.is_gh = "/" in target and not Path(target).exists()
        self.root = None if self.is_gh else Path(target)
        if self.is_gh and sh(["gh", "auth", "status"]) is None:
            sys.exit("gh is not authenticated — run `gh auth login` or pass a local path")

    def read(self, rel):
        if not self.is_gh:
            f = self.root / rel
            return f.read_text(errors="replace") if f.is_file() else None
        out = sh(["gh", "api", f"repos/{self.target}/contents/{rel}",
                  "--jq", ".content", "-H", "Accept: application/vnd.github.raw+json"])
        if out is None:
            out = sh(["gh", "api", f"repos/{self.target}/contents/{rel}",
                      "-H", "Accept: application/vnd.github.raw"])
        return out

    def exists(self, rel):
        if not self.is_gh:
            return (self.root / rel).exists()
        # jq must handle BOTH shapes: a file returns an object, a directory returns
        # an array. `.name // .[0].name` errors on the array, gh exits non-zero, and
        # the check silently reports "absent" for every directory — which produced a
        # false "no git hooks" on a repo that ships .githooks/.
        out = sh(["gh", "api", f"repos/{self.target}/contents/{rel}",
                  "--jq", 'if type == "array" then (.[0].name // "dir") else .name end'])
        return bool(out and out.strip())

    def listdir(self, rel):
        if not self.is_gh:
            d = self.root / rel
            return sorted(p.name for p in d.iterdir()) if d.is_dir() else []
        out = sh(["gh", "api", f"repos/{self.target}/contents/{rel}",
                  "--jq", 'if type == "array" then .[].name else .name end'])
        return sorted(out.split()) if out else []


def audit(repo):
    f = []          # findings
    have = {}       # what exists

    claude_md = None
    for name in ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md"):
        claude_md = repo.read(name)
        if claude_md:
            have["instructions_file"] = name
            break

    if not claude_md:
        f.append(dict(
            severity="info", area="instructions",
            finding="No CLAUDE.md or AGENTS.md found.",
            impact="Every session starts cold — the model re-derives your conventions from the code each time, and gets them wrong at the edges.",
            fix="Write one CLAUDE.md at the repo root: build/test commands, directory map, and the three conventions a new hire always gets wrong."))
    else:
        lines = claude_md.splitlines()
        approx_tokens = max(1, len(claude_md) // 4)
        have["instructions_tokens"] = approx_tokens
        if approx_tokens > 2000:
            f.append(dict(
                severity="high", area="token-cost",
                finding=f"{have['instructions_file']} is ~{approx_tokens:,} tokens and loads on every single turn.",
                impact=f"At ~{approx_tokens:,} tokens per turn, a 40-turn session pays ~{approx_tokens*40:,} tokens just re-reading instructions — before any of your code is read.",
                fix="Keep the always-on file under ~500 tokens (commands, layout, hard rules). Move everything task-specific into skills that load only when relevant."))

        rules = [l.strip() for l in lines if IMPERATIVE.match(l)]
        if rules:
            f.append(dict(
                severity="high", area="hooks",
                finding=f"{len(rules)} rule(s) are written as instructions for the model to remember, with no hook enforcing them.",
                impact="A prose rule holds early in a session and slips late in one. Anything that actually matters should fail loudly, not depend on recall.",
                fix="Convert each to a PreToolUse or PostToolUse hook. A hook that blocks the commit is worth more than a sentence asking the model not to.",
                examples=rules[:6]))

        cmds = [l.strip() for l in lines if CMD_LINE.match(l)]
        if len(cmds) >= 5:
            f.append(dict(
                severity="medium", area="skills",
                finding=f"{len(cmds)} shell commands are documented inline in {have['instructions_file']}.",
                impact="This is procedural knowledge billed as context on every turn, including the turns that never run any of it.",
                fix="Move each workflow into a skill. Same knowledge, loaded on demand.",
                examples=cmds[:6]))

    # ---- Claude Code tooling surface ----
    surface = {
        ".claude/skills": "skills",
        ".claude/agents": "sub-agents",
        ".claude/hooks": "hooks",
        ".claude/commands": "slash commands",
        ".claude/settings.json": "shared settings",
        ".mcp.json": "MCP servers",
    }
    present, missing = [], []
    for path, label in surface.items():
        entries = repo.listdir(path) if not path.endswith(".json") else ([path] if repo.exists(path) else [])
        (present if entries else missing).append(label)
        if entries and not path.endswith(".json"):
            have[label] = entries
    have["present"] = present
    have["missing"] = missing

    if "skills" in missing and claude_md:
        f.append(dict(
            severity="high", area="skills",
            finding="No .claude/skills/ directory — the instructions file is doing all the work.",
            impact="Everything the team knows lives in one always-loaded blob or in nobody's head. Nothing is reusable or testable.",
            fix="Start with two skills covering your most repeated tasks. Skills are versioned files in the repo, so they survive turnover."))
    if "sub-agents" in missing:
        f.append(dict(
            severity="medium", area="agents",
            finding="No .claude/agents/ — no specialized sub-agents defined.",
            impact="One context does planning, writing and reviewing. Self-review is the weakest review there is.",
            fix="Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written."))
    if "hooks" in missing:
        f.append(dict(
            severity="high", area="hooks",
            finding="No .claude/hooks/ — nothing is enforced mechanically at the agent layer.",
            impact="Standards are advisory. They hold on a good day.",
            fix="Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets."))

    # Git-layer enforcement. Checked SEPARATELY and reported as a STRENGTH, because
    # claiming a team "has no hooks" when they run Husky is the fastest way to be
    # contradicted in the first reply.
    git_hooks = []
    for p in (".husky", ".githooks", ".pre-commit-config.yaml", "lefthook.yml"):
        if repo.exists(p):
            git_hooks.append(p)
    have["git_hooks"] = git_hooks

    order = {"high": 0, "medium": 1, "info": 2}
    f.sort(key=lambda x: order.get(x["severity"], 3))
    return f, have


def render(target, findings, have):
    o = [f"# Claude Code audit — {target}", ""]
    if have.get("instructions_file"):
        o.append(f"Instructions file: `{have['instructions_file']}` (~{have.get('instructions_tokens', 0):,} tokens, loaded every turn)")
    o.append(f"Tooling present: {', '.join(have['present']) or 'none'}")
    o.append(f"Tooling missing: {', '.join(have['missing']) or 'none'}")
    if have.get("git_hooks"):
        o.append("")
        o.append(f"**Already enforcing at the git layer:** {', '.join(have['git_hooks'])} — "
                 "so the instinct is there; it just stops before the agent.")
    o.append("")
    counts = {}
    for x in findings:
        counts[x["severity"]] = counts.get(x["severity"], 0) + 1
    o.append("## Findings: " + ", ".join(f"{v} {k}" for k, v in counts.items()) if findings else "## No findings")
    o.append("")
    for i, x in enumerate(findings, 1):
        o.append(f"### {i}. [{x['severity'].upper()}] {x['finding']}")
        o.append(f"*{x['area']}*")
        o.append("")
        o.append(f"**Why it costs you:** {x['impact']}")
        o.append("")
        o.append(f"**Fix:** {x['fix']}")
        if x.get("examples"):
            o.append("")
            o.append("Examples found in your own file:")
            for e in x["examples"]:
                o.append(f"- `{e[:160]}`")
        o.append("")
    return "\n".join(o)



# ---------------------------------------------------------------- generation --
# --generate turns findings into files. This is what makes the $2,500 setup tier
# repeatable delivery instead of bespoke work every time: the audit says what is
# missing, this writes the thing that fixes it.

# Detected by manifest file. Each entry: (linter command, what it lints).
STACKS = [
    ("composer.json", "vendor/bin/phpcs --standard=phpcs.xml", "PHP"),
    ("package.json", "npx --no-install eslint", "JavaScript/TypeScript"),
    ("Gemfile", "bundle exec rubocop", "Ruby"),
    ("pyproject.toml", "ruff check", "Python"),
    ("mix.exs", "mix format --check-formatted", "Elixir"),
    ("go.mod", "gofmt -l", "Go"),
]

LINT_HOOK = """#!/bin/sh
# Runs {lang} lint on every file Claude edits, immediately after the edit.
#
# Replaces the prose rule "always lint before committing" with something that
# actually fails. A rule the model has to remember holds early in a session and
# slips late in one; this does not slip.
#
# PostToolUse passes a JSON payload on stdin. We pull the edited path out of it.
# Exit non-zero and the failure is reported back to Claude, which then fixes it.
set -u

PAYLOAD=$(cat)
FILE=$(printf '%s' "$PAYLOAD" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

case "$FILE" in
{globs}
    *) exit 0 ;;
esac

OUT=$({linter} "$FILE" 2>&1) || {{
    echo "Lint failed for $FILE:" >&2
    echo "$OUT" >&2
    exit 2
}}
exit 0
"""

FORBID_HOOK = """#!/bin/sh
# Blocks content this project has explicitly forbidden, before it is written.
#
# Generated from FORBIDDEN literals in the project's own instructions file. Each
# was phrased as an instruction to the model; a PreToolUse hook makes it a wall
# instead of a request.
#
# Exit 2 blocks the tool call and reports the reason back to Claude.
#
# NOTE ON THE LOOP: patterns are iterated with a plain `for` over an unquoted
# expansion, NOT `printf ... | while read`. A piped while runs in a SUBSHELL, so
# its `exit 2` leaves the subshell and the hook returns 0 - it would silently
# never block. That bug shipped in the first version of this generator.
set -u

PAYLOAD=$(cat)

# Literal patterns only (grep -F), so regex metacharacters cannot change meaning.
FORBIDDEN="{forbidden}"

OLD_IFS=$IFS
IFS='
'
for pat in $FORBIDDEN; do
    [ -n "$pat" ] || continue
    if printf '%s' "$PAYLOAD" | grep -qF -- "$pat"; then
        IFS=$OLD_IFS
        echo "Blocked: this project forbids '$pat' (see its instructions file)." >&2
        exit 2
    fi
done
IFS=$OLD_IFS
exit 0
{review_block}"""

REVIEWER_AGENT = """---
name: reviewer
description: Reviews code changes in a context that did not write them. Use after any non-trivial edit.
tools: Read, Grep, Glob, Bash
---

You review code you did not write. That separation is the entire point — a
context that just produced code is the worst possible judge of it.

## What to check

1. **Correctness.** Trace the actual flow. Name a concrete input that produces a
   wrong output, or say the logic holds. No vague concerns.
2. **Convention.** The project's rules live in its instructions file. Check the
   change against them specifically, not against generic best practice.
3. **Blast radius.** Grep every caller of anything you changed. A fix that
   repairs one call site and leaves three broken is not a fix.
4. **Tests.** Does a test exist that fails if this logic breaks? If not, say
   which one is missing.

## How to report

One line per finding: `path:line — problem. fix.`
Ranked most severe first. No praise, no summary of what the code does.
If nothing is wrong, say so in one line and stop.
"""

SKILL_TEMPLATE = """---
name: {name}
description: {desc}
---

# {title}

{body}

## Commands

```console
{commands}
```

## Notes

Generated from the project's instructions file, where these commands were
documented inline. Inline they cost context on every turn, including the many
turns that never run them; here they load only when relevant.

Fill in the specifics a newcomer would get wrong — required env vars, the order
these must run in, what "done" looks like.
"""


def detect_stack(repo):
    for manifest, linter, lang in STACKS:
        if repo.exists(manifest):
            return linter, lang
    return None, None


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s or "workflow")[:40]


def generate(repo, findings, have, outdir):
    out = Path(outdir)
    written = []

    def write(rel, content, executable=False):
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)
        if executable:
            f.chmod(0o755)
        written.append(str(f))

    linter, lang = detect_stack(repo)

    # 1. lint-on-edit hook, only when we know what the linter actually is.
    if linter:
        exts = {
            "PHP": ["*.php"],
            "JavaScript/TypeScript": ["*.js", "*.jsx", "*.ts", "*.tsx"],
            "Ruby": ["*.rb"],
            "Python": ["*.py"],
            "Elixir": ["*.ex", "*.exs"],
            "Go": ["*.go"],
        }[lang]
        globs = "\n".join(f"    {e}) ;;" for e in exts)
        write(".claude/hooks/lint-on-edit.sh",
              LINT_HOOK.format(lang=lang, linter=linter, globs=globs),
              executable=True)

    # 2. forbid hook, built from the project's own NEVER/DO NOT rules.
    # Only block on literals distinctive enough to be safe. A naive extraction
    # pulled "Claude" out of "Never use Claude watermark in commits" and "bold"
    # out of "Never use bold text as headings" - a hook blocking every payload
    # containing "Claude" would block essentially every tool call.
    #
    # So: take only quoted or backticked literals, require a separator (- _ : @ /)
    # and length >= 8. "Co-Authored-By" passes; "Claude" and "bold" do not.
    # Everything rejected is emitted as a commented candidate for a human to
    # promote deliberately. Never auto-generate a block on a guess.
    forbidden, candidates = [], []
    literal_re = re.compile(r"[\"'`]([^\"'`]{3,60})[\"'`]")
    negative_re = re.compile(r"\b(never|forbidden|do not|don't)\b", re.I)
    for f in findings:
        if f["area"] != "hooks":
            continue
        for rule in f.get("examples", []):
            if not negative_re.search(rule):
                continue
            for lit in literal_re.findall(rule):
                lit = lit.strip()
                if not lit:
                    continue
                if len(lit) >= 8 and re.search(r"[-_:@/]", lit):
                    forbidden.append(lit)
                else:
                    candidates.append((lit, " ".join(rule.split())[:100]))

    if forbidden or candidates:
        review = ""
        if candidates:
            review = ("\n# --- candidates NOT enabled (too generic to block on safely) ---\n"
                      "# Promote one only if it is genuinely a literal that must never appear.\n")
            for lit, rule in sorted(set(candidates))[:8]:
                review += "#   %r  from: %s\n" % (lit, rule)
        write(".claude/hooks/forbid.sh",
              FORBID_HOOK.format(forbidden="\n".join(sorted(set(forbidden))),
                                 review_block=review),
              executable=True)

    # 3. settings.json wiring whatever hooks we produced.
    hooks_cfg = {}
    if linter:
        hooks_cfg["PostToolUse"] = [{
            "matcher": "Write|Edit",
            "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/lint-on-edit.sh", "timeout": 30}],
        }]
    if forbidden:
        hooks_cfg["PreToolUse"] = [{
            "matcher": "Write|Edit|Bash",
            "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/forbid.sh", "timeout": 10}],
        }]
    if hooks_cfg:
        write(".claude/settings.json", json.dumps({"hooks": hooks_cfg}, indent=2) + "\n")

    # 4. reviewer sub-agent — the one every audited repo was missing.
    write(".claude/agents/reviewer.md", REVIEWER_AGENT)

    # 5. a skill seeded from the commands documented inline.
    cmds = []
    for f in findings:
        if f["area"] == "skills" and f.get("examples"):
            cmds = [c.lstrip("-*$> ").strip() for c in f["examples"]]
    if cmds:
        name = slugify(f"{lang or 'project'}-workflows")
        write(f".claude/skills/{name}/SKILL.md",
              SKILL_TEMPLATE.format(
                  name=name,
                  desc=f"Common {lang or 'project'} commands for this repo. Use when running, building, or resetting the local environment.",
                  title=f"{lang or 'Project'} workflows",
                  body="The commands this project documents for day-to-day work.",
                  commands="\n".join(cmds)))

    return written


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    target = args[0]
    repo = Repo(target)
    findings, have = audit(repo)
    if "--generate" in sys.argv:
        i = sys.argv.index("--generate")
        if i + 1 >= len(sys.argv):
            sys.exit("--generate needs an output directory")
        written = generate(repo, findings, have, sys.argv[i + 1])
        print(f"Wrote {len(written)} file(s):")
        for w in written:
            print(" ", w)
        print("\nReview each one, then commit. The settings.json wires the hooks;")
        print("the skill and reviewer agent are seeded and need project specifics.")
        return

    if "--json" in sys.argv:
        print(json.dumps({"target": target, "have": have, "findings": findings}, indent=2))
    else:
        print(render(target, findings, have))


if __name__ == "__main__":
    main()
