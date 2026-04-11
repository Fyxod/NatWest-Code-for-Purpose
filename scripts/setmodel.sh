#!/usr/bin/env bash
set -e

echo " Pulling base model"
ollama pull gpt-oss:20b
ollama pull gemma3:12b

echo " Creating custom model gpt-oss:20b-50k-8k"
ollama create gpt-oss:20b-50k-8k -f scripts/model_oss
