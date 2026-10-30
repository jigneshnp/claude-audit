---
name: elixir-workflows
description: Common Elixir commands for this repo. Use when running, building, or resetting the local environment.
---

# Elixir workflows

The commands this project documents for day-to-day work.

## Commands

```console
mix usage_rules.docs Enum
mix usage_rules.docs Enum.zip
mix usage_rules.docs Enum.zip/1
mix usage_rules.search_docs Enum.zip
mix usage_rules.search_docs Req.get -p req
mix usage_rules.search_docs "making requests" -p req
```

## Notes

Generated from the project's instructions file, where these commands were
documented inline. Inline they cost context on every turn, including the many
turns that never run them; here they load only when relevant.

Fill in the specifics a newcomer would get wrong — required env vars, the order
these must run in, what "done" looks like.
