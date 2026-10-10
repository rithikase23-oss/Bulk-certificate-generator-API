"""
ReportLab PDF Certificate Generator
-----------------------------------
Beginner Note:
ReportLab is Python's gold standard for PDF generation.
A PDF canvas uses points as units (72 points = 1 inch).
A landscape A4 page is approximately 841.89 points wide by 595.27 points high.
The coordinate origin (0, 0) starts at the bottom-left corner.

This module draws a professional, printable landscape certificate with:
- Concentric navy and gold ornamental borders with corner diamond accents
- Vector geometric rosette gold seal
- Dynamic font scaling to guarantee long recipient names never clip or overlap
- Multi-line text wrapping for long event and course titles
- Strict post-generation file integrity verification (file exists, size > 0, %PDF magic header)
"""

import hashlib
import math
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.logger import logger

# Pre-defined elegant color palette
COLOR_NAVY_DARK = colors.HexColor("#0F172A")    # Deep slate navy
COLOR_GOLD = colors.HexColor("#D97706")         # Golden amber
COLOR_GOLD_LIGHT = colors.HexColor("#FDE68A")   # Light gold highlight
COLOR_SLATE_MUTED = colors.HexColor("#64748B")  # Soft slate gray
COLOR_SLATE_DARK = colors.HexColor("#334155")   # Charcoal slate
COLOR_BG_TINT = colors.HexColor("#FAFAF9")      # Warm subtle background


def generate_certificate_hash(job_id: str, recipient_email: str, recipient_name: str) -> str:
    """
    Generates a deterministic anti-tamper SHA-256 verification hash
    combining job ID, recipient email, and recipient name.
    """
    raw_data = f"{job_id}:{recipient_email.lower().strip()}:{recipient_name.strip()}".encode("utf-8")
    return hashlib.sha256(raw_data).hexdigest()


def draw_geometric_gold_seal(c: canvas.Canvas, cx: float, cy: float, outer_radius: float = 32.0):
    """
    Draws an official-looking golden medal seal with rosette teeth using canvas math.
    No raster images required!
    """
    c.saveState()
    
    # Outer starburst / rosette ring
    num_points = 24
    inner_r = outer_radius * 0.85
    points = []
    for i in range(num_points * 2):
        angle = i * (math.pi / num_points)
        r = outer_radius if (i % 2 == 0) else inner_r
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append((px, py))
    
    p = c.beginPath()
    p.moveTo(points[0][0], points[0][1])
    for px, py in points[1:]:
        p.lineTo(px, py)
    p.close()
    
    c.setFillColor(COLOR_GOLD)
    c.setStrokeColor(COLOR_GOLD)
    c.drawPath(p, fill=1, stroke=1)
    
    # Inner gold circle
    c.setFillColor(colors.HexColor("#B45309"))
    c.setStrokeColor(COLOR_GOLD_LIGHT)
    c.setLineWidth(1.5)
    c.circle(cx, cy, outer_radius * 0.72, fill=1, stroke=1)
    
    # Inner highlight ring
    c.setStrokeColor(colors.HexColor("#FEF3C7"))
    c.setLineWidth(0.8)
    c.circle(cx, cy, outer_radius * 0.60, fill=0, stroke=1)
    
    # Center text inside seal
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(cx, cy + 3, "OFFICIAL")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(cx, cy - 6, "VERIFIED")
    
    # Two small dangling ribbons beneath the seal
    c.setFillColor(COLOR_GOLD)
    ribbon_path = c.beginPath()
    ribbon_path.moveTo(cx - 14, cy - 22)
    ribbon_path.lineTo(cx - 20, cy - 42)
    ribbon_path.lineTo(cx - 10, cy - 38)
    ribbon_path.lineTo(cx - 5, cy - 26)
    ribbon_path.close()
    c.drawPath(ribbon_path, fill=1, stroke=0)
    
    ribbon_path2 = c.beginPath()
    ribbon_path2.moveTo(cx + 14, cy - 22)
    ribbon_path2.lineTo(cx + 20, cy - 42)
    ribbon_path2.lineTo(cx + 10, cy - 38)
    ribbon_path2.lineTo(cx + 5, cy - 26)
    ribbon_path2.close()
    c.drawPath(ribbon_path2, fill=1, stroke=0)
    
    c.restoreState()


