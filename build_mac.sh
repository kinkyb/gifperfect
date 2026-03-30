#!/bin/bash
set -e

PYTHON=/opt/homebrew/bin/python3.12
APP_NAME="GIF Perfect"
VERSION="1.0.0"
DMG_NAME="GifPerfect-${VERSION}-mac.dmg"

echo "==> Building GIF Perfect for macOS..."

# Clean previous builds
rm -rf build dist

# Run PyInstaller
$PYTHON -m PyInstaller gifperfect.spec --noconfirm

echo "==> Build complete: dist/GifPerfect.app"

# Create DMG
echo "==> Creating DMG..."

# Install create-dmg if needed
if ! command -v create-dmg &>/dev/null; then
  echo "Installing create-dmg..."
  brew install create-dmg
fi

create-dmg \
  --volname "$APP_NAME" \
  --volicon "icon.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "GifPerfect.app" 150 180 \
  --hide-extension "GifPerfect.app" \
  --app-drop-link 450 180 \
  --no-internet-enable \
  "dist/$DMG_NAME" \
  "dist/GifPerfect.app"

echo "==> Done: dist/$DMG_NAME"
