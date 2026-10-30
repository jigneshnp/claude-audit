---
name: php-workflows
description: Common PHP commands for this repo. Use when running, building, or resetting the local environment.
---

# PHP workflows

The commands this project documents for day-to-day work.

## Commands

```console
if [ -x vendor/bin/pint ]; then vendor/bin/pint --test "$FILE"; elif [ -x vendor/bin/phpcs ] && [ -f phpcs.xml ]; then vendor/bin/phpcs --standard=phpcs.xml "$FILE"; else php -l "$FILE"; fi
```

## Notes

Generated from the project's instructions file, where these commands were
documented inline. Inline they cost context on every turn, including the many
turns that never run them; here they load only when relevant.

Fill in the specifics a newcomer would get wrong — required env vars, the order
these must run in, what "done" looks like.
