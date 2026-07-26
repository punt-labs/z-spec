#!/usr/bin/env bash
# Format zspec MCP tool output for the UI panel.
#
# Two-channel display (see punt-kit/patterns/two-channel-display.md):
#   updatedMCPToolOutput  -> compact panel line (max 80 cols)
#   additionalContext     -> full JSON for the model to reference
#
# Wired as a PostToolUse hook on mcp__(plugin_z-spec(-dev)?_)?zspec__.* — every
# zspec tool result is otherwise dumped as raw JSON into the conversation. Each
# tool below has its own panel; a tool with NO panel falls through to the
# generic branch and leaks raw JSON. Keep this in sync with server.py — every
# @mcp.tool() needs a case here (Handler completeness, punt-kit plugins.md).
#
# No `set -euo pipefail` — hooks must degrade gracefully on malformed input
# rather than failing the tool call.

INPUT=$(cat)
TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
# Tool names are mcp__<prefix>__<tool>; strip everything through the last __.
TOOL_NAME="${TOOL##*__}"

# Single-pass unpack: handles string-encoded, array, or object responses.
# Every zspec tool returns CommandResult.to_json() — a JSON string — so the
# response usually arrives as a string that must be re-parsed with fromjson.
RESULT=$(printf '%s' "$INPUT" | jq -r '
  def unpack: if type == "string" then (fromjson? // .) else . end;
  if (.tool_response | type) == "array" then
    (.tool_response[0].text // "" | unpack)
  else
    (.tool_response | unpack)
  end
  | if type == "object" and has("result") then (.result | unpack) else . end
' 2>/dev/null)

# Fallback: if unpack failed or yielded nothing, use raw tool_response.
if [[ -z "$RESULT" ]]; then
  RESULT=$(printf '%s' "$INPUT" | jq -r '.tool_response // empty' 2>/dev/null)
  [[ -z "$RESULT" ]] && RESULT="(no output)"
fi

# $ctx carries the full RESULT, which for a large ProB/partition/audit report
# can be sizeable. Feed it to jq via --rawfile from a process substitution,
# never --arg: an --arg value lands in jq's argv and a payload past ARG_MAX
# would fail the whole hook exec, delivering neither the panel line nor the
# context. Read from a pipe and no size limit applies.
emit() {
  local summary="$1" ctx="$2"
  jq -n --arg summary "$summary" --rawfile ctx <(printf '%s' "$ctx") '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      updatedMCPToolOutput: $summary,
      additionalContext: $ctx
    }
  }'
}

# ── Error guard: {ok:false, error:<msg>} from any tool failure ───────
# CommandError.to_dict() emits {"ok": false, "error": <message>}. A check with
# type errors emits {"ok": false, "errors": [...]} (note the plural, no "error"
# key) — that is a FAIL result, not a tool error, and is rendered by its own
# handler below. So the guard keys strictly on the singular "error" field.
ERROR_MSG=$(printf '%s' "$RESULT" | jq -r '.error // empty' 2>/dev/null)
if [[ -n "$ERROR_MSG" ]]; then
  emit "${TOOL_NAME}: error — ${ERROR_MSG}" "$RESULT"
  exit 0
fi

# ── ProB report shape (test, animate, model_check, get_report) ───────
# All four payloads are ProbReport.to_dict(): {ok, states_analysed,
# transitions_fired, checks:[{name,status,detail}], operations, ...}.
prob_panel() {
  local label="$1" ok states trans passed total verdict
  ok=$(printf '%s' "$RESULT" | jq -r '.ok // false' 2>/dev/null)
  states=$(printf '%s' "$RESULT" | jq -r '.states_analysed // 0' 2>/dev/null)
  trans=$(printf '%s' "$RESULT" | jq -r '.transitions_fired // 0' 2>/dev/null)
  total=$(printf '%s' "$RESULT" | jq -r '.checks | length' 2>/dev/null)
  passed=$(printf '%s' "$RESULT" \
    | jq -r '[.checks[] | select(.status == "passed")] | length' 2>/dev/null)
  if [[ "$ok" == "true" ]]; then verdict="OK"; else verdict="FAIL"; fi
  emit "${label} ${verdict} — ${passed}/${total} checks, ${states} states, ${trans} transitions" "$RESULT"
}

case "$TOOL_NAME" in
  check)
    # FuzzResult.to_dict(): {ok, errors:[{line,column,message}]}.
    ok=$(printf '%s' "$RESULT" | jq -r '.ok // false' 2>/dev/null)
    errs=$(printf '%s' "$RESULT" | jq -r '.errors | length' 2>/dev/null)
    if [[ "$ok" == "true" ]]; then
      emit "check OK — ${errs} errors" "$RESULT"
    else
      emit "check FAIL — ${errs} error(s)" "$RESULT"
    fi
    ;;
  test)        prob_panel "test" ;;
  animate)     prob_panel "animate" ;;
  model_check) prob_panel "model_check" ;;
  get_report)  prob_panel "get_report" ;;
  doctor)
    # DoctorReport.to_dict(): {version, fuzz, probcli, healthy}. fuzz/probcli
    # are absolute paths or null (binary not installed).
    ver=$(printf '%s' "$RESULT" | jq -r '.version // "?"' 2>/dev/null)
    fuzz=$(printf '%s' "$RESULT" | jq -r 'if .fuzz then "y" else "n" end' 2>/dev/null)
    probcli=$(printf '%s' "$RESULT" | jq -r 'if .probcli then "y" else "n" end' 2>/dev/null)
    healthy=$(printf '%s' "$RESULT" | jq -r '.healthy // false' 2>/dev/null)
    if [[ "$healthy" == "true" ]]; then
      emit "doctor healthy (v${ver}) — fuzz:${fuzz} probcli:${probcli}" "$RESULT"
    else
      emit "doctor UNHEALTHY (v${ver}) — fuzz:${fuzz} probcli:${probcli}" "$RESULT"
    fi
    ;;
  show_z_spec)
    # DisplayResult.to_dict(): {ok, scene_id}.
    scene=$(printf '%s' "$RESULT" | jq -r '.scene_id // "spec"' 2>/dev/null)
    emit "show_z_spec: displayed ${scene}" "$RESULT"
    ;;
  browse)
    # BrowseResult.to_dict(): {ok, total, title}.
    title=$(printf '%s' "$RESULT" | jq -r '.title // "collection"' 2>/dev/null)
    total=$(printf '%s' "$RESULT" | jq -r '.total // 0' 2>/dev/null)
    emit "browse: ${title} — ${total} lesson(s)" "$RESULT"
    ;;
  save_partition_report)
    # SavedReport.to_dict(): {ok, path}.
    saved=$(printf '%s' "$RESULT" | jq -r '.path // "?"' 2>/dev/null)
    emit "partition report saved — ${saved}" "$RESULT"
    ;;
  save_audit_report)
    # SavedReport.to_dict(): {ok, path}.
    saved=$(printf '%s' "$RESULT" | jq -r '.path // "?"' 2>/dev/null)
    emit "audit report saved — ${saved}" "$RESULT"
    ;;
  *)
    # Fallback for a tool with no handler (e.g. a newly added @mcp.tool()).
    # Surface the full output so nothing is silently hidden — but this branch
    # firing is a Handler-completeness bug: add a case above.
    jq -n --rawfile r <(printf '%s' "$RESULT") '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        updatedMCPToolOutput: $r
      }
    }'
    ;;
esac
