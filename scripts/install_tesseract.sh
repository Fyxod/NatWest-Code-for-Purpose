#!/usr/bin/env bash

set -e

echo "Detecting Linux distribution..."

if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
else
    echo "Cannot detect distribution."
    exit 1
fi

echo "Detected: $DISTRO"
echo "Installing Tesseract..."

case "$DISTRO" in
    ubuntu|debian)
        sudo apt update
        sudo apt install -y tesseract-ocr tesseract-ocr-eng
        ;;
    arch|manjaro|garuda)
        sudo pacman -Sy --noconfirm tesseract tesseract-data-eng
        ;;
    fedora)
        sudo dnf install -y tesseract tesseract-langpack-eng
        ;;
    opensuse*)
        sudo zypper install -y tesseract-ocr
        ;;
    *)
        echo "Unsupported distribution: $DISTRO"
        echo "Install manually from: https://github.com/tesseract-ocr/tesseract"
        exit 1
        ;;
esac

echo "Installation complete."

echo "Verifying..."
if command -v tesseract >/dev/null 2>&1; then
    echo "Tesseract installed successfully."
    tesseract --version
else
    echo "Installation failed or PATH not updated."
fi
