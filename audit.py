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
CMD_LINE = re.compile(r"^\s*(?:[-*>]|\d+\.)?\s*`?(?:\$|>)?\s*(npm|npx|yarn|pnpm|bun|make|docker|ddev|php|python|pytest|go|cargo|rails|bundle|composer|mix|iex|gulp|vite|terraform|kubectl)\s+\S")


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


    # ---- Silent-failure checks. These are the ones worth publishing a tool for:
    # each looks fine in a code review and does nothing at runtime.

    # A. .claude/ in .gitignore. Extremely common and self-defeating: skills,
    # agents and hooks are the shareable part. Ignored, every engineer rebuilds
    # them privately and the team never converges.
    gi = repo.read(".gitignore") or ""
    # Only the whole tree counts. Ignoring .claude/settings.local.json is CORRECT
    # — that is the per-developer file — and flagging it made the tool contradict
    # its own remediation advice.
    ignored = []
    for line in gi.splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        if entry.rstrip("/") in (".claude", "**/.claude", "*/.claude"):
            ignored.append(entry)
    if ignored:
        f.append(dict(
            severity="high", area="sharing",
            finding=f".gitignore excludes .claude ({', '.join(ignored[:3])}).",
            impact="Skills, sub-agents and hooks are the part worth sharing. Ignored, each engineer rebuilds them privately, nothing is reviewed, and none of it survives someone leaving.",
            fix="Commit .claude/. Keep only .claude/settings.local.json ignored — that is the per-developer file; settings.json is the shared one."))

    # B. Hooks configured but the script is missing. The hook silently no-ops.
    raw_settings = repo.read(".claude/settings.json")
    if raw_settings:
        try:
            cfg = json.loads(raw_settings)
        except (ValueError, TypeError):
            cfg = None
            f.append(dict(
                severity="high", area="hooks",
                finding=".claude/settings.json is not valid JSON.",
                impact="An unparseable settings file means every hook in it is silently inactive. Nothing warns you.",
                fix="Validate it: python3 -c \"import json;json.load(open('.claude/settings.json'))\""))
        if cfg:
            missing_scripts, hook_count = [], 0
            for event, groups in (cfg.get("hooks") or {}).items():
                for group in groups if isinstance(groups, list) else []:
                    for h in (group.get("hooks") or []):
                        cmd = str(h.get("command", ""))
                        hook_count += 1
                        m = re.search(r"([\w./$-]*\.claude/hooks/[\w.-]+)", cmd)
                        if m:
                            rel = re.sub(r"^\$?\{?CLAUDE_PROJECT_DIR\}?/", "", m.group(1))
                            # NOT .lstrip("./") — that strips every leading '.' and
                            # '/' character, turning ".claude/..." into "claude/..."
                            # so every hook read as missing.
                            if rel.startswith("./"):
                                rel = rel[2:]
                            if not repo.exists(rel):
                                missing_scripts.append((event, rel))
            have["hook_count"] = hook_count
            if missing_scripts:
                f.append(dict(
                    severity="high", area="hooks",
                    finding=f"{len(missing_scripts)} hook(s) point at a script that is not in the repo.",
                    impact="A hook whose command is missing fails open. The rule it was meant to enforce is simply not enforced, and nothing reports it.",
                    fix="Commit the referenced scripts, or remove the stale entries from settings.json.",
                    examples=[f"{e}: {p}" for e, p in missing_scripts[:5]]))

    # C. Skills missing a description. A skill without one is never selected —
    # the description is what the model matches against.
    skill_dirs = repo.listdir(".claude/skills")
    undescribed = []
    for d in skill_dirs[:25]:
        body = repo.read(f".claude/skills/{d}/SKILL.md")
        if body is None:
            continue
        head = body[:600]
        if not re.search(r"^description:\s*\S", head, re.M):
            undescribed.append(d)
    if undescribed:
        f.append(dict(
            severity="high", area="skills",
            finding=f"{len(undescribed)} skill(s) have no `description:` in their frontmatter.",
            impact="The description is what the model matches a task against. Without it the skill is effectively invisible — it exists, it is committed, and it never fires.",
            fix="Add a description that names the trigger, not the topic: 'Use when deploying to staging', not 'Deployment stuff'.",
            examples=undescribed[:6]))

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
    ("composer.json", 'if [ -x vendor/bin/pint ]; then vendor/bin/pint --test "$FILE"; elif [ -x vendor/bin/phpcs ] && [ -f phpcs.xml ]; then vendor/bin/phpcs --standard=phpcs.xml "$FILE"; else php -l "$FILE"; fi', "PHP"),
    ("package.json", 'npx --no-install eslint "$FILE"', "JavaScript/TypeScript"),
    ("Gemfile", 'bundle exec rubocop "$FILE"', "Ruby"),
    ("pyproject.toml", 'ruff check "$FILE"', "Python"),
    ("mix.exs", 'mix format --check-formatted "$FILE"', "Elixir"),
    ("go.mod", 'UNFMT=$(gofmt -l "$FILE") && [ -z "$UNFMT" ]', "Go"),
]

