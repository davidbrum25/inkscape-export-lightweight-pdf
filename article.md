# Source notes for an X article

Write a public X article from these notes. Voice: David Brum, first person, plain and short. This is a maker post about a small Inkscape tool, not a changelog and not a troubleshooting log.

Link: https://github.com/davidbrum25/inkscape-export-lightweight-pdf

Screenshots to attach, in this order, from the `media` folder:

1. `001_heavy_file.png` — a 90+ MB PDF exported natively by Inkscape next to its lightweight 3–4 MB counterpart.
2. `002_menu.png` — menu open at Extensions → Export → Export Lightweight PDF.
3. `003_dialog.png` — the extension dialog showing presets (SD, Draft, Screen, HD, Print) and JPEG quality.
4. `004_report.png` — the summary report dialog showing 95%+ space savings.
5. `005_side_by_side.png` — visual comparison showing vectors and images remaining crisp and identical.

## TLDR, step by step

1. Whenever you export an SVG with photos, storyboard panels, or embedded renders in Inkscape, the PDF balloons in size. A 16-panel storyboard can easily produce a 95 MB PDF because Cairo doesn't recompress embedded rasters properly.

2. Inkscape has no native way during PDF export to choose downsampling or set a target image resolution.

3. So I wrote an extension called **Export Lightweight PDF**.

4. How it works: Extensions → Export → Export Lightweight PDF. Pick a preset like **SD (50% scale / ~75 DPI)**, **Screen (~96 DPI)**, or **Draft (25% scale)**, set your output folder, and click Apply.

5. It exports the PDF and downsamples the image streams directly, turning a 93 MB storyboard into a 3.5 MB file (over 95% space reduction) in seconds.

6. Vectors, fonts, lines, and layout stay 100% untouched and razor-sharp. Even transparent cutouts are handled cleanly with synchronized alpha masks.

7. Tested on Inkscape 1.4 on Linux. Works cleanly.

8. The repo is public: https://github.com/davidbrum25/inkscape-export-lightweight-pdf
   License is GPL-2.0-or-later, matching Inkscape's own extensions. Works with Inkscape 1.2+.

9. Install is a clone into the user extensions folder, then restart Inkscape:

   ```bash
   git clone https://github.com/davidbrum25/inkscape-export-lightweight-pdf.git \
     ~/.config/inkscape/extensions/export-lightweight-pdf
   ```

   On Windows that folder is `%APPDATA%\inkscape\extensions`.

## Facts to keep straight

- Author: David Brum. GitHub: davidbrum25.
- Menu path: Extensions → Export → Export Lightweight PDF.
- Uses Ghostscript for lightning-fast downsampling and stream compression, with PikePDF fallback.
- Tested and built on Inkscape 1.4. Requires 1.2+.
- Reduces typical storyboard and presentation PDFs by 90–96% without sacrificing visual fidelity.

## Leave out of the post

Skip install friction, terminal dependencies, and detailed command line options. The story is the bloated PDF problem, the clean one-click solution, and the link.
