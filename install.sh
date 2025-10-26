#!/bin/bash
# Installation script for Clipboard Manager

echo "Installing Clipboard Manager for GNOME..."

# Check if running on GNOME
if [ "$XDG_CURRENT_DESKTOP" != "GNOME" ]; then
    echo "Warning: This application is designed for GNOME desktop"
fi

# Check dependencies
echo "Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required but not installed"
    exit 1
fi

# Required Python packages
echo "Installing required packages..."
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-appindicator3-0.1

# Create application directory
APP_DIR="$HOME/.local/bin/clipboard-manager"
mkdir -p "$APP_DIR"

# Copy files
cp clipboard_manager.py "$APP_DIR/"
cp README.md "$APP_DIR/"

# Create executable script
cat > "$APP_DIR/clipboard-manager" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 clipboard_manager.py "$@"
EOF

chmod +x "$APP_DIR/clipboard-manager"

# Create desktop entry
mkdir -p "$HOME/.local/share/applications"
cat > "$HOME/.local/share/applications/clipboard-manager.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Clipboard Manager
Comment=Clipboard history manager for GNOME
Exec=$APP_DIR/clipboard-manager
Icon=edit-paste-symbolic
Categories=Utility;
Keywords=clipboard;history;paste;copy;
StartupNotify=false
Terminal=false
EOF

# Update desktop database
update-desktop-database "$HOME/.local/share/applications/"

echo "Installation complete!"
echo "You can now run 'clipboard-manager' or find it in your application menu"
echo "Data will be stored in: ~/.local/share/clipboard-manager/"
