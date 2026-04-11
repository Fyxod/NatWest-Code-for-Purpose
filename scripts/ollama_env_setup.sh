#!/bin/bash
# ==============================================================================
# Ollama Performance Environment Variables — Dual Instance Setup (Ubuntu)
# ==============================================================================
#
# This project runs TWO Ollama instances:
#   - Instance 1: Port 11434 (default)
#   - Instance 2: Port 11435
#
# ── OPTION 1: systemd services (RECOMMENDED for Ubuntu) ──────────────────────
#
#   sudo bash scripts/ollama_env_setup.sh --install-services
#
#   This creates two systemd services with all optimizations baked in.
#   Manage them with:
#     sudo systemctl start ollama-1 ollama-2
#     sudo systemctl stop ollama-1 ollama-2
#     sudo systemctl status ollama-1 ollama-2
#     journalctl -u ollama-1 -f    # view logs
#     journalctl -u ollama-2 -f
#
# ── OPTION 2: Manual terminal launch ─────────────────────────────────────────
#
#   # Terminal 1:
#   source scripts/ollama_env_setup.sh
#   OLLAMA_HOST=0.0.0.0:11434 ollama serve
#
#   # Terminal 2:
#   source scripts/ollama_env_setup.sh
#   OLLAMA_HOST=0.0.0.0:11435 ollama serve
#
# ── OPTION 3: Windows (setx) ─────────────────────────────────────────────────
#
#   setx OLLAMA_FLASH_ATTENTION 1
#   setx OLLAMA_KV_CACHE_TYPE q8_0
#   setx OLLAMA_NUM_PARALLEL 2
#   setx OLLAMA_MAX_LOADED_MODELS 3
#   setx OLLAMA_KEEP_ALIVE -1
#   (Then restart both Ollama instances)
#
# ==============================================================================

# ── Performance env vars (shared by both instances) ──────────────────────────

# Flash Attention: Zero quality loss, 10-20% faster attention computation
export OLLAMA_FLASH_ATTENTION=1

# KV Cache Quantization: 50% VRAM reduction for KV cache
# ⚠️  WARNING: If GPT-OSS:20B is Gemma3-based, comment out this line
#     (known regression: ~30 tok/s → ~5 tok/s on Gemma3 with q8_0)
export OLLAMA_KV_CACHE_TYPE=q8_0

# Allow 2 concurrent requests per model per instance
export OLLAMA_NUM_PARALLEL=2

# Keep main model + VLM model loaded in VRAM
export OLLAMA_MAX_LOADED_MODELS=3

# Keep models loaded indefinitely (no cold-start latency)
export OLLAMA_KEEP_ALIVE=-1

# ── systemd installer ────────────────────────────────────────────────────────

install_services() {
    echo "============================================="
    echo " Installing Ollama systemd services (×2)"
    echo "============================================="

    OLLAMA_BIN=$(which ollama 2>/dev/null || echo "/usr/local/bin/ollama")
    if [ ! -f "$OLLAMA_BIN" ]; then
        echo "ERROR: ollama binary not found. Install Ollama first."
        exit 1
    fi

    OLLAMA_USER="${SUDO_USER:-$USER}"
    echo "Ollama binary: $OLLAMA_BIN"
    echo "Running as user: $OLLAMA_USER"

    # ── Instance 1: Port 11434 ──
    cat > /etc/systemd/system/ollama-1.service <<UNIT
[Unit]
Description=Ollama LLM Server (Port 11434)
After=network-online.target

[Service]
ExecStart=$OLLAMA_BIN serve
User=$OLLAMA_USER
Group=$OLLAMA_USER
Restart=always
RestartSec=3

# Performance environment variables
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_MAX_LOADED_MODELS=3"
Environment="OLLAMA_KEEP_ALIVE=-1"

[Install]
WantedBy=default.target
UNIT

    # ── Instance 2: Port 11435 ──
    cat > /etc/systemd/system/ollama-2.service <<UNIT
[Unit]
Description=Ollama LLM Server (Port 11435)
After=network-online.target

[Service]
ExecStart=$OLLAMA_BIN serve
User=$OLLAMA_USER
Group=$OLLAMA_USER
Restart=always
RestartSec=3

# Performance environment variables
Environment="OLLAMA_HOST=0.0.0.0:11435"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_KV_CACHE_TYPE=q8_0"
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_MAX_LOADED_MODELS=3"
Environment="OLLAMA_KEEP_ALIVE=-1"

[Install]
WantedBy=default.target
UNIT

    # ── Stop default Ollama service if running ──
    if systemctl is-active --quiet ollama 2>/dev/null; then
        echo "Stopping default 'ollama' service..."
        systemctl stop ollama
        systemctl disable ollama
    fi

    # ── Enable and start both ──
    systemctl daemon-reload
    systemctl enable ollama-1 ollama-2
    systemctl start ollama-1
    systemctl start ollama-2

    echo ""
    echo "✓ ollama-1 (port 11434): $(systemctl is-active ollama-1)"
    echo "✓ ollama-2 (port 11435): $(systemctl is-active ollama-2)"
    echo ""
    echo "Commands:"
    echo "  sudo systemctl status ollama-1 ollama-2"
    echo "  sudo systemctl restart ollama-1 ollama-2"
    echo "  journalctl -u ollama-1 -f"
    echo "  journalctl -u ollama-2 -f"
}

# ── Entry point ──────────────────────────────────────────────────────────────

if [ "$1" = "--install-services" ]; then
    if [ "$EUID" -ne 0 ] && [ "$(id -u)" -ne 0 ]; then
        echo "ERROR: Run with sudo:  sudo bash scripts/ollama_env_setup.sh --install-services"
        exit 1
    fi
    install_services
else
    echo "[Ollama] Performance environment variables set:"
    echo "  OLLAMA_FLASH_ATTENTION=$OLLAMA_FLASH_ATTENTION"
    echo "  OLLAMA_KV_CACHE_TYPE=$OLLAMA_KV_CACHE_TYPE"
    echo "  OLLAMA_NUM_PARALLEL=$OLLAMA_NUM_PARALLEL"
    echo "  OLLAMA_MAX_LOADED_MODELS=$OLLAMA_MAX_LOADED_MODELS"
    echo "  OLLAMA_KEEP_ALIVE=$OLLAMA_KEEP_ALIVE"
    echo ""
    echo "To launch manually:"
    echo "  Terminal 1: OLLAMA_HOST=0.0.0.0:11434 ollama serve"
    echo "  Terminal 2: OLLAMA_HOST=0.0.0.0:11435 ollama serve"
    echo ""
    echo "To install as systemd services (recommended):"
    echo "  sudo bash scripts/ollama_env_setup.sh --install-services"
fi
