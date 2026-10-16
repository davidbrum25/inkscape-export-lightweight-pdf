#!/usr/bin/env python3
# Copyright (C) 2026 David Brum
# SPDX-License-Identifier: GPL-2.0-or-later
"""Export lightweight, optimized PDFs from Inkscape with customizable image resolution and presets."""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zlib

import inkex
from inkex import AbortExtension
from inkex.localization import inkex_gettext as _


def format_bytes(num_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} TB"


def find_ghostscript() -> str | None:
    """Find Ghostscript binary across platforms."""
    candidates = ["gs", "gswin64c", "gswin32c", "gsc"]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    # Common Windows fallback locations
    if sys.platform == "win32":
        for pf in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
            if not pf:
                continue
            gs_base = os.path.join(pf, "gs")
            if os.path.isdir(gs_base):
                for sub in sorted(os.listdir(gs_base), reverse=True):
                    exe = os.path.join(gs_base, sub, "bin", "gswin64c.exe")
                    if os.path.isfile(exe):
                        return exe
    return None


class ExportLightweightPDF(inkex.EffectExtension):
    """Inkscape extension to export lightweight PDFs by downsampling images."""

    def add_arguments(self, pars):
        # Tabs container (notebook)
        pars.add_argument("--tabs", type=str, default="", help="Active notebook tab")

        # Tab 1: Resolution & Presets
        pars.add_argument(
            "--preset",
            type=str,
            default="sd_50",
            help="Resolution preset: sd_50, screen_96, draft_25, hd_150, print_300, custom_scale, custom_dpi",
        )
        pars.add_argument(
            "--custom_scale",
            type=int,
            default=50,
            help="Custom percentage scale (10-100)",
        )
        pars.add_argument(
            "--custom_dpi",
            type=int,
            default=75,
            help="Custom target DPI",
        )
        pars.add_argument(
            "--jpeg_quality",
            type=int,
            default=85,
            help="JPEG quality (30-100)",
        )
        pars.add_argument(
            "--downsample_threshold",
            type=str,
            default="all",
            help="Downsampling trigger: 'all' or 'significant'",
        )
        pars.add_argument(
            "--optimize_alpha",
            type=inkex.Boolean,
            default=True,
            help="Compress transparent images as JPEG + Alpha mask",
        )

        # Tab 2: Export Settings
        pars.add_argument(
            "--output_dir",
            type=str,
            default="",
            help="Folder to save the output PDF",
        )
        pars.add_argument(
            "--filename_suffix",
            type=str,
            default="_SD",
            help="Suffix to append to the filename before .pdf",
        )
        pars.add_argument(
            "--overwrite",
            type=inkex.Boolean,
            default=True,
            help="Overwrite existing file if present",
        )
        pars.add_argument(
            "--export_area",
            type=str,
            default="page",
            help="Export area: page, all_pages, drawing, selection",
        )
        pars.add_argument(
            "--text_to_path",
            type=inkex.Boolean,
            default=False,
            help="Convert text to paths (outlines fonts)",
        )
        pars.add_argument(
            "--rasterize_dpi",
            type=int,
            default=96,
            help="DPI for rasterizing SVG filters and effects",
        )
        pars.add_argument(
            "--pdf_version",
            type=str,
            default="1.5",
            help="Target PDF version standard",
        )

        # Tab 3: Advanced & Actions
        pars.add_argument(
            "--engine",
            type=str,
            default="auto",
            help="Optimizer engine: auto, gs, pikepdf, svg_prescale",
        )
        pars.add_argument(
            "--deflate_streams",
            type=inkex.Boolean,
            default=True,
            help="Compress PDF object streams",
        )
        pars.add_argument(
            "--open_after",
            type=inkex.Boolean,
            default=False,
            help="Open PDF file after export",
        )
        pars.add_argument(
            "--reveal_file",
            type=inkex.Boolean,
            default=False,
            help="Open containing folder after export",
        )
        pars.add_argument(
            "--show_report",
            type=inkex.Boolean,
            default=True,
            help="Show summary report upon completion",
        )

    def resolve_document_name_and_dir(
        self, input_file: str | None = None
    ) -> tuple[str, str]:
        """Resolve the original document name and directory.

        Priority:
        1. sodipodi:docname attribute on the SVG root element (strip .svg, basename only).
        2. input_file basename if it does not match ^ink_ext_.
        3. Fallback "Untitled".

        Output directory default:
        - If sodipodi:docname has a directory, use it if it exists.
        - If sodipodi:docname is a bare name or missing, use input_file's directory (if it exists) or home.
        - Never write into the temp directory (tempfile.gettempdir()): fall back to home.
        """
        if input_file is None:
            input_file = getattr(self.options, "input_file", None)

        home_dir = os.path.expanduser("~")
        temp_dir = tempfile.gettempdir()

        raw_docname = None
        root = (
            self.document.getroot()
            if hasattr(self, "document") and self.document is not None
            else None
        )

        if root is not None:
            if hasattr(inkex, "addNS"):
                try:
                    raw_docname = root.get(inkex.addNS("docname", "sodipodi"))
                except Exception:
                    raw_docname = None
            if not raw_docname:
                raw_docname = root.get(
                    "{http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd}docname"
                )
            if not raw_docname:
                raw_docname = root.get("sodipodi:docname")
            if not raw_docname and hasattr(root, "attrib"):
                for key, val in root.attrib.items():
                    if key.endswith("}docname") or key == "sodipodi:docname":
                        raw_docname = val
                        break

        # Priority (1): sodipodi:docname attribute on self.document.getroot()
        doc_name = None
        if raw_docname:
            raw_str = str(raw_docname).strip()
            norm_name = raw_str.replace("\\", "/")
            base = os.path.basename(norm_name)
            if base.lower().endswith(".svg"):
                base = base[:-4]
            sanitized = base.replace("/", "").replace("\\", "").strip()
            if sanitized:
                doc_name = sanitized

        # Priority (2): if input_file basename does not match ^ink_ext_ then use it
        if not doc_name and input_file:
            norm_input = str(input_file).replace("\\", "/")
            inp_base = os.path.basename(norm_input)
            if not re.match(r"^ink_ext_", inp_base):
                if inp_base.lower().endswith(".svg"):
                    cand = inp_base[:-4]
                else:
                    cand = os.path.splitext(inp_base)[0]
                sanitized = cand.replace("/", "").replace("\\", "").strip()
                if sanitized:
                    doc_name = sanitized

        # Priority (3): fallback "Untitled"
        if not doc_name:
            doc_name = "Untitled"

        # Resolve output dir default
        doc_dir = None
        if raw_docname:
            norm_docname = str(raw_docname).strip().replace("\\", "/")
            docname_dir = os.path.dirname(norm_docname)
            if docname_dir and os.path.isdir(docname_dir):
                doc_dir = os.path.abspath(docname_dir)

        if not doc_dir:
            if input_file and os.path.isfile(input_file):
                doc_dir = os.path.dirname(os.path.abspath(input_file))
            else:
                doc_dir = home_dir

        def is_temp_dir(path: str) -> bool:
            try:
                norm_p = os.path.normcase(os.path.abspath(path))
                norm_t = os.path.normcase(os.path.abspath(temp_dir))
                if norm_p == norm_t:
                    return True
                if os.path.normcase(os.path.realpath(path)) == os.path.normcase(
                    os.path.realpath(temp_dir)
                ):
                    return True
            except OSError:
                pass
            return False

        if is_temp_dir(doc_dir) or not os.path.isdir(doc_dir):
            doc_dir = home_dir

        return doc_name, doc_dir

    def effect(self):
        # 1. Determine input document path
        doc_path = self.options.input_file
        is_temp_doc = False

        if not doc_path or not os.path.isfile(doc_path):
            # Document hasn't been saved to disk yet or is piped
            tmp_svg = tempfile.NamedTemporaryFile(
                prefix="inkscape_export_", suffix=".svg", delete=False
            )
            tmp_svg.close()
            with open(tmp_svg.name, "wb") as f:
                self.document.write(f)
            doc_path = tmp_svg.name
            is_temp_doc = True
            doc_name = "Untitled"
            doc_dir = os.path.expanduser("~")
        else:
            doc_name, doc_dir = self.resolve_document_name_and_dir(doc_path)

        try:
            # 2. Determine target output path
            out_dir = self.options.output_dir.strip()
            if not out_dir or not os.path.isdir(out_dir):
                out_dir = doc_dir

            suffix = self.options.filename_suffix.strip()
            target_filename = f"{doc_name}{suffix}.pdf"
            final_pdf_path = os.path.join(out_dir, target_filename)

            if not self.options.overwrite and os.path.exists(final_pdf_path):
                counter = 1
                while os.path.exists(final_pdf_path):
                    target_filename = f"{doc_name}{suffix}_{counter}.pdf"
                    final_pdf_path = os.path.join(out_dir, target_filename)
                    counter += 1

            # 3. Resolve resolution preset
            preset = self.options.preset
            scale = 0.50
            target_dpi = 75
            preset_name = "SD — 50% scale (~75 DPI)"

            if preset == "sd_50":
                scale = 0.50
                target_dpi = 75
                preset_name = "SD (50% scale / ~75 DPI)"
            elif preset == "screen_96":
                scale = 0.64
                target_dpi = 96
                preset_name = "Screen (~96 DPI)"
            elif preset == "draft_25":
                scale = 0.25
                target_dpi = 50
                preset_name = "Draft (25% scale / ~50 DPI)"
            elif preset == "hd_150":
                scale = 0.75
                target_dpi = 150
                preset_name = "HD (75% scale / ~150 DPI)"
            elif preset == "print_300":
                scale = 1.00
                target_dpi = 300
                preset_name = "Print (100% scale / ~300 DPI)"
            elif preset == "custom_scale":
                custom_scale_pct = max(5, min(100, self.options.custom_scale))
                scale = custom_scale_pct / 100.0
                target_dpi = max(30, int(round(150 * scale)))
                preset_name = f"Custom Scale ({custom_scale_pct}%)"
            elif preset == "custom_dpi":
                target_dpi = max(30, min(1200, self.options.custom_dpi))
                scale = max(0.05, min(1.0, target_dpi / 150.0))
                preset_name = f"Custom DPI ({target_dpi} DPI)"

            with tempfile.TemporaryDirectory(prefix="inkscape_lightweight_pdf_") as tmpdir:
                raw_pdf = os.path.join(tmpdir, "intermediate_raw.pdf")

                # 4. Export SVG to raw PDF using Inkscape
                self.export_inkscape_pdf(doc_path, raw_pdf)

                if not os.path.isfile(raw_pdf) or os.path.getsize(raw_pdf) == 0:
                    raise AbortExtension(
                        _("Inkscape failed to export the intermediate PDF file.")
                    )

                raw_size = os.path.getsize(raw_pdf)

                # 5. Optimize and downsample images
                engine_used = self.optimize_pdf(
                    raw_pdf,
                    final_pdf_path,
                    target_dpi=target_dpi,
                    scale=scale,
                    jpeg_quality=self.options.jpeg_quality,
                    pdf_version=self.options.pdf_version,
                )

                if not os.path.isfile(final_pdf_path) or os.path.getsize(final_pdf_path) == 0:
                    raise AbortExtension(
                        _("Failed to generate the optimized lightweight PDF.")
                    )

                final_size = os.path.getsize(final_pdf_path)
                reduction_pct = (
                    ((raw_size - final_size) / raw_size) * 100.0 if raw_size > 0 else 0.0
                )

                # 6. Post-actions
                if self.options.open_after:
                    self.open_file(final_pdf_path)

                if self.options.reveal_file:
                    self.open_file(out_dir)

                # 7. Summary Report
                if self.options.show_report:
                    report = (
                        "====================================================\n"
                        "  Lightweight PDF Export Complete!\n"
                        "====================================================\n\n"
                        f"• Output File:   {final_pdf_path}\n"
                        f"• Preset:        {preset_name}\n"
                        f"• Target DPI:    {target_dpi} DPI\n"
                        f"• JPEG Quality:  {self.options.jpeg_quality}%\n"
                        f"• Engine Used:   {engine_used}\n\n"
                        "----------------------------------------------------\n"
                        f"  Original PDF:   {format_bytes(raw_size)}\n"
                        f"  Optimized PDF:  {format_bytes(final_size)}\n"
                        f"  Space Saved:    {reduction_pct:.1f}% reduction\n"
                        "===================================================="
                    )
                    inkex.errormsg(report)

        finally:
            if is_temp_doc and os.path.isfile(doc_path):
                try:
                    os.remove(doc_path)
                except OSError:
                    pass

    def current_page_index(self) -> int | None:
        """Return the 1-based index of the active page, or None if unknown.

        Inkscape 1.2+ stores the active page id in the namedview attribute
        ``inkscape:current-page``; pages are ``inkscape:page`` elements.
        Returns None for documents without explicit pages.
        """
        try:
            pages = self.svg.xpath("//inkscape:page")
            if not pages:
                return None
            current = self.svg.namedview.get("inkscape:current-page")
            for idx, page in enumerate(pages, start=1):
                if current and page.get("id") == current:
                    return idx
            return 1
        except Exception:
            return None

    def export_inkscape_pdf(self, input_svg: str, output_pdf: str):
        """Invoke Inkscape CLI to export the SVG to a PDF file."""
        cmd = [
            "inkscape",
            f"--export-filename={output_pdf}",
            "--export-type=pdf",
            f"--export-pdf-version={self.options.pdf_version}",
            f"--export-dpi={self.options.rasterize_dpi}",
        ]

        # Area option
        area = self.options.export_area
        if area == "drawing":
            cmd.append("--export-area-drawing")
        elif area == "page":
            cmd.append("--export-area-page")
            # Inkscape 1.2+ exports every page unless one is requested.
            page_idx = self.current_page_index()
            if page_idx is not None:
                cmd.append(f"--export-page={page_idx}")
        elif area == "all_pages":
            # Omitting --export-page exports all pages (1.4 treats "all" as
            # a single page); single-page and older versions are unaffected.
            cmd.append("--export-area-page")
        elif area == "selection":
            # If objects are selected, export selection
            if self.svg.selected:
                ids = ";".join(self.svg.selected.keys())
                cmd.extend([f"--export-id={ids}", "--export-id-only"])
            else:
                cmd.append("--export-area-page")

        if self.options.text_to_path:
            cmd.append("--export-text-to-path")

        cmd.append(input_svg)

        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip()
                raise AbortExtension(
                    _("Inkscape CLI export error (code {0}): {1}").format(
                        res.returncode, err_msg
                    )
                )
        except FileNotFoundError:
            raise AbortExtension(
                _("Could not execute 'inkscape' command line. Is Inkscape in your PATH?")
            )

    def optimize_pdf(
        self,
        raw_pdf: str,
        output_pdf: str,
        target_dpi: int,
        scale: float,
        jpeg_quality: int,
        pdf_version: str,
    ) -> str:
        """Optimize and downsample the PDF images."""
        engine = self.options.engine
        gs_bin = find_ghostscript()

        # Check pikepdf availability
        pikepdf_module = None
        try:
            import pikepdf
            pikepdf_module = pikepdf
        except ImportError:
            pikepdf_module = None

        # Decide which engine to use
        if engine == "gs" or (engine == "auto" and gs_bin is not None):
            if gs_bin is None:
                raise AbortExtension(
                    _("Ghostscript engine selected, but Ghostscript ('gs') was not found on your system.")
                )
            self.optimize_with_ghostscript(
                gs_bin, raw_pdf, output_pdf, target_dpi, jpeg_quality, pdf_version
            )
            return "Ghostscript (DPI Downsampler)"

        if engine == "pikepdf" or (engine == "auto" and pikepdf_module is not None):
            if pikepdf_module is None:
                raise AbortExtension(
                    _("PikePDF engine selected, but python library 'pikepdf' is not installed.")
                )
            self.optimize_with_pikepdf(
                pikepdf_module, raw_pdf, output_pdf, scale, jpeg_quality
            )
            return "PikePDF (Object Stream Resizer)"

        # Fallback if Ghostscript is found
        if gs_bin:
            self.optimize_with_ghostscript(
                gs_bin, raw_pdf, output_pdf, target_dpi, jpeg_quality, pdf_version
            )
            return "Ghostscript (Auto fallback)"

        # If nothing else available, copy file directly and alert user
        shutil.copy2(raw_pdf, output_pdf)
        inkex.errormsg(
            _(
                "Note: Neither Ghostscript nor PikePDF was found. The PDF was exported "
                "with standard Inkscape settings without image downsampling. To enable "
                "massively compressed PDFs, install Ghostscript ('sudo pacman -S ghostscript' "
                "or 'brew install ghostscript')."
            )
        )
        return "Inkscape Standard (No compressor found)"

    def optimize_with_ghostscript(
        self,
        gs_bin: str,
        raw_pdf: str,
        output_pdf: str,
        target_dpi: int,
        jpeg_quality: int,
        pdf_version: str,
    ):
        """Use Ghostscript pdfwrite to downsample and compress images."""
        thresh = "1.0" if self.options.downsample_threshold == "all" else "1.5"

        cmd = [
            gs_bin,
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=pdfwrite",
            f"-dCompatibilityLevel={pdf_version}",
            "-dDownsampleColorImages=true",
            f"-dColorImageResolution={target_dpi}",
            "-dColorImageDownsampleType=/Bicubic",
            f"-dColorImageDownsampleThreshold={thresh}",
            "-dDownsampleGrayImages=true",
            f"-dGrayImageResolution={target_dpi}",
            "-dGrayImageDownsampleType=/Bicubic",
            f"-dGrayImageDownsampleThreshold={thresh}",
            "-dDownsampleMonoImages=true",
            f"-dMonoImageResolution={min(target_dpi * 2, 600)}",
            "-dMonoImageDownsampleType=/Bicubic",
            f"-dMonoImageDownsampleThreshold={thresh}",
            "-dAutoFilterColorImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dAutoFilterGrayImages=false",
            "-dGrayImageFilter=/DCTEncode",
            f"-dJPEGQ={jpeg_quality}",
        ]

        if self.options.deflate_streams:
            cmd.append("-dCompressStreams=true")

        cmd.extend([f"-sOutputFile={output_pdf}", raw_pdf])

        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode != 0:
            raise AbortExtension(
                _("Ghostscript compression failed: {0}").format(res.stderr.strip())
            )

    def optimize_with_pikepdf(
        self,
        pikepdf,
        raw_pdf: str,
        output_pdf: str,
        scale: float,
        jpeg_quality: int,
    ):
        """Use PikePDF + Pillow for object-level image downsampling."""
        try:
            from PIL import Image
        except ImportError:
            raise AbortExtension(_("Pillow (PIL) is required for PikePDF optimization."))

        pdf = pikepdf.open(raw_pdf)

        # Map images to their smasks
        smask_map = {}
        all_smasks = set()
        for obj in pdf.objects:
            if isinstance(obj, (pikepdf.Dictionary, pikepdf.Stream)):
                if "/SMask" in obj and isinstance(obj["/SMask"], pikepdf.Object):
                    sm = obj["/SMask"]
                    if isinstance(sm, pikepdf.Stream) and sm.get("/Subtype") == "/Image":
                        smask_map[obj.objgen] = sm.objgen
                        all_smasks.add(sm.objgen)

        processed = set()
        for obj in list(pdf.objects):
            if not (isinstance(obj, pikepdf.Stream) and obj.get("/Subtype") == "/Image"):
                continue
            if obj.objgen in all_smasks or obj.objgen in processed:
                continue
            processed.add(obj.objgen)

            orig_w = int(obj.get("/Width", 0))
            orig_h = int(obj.get("/Height", 0))
            if orig_w <= 1 or orig_h <= 1:
                continue

            new_w = max(1, int(round(orig_w * scale)))
            new_h = max(1, int(round(orig_h * scale)))

            has_smask = obj.objgen in smask_map
            smask_obj = pdf.get_object(smask_map[obj.objgen]) if has_smask else None

            try:
                pdf_img = pikepdf.PdfImage(obj)
                pil_img = pdf_img.as_pil_image()
            except Exception:
                continue

            alpha_channel = None
            if has_smask and smask_obj:
                if "A" in pil_img.getbands():
                    alpha_channel = pil_img.getchannel("A")
                else:
                    try:
                        sm_img = pikepdf.PdfImage(smask_obj)
                        alpha_channel = sm_img.as_pil_image().convert("L")
                    except Exception:
                        alpha_channel = None

            resized_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            if alpha_channel is not None and self.options.optimize_alpha:
                resized_alpha = alpha_channel.resize((new_w, new_h), Image.Resampling.LANCZOS)
                rgb_img = resized_img.convert("RGB")
                buf = io.BytesIO()
                rgb_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)

                obj.write(buf.getvalue(), filter=pikepdf.Name("/DCTDecode"))
                obj.Width = new_w
                obj.Height = new_h
                obj.ColorSpace = pikepdf.Name("/DeviceRGB")
                obj.BitsPerComponent = 8
                if "/DecodeParms" in obj:
                    del obj.DecodeParms

                alpha_bytes = zlib.compress(resized_alpha.tobytes(), level=9)
                smask_obj.write(alpha_bytes, filter=pikepdf.Name("/FlateDecode"))
                smask_obj.Width = new_w
                smask_obj.Height = new_h
                smask_obj.ColorSpace = pikepdf.Name("/DeviceGray")
                smask_obj.BitsPerComponent = 8
                if "/DecodeParms" in smask_obj:
                    del smask_obj.DecodeParms
                obj.SMask = smask_obj
                processed.add(smask_obj.objgen)
            else:
                cs = str(obj.get("/ColorSpace"))
                if cs == "/DeviceGray" or resized_img.mode == "L":
                    gray_img = resized_img.convert("L")
                    buf = io.BytesIO()
                    gray_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
                    obj.write(buf.getvalue(), filter=pikepdf.Name("/DCTDecode"))
                    obj.Width = new_w
                    obj.Height = new_h
                    obj.ColorSpace = pikepdf.Name("/DeviceGray")
                    obj.BitsPerComponent = 8
                else:
                    rgb_img = resized_img.convert("RGB")
                    buf = io.BytesIO()
                    rgb_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
                    obj.write(buf.getvalue(), filter=pikepdf.Name("/DCTDecode"))
                    obj.Width = new_w
                    obj.Height = new_h
                    obj.ColorSpace = pikepdf.Name("/DeviceRGB")
                    obj.BitsPerComponent = 8
                if "/DecodeParms" in obj:
                    del obj.DecodeParms

        pdf.save(
            output_pdf,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
            compress_streams=self.options.deflate_streams,
            recompress_flate=True,
        )

    def open_file(self, target_path: str):
        """Open a file or directory using the OS default application."""
        try:
            if sys.platform == "win32":
                os.startfile(target_path)
            else:
                # Launch through a shell that backgrounds the opener and exits,
                # so no child process is left unreaped (a bare Popen that is never
                # waited on makes Inkscape show a ResourceWarning dialog).
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.run(
                    ["sh", "-c", '"$0" "$1" >/dev/null 2>&1 &', opener, target_path],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        except Exception:
            pass


if __name__ == "__main__":
    ExportLightweightPDF().run()
