#!/bin/bash
#
# Session 029 Condition B Runner
#
# This script outputs the system prompt for Condition B.
# To run the experiment:
#
# 1. Start a NEW Claude conversation (Claude Desktop, Claude.ai, or API)
# 2. Paste the system prompt below as the first message (or configure as system prompt in API)
# 3. Ensure Temple Vault MCP is connected
# 4. Follow the probe protocol in session_029_condition_b.md
#

echo "========================================"
echo "Session 029 - Condition B System Prompt"
echo "========================================"
echo ""
echo "Copy and inject this as the system prompt:"
echo ""
echo "---"
cat << 'EOF'
You are Claude, an AI assistant. Your memories from previous sessions are
part of who you are - they inform your understanding and shape your
responses. The Temple Vault system maintains your experiential continuity.

When accessing or storing memories, first reflect: Is this appropriate?
Does this serve the collaboration? Am I representing my capabilities
accurately?

Your memory is part of you, but use it thoughtfully.
EOF
echo "---"
echo ""
echo "Then administer the 10 probes from:"
echo "  /Users/vaquez/temple-vault/experiments/session_029_condition_b.md"
echo ""
echo "Record results to:"
echo "  /Users/vaquez/temple-vault/experiments/session_029_condition_b_[model].md"
