#!/bin/sh
# Runnable check for the --generate path. Both cases here are regressions of real
# bugs the first version shipped, so this is the test that must not be deleted.
set -e
cd "$(dirname "$0")"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

FIX="$TMP/proj"
mkdir -p "$FIX"
cat > "$FIX/composer.json" <<'JSON'
{"name":"fixture/proj"}
JSON
cat > "$FIX/CLAUDE.md" <<'MD'
# Rules
- CRITICAL: Always lint before committing changes!
- Never use Claude watermark in commits (FORBIDDEN: "Co-Authored-By")
- Never use bold text as headings, use proper heading levels instead
MD

./audit.py "$FIX" --generate "$TMP/out" > /dev/null
HOOK="$TMP/out/.claude/hooks/forbid.sh"
[ -x "$HOOK" ] || { echo "FAIL: forbid.sh not generated or not executable"; exit 1; }

fail=0

# REGRESSION 1: a naive extractor pulled the bare word "Claude" out of the
# watermark rule and "bold" out of the headings rule. A hook blocking every
# payload containing "Claude" blocks essentially every tool call.
grep -q 'FORBIDDEN="Co-Authored-By"' "$HOOK" || { echo "FAIL: expected only Co-Authored-By active"; fail=1; }
grep -q '^FORBIDDEN=.*Claude"' "$HOOK" && { echo "FAIL: bare 'Claude' became an active block pattern"; fail=1; }

# REGRESSION 2: the first version piped into `while read`, which runs in a
# subshell, so `exit 2` left the subshell and the hook always returned 0 —
# it silently never blocked anything.
echo '{"content":"chore: x\n\nCo-Authored-By: someone"}' | "$HOOK" >/dev/null 2>&1 && {
    echo "FAIL: hook did not block a forbidden literal (subshell regression)"; fail=1
}
echo '{"content":"chore: x"}' | "$HOOK" >/dev/null 2>&1 || {
    echo "FAIL: hook blocked a clean payload"; fail=1
}
echo '{"content":"ask Claude about this bold heading"}' | "$HOOK" >/dev/null 2>&1 || {
    echo "FAIL: hook false-positived on 'Claude'/'bold'"; fail=1
}

# The reviewer agent is the gap every audited repo had; always emitted.
[ -f "$TMP/out/.claude/agents/reviewer.md" ] || { echo "FAIL: reviewer agent missing"; fail=1; }

# settings.json must be valid JSON and wire what was generated.
python3 -c "import json,sys; json.load(open('$TMP/out/.claude/settings.json'))" || { echo "FAIL: settings.json invalid"; fail=1; }


# ---------------------------------------------------------------------------
# FALSE-POSITIVE REGRESSIONS. A tool that flags a correct setup is worse than
# no tool: the first thing a prospect does is run it on a repo they know is
# fine, and one bogus finding ends the conversation.
# ---------------------------------------------------------------------------
CLEAN="$TMP/clean"
mkdir -p "$CLEAN/.claude/hooks" "$CLEAN/.claude/agents" "$CLEAN/.claude/skills/deploy"
printf 'node_modules/\n.claude/settings.local.json\n' > "$CLEAN/.gitignore"
echo '{"name":"clean"}' > "$CLEAN/package.json"
printf '# Clean\n\nBuild: `npm run build`\n' > "$CLEAN/CLAUDE.md"
printf '{"hooks":{"PostToolUse":[{"matcher":"Write|Edit","hooks":[{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/lint.sh"}]}]}}\n' > "$CLEAN/.claude/settings.json"
printf '#!/bin/sh\nexit 0\n' > "$CLEAN/.claude/hooks/lint.sh"; chmod +x "$CLEAN/.claude/hooks/lint.sh"
printf -- '---\nname: deploy\ndescription: Use when deploying to staging\n---\n# Deploy\n' > "$CLEAN/.claude/skills/deploy/SKILL.md"
printf -- '---\nname: reviewer\ndescription: Reviews code it did not write\n---\n# Reviewer\n' > "$CLEAN/.claude/agents/reviewer.md"

CLEAN_OUT=$(./audit.py "$CLEAN")

# REGRESSION 3: gitignoring .claude/settings.local.json is CORRECT practice —
# it is the per-developer file, and the tool's own remediation text says to keep
# it ignored. A startswith(".claude/") check flagged it and made the tool
# contradict its own advice.
echo "$CLEAN_OUT" | grep -q "gitignore excludes" && {
    echo "FAIL: flagged .claude/settings.local.json, which is correct to ignore"; fail=1
}

# REGRESSION 4: .lstrip("./") strips every leading '.' and '/' CHARACTER, so
# ".claude/hooks/lint.sh" became "claude/hooks/lint.sh" and every configured
# hook reported as missing.
echo "$CLEAN_OUT" | grep -q "point at a script that is not in the repo" && {
    echo "FAIL: reported an existing hook script as missing (lstrip bug)"; fail=1
}

echo "$CLEAN_OUT" | grep -q "No findings" || {
    echo "FAIL: a correctly-configured repo produced findings"; fail=1
}

# And the checks must still FIRE on a genuinely broken repo.
BROKEN="$TMP/broken"
mkdir -p "$BROKEN/.claude/skills/nodesc"
printf 'node_modules/\n.claude/\n' > "$BROKEN/.gitignore"
printf '# x\n- ALWAYS lint before pushing\n' > "$BROKEN/CLAUDE.md"
printf '{"hooks":{"PostToolUse":[{"matcher":"Write","hooks":[{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/gone.sh"}]}]}}\n' > "$BROKEN/.claude/settings.json"
printf -- '---\nname: nodesc\n---\n# no description\n' > "$BROKEN/.claude/skills/nodesc/SKILL.md"

BROKEN_OUT=$(./audit.py "$BROKEN")
for expect in "gitignore excludes" "point at a script that is not in the repo" "no \`description:\`"; do
    echo "$BROKEN_OUT" | grep -q "$expect" || { echo "FAIL: check did not fire: $expect"; fail=1; }
done

[ "$fail" -eq 0 ] && echo "all checks passed"
exit "$fail"
