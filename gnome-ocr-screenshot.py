#!/usr/bin/env python3

import gi
import os

try:
    from PIL import Image
except ImportError:
    import Image
import pytesseract
from datetime import datetime
import argparse
import logging
import logging.handlers


gi.require_version("Gtk", "4.0")
gi.require_version("Xdp", "1.0")
gi.require_version("Adw", "1")
from gi.repository import (
    Gtk,
    GLib,
    Xdp,
    Gdk,
    Adw,
    GObject,
    Gio,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
logger.addHandler(syslog_handler)


try:
    from pyzbar.pyzbar import decode
    QR_CODE_SUPPORTED = True
except ImportError:
    logger.warning("pyzbar not installed, qr code extraction will not work.")
    QR_CODE_SUPPORTED = False


class TextDialog(Gtk.Dialog):
    def __init__(self, app, text=""):
        super().__init__(title="Extracted Text", application=app, modal=True)
        self.app = app

        self.set_default_size(500, 400)
        self.toast_overlay = Adw.ToastOverlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.set_child(box)
        box.append(self.toast_overlay)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_editable(True)
        self.text_view.set_cursor_visible(True)

        self.text_view.set_margin_start(12)
        self.text_view.set_margin_end(12)
        self.text_view.set_margin_top(12)
        self.text_view.set_margin_bottom(3)
        self.text_view.set_vexpand(True)
        buffer = self.text_view.get_buffer()
        buffer.set_text(text)

        scrolled_window.set_child(self.text_view)

        self.toast_overlay.set_child(scrolled_window)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(12)
        button_box.set_margin_start(6)
        button_box.set_margin_end(12)
        button_box.set_halign(Gtk.Align.END)

        save_button = Gtk.Button(label="Save to File")
        copy_button = Gtk.Button(label="Copy to Clipboard")

        save_button.connect("clicked", self.on_save_clicked)
        copy_button.connect("clicked", self.on_copy_clicked)

        button_box.append(save_button)
        button_box.append(copy_button)
        box.append(button_box)
        self.present()

    def get_text(self):
        buffer = self.text_view.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        return buffer.get_text(start_iter, end_iter, True)

    def on_save_clicked(self, button):
        dialog = Gtk.FileDialog()
        dialog.set_title("Save Extracted Text")
        dialog.set_initial_name(
            f"clipboard_{datetime.now().strftime('%H-%M_%y-%m')}.txt"
        )

        if self.app.save_location:
            initial_folder = Gio.File.new_for_path(self.app.save_location)
            dialog.set_initial_folder(initial_folder)
        else:
            documents_path = GLib.get_user_special_dir(
                GLib.UserDirectory.DIRECTORY_DOCUMENTS
            )
            if documents_path:
                initial_folder = Gio.File.new_for_path(documents_path)
                dialog.set_initial_folder(initial_folder)

        dialog.set_modal(True)
        dialog.set_accept_label("Save")

        cancellable = Gio.Cancellable()
        dialog.save(
            parent=self, cancellable=cancellable, callback=self._on_save_response
        )

    def _on_save_response(self, dialog, result):
        try:
            file = dialog.save_finish(result)
            if file is not None:
                path = file.get_path()
                try:
                    with open(path, "w") as f:
                        f.write(self.get_text())
                except Exception as e:
                    error_dialog = Gtk.MessageDialog(
                        parent=self,
                        flags=Gtk.DialogFlags.MODAL,
                        type=Gtk.MessageType.ERROR,
                        buttons=Gtk.ButtonsType.OK,
                        message_format=f"Error saving file: {str(e)}",
                    )
                    error_dialog.connect(
                        "response", lambda *args: error_dialog.destroy()
                    )
                    error_dialog.present()
                else:
                    if not self.app.no_close_on_action:
                        self.app.quit()
        except GLib.Error as e:
            logger.error(f"Error in file dialog: {e.message}")

    def on_copy_clicked(self, button):
        text = self.get_text()
        clipboard = self.get_clipboard()
        provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
        clipboard.set_content(provider)

        GLib.timeout_add(50, lambda: self.app.quit())


class GnomeOCRApp(Gtk.Application):
    def __init__(
        self,
        enable_saving=False,
        no_close_on_action=False,
        lang=None,
        save_location=None,
    ):
        super().__init__()
        self.portal = Xdp.Portal()
        self.enable_saving = enable_saving
        self.no_close_on_action = no_close_on_action
        self.lang = lang

        # Validate and store save location
        if save_location:
            if os.path.isdir(save_location):
                self.save_location = save_location
            else:
                logger.warning(
                    f"Save location '{save_location}' is not a valid directory. Using default."
                )
                self.save_location = None
        else:
            self.save_location = None

    def do_activate(self):
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_default_size(1, 1)
        self.win.set_decorated(False)
        self.win.set_opacity(0)
        self.win.present()
        GLib.timeout_add(100, self.take_screenshot)

    def take_screenshot(self):
        self.portal.take_screenshot(
            None,
            Xdp.ScreenshotFlags.INTERACTIVE,
            None,
            self.on_screenshot_taken,
            None,
        )
        return False

    def on_screenshot_taken(self, source_object, res, user_data):
        if res.had_error():
            logger.error("Error: Can't take a screenshot.")
            self.quit()
            return

        filename = self._process_screenshot(res)
        if not filename:
            self.quit()
            return

        text = self._extract_text_from_image(filename)
        if text is None:
            self._cleanup_file(filename)
            self.quit()
            return

        self._show_text_dialog(text)

        if not self.enable_saving:
            self._cleanup_file(filename)
        else:
            logger.info(f"Screenshot saved at: {filename}")

    def _process_screenshot(self, res):
        """Process the screenshot and return the filename."""
        try:
            filename = self.portal.take_screenshot_finish(res)
            filename = filename[7:]  # Remove 'file://' prefix
            return GLib.Uri.unescape_string(filename)
        except Exception as e:
            logger.error(f"Error: Failed to process screenshot: {str(e)}")
            return None

    def _extract_text_from_image(self, filename):
        """Extract text or QR code data from the image."""
        try:
            available_langs = pytesseract.get_languages()
            ocr_lang = self.lang or "+".join(available_langs[:-1])
            logger.info(f"Using language(s): {ocr_lang}")

            if QR_CODE_SUPPORTED:
                try:
                    qr_text = decode(Image.open(filename))
                    return qr_text[0].data.decode("utf-8")
                except Exception as e:
                    logger.warning(f"Error decoding QR code: {str(e)}")

            return pytesseract.image_to_string(Image.open(filename), lang=ocr_lang)
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return None

    def _show_text_dialog(self, text):
        """Display the extracted text in a dialog."""
        dialog = TextDialog(self, text)
        dialog.connect("close-request", self.on_dialog_close)
        dialog.present()

    def _cleanup_file(self, filename):
        """Delete the screenshot file if saving is not enabled."""
        try:
            os.unlink(filename)
        except Exception as e:
            logger.error(f"Error deleting screenshot file: {str(e)}")

    def on_dialog_close(self, dialog):
        logger.info(f"Text from dialog: {dialog.get_text()}")
        dialog.destroy()
        self.quit()


parser = argparse.ArgumentParser(
    description="A tool for GNOME desktop environment to extract text from screenshots."
)
parser.add_argument(
    "--enablesaving",
    action="store_true",
    help="Do not delete the screenshot after extracting text.",
)

parser.add_argument(
    "--nocloseonaction",
    action="store_true",
    help="Do not quit the app after saving text or copying to clipboard.",
)

parser.add_argument(
    "--lang",
    action="store",
    help="Language(s) to use for OCR. Default is all available languages. Make sure to install the required language data.\n Example usage: --lang eng+deu",
)

parser.add_argument(
    "--save-location",
    action="store",
    help="Default directory for saving text files. Must be an existing directory.",
)

args = parser.parse_args()
app = GnomeOCRApp(
    enable_saving=args.enablesaving,
    no_close_on_action=args.nocloseonaction,
    lang=args.lang,
    save_location=args.save_location,
)
app.run(None)
