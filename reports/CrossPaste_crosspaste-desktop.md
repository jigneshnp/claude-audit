# Claude Code audit — CrossPaste/crosspaste-desktop

Instructions file: `CLAUDE.md` (~2,765 tokens, loaded every turn)
Tooling present: none
Tooling missing: skills, sub-agents, hooks, slash commands, shared settings, MCP servers

## Findings: 4 high, 1 medium

### 1. [HIGH] CLAUDE.md is ~2,765 tokens and loads on every single turn.
*token-cost*

**Why it costs you:** At ~2,765 tokens per turn, a 40-turn session pays ~110,600 tokens just re-reading instructions — before any of your code is read.

**Fix:** Keep the always-on file under ~500 tokens (commands, layout, hard rules). Move everything task-specific into skills that load only when relevant.

### 2. [HIGH] 2 rule(s) are written as instructions for the model to remember, with no hook enforcing them.
*hooks*

**Why it costs you:** A prose rule holds early in a session and slips late in one. Anything that actually matters should fail loudly, not depend on recall.

**Fix:** Convert each to a PreToolUse or PostToolUse hook. A hook that blocks the commit is worth more than a sentence asking the model not to.

Examples found in your own file:
- `- **Never normalize Windows paths to forward slashes when the path will be executed by cmd.exe** (`.bat`/`.cmd` hosts, `cmd /c` invocations — e.g. Chromium laun`
- `- **Never embed literal non-ASCII paths in generated `.bat` files.** The files are written as UTF-8 but cmd.exe reads them in the OEM code page (e.g. GBK), garb`

### 3. [HIGH] No .claude/skills/ directory — the instructions file is doing all the work.
*skills*

**Why it costs you:** Everything the team knows lives in one always-loaded blob or in nobody's head. Nothing is reusable or testable.

**Fix:** Start with two skills covering your most repeated tasks. Skills are versioned files in the repo, so they survive turnover.

### 4. [HIGH] No .claude/hooks/ — nothing is enforced mechanically at the agent layer.
*hooks*

**Why it costs you:** Standards are advisory. They hold on a good day.

**Fix:** Add a PostToolUse hook running your existing linter on every edited file. Usually a few lines, and it never forgets.

### 5. [MEDIUM] No .claude/agents/ — no specialized sub-agents defined.
*agents*

**Why it costs you:** One context does planning, writing and reviewing. Self-review is the weakest review there is.

**Fix:** Add a reviewer sub-agent with its own context so review is genuinely independent of the code that was just written.

