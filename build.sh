#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Colors for output formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting OmniFlow Build Process ===${NC}"

# 1. Setup/Activate Python virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}[1/6] Creating Python virtual environment .venv...${NC}"
    python3 -m venv .venv
else
    echo -e "${GREEN}[1/6] Python virtual environment .venv already exists.${NC}"
fi

echo -e "${BLUE}[2/6] Activating virtual environment and updating dependencies...${NC}"
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

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
pyinstaller OmniFlow.spec --noconfirm --clean

# 4. Strip extended attributes and sign ad-hoc in a temp folder to bypass iCloud FileProvider issues
echo -e "${BLUE}[5/6] Stripping extended attributes and signing ad-hoc in a temp directory...${NC}"
if [ -d "dist/OmniFlow.app" ]; then
    TEMP_DIR="$HOME/OnmiFlow_temp"
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    
    # Copy to temp directory outside iCloud
    cp -R dist/OmniFlow.app "$TEMP_DIR/OmniFlow.app"
    
    # Strip attributes and sign
    xattr -cr "$TEMP_DIR/OmniFlow.app"
    codesign --force --deep --sign - "$TEMP_DIR/OmniFlow.app"
    
    # 5. Create DMG installer with an Applications shortcut for drag-and-drop install
    echo -e "${BLUE}[6/6] Creating DMG installer with Applications shortcut...${NC}"
    STAGING_DIR="$TEMP_DIR/dmg_staging"
    rm -rf "$STAGING_DIR"
    mkdir -p "$STAGING_DIR"
    cp -R "$TEMP_DIR/OmniFlow.app" "$STAGING_DIR/OmniFlow.app"
    ln -s /Applications "$STAGING_DIR/Applications"

    # Detach a stale "OmniFlow" volume left mounted from a previous run, if any
    if [ -d "/Volumes/OmniFlow" ]; then
        hdiutil detach "/Volumes/OmniFlow" -force >/dev/null 2>&1 || true
    fi

    RW_DMG="$TEMP_DIR/OmniFlow-rw.dmg"
    rm -f "$RW_DMG"
    hdiutil create -volname OmniFlow -srcfolder "$STAGING_DIR" -ov -format UDRW -fs HFS+ "$RW_DMG"
    MOUNT_OUTPUT=$(hdiutil attach "$RW_DMG" -readwrite -noverify -noautoopen)
    MOUNT_DIR=$(echo "$MOUNT_OUTPUT" | grep -o '/Volumes/OmniFlow.*')

    # Best-effort Finder styling (icon layout) — arranges the app + Applications
    # shortcut side by side. Backgrounded with a hard 15s cutoff so a missing
    # Finder-automation permission (System Settings > Privacy > Automation) can
    # never hang the build; the DMG is still fully functional without this step,
    # just with default icon placement.
    osascript <<APPLESCRIPT &
tell application "Finder"
    tell disk "OmniFlow"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 700, 420}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set position of item "OmniFlow.app" of container window to {125, 150}
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
    hdiutil detach "$MOUNT_DIR" -force >/dev/null 2>&1 || hdiutil detach "/Volumes/OmniFlow" -force >/dev/null 2>&1 || true

    rm -f "$TEMP_DIR/OmniFlow.dmg"
    hdiutil convert "$RW_DMG" -format UDZO -ov -o "$TEMP_DIR/OmniFlow.dmg"
    rm -f "$RW_DMG"

    # Copy signed app and DMG back to dist/
    echo -e "${BLUE}Copying signed app and DMG back to dist/...${NC}"
    rm -rf dist/OmniFlow.app
    cp -R "$TEMP_DIR/OmniFlow.app" dist/OmniFlow.app
    cp "$TEMP_DIR/OmniFlow.dmg" dist/OmniFlow.dmg
    
    # Clean up temp dir
    rm -rf "$TEMP_DIR"
    
    echo -e "${GREEN}App successfully signed ad-hoc and DMG created with an Applications shortcut!${NC}"
else
    echo -e "${RED}Error: dist/OmniFlow.app was not created!${NC}"
    exit 1
fi

# 6. Clean up temporary build files
echo -e "${BLUE}Cleaning up temporary build artifacts...${NC}"
rm -rf build/
echo -e "${GREEN}Temporary build/ folder removed.${NC}"

echo -e "\n${GREEN}=== Build Completed Successfully! ===${NC}"
echo -e "You can find and run your app here:"
echo -e "  - Standalone App: ${BLUE}dist/OmniFlow.app${NC}"
echo -e "  - DMG Installer:  ${BLUE}dist/OmniFlow.dmg${NC}"
echo -e "Double-click ${BLUE}dist/OmniFlow.app${NC} to start and test it!\n"
