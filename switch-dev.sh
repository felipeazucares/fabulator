#!/bin/bash
set -e

case $1 in
  claude)
    rm -rf .devcontainer  # Changed to -rf
    ln -s .devcontainer-claude .devcontainer
    echo "✓ Switched to Claude. Run: code ."
    ;;
  qwen)
    rm -rf .devcontainer  # Changed to -rf
    ln -s .devcontainer-qwen .devcontainer
    echo "✓ Switched to Qwen. Run: code ."
    ;;
  *)
    echo "Usage: ./switch-dev.sh [claude|qwen]"
    exit 1
    ;;
esac