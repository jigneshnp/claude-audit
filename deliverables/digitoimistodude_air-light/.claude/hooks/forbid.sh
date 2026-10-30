#!/bin/sh
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
FORBIDDEN="Co-Authored-By"

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
