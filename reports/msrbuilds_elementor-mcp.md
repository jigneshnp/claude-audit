# Claude Code audit — msrbuilds/elementor-mcp

Instructions file: `CLAUDE.md` (~50 tokens, loaded every turn)
Tooling present: none
Tooling missing: skills, sub-agents, hooks, slash commands, shared settings, MCP servers

## Findings: 2 high, 1 medium

### 1. [HIGH] No .claude/skills/ directory — the instructions file is doing all the work.
*skills*

**Why it costs you:** Everything the team knows lives in one always-loaded blob or in nobody's head. Nothing is reusable or testable.

**Fix:** Start with two skills covering your most repeated tasks. Skills are versioned files in the repo, so they survive turnover.

### 2. [HIGH] No .claude/hooks/ — nothing is enforced mechanically at the agent layer.
*hooks*

**Why it costs you:** Standards are advisory. They hold on a good day.

**Fix:** Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets.

### 3. [MEDIUM] No .claude/agents/ — no specialized sub-agents defined.
*agents*

**Why it costs you:** One context does planning, writing and reviewing. Self-review is the weakest review there is.

**Fix:** Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written.

