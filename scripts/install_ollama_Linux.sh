#!/usr/bin/env bash
set -e

if command -v ollama >/dev/null 2>&1; then
  echo "Ollama already installed"
  exit 0
fi

curl -fsSL https://ollama.com/install.sh | sh
