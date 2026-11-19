#!/usr/bin/env bash
# End-to-end local smoke test on the Engineering Explained pilot. Zero paid calls.
# Uses a throwaway projects dir so it never touches your real workspace.
#   ./scripts/smoke_test.sh            # mock (silent placeholder) narration
#   VOICE=macos_say ./scripts/smoke_test.sh   # listenable local preview (macOS only)
set -euo pipefail
cd "$(dirname "$0")/.."

export STUDIO_PROJECTS_DIR="${STUDIO_PROJECTS_DIR:-$(mktemp -d)/projects}"
VOICE="${VOICE:-mock}"
S() { uv run studio "$@" </dev/null; }

echo "== workspace: $STUDIO_PROJECTS_DIR"
S init
S channels list
S ideas --channel engineering_explained --count 5
S episode create --channel engineering_explained \
  --topic "How undersea internet cables work" --minutes 9
EP=ee-0001
S research "$EP"
S claim import-proposals "$EP" samples/undersea_cables/verification_proposals.json
S script "$EP"
S storyboard "$EP"
S assets build "$EP"
S assets check "$EP" || echo "(expected: placeholder/preview narration licence blocks)"
S voice "$EP" --provider "$VOICE" --dry-run
S voice "$EP" --provider "$VOICE"
S cost preflight "$EP"
S render "$EP" --preview
S render "$EP"
S shorts "$EP" --count 3 --provider "$VOICE"
S review "$EP" || true
echo "== approval must be refused while claims are unverified:"
if S decide "$EP" approve --reviewer smoke --ai-disclosure no; then
  echo "FAIL: approval should have been blocked"; exit 1
fi
echo "== publish must be refused without approval:"
if S publish "$EP"; then echo "FAIL: publish should have been blocked"; exit 1; fi
S analytics --mock
S cost report
S episode show "$EP"
echo "== SMOKE TEST OK. Outputs under $STUDIO_PROJECTS_DIR"
