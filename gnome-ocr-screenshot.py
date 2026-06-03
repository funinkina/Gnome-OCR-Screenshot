#!/usr/bin/env python3

import gi
import os
import subprocess
import threading

try:
    from PIL import Image, ImageEnhance
except ImportError:
    import Image
    import ImageEnhance
import pytesseract
from datetime import datetime
import argparse
import logging
import logging.handlers


gi.require_version("Gtk", "4.0")
gi.require_version("Xdp", "1.0")
gi.require_version("Adw", "1")
from gi.repository import (  # noqa: E402
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

try:
    syslog_handler = logging.handlers.SysLogHandler(address="/dev/log")
    logger.addHandler(syslog_handler)
except OSError:
    logger.addHandler(logging.StreamHandler())

_NON_LANG = {"osd", "equ"}

try:
    from pyzbar.pyzbar import decode

    QR_CODE_SUPPORTED = True
except ImportError:
    logger.warning("pyzbar not installed, qr code extraction will not work.")
    QR_CODE_SUPPORTED = False


class TextDialog(Gtk.Dialog):
    def __init__(self, app):
        super().__init__(title="Extracting text…", application=app, modal=True)
        self.app = app

        self.set_default_size(500, 400)
        self.toast_overlay = Adw.ToastOverlay()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_start(0)
        box.set_margin_end(0)
        box.set_margin_top(0)
        box.set_margin_bottom(0)
        self.set_child(box)
        box.append(self.toast_overlay)

        self.spinner = Gtk.Spinner()
        self.spinner.set_margin_top(40)
        self.spinner.set_margin_bottom(40)
        self.spinner.set_size_request(48, 48)
        self.spinner.set_vexpand(True)
        self.spinner.set_halign(Gtk.Align.CENTER)
        self.spinner.set_valign(Gtk.Align.CENTER)
        self.spinner.start()
        self.toast_overlay.set_child(self.spinner)

        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_hexpand(True)
        self.scrolled_window.set_vexpand(True)

        self.text_view = Gtk.TextView()
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_view.set_editable(True)
        self.text_view.set_cursor_visible(True)
        self.text_view.set_left_margin(12)
        self.text_view.set_right_margin(12)
        self.text_view.set_top_margin(12)
        self.text_view.set_bottom_margin(12)
        self.text_view.set_vexpand(True)
        self.scrolled_window.set_child(self.text_view)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_margin_top(6)
        button_box.set_margin_bottom(12)
        button_box.set_margin_start(12)
        button_box.set_margin_end(12)
        button_box.set_halign(Gtk.Align.FILL)
        button_box.set_homogeneous(True)
        button_box.set_hexpand(True)

        self.btn_save_to_file = Gtk.Button(label="Save to File")
        self.btn_save_to_file.set_hexpand(True)
        self.btn_save_to_file.set_sensitive(False)
        self.btn_copytoclipboard = Gtk.Button(label="Copy to Clipboard")
        self.btn_copytoclipboard.set_hexpand(True)
        self.btn_copytoclipboard.set_sensitive(False)
        self.btn_retake_screenshot = Gtk.Button(label="Retake Screenshot")
        self.btn_retake_screenshot.set_hexpand(True)

        self.btn_save_to_file.connect("clicked", self.on_save_clicked)
        self.btn_copytoclipboard.connect("clicked", self.on_copy_clicked)
        self.btn_retake_screenshot.connect("clicked", self.on_take_another_clicked)

        button_box.append(self.btn_save_to_file)
        button_box.append(self.btn_copytoclipboard)
        button_box.append(self.btn_retake_screenshot)
        box.append(button_box)
        self.present()

    def set_text(self, text):
        self.spinner.stop()
        self.toast_overlay.set_child(self.scrolled_window)

        buffer = self.text_view.get_buffer()
        buffer.set_text(text)

        word_count = len(text.split())
        char_count = len(text)
        self.set_title(f"Extracted Text ({word_count} words, {char_count} chars)")

        self.btn_save_to_file.set_sensitive(True)
        self.btn_copytoclipboard.set_sensitive(True)

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

    def on_take_another_clicked(self, button):
        self.destroy()
        GLib.timeout_add(150, self.app.take_screenshot)


class GnomeOCRApp(Adw.Application):
    def __init__(
        self,
        enable_saving=False,
        no_close_on_action=False,
        lang=None,
        save_location=None,
        preprocess=False,
        psm=3,
        autocopy=False,
    ):
        super().__init__()
        self.portal = Xdp.Portal()
        self.enable_saving = enable_saving
        self.no_close_on_action = no_close_on_action
        self.lang = lang
        self.preprocess = preprocess
        self.psm = psm
        self.autocopy = autocopy

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
        self.win = Adw.ApplicationWindow(application=self)
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
        filename = self._process_screenshot(res)
        if not filename:
            self.quit()
            return

        if self.autocopy:

            def do_ocr():
                text = self._extract_text_from_image(filename)
                GLib.idle_add(self._on_ocr_done, None, filename, text)

            threading.Thread(target=do_ocr, daemon=True).start()
        else:
            dialog = TextDialog(self)
            dialog.connect("close-request", self.on_dialog_close)

            def do_ocr():
                text = self._extract_text_from_image(filename)
                GLib.idle_add(self._on_ocr_done, dialog, filename, text)

            threading.Thread(target=do_ocr, daemon=True).start()

    def _on_ocr_done(self, dialog, filename, text):
        if text is None:
            self._cleanup_file(filename)
            if dialog:
                dialog.destroy()
            self.quit()
            return False

        if self.autocopy:
            encoded = text.encode()
            try:
                subprocess.run(["wl-copy"], input=encoded, check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    subprocess.run(["xclip", "-selection", "clipboard"], input=encoded, check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    clipboard = self.win.get_clipboard()
                    provider = Gdk.ContentProvider.new_for_value(GObject.Value(str, text))
                    clipboard.set_content(provider)
            self.quit()
            return False

        dialog.set_text(text)

        if not self.enable_saving:
            self._cleanup_file(filename)
        else:
            logger.info(f"Screenshot saved at: {filename}")

        return False

    def _process_screenshot(self, res):
        try:
            filename = self.portal.take_screenshot_finish(res)
            filename = filename[7:]
            return GLib.Uri.unescape_string(filename)
        except GLib.Error as e:
            logger.error(f"Error taking screenshot: {e.message}")
            return None
        except Exception as e:
            logger.error(f"Error processing screenshot result: {str(e)}")
            return None

    def _extract_text_from_image(self, filename):
        try:
            available_langs = pytesseract.get_languages()
            ocr_lang = self.lang or "+".join(
                lang for lang in available_langs if lang not in _NON_LANG
            )
            logger.info(f"Using language(s): {ocr_lang}")

            img = Image.open(filename)

            if QR_CODE_SUPPORTED:
                try:
                    qr_results = decode(img)
                    if qr_results and qr_results[0].data:
                        return qr_results[0].data.decode("utf-8")
                except Exception as e:
                    logger.warning(f"Error decoding QR code: {str(e)}")

            if self.preprocess:
                img = img.convert("L")
                img = ImageEnhance.Contrast(img).enhance(2.0)
                img = ImageEnhance.Sharpness(img).enhance(2.0)

            config = f"--psm {self.psm}"
            return pytesseract.image_to_string(img, lang=ocr_lang, config=config)
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return None

    def _cleanup_file(self, filename):
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
parser.add_argument(
    "--preprocess",
    action="store_true",
    help="Apply grayscale + contrast + sharpen to image before OCR. Improves accuracy on low-contrast or noisy screenshots.",
)
parser.add_argument(
    "--psm",
    type=int,
    default=3,
    metavar="N",
    help="Tesseract page segmentation mode (0-13). Default: 3 (auto). Use 7 for single lines, 6 for uniform text blocks.",
)
parser.add_argument(
    "--autocopy",
    action="store_true",
    help="Copy extracted text directly to clipboard without showing a dialog.",
)

args = parser.parse_args()
app = GnomeOCRApp(
    enable_saving=args.enablesaving,
    no_close_on_action=args.nocloseonaction,
    lang=args.lang,
    save_location=args.save_location,
    preprocess=args.preprocess,
    psm=args.psm,
    autocopy=args.autocopy,
)
app.run(None)
