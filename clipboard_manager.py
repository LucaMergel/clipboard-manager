#!/usr/bin/env python3
"""
Clipboard Manager for GNOME
A simple clipboard history manager for Linux with GNOME
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, Gdk, GLib, AppIndicator3, Pango
import sqlite3
import os
import signal
from datetime import datetime

class ClipboardManager:
    def __init__(self):
        # Use XDG data directory (works on all Linux systems)
        self.data_dir = os.path.join(
            os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')),
            'clipboard-manager'
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, 'history.db')
        
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.init_database()
        self.setup_app_indicator()
        self.setup_gui()
        
        self.last_content = ""
        self.is_paused = False
        
        print("Clipboard Manager started successfully!")

    def setup_app_indicator(self):
        """Setup system tray icon"""
        self.indicator = AppIndicator3.Indicator.new(
            "clipboard-manager",
            "edit-paste-symbolic",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Clipboard Manager")
        self.indicator.set_menu(self.create_tray_menu())
        
    def create_tray_menu(self):
        """Create tray icon context menu"""
        menu = Gtk.Menu()
        
        # Show History
        show_item = Gtk.MenuItem(label="Show History")
        show_item.connect("activate", self.show_window)
        menu.append(show_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Pause Toggle
        self.pause_tray_item = Gtk.CheckMenuItem(label="Pause Monitoring")
        self.pause_tray_item.connect("toggled", self.on_pause_toggled)
        menu.append(self.pause_tray_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit_application)
        menu.append(quit_item)
        
        menu.show_all()
        return menu

    def init_database(self):
        """Initialize SQLite database"""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clipboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def setup_gui(self):
        """Setup main application window"""
        self.window = Gtk.Window(title="Clipboard History")
        self.window.set_default_size(600, 400)
        
        # Main layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Controls
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        self.pause_button = Gtk.ToggleButton(label="Pause")
        self.pause_button.connect("toggled", self.on_pause_toggled)
        
        self.clear_button = Gtk.Button(label="Clear History")
        self.clear_button.connect("clicked", self.clear_history)
        
        controls_box.pack_start(self.pause_button, False, False, 0)
        controls_box.pack_start(self.clear_button, False, False, 0)
        
        # Search
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        search_label = Gtk.Label(label="Search:")
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search history...")
        self.search_entry.connect("search-changed", self.on_search_changed)
        
        search_box.pack_start(search_label, False, False, 0)
        search_box.pack_start(self.search_entry, True, True, 0)
        
        # History list
        self.liststore = Gtk.ListStore(str, str, str)  # Preview, Time, Full Content
        self.treeview = Gtk.TreeView(model=self.liststore)
        
        # Columns
        renderer = Gtk.CellRendererText()
        renderer.set_property("wrap-width", 300)
        renderer.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
        
        column_content = Gtk.TreeViewColumn("Content", renderer, text=0)
        column_content.set_min_width(400)
        
        column_time = Gtk.TreeViewColumn("Time", Gtk.CellRendererText(), text=1)
        column_time.set_min_width(100)
        
        self.treeview.append_column(column_content)
        self.treeview.append_column(column_time)
        
        # Events
        self.treeview.connect("row-activated", self.on_row_activated)
        self.treeview.connect("button-press-event", self.on_treeview_click)
        
        # Scrollable area
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.treeview)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_text("Ready - Copy something to see it in history!")
        
        # Assemble UI
        main_box.pack_start(controls_box, False, False, 0)
        main_box.pack_start(search_box, False, False, 0)
        main_box.pack_start(scrolled_window, True, True, 0)
        main_box.pack_start(self.status_label, False, False, 0)
        
        self.window.add(main_box)
        self.window.connect("delete-event", self.on_window_close)
        
        # Start clipboard monitoring
        self.clipboard.connect('owner-change', self.on_clipboard_change)
        self.load_history()

    def on_clipboard_change(self, clipboard, event):
        """Handle clipboard changes"""
        if self.is_paused:
            return
            
        try:
            text = clipboard.wait_for_text()
            if text and text.strip() and text != self.last_content:
                self.last_content = text
                self.save_to_history(text)
                self.load_history()
                self.status_label.set_text(f"Saved: {text[:30]}...")
        except Exception as e:
            print(f"Error reading clipboard: {e}")

    def save_to_history(self, content):
        """Save content to database"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO clipboard_history (content) VALUES (?)", (content,))
        self.conn.commit()

    def load_history(self, search_term=None):
        """Load history from database"""
        self.liststore.clear()
        cursor = self.conn.cursor()
        
        if search_term:
            cursor.execute(
                "SELECT content, timestamp FROM clipboard_history WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 50",
                (f"%{search_term}%",)
            )
        else:
            cursor.execute(
                "SELECT content, timestamp FROM clipboard_history ORDER BY timestamp DESC LIMIT 50"
            )
        
        for content, timestamp in cursor.fetchall():
            time_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            time_str = time_obj.strftime("%H:%M:%S")
            preview = content[:80] + "..." if len(content) > 80 else content
            preview = preview.replace("\n", " ")
            self.liststore.append([preview, time_str, content])

    def on_row_activated(self, treeview, path, column):
        """Double-click to copy back to clipboard"""
        model = treeview.get_model()
        treeiter = model.get_iter(path)
        if treeiter:
            full_content = model[treeiter][2]
            self.clipboard.set_text(full_content, -1)
            self.status_label.set_text("Content copied to clipboard!")

    def on_treeview_click(self, treeview, event):
        """Right-click context menu"""
        if event.button == 3:  # Right click
            selection = treeview.get_selection()
            model, treeiter = selection.get_selected()
            if treeiter:
                content = model[treeiter][2]
                self.show_context_menu(content, event)

    def show_context_menu(self, content, event):
        """Show context menu for history entries"""
        menu = Gtk.Menu()
        
        copy_item = Gtk.MenuItem(label="Copy to Clipboard")
        copy_item.connect("activate", lambda x: self.copy_to_clipboard(content))
        
        delete_item = Gtk.MenuItem(label="Delete Entry")
        delete_item.connect("activate", lambda x: self.delete_from_history(content))
        
        menu.append(copy_item)
        menu.append(delete_item)
        menu.show_all()
        menu.popup(None, None, None, None, event.button, event.time)

    def copy_to_clipboard(self, content):
        """Copy content back to clipboard"""
        self.clipboard.set_text(content, -1)
        self.status_label.set_text("Content copied!")

    def delete_from_history(self, content):
        """Delete entry from history"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM clipboard_history WHERE content = ?", (content,))
        self.conn.commit()
        self.load_history()
        self.status_label.set_text("Entry deleted")

    def clear_history(self, widget=None):
        """Clear entire history"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Clear entire history?"
        )
        dialog.format_secondary_text("This cannot be undone.")
        
        response = dialog.run()
        if response == Gtk.ResponseType.YES:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM clipboard_history")
            self.conn.commit()
            self.load_history()
            self.status_label.set_text("History cleared")
        
        dialog.destroy()

    def on_pause_toggled(self, widget):
        """Pause/resume monitoring"""
        self.is_paused = not self.is_paused
        status = "paused" if self.is_paused else "active"
        self.status_label.set_text(f"Monitoring: {status}")

    def on_search_changed(self, entry):
        """Search history"""
        search_term = entry.get_text()
        self.load_history(search_term if search_term else None)

    def show_window(self, widget=None):
        """Show main window"""
        self.window.show_all()
        self.load_history()
        self.status_label.set_text("History loaded - Double-click or right-click to copy")

    def on_window_close(self, widget, event):
        """Hide window on close"""
        widget.hide()
        return True

    def quit_application(self, widget=None):
        """Quit application"""
        self.conn.close()
        Gtk.main_quit()

def main():
    # Handle Ctrl+C properly
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # Start application
    app = ClipboardManager()
    app.window.hide()  # Start hidden (tray only)
    Gtk.main()

if __name__ == "__main__":
    main()
