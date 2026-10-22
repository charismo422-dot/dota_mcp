# Lessons Learned (`LESSONS.md`)

Agent self-learning log: what works, what does not, and how it was solved. Broader than [BUG_LOG.md](./BUG_LOG.md) (which records MCP/addon bugs via `log_bug_report`): also covers workflow, tooling, environment and agent-behaviour findings.

**Agents:** read this file before starting a task; append an entry after finishing one whenever something new was learned. Keep entries short. If an entry turns out wrong, fix or delete it.

Entry format:

```
### YYYY-MM-DD — <short topic>
- **Works / Doesn't work:** ...
- **Solution / Rule:** ...
```

---

### 2026-10-22 — Antigravity global rules loading
- **Doesn't work:** `~/.gemini/config/rules/*.md` without YAML frontmatter (`trigger: always_on|model_decision|glob|manual`) is silently ignored. `~/.gemini/GEMINI.md` and `~/.gemini/config/GEMINI.md` both load and stack, so duplicates double the rules.
- **Solution / Rule:** keep one standalone global rules file; modular rule files always need frontmatter (source: antigravity.google/docs/rules).

### 2026-10-22 — Antigravity MCP config path
- **Works:** the documented global MCP config is `~/.gemini/config/mcp_config.json` (source: antigravity.google/docs/mcp). `~/.gemini/antigravity/mcp_config.json` is not documented.
- **Solution / Rule:** `setup.py` writes only the documented path and only when `~/.gemini` exists or `--antigravity` is passed.

### 2026-10-22 — Testing setup.py safely
- **Rule:** always run `python setup.py --home <temp dir>` when testing, so real user configs are untouched. Note: `.mcp.json` and `.claude/skills/` in the repo are still rewritten (gitignored).

### 2026-10-22 — Test plan stage 0 (offline part, `mcp_lab`)
- **Works:** `create_or_configure_addon`, `prepare_map_from_template`, `compile_addon_resource` for `.vmap` (12 compiled, 0 failed, ~9 s) without a running game. `Error creating shader generic.vfx` and missing `soundevents_test` / `nav_hulls` lines in the map compile log appear on a successful compile and do not block it.
- **Doesn't work:** fresh addon failed validation because of template `resource/flash3` (fixed, see BUG_LOG). `list_map_entities` returns every property of every entity (template map ≈ 5 KB of JSON) — heavy for context.
- **Rule:** code changes in `src/dota2_mcp/` take effect in the agent only after the MCP server restarts; test them directly via `.venv` Python meanwhile.

### 2026-10-22 — Commit messages from PowerShell
- **Doesn't work:** `git commit -F - @'...'@` in Windows PowerShell 5.1 — the here-string is passed as a pathspec, not stdin.
- **Solution / Rule:** write the message to a temp file and use `git commit -F <file>`.
