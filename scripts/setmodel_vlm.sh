#!/usr/bin/env bash
set -e

echo "=== Pulling VLM (Vision Language Model) for PDF/Slide Parsing ==="
echo ""

# Pull the Qwen3-VL model for visual document understanding
echo "Pulling qwen3-vl:8b (Vision model for slide/PDF text extraction)..."
ollama pull qwen3-vl:8b

echo ""
echo "=== VLM Model Setup Complete ==="
echo ""
echo "To verify, run:  ollama list"
echo "To test, run:    ollama run qwen3-vl:8b 'describe this image' --images test.png"
echo ""
echo "The VLM will be used automatically when:"
echo "  1. PDF pages have low text density (auto-detect mode)"
echo "  2. USE_VLM_FOR_PDF=True is set in .env (force mode)"
