# GNOME Screenshot OCR

A simple OCR (Optical Character Recognition) tool for the GNOME desktop environment that allows you to extract text automatically from screenshots.

## Features

- Interactive screenshot selection
- Text extraction using Tesseract OCR
- Copy extracted text to clipboard
- Save extracted text to file
- Multi-language support
- GNOME desktop integration

## Requirements

- Python 3.x
- GTK 4
- Tesseract OCR
- Python packages:
  - PyGObject
  - Pillow
  - pytesseract

## Installation

1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 tesseract-ocr python3-pip

# Fedora
sudo dnf install python3-gobject gtk4 tesseract python3-pip
```

2. Install Python dependencies:
```bash
pip install pillow pytesseract
```

3. For additional language support, install the corresponding Tesseract language packages:
```bash
# Example for German language support
sudo apt install tesseract-ocr-deu  # Ubuntu/Debian
sudo dnf install tesseract-langpack-deu  # Fedora
```

## Usage

Basic usage:
```bash
python main.py
```

### Command-line Options

- `--enablesaving`: Keep the screenshot file after text extraction
- `--nocloseonaction`: Keep the application running after saving text or copying to clipboard
- `--lang`: Specify OCR language(s) (e.g., `--lang eng+deu` for English and German)
- `--save-location`: Set default directory for saving text files

Example with options:
```bash
python main.py --lang eng+deu --save-location ~/Documents
```

## How It Works

1. Launch the application
2. Select an area of your screen to capture
3. The application will extract text from the selected area
4. View the extracted text in a dialog window
5. Choose to either copy the text to clipboard or save it to a file

## License

[Insert your chosen license here]