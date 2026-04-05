#!/bin/bash
# ReefPilot iOS Setup Script
# Run this after installing Node.js and Xcode

set -e

echo "=== ReefPilot iOS Setup ==="
echo ""

# Check prerequisites
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is required. Install it from https://nodejs.org/"
    exit 1
fi

if ! command -v xcodebuild &> /dev/null; then
    echo "ERROR: Xcode is required. Install it from the App Store."
    exit 1
fi

echo "1. Installing npm dependencies..."
npm install

echo ""
echo "2. Adding iOS platform..."
npx cap add ios

echo ""
echo "3. Syncing web assets to iOS project..."
npx cap sync ios

echo ""
echo "4. Copying app icons..."
ICON_DIR="ios/App/App/Assets.xcassets/AppIcon.appiconset"
if [ -d "$ICON_DIR" ]; then
    cp static/reef/icons/icon-1024.png "$ICON_DIR/AppIcon-1024.png" 2>/dev/null || true
    echo "   1024px icon copied."

    # Create the Contents.json for the App Icon set (single 1024px icon, required by modern Xcode)
    cat > "$ICON_DIR/Contents.json" << 'ICONJSON'
{
  "images" : [
    {
      "filename" : "AppIcon-1024.png",
      "idiom" : "universal",
      "platform" : "ios",
      "size" : "1024x1024"
    }
  ],
  "info" : {
    "author" : "xcode",
    "version" : 1
  }
}
ICONJSON
    echo "   App icon configured for Xcode."
fi

echo ""
echo "5. Applying Info.plist additions..."
PLIST="ios/App/App/Info.plist"
if [ -f "$PLIST" ] && command -v /usr/libexec/PlistBuddy &> /dev/null; then
    PB="/usr/libexec/PlistBuddy"

    # Camera usage
    $PB -c "Add :NSCameraUsageDescription string 'ReefPilot needs camera access to take photos of your reef tank.'" "$PLIST" 2>/dev/null || true

    # Photo library
    $PB -c "Add :NSPhotoLibraryUsageDescription string 'ReefPilot needs photo library access to select tank photos.'" "$PLIST" 2>/dev/null || true
    $PB -c "Add :NSPhotoLibraryAddUsageDescription string 'ReefPilot needs permission to save tank photos to your library.'" "$PLIST" 2>/dev/null || true

    # Portrait only on iPhone
    $PB -c "Delete :UISupportedInterfaceOrientations" "$PLIST" 2>/dev/null || true
    $PB -c "Add :UISupportedInterfaceOrientations array" "$PLIST"
    $PB -c "Add :UISupportedInterfaceOrientations:0 string UIInterfaceOrientationPortrait" "$PLIST"

    # Full screen (no slide-over on iPad)
    $PB -c "Add :UIRequiresFullScreen bool true" "$PLIST" 2>/dev/null || true

    # Light status bar
    $PB -c "Add :UIStatusBarStyle string UIStatusBarStyleLightContent" "$PLIST" 2>/dev/null || true
    $PB -c "Set :UIViewControllerBasedStatusBarAppearance true" "$PLIST" 2>/dev/null || true

    # Privacy — no tracking
    $PB -c "Add :NSPrivacyTracking bool false" "$PLIST" 2>/dev/null || true

    echo "   Info.plist updated with permissions and privacy keys."
else
    echo "   WARNING: Could not update Info.plist automatically."
    echo "   See ios-config/Info.plist.additions for keys to add manually."
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Open Xcode:  npx cap open ios"
echo "  2. Select your Apple Developer Team in Signing & Capabilities"
echo "  3. Update the Bundle Identifier if needed (currently: com.reefpilot.app)"
echo "  4. Set the Display Name to 'ReefPilot'"
echo "  5. Set Version to 1.0.0 and Build to 1"
echo "  6. Build & run on a simulator or device"
echo ""
echo "To submit to App Store:"
echo "  1. Product > Archive in Xcode"
echo "  2. Upload to App Store Connect via Xcode Organizer"
echo "  3. Fill in App Store listing: screenshots, description, privacy policy URL"
echo "     Privacy Policy URL: https://reefpilot.app/privacy"
echo "     Terms of Service URL: https://reefpilot.app/terms"
