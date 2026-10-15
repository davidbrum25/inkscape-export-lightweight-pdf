# Export Lightweight PDF

An Inkscape extension that exports optimized, lightweight PDF documents with customizable image resolution and presets, reducing bloated file sizes by up to 95%.

When exporting SVG documents containing high-resolution photos, renders, or storyboard panels, Inkscape often produces massive PDF files (e.g., 50–100+ MB) because Cairo embeds raster images with little or no lossy compression. This extension automates exporting to PDF while downsampling and recompressing embedded and linked images to your chosen target resolution, while preserving 100% of your vector graphics, text, fonts, and layout.

---

## Features

- **One-Click Presets:**
  - **SD (50% scale / ~75 DPI)**: Recommended for storyboards, review decks, and client feedback (reduces 90MB files to ~3–4MB).
  - **Screen (~96 DPI)**: Balanced for web viewing, email attachments, and digital presentations.
  - **Draft (25% scale / ~50 DPI)**: Ultra-compact output for instant chat or mobile sharing.
  - **HD (75% scale / ~150 DPI)**: High-definition digital viewing.
  - **Print (100% scale / ~300 DPI)**: Clean stream compression at full resolution.
- **Custom Scale & DPI:** Set any percentage (e.g., 50%) or exact DPI value.
- **Smart Transparency Handling:** Automatically splits transparent images into RGB JPEG + synchronized Alpha mask streams (`/SMask`), dramatically slashing file sizes without clipping artifacts.
- **Vector & Text Integrity:** Vector paths, outlines, strokes, and editable fonts remain completely untouched and pixel-perfect.
- **Single & Multi-Page Support:** Seamlessly supports multi-page Inkscape documents, single pages, bounding boxes, or selection exports.

---

## Install

Inkscape 1.2 or newer (developed and tested on Inkscape 1.4).

Requires **Ghostscript** (`gs`) installed on your system:
- **Arch Linux / Manjaro:** `sudo pacman -S ghostscript`
- **Ubuntu / Debian:** `sudo apt install ghostscript`
- **Fedora:** `sudo dnf install ghostscript`
- **macOS:** `brew install ghostscript`
- **Windows:** Download the Ghostscript AGPL installer from [ghostscript.com](https://ghostscript.com/releases/).

### Clone or Copy Extension

```bash
mkdir -p ~/.config/inkscape/extensions
git clone https://github.com/davidbrum25/inkscape-export-lightweight-pdf.git \
  ~/.config/inkscape/extensions/export-lightweight-pdf
```

Restart Inkscape. The command is located under **Extensions → Export → Export Lightweight PDF...**

*(On Windows, the extensions folder is `%APPDATA%\inkscape\extensions`).*

---

## How to Use

1. Open your SVG document in Inkscape.
2. Go to **Extensions → Export → Export Lightweight PDF...**
3. Select your desired resolution preset (e.g. **SD — 50% Scale / ~75 DPI**) and JPEG quality.
4. Set your output folder or leave it empty to save in the same directory as your SVG.
5. Click **Apply**.
6. A summary report appears with the before/after file size and exact percentage saved.

---

## Options

### Resolution Tab

| Option | Description |
| --- | --- |
| **Resolution preset** | Quick presets: SD (50%), Screen (96 DPI), Draft (25%), HD (150 DPI), Print (300 DPI), or Custom. |
| **Custom scale (%)** | Percentage scale applied when preset is set to Custom percentage scale. |
| **Custom target DPI** | DPI value applied when preset is set to Custom target DPI. |
| **JPEG image quality (%)** | Compression quality for photos and bitmaps (default `85%` offers optimal fidelity/size). |
| **Downsampling trigger** | Choose whether to downsample all images above target resolution or only those exceeding 1.5x. |
| **Compress transparent images as JPEG + Alpha mask** | Enabled by default. Separates RGB channels and alpha masks to maximize compression while retaining clean transparency. |

### Output & Scope Tab

| Option | Description |
| --- | --- |
| **Output folder** | Destination directory for the PDF. Defaults to current SVG directory. |
| **Filename suffix** | Suffix added before `.pdf` (default: `_SD`). |
| **Overwrite existing file** | Overwrite if file exists, or auto-append incremental counters (`_1`, `_2`). |
| **Export area** | Current page / artboard, all pages (multi-page PDF), whole drawing area, or selected objects. |
| **Convert text to paths** | Outlines all text into vector curves so no fonts need to be installed on target devices. |
| **Filter rasterization DPI** | DPI used by Inkscape when rasterizing blur and filter effects (default `96`). |
| **PDF version** | Target PDF standard: 1.4, 1.5 (default), 1.6, or 1.7. |

### Advanced Tab

| Option | Description |
| --- | --- |
| **Optimizer engine** | Auto (recommended), Ghostscript, or PikePDF (if installed). |
| **Compress PDF object streams** | Flate-compresses cross-reference tables and streams for minimal footprint. |
| **Open PDF file after export** | Automatically opens the exported PDF in the system viewer. |
| **Reveal in file manager after export** | Opens the destination directory in your file manager. |
| **Show detailed compression report** | Displays the before/after size and percentage saved. |

---

## License

[GPL-2.0-or-later](LICENSE). Same license family as Inkscape's own extensions.
