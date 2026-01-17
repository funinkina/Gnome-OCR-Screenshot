<h1 style="text-align: center;"> GNOME Screenshot OCR </h1>

A simple OCR (Optical Character Recognition) tool for the GNOME desktop environment that allows you to extract text as well as scan QR codes directly automatically from screenshots.

![Screenshot](screenshot.png)

## Features

- Uses native GNOME screenshot portal
- Minimal Dependencies (pytesseract and pyzbar only)
- Single file for easy shortcut setup
- Ability to scan QR codes without any additional setup
- Can save as file directly
- Can copy to clipboard directly
- Supports multiple languages
- Customizable save location
- Customizable keyboard shortcuts

## Requirements

- Python 3.x (Preinstalled on most Linux distributions)
- python-gobject (For gi module in python)
- GTK 4 (Preinstalled on GNOME-based distributions)
- Python Tesseract OCR (See below for installation instructions)
- pyzbar (optional, for QR code scanning)

## Installation

### 1. Install system dependencies:
```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr

# Fedora
sudo dnf install tesseract
sudo dnf install python3-pytesseract

# Arch Linux
sudo pacman -S tesseract
sudo pacman -S python-pytesseract

# Using builtin python package manager
pip install pytesseract
```

### You can also install `pyzbar` optionally for QR code scanning support:
```bash
# Ubuntu/Debian
sudo apt-get install libzbar0
sudo apt install python3-pyzbar 

# Arch Linux from AUR
yay -S pyzbar

#Using builtin python package manager
pip install pyzbar
```


### 2. For additional language support, install the corresponding Tesseract language packages:
```bash
# Example for hindi language support
sudo apt install tesseract-ocr-hin  # Ubuntu/Debian
sudo dnf install tesseract-langpack-hin  # Fedora
sudo pacman -S tesseract-data-hin  # Arch Linux
```

## Usage

Basic usage:
```bash
python gnome-ocr-screenshot.py
```

## Recommended Usage
Move the script to a directory in your PATH and create keyboard shortcut for quick access.

```bash
git clone https://github.com/funinkina/Gnome-OCR-Screenshot
cd Gnome-OCR-Screenshot
sudo cp gnome-ocr-screenshot.py ~/.local/bin/gnome-ocr-screenshot
# alternatively, you can create a symbolic link
# sudo ln -s gnome-ocr-screenshot.py ~/.local/bin/gnome-ocr-screenshot
sudo chmod +x ~/.local/bin/gnome-ocr-screenshot
```

### Then make keyboard shortcut in gnome control center to run the script.
1. Open GNOME settings
2. Go to Keyboard Shortcuts
3. Add a new shortcut with the command `gnome-screenshot-ocr` with the appropriate arguments (see below)
4. Assign a key combination to the shortcut, for example: `Meta+PrintScreen`. 

### Command-line Options

- `--help`: Show help message and exit.
- `--enablesaving`: Keep the screenshot file after text extraction.
- `--nocloseonaction`: Keep the application running after saving text or copying to clipboard.
- `--lang`: Specify OCR language(s) (e.g., `--lang eng+deu` for English and German). Default is all the available languages of Tesseract data installed on your system.
- `--save-location`: Set default directory for saving text files (e.g., `--save-location ~/Documents`). Default is the user's documents directory.

Example with options:
```bash
gnome-screenshot-ocr --lang eng+deu --save-location ~/Documents
```
![shortcut example](shortcut_demo.png)

## How It Works

1. Launch the application
2. Select an area of your screen to capture
3. The application will extract text from the selected area
4. View the extracted text in a dialog window
5. Choose to either copy the text to clipboard or save it to a file

## License

[MIT](https://github.com/funinkina/Gnome-OCR-Screenshot/blob/main/LICENSE)
