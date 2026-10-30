# Claude Code audit — resilient-tech/india-compliance

Instructions file: `CLAUDE.md` (~79 tokens, loaded every turn)
Tooling present: skills, shared settings
Tooling missing: sub-agents, hooks, slash commands, MCP servers

**Already enforcing at the git layer:** .pre-commit-config.yaml — so the instinct is there; it just stops before the agent.

## Findings: 2 high, 1 medium

### 1. [HIGH] No .claude/hooks/ — nothing is enforced mechanically at the agent layer.
*hooks*

**Why it costs you:** Standards are advisory. They hold on a good day.

**Fix:** Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets.

### 2. [HIGH] .claude/settings.json is not valid JSON.
*hooks*

**Why it costs you:** An unparseable settings file means every hook in it is silently inactive. Nothing warns you.

**Fix:** Validate it: python3 -c "import json;json.load(open('.claude/settings.json'))"

### 3. [MEDIUM] No .claude/agents/ — no specialized sub-agents defined.
*agents*

**Why it costs you:** One context does planning, writing and reviewing. Self-review is the weakest review there is.

**Fix:** Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written.

