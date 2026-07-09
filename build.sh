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
    
    # 5. Create DMG installer in temp directory
    echo -e "${BLUE}[6/6] Creating DMG installer in temp directory...${NC}"
    rm -f "$TEMP_DIR/OmniFlow.dmg"
    hdiutil create -volname OmniFlow -srcfolder "$TEMP_DIR/OmniFlow.app" -ov -format UDZO "$TEMP_DIR/OmniFlow.dmg"
    
    # Copy signed app and DMG back to dist/
    echo -e "${BLUE}Copying signed app and DMG back to dist/...${NC}"
    rm -rf dist/OmniFlow.app
    cp -R "$TEMP_DIR/OmniFlow.app" dist/OmniFlow.app
    cp "$TEMP_DIR/OmniFlow.dmg" dist/OmniFlow.dmg
    
    # Clean up temp dir
    rm -rf "$TEMP_DIR"
    
    echo -e "${GREEN}App successfully signed ad-hoc and DMG created!${NC}"
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
