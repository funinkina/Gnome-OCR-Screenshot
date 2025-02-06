import gi
import os
from PIL import Image
import pytesseract
from datetime import datetime
import argparse

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

        # Use custom save location if specified
        if self.app.save_location:
            initial_folder = Gio.File.new_for_path(self.app.save_location)
            dialog.set_initial_folder(initial_folder)
        else:
            # Default to Documents folder
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
            print(f"Error in file dialog: {e.message}")

    def on_copy_clicked(self, button):
        text = self.get_text()
        clipboard = self.get_clipboard()
        provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
        clipboard.set_content(provider)

        toast = Adw.Toast.new("Text copied to clipboard")
        toast.set_timeout(2)
        self.toast_overlay.add_toast(toast)

        if not self.app.no_close_on_action:
            GLib.timeout_add(2100, lambda: self.app.quit())


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
                print(
                    f"Warning: Save location '{save_location}' is not a valid directory. Using default."
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
            print("Error: Can't take a screenshot.")
            self.quit()
            return

        try:
            filename = self.portal.take_screenshot_finish(res)
            filename = filename[7:]
            filename = GLib.Uri.unescape_string(filename)
        except Exception as e:
            print(f"Error: Failed to process screenshot: {str(e)}")
            self.quit()
            return

        try:
            available_langs = pytesseract.get_languages()
            if self.lang:
                ocr_lang = self.lang
                print(f"Using language(s): {ocr_lang}")
            else:
                ocr_lang = "+".join(available_langs[:-1])
                print(f"Available languages: {available_langs[:-1]}")

            text = pytesseract.image_to_string(Image.open(filename), lang=ocr_lang)
            print("Extracted text:", text)
            dialog = TextDialog(self, text)
            dialog.connect("close-request", self.on_dialog_close)
            dialog.present()

        except Exception as e:
            print(f"Error extracting text: {str(e)}")
            if not self.enable_saving:
                try:
                    os.unlink(filename)
                except Exception as e:
                    print(f"Error deleting screenshot file: {str(e)}")
            self.quit()
            return

        if not self.enable_saving:
            try:
                os.unlink(filename)
            except Exception as e:
                print("Error deleting screenshot file:", e)
        else:
            print(f"Screenshot saved at: {filename}")

    def on_dialog_close(self, dialog):
        print("Text from dialog:", dialog.get_text())
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
