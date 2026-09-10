# Claude Code audit — digitoimistodude/air-light

Instructions file: `CLAUDE.md` (~1,570 tokens, loaded every turn)
Tooling present: none
Tooling missing: skills, sub-agents, hooks, slash commands, shared settings, MCP servers

## Findings: 3 high, 1 medium

### 1. [HIGH] 13 rule(s) are written as instructions for the model to remember, with no hook enforcing them.
*hooks*

**Why it costs you:** A prose rule holds early in a session and slips late in one. Anything that actually matters should fail loudly, not depend on recall.

**Fix:** Convert each to a PreToolUse or PostToolUse hook. A hook that blocks the commit is worth more than a sentence asking the model not to.

Examples found in your own file:
- `- CRITICAL: Always lint before committing changes!`
- `- Always commit build and asset files`
- `- Never use bold text as headings, use proper heading levels instead`
- `- Always add an empty line after headings`
- `- Never use Claude watermark in commits (FORBIDDEN: "Co-Authored-By")`
- `- Always add tasks to the Claude Code to-do list and keep it up to date.`

### 2. [HIGH] No .claude/skills/ directory — the instructions file is doing all the work.
*skills*

**Why it costs you:** Everything the team knows lives in one always-loaded blob or in nobody's head. Nothing is reusable or testable.

**Fix:** Start with two skills covering your most repeated tasks. Skills are versioned files in the repo, so they survive turnover.

### 3. [HIGH] No .claude/hooks/ — nothing is enforced mechanically at the agent layer.
*hooks*

**Why it costs you:** Standards are advisory. They hold on a good day.

**Fix:** Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets.

### 4. [MEDIUM] No .claude/agents/ — no specialized sub-agents defined.
*agents*

**Why it costs you:** One context does planning, writing and reviewing. Self-review is the weakest review there is.

**Fix:** Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written.

