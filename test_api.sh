#!/bin/bash
# End-to-end test script for Docu-Sync API

echo "🧪 Testing Docu-Sync API - End-to-End Workflow"
echo "=============================================="
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
curl -s http://localhost:8080/health | python -m json.tool
echo ""
echo ""

# Test 2: Detect Changes
echo "Test 2: Detect UI Changes"
echo "-------------------------"
# Run from the repo root: bash test_api.sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/demo"
curl -s -X POST http://localhost:8080/detect-change \
  -F "old_image=@demo_before.png" \
  -F "new_image=@demo_after.png" | python -m json.tool
echo ""
echo ""

# Test 3: Generate Documentation Update
echo "Test 3: Generate Documentation Update (Gemini AI)"
echo "--------------------------------------------------"
curl -s -X POST http://localhost:8080/generate-update \
  -H "Content-Type: application/json" \
  -d '{
    "change_summary": "Button color changed from blue to green. Text changed from Submit Form to Continue.",
    "current_readme": "## UI Components\nOur app has a blue submit button for form submission."
  }' | python -m json.tool
echo ""
echo ""

echo "✅ All tests complete!"
echo ""
echo "Note: Test 3 (Create PR) is skipped to avoid creating test PRs."
echo "You can test it manually if needed."
