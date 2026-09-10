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

[ "$fail" -eq 0 ] && echo "all checks passed"
exit "$fail"
