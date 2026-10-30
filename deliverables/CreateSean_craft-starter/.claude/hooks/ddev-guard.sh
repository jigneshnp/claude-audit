#!/bin/sh
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