LINT_HOOK = r"""#!/bin/sh
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

OUT=$({linter} 2>&1) || {{
    echo "Lint failed for $FILE:" >&2
    echo "$OUT" >&2
    exit 2
}}
exit 0
"""

DDEV_GUARD_HOOK = r"""#!/bin/sh
# PreToolUse guard for DDEV repositories: blocks bare host php/composer/craft
# commands in Bash tool calls so Claude always prefixes with `ddev `.
set -u

PAYLOAD=$(cat)
CMD=$(printf '%s' "$PAYLOAD" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

[ -n "$CMD" ] || exit 0

case "$CMD" in
    php\ *|composer\ *|craft\ *|./craft\ *)
        echo "Blocked: do not run '$CMD' directly on the host. Prefix with 'ddev ' (e.g. 'ddev $CMD')." >&2
        exit 2
        ;;
esac
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
            if manifest == "composer.json":
                comp_txt = (repo.read("composer.json") or "").lower()
                if "laravel/pint" in comp_txt:
                    return 'if [ -x vendor/bin/pint ]; then vendor/bin/pint --test "$FILE"; else php -l "$FILE"; fi', "PHP"
                if "squizlabs/php_codesniffer" in comp_txt or repo.exists("phpcs.xml"):
                    return 'if [ -x vendor/bin/phpcs ] && [ -f phpcs.xml ]; then vendor/bin/phpcs --standard=phpcs.xml "$FILE"; else php -l "$FILE"; fi', "PHP"
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
    inst_txt = repo.read(have.get("instructions_file") or "CLAUDE.md") or ""
    forbidden, candidates = [], []
    has_ddev_rule = bool("ddev " in inst_txt.lower() or repo.exists(".ddev/config.yaml"))
    literal_re = re.compile(r"[\"'`]([^\"'`]{3,60})[\"'`]")
    negative_re = re.compile(r"\b(never|forbidden|do not|don't)\b", re.I)
    for f in findings:
        if f["area"] != "hooks":
            continue
        for rule in f.get("examples", []):
            if "ddev" in rule.lower() or "directly on the host" in rule.lower():
                has_ddev_rule = True
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

    if has_ddev_rule:
        write(".claude/hooks/ddev-guard.sh", DDEV_GUARD_HOOK, executable=True)

    # 3. settings.json wiring whatever hooks we produced.
    hooks_cfg = {}
    if linter:
        hooks_cfg["PostToolUse"] = [{
            "matcher": "Write|Edit",
            "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/lint-on-edit.sh", "timeout": 30}],
        }]
    pre_hooks = []
    if forbidden:
        pre_hooks.append({
            "matcher": "Write|Edit|Bash",
            "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/forbid.sh", "timeout": 10}],
        })
    if has_ddev_rule:
        pre_hooks.append({
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/ddev-guard.sh", "timeout": 10}],
        })
    if pre_hooks:
        hooks_cfg["PreToolUse"] = pre_hooks
    if hooks_cfg:
        write(".claude/settings.json", json.dumps({"hooks": hooks_cfg}, indent=2) + "\n")

    # 4. reviewer sub-agent — the one every audited repo was missing.
    write(".claude/agents/reviewer.md", REVIEWER_AGENT)

    # 5. a skill seeded from the commands documented inline (or fallback when skills are missing).
    cmds = []
    for f in findings:
        if f["area"] == "skills" and f.get("examples"):
            cmds = [c.lstrip("-*$> `").rstrip("`").strip() for c in f["examples"]]
    if not cmds and "skills" in have.get("missing", []):
        inline_cmds = [l.strip().lstrip("-*$> `").rstrip("`").strip() for l in inst_txt.splitlines() if CMD_LINE.match(l)]
        cmds = inline_cmds[:8] if inline_cmds else ([linter] if linter else [])
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
