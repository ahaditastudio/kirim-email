import io
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from dataclasses import dataclass
from typing import Optional


@dataclass
class WatermarkOptions:
    font_size: int = 42
    opacity: float = 0.15
    rotation: int = 45
    color: tuple = (0.7, 0.7, 0.7)
    spacing_x: int = 200
    spacing_y: int = 150
    rasterize: bool = False
    dpi: int = 200


def _generate_watermark_pdf(
    email: str,
    page_width: float,
    page_height: float,
    options: WatermarkOptions,
) -> bytes:
    """Generate a single-page watermark PDF in memory using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    r, g, b = options.color
    c.setFillColor(Color(r, g, b, alpha=options.opacity))
    c.setFont("Helvetica-Bold", options.font_size)

    margin = max(page_width, page_height) * 0.5
    start_x = -margin
    start_y = -margin
    end_x = page_width + margin
    end_y = page_height + margin

    row = 0
    y = start_y
    while y < end_y:
        x = start_x + (options.spacing_x * 0.5 if row % 2 else 0)
        while x < end_x:
            c.saveState()
            c.translate(x, y)
            c.rotate(options.rotation)
            c.drawString(0, 0, email)
            c.restoreState()
            x += options.spacing_x
        y += options.spacing_y
        row += 1

    c.save()
    return buf.getvalue()


def apply_watermark(
    source_pdf_path: str,
    email: str,
    output_pdf_path: str,
    options: Optional[WatermarkOptions] = None,
    source_bytes: Optional[bytes] = None,
) -> str:
    """Apply watermark to every page of a PDF and save.

    Args:
        source_pdf_path: Path to source PDF (used if source_bytes is None)
        source_bytes: Pre-loaded PDF bytes (avoids disk I/O)
    """
    if options is None:
        options = WatermarkOptions()

    # Open from bytes (faster) or from disk
    if source_bytes:
        doc = fitz.open(stream=source_bytes, filetype="pdf")
    else:
        doc = fitz.open(source_pdf_path)

    # Pre-generate foreground watermark options
    fg_options = WatermarkOptions(
        font_size=options.font_size,
        opacity=options.opacity * 0.6,
        rotation=options.rotation,
        color=options.color,
        spacing_x=options.spacing_x,
        spacing_y=options.spacing_y,
    )

    for page in doc:
        rect = page.rect
        pw, ph = rect.width, rect.height

        # Background watermark
        wm_bytes = _generate_watermark_pdf(email, pw, ph, options)
        wm_doc = fitz.open(stream=wm_bytes, filetype="pdf")
        page.show_pdf_page(rect, wm_doc, overlay=False)

        # Foreground watermark
        wm_bytes_fg = _generate_watermark_pdf(email, pw, ph, fg_options)
        wm_doc_fg = fitz.open(stream=wm_bytes_fg, filetype="pdf")
        page.show_pdf_page(rect, wm_doc_fg, overlay=True)

        page.clean_contents()
        wm_doc.close()
        wm_doc_fg.close()

    if options.rasterize:
        new_doc = fitz.open()
        for page in doc:
            pix = page.get_pixmap(dpi=options.dpi)
            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, pixmap=pix.tobytes("png"))
        new_doc.save(output_pdf_path)
        new_doc.close()
    else:
        doc.save(output_pdf_path)

    doc.close()
    return output_pdf_path


def generate_preview(
    source_pdf_path: str,
    email: str,
    options: Optional[WatermarkOptions] = None,
) -> bytes:
    """Generate a watermarked preview of only the first page. Returns PDF bytes."""
    if options is None:
        options = WatermarkOptions()

    doc = fitz.open(source_pdf_path)
    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF has no pages")

    preview_doc = fitz.open()
    preview_doc.insert_pdf(doc, from_page=0, to_page=0)
    doc.close()

    page = preview_doc[0]
    rect = page.rect
    wm_bytes = _generate_watermark_pdf(email, rect.width, rect.height, options)
    wm_doc = fitz.open(stream=wm_bytes, filetype="pdf")
    page.show_pdf_page(rect, wm_doc, overlay=False)

    fg_options = WatermarkOptions(
        font_size=options.font_size,
        opacity=options.opacity * 0.6,
        rotation=options.rotation,
        color=options.color,
        spacing_x=options.spacing_x,
        spacing_y=options.spacing_y,
    )
    wm_bytes_fg = _generate_watermark_pdf(email, rect.width, rect.height, fg_options)
    wm_doc_fg = fitz.open(stream=wm_bytes_fg, filetype="pdf")
    page.show_pdf_page(rect, wm_doc_fg, overlay=True)
    page.clean_contents()

    wm_doc.close()
    wm_doc_fg.close()

    buf = io.BytesIO()
    preview_doc.save(buf)
    preview_doc.close()
    return buf.getvalue()
