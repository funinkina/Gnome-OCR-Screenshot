import gi
import os
from PIL import Image
import pytesseract
from datetime import datetime

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

        self.set_default_size(500, 700)
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

        save_button = Gtk.Button(label="Save")
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

        GLib.timeout_add(2100, lambda: self.app.quit())


class MyApp(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.portal = Xdp.Portal()

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
            return

        filename = self.portal.take_screenshot_finish(res)
        filename = filename[7:]
        filename = GLib.Uri.unescape_string(filename)

        try:
            langs = pytesseract.get_languages()
            print("Available languages:", langs[:-1])
            text = pytesseract.image_to_string(
                Image.open(filename), lang="+".join(langs[:-1])
            )
            print("Extracted text:", text)
            dialog = TextDialog(self, text)
            dialog.connect("close-request", self.on_dialog_close)
            dialog.present()

        except Exception as e:
            print("Error extracting text:", e)

        try:
            os.unlink(filename)
        except Exception as e:
            print("Error deleting screenshot file:", e)

    def on_dialog_close(self, dialog):
        print("Text from dialog:", dialog.get_text())
        dialog.destroy()
        self.quit()


app = MyApp()
app.run(None)