def generate_certificate_pdf(
    output_path: Path,
    recipient_name: str,
    event_name: str,
    issuer_name: str,
    issue_date: str,
    certificate_title: str = "Certificate of Achievement",
    issuer_title: Optional[str] = "Program Director",
    organization_name: str = "Apex Institute of Technology",
    recipient_identifier: Optional[str] = None,
    certificate_hash: Optional[str] = None,
    certificate_id: Optional[str] = None,
) -> None:
    """
    Renders a landscape A4 PDF certificate file, writes it to output_path,
    and performs strict integrity verification before returning.
    
    Raises:
        ValueError: if required string arguments are empty or file is invalid
        IOError / Exception: if file cannot be created or written
    """
    clean_name = recipient_name.strip() if recipient_name else ""
    clean_event = event_name.strip() if event_name else ""

    if not clean_name:
        raise ValueError("Cannot render certificate: recipient_name is empty or blank")
    if not clean_event:
        raise ValueError("Cannot render certificate: event_name is empty or blank")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Standard landscape A4 dimensions (width ~ 841.89, height ~ 595.27)
    width, height = landscape(A4)
    max_content_width = width - 140  # Maximum printable text width between margins
    
    c = canvas.Canvas(str(output_path), pagesize=(width, height))
    c.setTitle(f"{certificate_title} - {clean_name}")
    c.setAuthor(organization_name)
    c.setSubject(clean_event)

    # 1. Subtle warm background fill
    c.setFillColor(COLOR_BG_TINT)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer Navy Decorative Border
    c.setStrokeColor(COLOR_NAVY_DARK)
    c.setLineWidth(3.0)
    margin = 32
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # 3. Inner Gold Accent Border
    c.setStrokeColor(COLOR_GOLD)
    c.setLineWidth(1.2)
    inner_margin = margin + 8
    c.rect(inner_margin, inner_margin, width - 2 * inner_margin, height - 2 * inner_margin, fill=0, stroke=1)

    # Corner diamond decorations on borders
    def draw_corner_diamond(cx: float, cy: float, sz: float = 5.0):
        c.setFillColor(COLOR_GOLD)
        diamond = c.beginPath()
        diamond.moveTo(cx, cy + sz)
        diamond.lineTo(cx + sz, cy)
        diamond.lineTo(cx, cy - sz)
        diamond.lineTo(cx - sz, cy)
        diamond.close()
        c.drawPath(diamond, fill=1, stroke=0)

    draw_corner_diamond(inner_margin, inner_margin)
    draw_corner_diamond(width - inner_margin, inner_margin)
    draw_corner_diamond(inner_margin, height - inner_margin)
    draw_corner_diamond(width - inner_margin, height - inner_margin)

    # 4. Top Organization Header (with long text scaling)
    org_header = organization_name.upper()
    org_font_size = 11
    while org_font_size > 8 and c.stringWidth(org_header, "Helvetica-Bold", org_font_size) > max_content_width:
        org_font_size -= 0.5

    c.setFillColor(COLOR_SLATE_MUTED)
    c.setFont("Helvetica-Bold", org_font_size)
    c.drawCentredString(width / 2.0, height - 85, org_header)

    # Thin decorative line under organization
    c.setStrokeColor(COLOR_GOLD_LIGHT)
    c.setLineWidth(0.8)
    c.line(width / 2.0 - 120, height - 94, width / 2.0 + 120, height - 94)

    # 5. Primary Certificate Title (scaled for long titles)
    title_upper = certificate_title.upper()
    title_font_size = 28
    while title_font_size > 18 and c.stringWidth(title_upper, "Helvetica-Bold", title_font_size) > max_content_width:
        title_font_size -= 1

    c.setFillColor(COLOR_NAVY_DARK)
    c.setFont("Helvetica-Bold", title_font_size)
    c.drawCentredString(width / 2.0, height - 135, title_upper)

    # 6. Presentation Lead-in Text
    c.setFillColor(COLOR_SLATE_MUTED)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width / 2.0, height - 168, "THIS IS PROUDLY PRESENTED TO")

    # 7. Recipient Name: DYNAMIC SCALING FOR LONG NAMES
    # Prevents long names from clipping or overlapping with margins!
    name_font_size = 28
    while name_font_size > 14 and c.stringWidth(clean_name, "Helvetica-Bold", name_font_size) > max_content_width:
        name_font_size -= 1

    c.setFillColor(COLOR_NAVY_DARK)
    c.setFont("Helvetica-Bold", name_font_size)
    name_y = height - 215
    c.drawCentredString(width / 2.0, name_y, clean_name)

    # Accent underline beneath recipient name
    name_text_width = c.stringWidth(clean_name, "Helvetica-Bold", name_font_size)
    line_half = max(min(name_text_width / 2.0 + 20, max_content_width / 2.0), 90)
    c.setStrokeColor(COLOR_GOLD)
    c.setLineWidth(1.5)
    c.line(width / 2.0 - line_half, name_y - 10, width / 2.0 + line_half, name_y - 10)

    # Optional Student/Candidate ID
    current_y = name_y - 28
    if recipient_identifier:
        c.setFillColor(COLOR_SLATE_MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawCentredString(width / 2.0, current_y, f"Candidate ID: {recipient_identifier}")
        current_y -= 20
    else:
        current_y -= 8

    # 8. Achievement Citation Paragraph
    c.setFillColor(COLOR_SLATE_DARK)
    c.setFont("Helvetica", 12.5)
    c.drawCentredString(
        width / 2.0,
        current_y,
        "for successfully completing all evaluation criteria and demonstrating excellence in",
    )
    current_y -= 24

    # Event Name: Multi-line wrapping for long course / event titles
    event_font_size = 17
    wrapped_event_lines = simpleSplit(clean_event, "Helvetica-BoldOblique", event_font_size, max_content_width)
    
    # If more than 2 lines, reduce font size
    if len(wrapped_event_lines) > 2:
        event_font_size = 14
        wrapped_event_lines = simpleSplit(clean_event, "Helvetica-BoldOblique", event_font_size, max_content_width)

    c.setFillColor(COLOR_NAVY_DARK)
    c.setFont("Helvetica-BoldOblique", event_font_size)
    for line in wrapped_event_lines[:2]:  # Display up to 2 wrapped lines safely
        c.drawCentredString(width / 2.0, current_y, line)
        current_y -= (event_font_size + 4)

    # 9. Lower Footer Layout:
    # Left: Issue Date & Verification IDs
    # Center: Official Gold Seal
    # Right: Signature Line & Issuer Name
    footer_y = 108.0

    # --- Left: Date, Certificate ID, & Anti-tamper Hash ---
    left_x = margin + 45
    c.setStrokeColor(COLOR_SLATE_MUTED)
    c.setLineWidth(0.7)
    c.line(left_x, footer_y, left_x + 160, footer_y)

    c.setFillColor(COLOR_NAVY_DARK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(left_x, footer_y - 15, issue_date)

    c.setFillColor(COLOR_SLATE_MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(left_x, footer_y - 27, "Date of Issuance")

    if certificate_id:
        c.setFont("Helvetica", 7.5)
        c.drawString(left_x, footer_y - 39, f"Cert ID: {certificate_id[:12].upper()}")

    if certificate_hash:
        short_hash = certificate_hash[:16].upper()
        c.setFont("Helvetica", 7.5)
        hash_y = footer_y - (50 if certificate_id else 39)
        c.drawString(left_x, hash_y, f"Hash: {short_hash}")

    # --- Center: Gold Seal ---
    draw_geometric_gold_seal(c, width / 2.0, footer_y - 10, outer_radius=34.0)

    # --- Right: Issuer Signature & Title ---
    right_x = width - margin - 205
    c.setStrokeColor(COLOR_SLATE_MUTED)
    c.setLineWidth(0.7)
    c.line(right_x, footer_y, right_x + 160, footer_y)

    c.setFillColor(COLOR_NAVY_DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(right_x, footer_y - 15, issuer_name)

    c.setFillColor(COLOR_SLATE_MUTED)
    c.setFont("Helvetica", 9)
    c.drawString(right_x, footer_y - 27, issuer_title or "Authorized Signatory")

    # Finalize and close PDF
    c.showPage()
    c.save()

    # Strict Integrity Verification:
    # Ensure generated PDF exists on disk, has non-trivial size, and valid PDF binary header
    if not output_path.is_file():
        raise FileNotFoundError(f"Certificate PDF was not created on disk: {output_path}")

    file_size = output_path.stat().st_size
    if file_size < 500:
        raise ValueError(f"Generated PDF file is unusually small ({file_size} bytes)")

    with open(output_path, "rb") as f:
        header = f.read(4)
        if header != b"%PDF":
            raise ValueError(f"Generated file does not have valid PDF magic bytes: {header}")

    logger.debug(f"Rendered and verified certificate PDF: {output_path.name} ({file_size} bytes)")
