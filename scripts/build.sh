#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Colors for output formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting ViDrop Build Process ===${NC}"

# Which Mac this build is for. The DMG is named after it so both can live side by side
# in a release: ViDrop-AppleSilicon.dmg (arm64) and ViDrop-Intel.dmg (x86_64).
# Defaults build for THIS machine with .venv. For the Intel build on an Apple Silicon Mac
# (needs Rosetta 2), point it at the x86_64 Python:
#   PYTHON_BIN=envs/x86_64/bin/python ARCH_PREFIX="arch -x86_64" TARGET_ARCH=x86_64 ./scripts/build.sh
#
# WHERE THINGS GO. The result is published under release/v<VERSION>/ (VERSION is read from
# frontend/package.json, the one place the version lives):
#   release/v<VERSION>/<DMG_NAME>                the installer
#   release/v<VERSION>/SHA256SUMS.txt            refreshed from every DMG in that folder
#   release/v<VERSION>/_build/<arch>/ViDrop.app  the signed app the DMG was made from
# A DMG of the same name that is already there is moved to release/_archive/, never deleted.
# Everything else (PyInstaller's output and work files) goes to build/, which is temporary and
# removed at the end. RELEASE_ROOT overrides the release/ folder (used when building from a
# git worktree whose release/ lives in the main checkout).
TARGET_ARCH="${TARGET_ARCH:-$(uname -m)}"
if [ "$TARGET_ARCH" = "arm64" ]; then DMG_NAME="ViDrop-AppleSilicon.dmg"; else DMG_NAME="ViDrop-Intel.dmg"; fi
VERSION="$(python3 -c "import json; print(json.load(open('frontend/package.json'))['version'])")"
RELEASE_ROOT="${RELEASE_ROOT:-release}"
RELEASE_DIR="$RELEASE_ROOT/v$VERSION"
DIST_DIR="${DIST_DIR:-build/dist-$TARGET_ARCH}"
PYTHON_BIN="${PYTHON_BIN:-}"
ARCH_PREFIX="${ARCH_PREFIX:-}"

# 1. Setup/Activate Python virtual environment
if [ -n "$PYTHON_BIN" ]; then
    echo -e "${GREEN}[1/6] Using $PYTHON_BIN (${TARGET_ARCH}) instead of .venv.${NC}"
elif [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[1/6] Creating Python virtual environment .venv...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}[1/6] Python virtual environment .venv already exists.${NC}"
fi

echo -e "${BLUE}[2/6] Activating virtual environment and updating dependencies...${NC}"
if [ -n "$PYTHON_BIN" ]; then
    $ARCH_PREFIX "$PYTHON_BIN" -m pip install --upgrade pip
    $ARCH_PREFIX "$PYTHON_BIN" -m pip install -r requirements.txt
else
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# 2. Build the React Frontend
echo -e "${BLUE}[3/6] Building React frontend...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}node_modules not found, running npm install...${NC}"
    npm install
fi
npm run build
cd ..

# 3. Build standalone macOS app using PyInstaller
echo -e "${BLUE}[4/6] Packaging desktop app with PyInstaller...${NC}"
if [ -n "$PYTHON_BIN" ]; then
    $ARCH_PREFIX "$PYTHON_BIN" -m PyInstaller vidrop.spec --noconfirm --clean --distpath "$DIST_DIR"
else
    pyinstaller vidrop.spec --noconfirm --clean --distpath "$DIST_DIR"
fi

# 4. Strip extended attributes and sign ad-hoc in a temp folder to bypass iCloud FileProvider issues
echo -e "${BLUE}[5/6] Stripping extended attributes and signing ad-hoc in a temp directory...${NC}"
if [ -d "$DIST_DIR/ViDrop.app" ]; then
    TEMP_DIR="$HOME/ViDrop_temp"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    # Copy to temp directory outside iCloud
    cp -R "$DIST_DIR/ViDrop.app" "$TEMP_DIR/ViDrop.app"
    
    # Strip attributes and sign
    xattr -cr "$TEMP_DIR/ViDrop.app"
    codesign --force --deep --sign - "$TEMP_DIR/ViDrop.app"
    
    # 5. Create DMG installer with an Applications shortcut for drag-and-drop install
    echo -e "${BLUE}[6/6] Creating DMG installer with Applications shortcut...${NC}"
    STAGING_DIR="$TEMP_DIR/dmg_staging"
    rm -rf "$STAGING_DIR"
    mkdir -p "$STAGING_DIR"
    cp -R "$TEMP_DIR/ViDrop.app" "$STAGING_DIR/ViDrop.app"
    ln -s /Applications "$STAGING_DIR/Applications"

    # Detach a stale "ViDrop" volume left mounted from a previous run, if any
    if [ -d "/Volumes/ViDrop" ]; then
        hdiutil detach "/Volumes/ViDrop" -force >/dev/null 2>&1 || true
    fi

    RW_DMG="$TEMP_DIR/ViDrop-rw.dmg"
    rm -f "$RW_DMG"
    hdiutil create -volname ViDrop -srcfolder "$STAGING_DIR" -ov -format UDRW -fs HFS+ "$RW_DMG"
    MOUNT_OUTPUT=$(hdiutil attach "$RW_DMG" -readwrite -noverify -noautoopen)
    MOUNT_DIR=$(echo "$MOUNT_OUTPUT" | grep -o '/Volumes/ViDrop.*')

    # Best-effort Finder styling (icon layout) — arranges the app + Applications
    # shortcut side by side. Backgrounded with a hard 15s cutoff so a missing
    # Finder-automation permission (System Settings > Privacy > Automation) can
    # never hang the build; the DMG is still fully functional without this step,
    # just with default icon placement.
    osascript <<APPLESCRIPT &
