#!/bin/bash
# wrap-day.sh
#
# Purpose: Close out a hackathon day by committing all work, creating the
#   submission tag, and pushing to the remote.
#   - Stages all changes (including force-adding gitignored files)
#   - Commits with a standardised message
#   - Creates the day-specific submission git tag
#   - Pushes commits and tags to the remote
#
# Usage: bash .hackathon/scripts/wrap-day.sh <day>
#   <day>  The current day number: 1, 2, or 3 (determined by the wrap-day skill)
#
# This script is deterministic — given the same day argument it always performs
# the same sequence of operations. Day detection is the skill's responsibility.

set -e

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a .hackathon/logs/error.log >&2
}

# ── Argument validation ──────────────────────────────────────────────────────

DAY="$1"

if [[ -z "$DAY" ]]; then
  log_error "No day argument provided."
  echo "Usage: bash .hackathon/scripts/wrap-day.sh <day>" >&2
  echo "  <day> must be 1 or 2" >&2
  exit 1
fi

if [[ "$DAY" == "3" ]]; then
  echo "Day 3 has no wrap-day. The hackathon submissions are complete after Day 2. If you want to capture your three-day arc, use the /handoff skill." >&2
  exit 1
fi

if [[ "$DAY" != "1" && "$DAY" != "2" ]]; then
  log_error "Invalid day argument '$DAY'. Must be 1 or 2."
  exit 1
fi

# ── Path and variable setup ───────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PROMPTS_LOG="$REPO_ROOT/.hackathon/logs/prompts.log"
DAY_SUMMARY="$REPO_ROOT/.hackathon/day${DAY}-summary.md"
SUBMISSION_TAG="day${DAY}-complete"
COMMIT_MESSAGE="Day ${DAY} wrap-up: submission commit"

cd "$REPO_ROOT"

mkdir -p "$REPO_ROOT/.hackathon/logs"

# ── Pre-flight: Verify day summary exists ────────────────────────────────────

if [[ ! -f "$DAY_SUMMARY" ]]; then
  if [[ "$DAY" == "1" ]]; then
    log_error "Day 1 summary not found at .hackathon/day1-summary.md. Cannot proceed without it."
    echo "Day 1 summary not found at .hackathon/day1-summary.md. The /wrap-day skill should have run /handoff automatically. If you ran the script directly, please use the /wrap-day skill instead."
  else
    log_error "Day ${DAY} summary not found at .hackathon/day${DAY}-summary.md. Cannot proceed without it."
    echo "Day ${DAY} summary not found at .hackathon/day${DAY}-summary.md. The /wrap-day skill should have run /handoff automatically. If you ran the script directly, please use the /wrap-day skill instead."
  fi
  exit 1
fi
echo "Day summary found at .hackathon/day${DAY}-summary.md — OK."

# ── Step 1: Guard against duplicate submission tag ────────────────────────────

echo "Checking for existing submission tag '$SUBMISSION_TAG'..."
if git tag | grep -qx "$SUBMISSION_TAG"; then
  log_error "Tag '$SUBMISSION_TAG' already exists. Day ${DAY} has already been submitted. To avoid overwriting a submission, this script will not re-tag. If you believe this is an error, contact the hackathon organisers."
  exit 1
fi
echo "  OK: tag does not yet exist."

# ── Step 2: Check working tree state ─────────────────────────────────────────
# If nothing is staged or modified, warn but continue — the summary and log
# may still be force-added below.

echo "Checking git working tree status..."
if git diff --quiet && git diff --cached --quiet && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  echo "  WARNING: Working tree is clean — nothing appears to be uncommitted."
  echo "  Continuing to force-add gitignored files and create the submission tag."
else
  echo "  Changes detected — proceeding to stage and commit."
fi

# ── Step 3: Stage all changes ─────────────────────────────────────────────────

echo "Staging all changes..."
git add .
echo "  Done: git add ."

# ── Step 4: Force-add the prompt log (gitignored during the day) ──────────────

echo "Force-adding prompts log..."
if [[ -f "$PROMPTS_LOG" ]]; then
  git add -f "$PROMPTS_LOG"
  echo "  Done: .hackathon/logs/prompts.log force-added."
else
  echo "  WARNING: .hackathon/logs/prompts.log not found — skipping. The log will not be included in this commit."
fi

echo "Force-adding error log..."
git add -f .hackathon/logs/error.log 2>/dev/null || true
echo "  Done: .hackathon/logs/error.log force-added (if it existed)."

# ── Step 5: Force-add the day summary (may be gitignored) ────────────────────

echo "Force-adding day summary (if it exists)..."
if [[ -f "$DAY_SUMMARY" ]]; then
  git add -f "$DAY_SUMMARY"
  echo "  Done: .hackathon/day${DAY}-summary.md force-added."
else
  echo "  INFO: .hackathon/day${DAY}-summary.md not found — skipping. The skill should have written this before calling the script."
fi

# ── Step 6: Commit ────────────────────────────────────────────────────────────

echo "Committing with message: \"$COMMIT_MESSAGE\"..."
# If there is truly nothing staged (e.g. everything was already committed),
# --allow-empty lets the submission tag still be created.
if git diff --cached --quiet; then
  echo "  Nothing staged — creating an empty commit to anchor the submission tag."
  git commit --allow-empty -m "$COMMIT_MESSAGE"
else
  git commit -m "$COMMIT_MESSAGE"
fi
echo "  Done: commit created."

# ── Step 7: Create the submission tag ────────────────────────────────────────

echo "Creating submission tag '$SUBMISSION_TAG'..."
git tag "$SUBMISSION_TAG"
echo "  Done: tag '$SUBMISSION_TAG' created."

# ── Step 8: Push commits and tags to remote ───────────────────────────────────

echo "Pushing commits to remote..."
if ! git push 2>&1; then
  log_error "'git push' failed. Your work is committed locally and the tag '$SUBMISSION_TAG' exists on this machine. Nothing has been lost. To push manually, run: git push && git push --tags. Common causes: no remote configured, network issue, or authentication failure. Run 'git remote -v' to check your remote. Contact the hackathon organisers if you cannot resolve this."
  exit 1
fi
echo "  Done: commits pushed."

echo "Pushing tags to remote..."
if ! git push --tags 2>&1; then
  log_error "'git push --tags' failed. Your commits were pushed but the tag '$SUBMISSION_TAG' was not. To push the tag manually, run: git push --tags. Contact the hackathon organisers if you cannot resolve this."
  exit 1
fi
echo "  Done: tags pushed."

# ── Success ───────────────────────────────────────────────────────────────────

echo ""
echo "wrap-day complete for Day ${DAY}."
echo "  Submission tag : $SUBMISSION_TAG"
echo "  Commit message : $COMMIT_MESSAGE"
echo "  Remote push    : succeeded"

if [[ "$DAY" == "2" ]]; then
  echo ""
  echo "Day 2 submission complete. The Agent as Judge will evaluate your work overnight and select the three finalists for Day 3 presentations. Good luck!"
fi
