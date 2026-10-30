#!/bin/sh
# Runs JavaScript/TypeScript lint on every file Claude edits, immediately after the edit.
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
    *.js) ;;
    *.jsx) ;;
    *.ts) ;;
    *.tsx) ;;
    *) exit 0 ;;
esac

OUT=$(npx --no-install eslint "$FILE" 2>&1) || {
    echo "Lint failed for $FILE:" >&2
    echo "$OUT" >&2
    exit 2
}
exit 0