tell application "Finder"
    tell disk "ViDrop"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 700, 420}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set position of item "ViDrop.app" of container window to {125, 150}
        set position of item "Applications" of container window to {375, 150}
        close
        open
        update without registering applications
        delay 1
    end tell
end tell
APPLESCRIPT
    OSA_PID=$!
    for i in $(seq 1 15); do
        kill -0 $OSA_PID 2>/dev/null || break
        sleep 1
    done
    kill $OSA_PID 2>/dev/null || true

    sync
    hdiutil detach "$MOUNT_DIR" -force >/dev/null 2>&1 || hdiutil detach "/Volumes/ViDrop" -force >/dev/null 2>&1 || true

    rm -f "$TEMP_DIR/$DMG_NAME"
    hdiutil convert "$RW_DMG" -format UDZO -ov -o "$TEMP_DIR/$DMG_NAME"
    rm -f "$RW_DMG"

    # Copy signed app and DMG back to dist/
    echo -e "${BLUE}Copying the signed app and the DMG next to the build output...${NC}"
    rm -rf "$DIST_DIR/ViDrop.app"
    cp -R "$TEMP_DIR/ViDrop.app" "$DIST_DIR/ViDrop.app"
    cp "$TEMP_DIR/$DMG_NAME" "$DIST_DIR/$DMG_NAME"
    
    # Clean up temp dir
    rm -rf "$TEMP_DIR"
    
    echo -e "${GREEN}App successfully signed ad-hoc and DMG created with an Applications shortcut!${NC}"
else
    echo -e "${RED}Error: $DIST_DIR/ViDrop.app was not created!${NC}"
    exit 1
fi

# 6. Publish into release/v<VERSION>/ (nothing already there is deleted)
echo -e "${BLUE}Publishing to $RELEASE_DIR ...${NC}"
mkdir -p "$RELEASE_DIR/_build/$TARGET_ARCH"
if [ -f "$RELEASE_DIR/$DMG_NAME" ]; then
    mkdir -p "$RELEASE_ROOT/_archive/v$VERSION-replaced"
    mv "$RELEASE_DIR/$DMG_NAME" "$RELEASE_ROOT/_archive/v$VERSION-replaced/$(date +%Y%m%d-%H%M%S)-$DMG_NAME"
fi
if [ -d "$RELEASE_DIR/_build/$TARGET_ARCH/ViDrop.app" ]; then
    mkdir -p "$RELEASE_ROOT/_archive/v$VERSION-replaced"
    mv "$RELEASE_DIR/_build/$TARGET_ARCH/ViDrop.app" "$RELEASE_ROOT/_archive/v$VERSION-replaced/$(date +%Y%m%d-%H%M%S)-$TARGET_ARCH-ViDrop.app"
fi
cp -R "$DIST_DIR/ViDrop.app" "$RELEASE_DIR/_build/$TARGET_ARCH/ViDrop.app"
cp "$DIST_DIR/$DMG_NAME" "$RELEASE_DIR/$DMG_NAME"
(cd "$RELEASE_DIR" && shasum -a 256 *.dmg > SHA256SUMS.txt)

# 7. Clean up temporary build files (build/ also holds the PyInstaller output folder)
echo -e "${BLUE}Cleaning up temporary build artifacts...${NC}"
rm -rf build/ .ffmpeg_stage/
echo -e "${GREEN}Temporary build/ and .ffmpeg_stage/ folders removed.${NC}"

echo -e "\n${GREEN}=== Build Completed Successfully! ===${NC}"
echo -e "  - DMG Installer:  ${BLUE}$RELEASE_DIR/$DMG_NAME${NC}"
echo -e "  - Standalone App: ${BLUE}$RELEASE_DIR/_build/$TARGET_ARCH/ViDrop.app${NC}"
echo -e "  - Checksums:      ${BLUE}$RELEASE_DIR/SHA256SUMS.txt${NC}"
echo -e "Double-click the app to start and test it!\n"
