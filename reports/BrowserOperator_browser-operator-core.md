# Claude Code audit — BrowserOperator/browser-operator-core

Instructions file: `CLAUDE.md` (~2,012 tokens, loaded every turn)
Tooling present: none
Tooling missing: skills, sub-agents, hooks, slash commands, shared settings, MCP servers

## Findings: 3 high, 2 medium

### 1. [HIGH] CLAUDE.md is ~2,012 tokens and loads on every single turn.
*token-cost*

**Why it costs you:** At ~2,012 tokens per turn, a 40-turn session pays ~80,480 tokens just re-reading instructions — before any of your code is read.

**Fix:** Keep the always-on file under ~500 tokens (commands, layout, hard rules). Move everything task-specific into skills that load only when relevant.

### 2. [HIGH] No .claude/skills/ directory — the instructions file is doing all the work.
*skills*

**Why it costs you:** Everything the team knows lives in one always-loaded blob or in nobody's head. Nothing is reusable or testable.

**Fix:** Start with two skills covering your most repeated tasks. Skills are versioned files in the repo, so they survive turnover.

### 3. [HIGH] No .claude/hooks/ — nothing is enforced mechanically at the agent layer.
*hooks*

**Why it costs you:** Standards are advisory. They hold on a good day.

**Fix:** Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets.

### 4. [MEDIUM] 17 shell commands are documented inline in CLAUDE.md.
*skills*

**Why it costs you:** This is procedural knowledge billed as context on every turn, including the turns that never run any of it.

**Fix:** Move each workflow into a skill. Same knowledge, loaded on demand.

Examples found in your own file:
- `npm install`
- `npm run build                    # Standard build (runs gn gen automatically)`
- `npm run build -- --watch         # Watch mode for development`
- `npm run build -- -t Debug        # Build to out/Debug instead of out/Default`
- `npm run build -- -t fast-build`
- `npm run build -- --watch`

### 5. [MEDIUM] No .claude/agents/ — no specialized sub-agents defined.
*agents*

**Why it costs you:** One context does planning, writing and reviewing. Self-review is the weakest review there is.

**Fix:** Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written.

