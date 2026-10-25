"""Session budget hook for Claude Code (stdlib only).

Events (hook_event_name from stdin JSON):
  SessionStart     -> print "## Следующий шаг" and "## Проверить глазами" from .private/STATUS.md
  PostToolUse      -> context > 150k: remind once per session to /wrap; > 200k: every time, with СТОП
  UserPromptSubmit -> context > 150k and prompt not starting with "!": block, ask for a new session

Context size = input + cache_read + cache_creation tokens of the last assistant reply in the
transcript tail. Any failure -> exit 0 with no output, so the hook never breaks a session.
"""
import json
import os
import sys
import tempfile

WARN = 150_000
STOP = 200_000
TAIL_BYTES = 200 * 1024
MAX_STATUS_LINES = 40
SECTIONS = ("## Следующий шаг", "## Проверить глазами")


def out_text(text):
    sys.stdout.buffer.write(text.encode("utf-8"))


def out_json(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True))


def context_tokens(transcript_path):
    if not transcript_path or not os.path.isfile(transcript_path):
        return 0
    with open(transcript_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - TAIL_BYTES))
        lines = f.read().split(b"\n")
    if size > TAIL_BYTES:
        lines = lines[1:]  # first line is likely cut in half
    for raw in reversed(lines):
        if b'"usage"' not in raw:
            continue
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if entry.get("type") != "assistant" or entry.get("isSidechain"):
            continue
        usage = (entry.get("message") or {}).get("usage") or {}
        if not usage:
            continue
        return sum(int(usage.get(k) or 0) for k in (
            "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return 0


def status_sections(project_dir):
    path = os.path.join(project_dir, ".private", "STATUS.md")
    if not os.path.isfile(path):
        return "STATUS.md не найден"
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    picked, keep = [], False
    for line in lines:
        if line.startswith("## "):
            keep = line.strip() in SECTIONS
        if keep:
            picked.append(line)
    if not picked:
        return "STATUS.md: разделов «Следующий шаг» / «Проверить глазами» нет"
    return "\n".join(picked[:MAX_STATUS_LINES])


def marker_path(session_id):
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_") or "unknown"
    return os.path.join(tempfile.gettempdir(), "claude_budget_%s.flag" % safe)


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    event = data.get("hook_event_name", "")

    if event == "SessionStart":
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
        out_text(status_sections(project_dir) + "\n")
        return

    tokens = context_tokens(data.get("transcript_path"))
    if tokens <= WARN:
        return
    k = tokens // 1000

    if event == "PostToolUse":
        if tokens > STOP:
            msg = "СТОП. Контекст %dk > 200k: закончи текущий пункт и сделай /wrap" % k
        else:
            marker = marker_path(data.get("session_id"))
            if os.path.exists(marker):
                return
            open(marker, "w").close()
            msg = "Контекст > 150k (%dk): закончи текущий пункт и сделай /wrap" % k
        out_json({"hookSpecificOutput": {
            "hookEventName": "PostToolUse", "additionalContext": msg}})
    elif event == "UserPromptSubmit":
        if str(data.get("prompt", "")).lstrip().startswith("!"):
            return
        out_json({"decision": "block", "reason": (
            "Сессия большая (%dk). Открой новую сессию и напиши /stage <результат>. "
            "Чтобы всё же отправить сюда — начни с !" % k)})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
