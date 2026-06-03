#!/usr/bin/env python3

import gi
import os
import shutil
from datetime import datetime
import argparse
import logging
import logging.handlers

gi.require_version("Gtk", "4.0")
gi.require_version("Xdp", "1.0")
gi.require_version("XdpGtk4", "1.0")
from gi.repository import Gtk, GLib, Xdp, XdpGtk4

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

try:
    syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
    logger.addHandler(syslog_handler)
except Exception:
    pass


def resolve_output_path(output_arg):
    """Resolve the output path, appending a filename if a directory is given."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    default_filename = f"screenshot_{timestamp}.png"

    if output_arg:
        if os.path.isdir(output_arg):
            # User passed a directory — append a default filename
            return os.path.join(output_arg, default_filename)
        else:
            # User passed a full file path
            parent_dir = os.path.dirname(output_arg)
            if parent_dir and not os.path.isdir(parent_dir):
                print(f"Error: Directory '{parent_dir}' does not exist.")
                exit(1)
            return output_arg
    else:
        pictures_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        base_dir = pictures_dir or os.path.expanduser("~")
        return os.path.join(base_dir, default_filename)


class ScreenshotApp(Gtk.Application):
    def __init__(self, output_path):
        super().__init__()
        self.portal = Xdp.Portal()
        self.output_path = output_path

    def do_activate(self):
        win = Gtk.ApplicationWindow(application=self)
        win.set_default_size(1, 1)
        win.set_decorated(False)
        win.set_opacity(0)
        win.present()
        GLib.timeout_add(100, self.take_screenshot)

    def take_screenshot(self):
        logger.debug("Requesting screenshot from portal...")
        window = self.get_active_window()
        parent = XdpGtk4.parent_new_gtk(window) if window else None
        self.portal.take_screenshot(
            parent,
            Xdp.ScreenshotFlags.NONE,
            None,
            self.on_screenshot_taken,
            None,
        )
        return False

    def on_screenshot_taken(self, source_object, res, user_data):
        try:
            uri = self.portal.take_screenshot_finish(res)
            logger.debug(f"Portal returned URI: {uri}")
        except GLib.Error as e:
            print(f"Error: Screenshot portal failed — {e.message}")
            self.quit()
            return

        if not uri:
            print("Error: Portal returned an empty URI.")
            self.quit()
            return

        # Strip "file://" prefix and unescape
        tmp_path = GLib.Uri.unescape_string(uri.removeprefix("file://"))
        logger.debug(f"Temp file path: {tmp_path}")

        if not os.path.exists(tmp_path):
            print(f"Error: Temp screenshot file not found at: {tmp_path}")
            self.quit()
            return

        try:
            shutil.copy2(tmp_path, self.output_path)
            os.unlink(tmp_path)
            print(f"Screenshot saved to: {self.output_path}")
        except Exception as e:
            print(f"Error saving screenshot to '{self.output_path}': {e}")

        self.quit()


parser = argparse.ArgumentParser(description="Take a full screenshot and save it to a file.")
parser.add_argument(
    "--output",
    action="store",
    help="File path or directory to save the screenshot. Defaults to ~/Pictures/screenshot_<timestamp>.png",
)
args = parser.parse_args()

output_path = resolve_output_path(args.output)
logger.debug(f"Resolved output path: {output_path}")

app = ScreenshotApp(output_path=output_path)
app.run(None)