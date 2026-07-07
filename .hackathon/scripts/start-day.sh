#!/bin/bash
# start-day.sh
#
# Purpose: Prepare the environment at the start of a hackathon day.
#   - Copies the day-appropriate coaching content into CLAUDE.md
#   - Wipes .hackathon/logs/prompts.log for a fresh day's logging
#
# Usage: bash .hackathon/scripts/start-day.sh <day>
#   <day>  The current day number: 1, 2, or 3 (determined by the start-day skill)
#
# This script is deterministic — given the same day argument it always produces
# the same result. Day detection is the skill's responsibility, not this script's.

set -e

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a .hackathon/logs/error.log >&2
}

# ── Argument validation ──────────────────────────────────────────────────────

DAY="$1"

if [[ -z "$DAY" ]]; then
  log_error "No day argument provided."
  echo "Usage: bash .hackathon/scripts/start-day.sh <day>" >&2
  echo "  <day> must be 1, 2, or 3" >&2
  exit 1
fi

if [[ "$DAY" != "1" && "$DAY" != "2" && "$DAY" != "3" ]]; then
  log_error "Invalid day argument '$DAY'. Must be 1, 2, or 3."
  exit 1
fi

# ── Path setup ────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COACHING_FILE="$REPO_ROOT/.hackathon/coaching/day${DAY}.md"
CLAUDE_MD="$REPO_ROOT/CLAUDE.md"
PROMPTS_LOG="$REPO_ROOT/.hackathon/logs/prompts.log"

mkdir -p "$REPO_ROOT/.hackathon/logs"

# ── Step 1: Verify coaching content exists ────────────────────────────────────

if [[ ! -f "$COACHING_FILE" ]]; then
  log_error "Coaching file not found: $COACHING_FILE"
  log_error "The file .hackathon/coaching/day${DAY}.md must exist before running start-day."
  exit 1
fi

# ── Step 2: Copy coaching content into CLAUDE.md ─────────────────────────────

echo "Copying Day ${DAY} coaching content to CLAUDE.md..."
if ! cp "$COACHING_FILE" "$CLAUDE_MD"; then
  log_error "Failed to copy $COACHING_FILE to $CLAUDE_MD."
  exit 1
fi
echo "  Done: CLAUDE.md updated with .hackathon/coaching/day${DAY}.md"

# ── Step 3: Wipe the prompts log ──────────────────────────────────────────────

echo "Wiping prompts log..."
# Truncate (or create) the file — always results in an empty file
: > "$PROMPTS_LOG"
echo "  Done: .hackathon/logs/prompts.log cleared"

# ── Success ───────────────────────────────────────────────────────────────────

echo ""
echo "start-day complete for Day ${DAY}."
echo "  CLAUDE.md  → loaded from .hackathon/coaching/day${DAY}.md"
echo "  logs/prompts.log → cleared"
