---
name: javascript-typescript-workflows
description: Common JavaScript/TypeScript commands for this repo. Use when running, building, or resetting the local environment.
---

# JavaScript/TypeScript workflows

The commands this project documents for day-to-day work.

## Commands

```console
npm install
npm run build                    # Standard build (runs gn gen automatically)
npm run build -- --watch         # Watch mode for development
npm run build -- -t Debug        # Build to out/Debug instead of out/Default
npm run build -- -t fast-build
npm run build -- --watch
```

## Notes

Generated from the project's instructions file, where these commands were
documented inline. Inline they cost context on every turn, including the many
turns that never run them; here they load only when relevant.

Fill in the specifics a newcomer would get wrong — required env vars, the order
these must run in, what "done" looks like.
