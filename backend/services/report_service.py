"""
MetrCheck AI — Professional Multilingual PDF Report Generator

This module consumes the existing AnalysisResponse and generates a professional,
multi-page PDF report localized in any of the 10 supported languages:
English, Hindi, Bengali, Marathi, Gujarati, Punjabi, Tamil, Telugu, Kannada, Malayalam.

It does NOT recalculate compliance, scoring, or recommendations.
Uses: reportlab with Unicode Indic font support.
"""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from utils.datetime_utils import format_ist_datetime, get_current_ist_datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as RLImage, PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Circle
from reportlab.graphics import renderPDF
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from models.schemas import AnalysisResponse
from config import settings
from multilingual.registry import normalize_language_code, SUPPORTED_LANGUAGES
from multilingual.localization import (
    localize_rule_label,
    localize_status,
    localize_explanation,
    get_report_ui_labels
)

logger = logging.getLogger(__name__)

# ── Dynamic Unicode & Indic Font Registration ──────────────────
_FONT_REGULAR = 'Helvetica'
_FONT_BOLD = 'Helvetica-Bold'
_FONT_OBLIQUE = 'Helvetica-Oblique'

def _init_report_fonts():
    global _FONT_REGULAR, _FONT_BOLD, _FONT_OBLIQUE
    font_candidates = [
        (r'C:\Windows\Fonts\Nirmala.ttc', 0, 1),
        (r'/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf', None, None),
    ]
    for p, idx0, idx1 in font_candidates:
        if os.path.exists(p):
            try:
                if idx0 is not None:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p, subfontIndex=idx0))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p, subfontIndex=idx1))
                else:
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic', p))
                    pdfmetrics.registerFont(TTFont('MetrCheckIndic-Bold', p))
                _FONT_REGULAR = 'MetrCheckIndic'
                _FONT_BOLD = 'MetrCheckIndic-Bold'
                logger.info(f"Registered Unicode Indic font for reports from {p}")
                return
            except Exception as e:
                logger.warning(f"Could not register font from {p}: {e}")

_init_report_fonts()

# ── Color Palette ──────────────────────────────────────────────
INDIGO = colors.HexColor('#4338ca')
INDIGO_LIGHT = colors.HexColor('#e0e7ff')
INDIGO_DARK = colors.HexColor('#312e81')
EMERALD = colors.HexColor('#059669')
EMERALD_LIGHT = colors.HexColor('#d1fae5')
AMBER = colors.HexColor('#d97706')
AMBER_LIGHT = colors.HexColor('#fef3c7')
RED = colors.HexColor('#dc2626')
RED_LIGHT = colors.HexColor('#fee2e2')
SLATE_50 = colors.HexColor('#f8fafc')
SLATE_100 = colors.HexColor('#f1f5f9')
SLATE_200 = colors.HexColor('#e2e8f0')
SLATE_400 = colors.HexColor('#94a3b8')
SLATE_500 = colors.HexColor('#64748b')
SLATE_600 = colors.HexColor('#475569')
SLATE_700 = colors.HexColor('#334155')
SLATE_800 = colors.HexColor('#1e293b')
SLATE_900 = colors.HexColor('#0f172a')
WHITE = colors.white

STATUS_COLORS = {
    'PASS': (EMERALD, EMERALD_LIGHT),
    'COMPLIANT': (EMERALD, EMERALD_LIGHT),
    'FAIL': (RED, RED_LIGHT),
    'NON_COMPLIANCE': (RED, RED_LIGHT),
    'POTENTIAL NON-COMPLIANCE': (RED, RED_LIGHT),
    'WARNING': (AMBER, AMBER_LIGHT),
    'NEEDS_REVIEW': (AMBER, AMBER_LIGHT),
    'NOT_APPLICABLE': (SLATE_500, SLATE_100),
}


def _status_color(status: str):
    s = (status or '').upper().replace('-', '_')
    return STATUS_COLORS.get(s, (SLATE_500, SLATE_100))


# ── Custom Styles ──────────────────────────────────────────────
def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'],
        fontName=_FONT_BOLD, fontSize=18, leading=22,
        textColor=INDIGO_DARK, spaceAfter=1*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=9, leading=12,
        textColor=SLATE_500, spaceAfter=3*mm, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        'SectionHeading', parent=styles['Heading2'],
        fontName=_FONT_BOLD, fontSize=11, leading=14,
        textColor=INDIGO_DARK, spaceBefore=4*mm, spaceAfter=2*mm,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'SubHeading', parent=styles['Heading3'],
        fontName=_FONT_BOLD, fontSize=9.5, leading=12,
        textColor=SLATE_800, spaceBefore=2.5*mm, spaceAfter=1.5*mm,
    ))
    styles.add(ParagraphStyle(
        'BodyText2', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=8.5, leading=11.5,
        textColor=SLATE_700, spaceAfter=2*mm,
        alignment=TA_JUSTIFY,
    ))
    styles.add(ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=9.5,
        textColor=SLATE_500, spaceAfter=1*mm,
    ))
    styles.add(ParagraphStyle(
        'TableCell', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=10,
        textColor=SLATE_700,
    ))
    styles.add(ParagraphStyle(
        'TableCellBold', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=10,
        textColor=SLATE_800,
    ))
    styles.add(ParagraphStyle(
        'TableCellCenter', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7.5, leading=10,
        textColor=SLATE_700, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'TableCellBoldCenter', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=7.5, leading=10,
        textColor=SLATE_800, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'Disclaimer', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_600, spaceAfter=2*mm,
        alignment=TA_JUSTIFY, borderWidth=0.5, borderColor=SLATE_200,
        borderPadding=5,
    ))
    styles.add(ParagraphStyle(
        'ScoreText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=26, leading=30,
        textColor=INDIGO_DARK, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'StatusText', parent=styles['Normal'],
        fontName=_FONT_BOLD, fontSize=12, leading=15,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'FooterText', parent=styles['Normal'],
        fontName=_FONT_REGULAR, fontSize=7, leading=9,
        textColor=SLATE_400, alignment=TA_CENTER,
    ))

    return styles


# ── Page Template Callbacks ────────────────────────────────────
def _header_footer(canvas, doc):
    """Draw header line and footer on every page."""
    canvas.saveState()
    w, h = A4

    # Header line
    canvas.setStrokeColor(INDIGO)
    canvas.setLineWidth(1.5)
    canvas.line(15*mm, h - 12*mm, w - 15*mm, h - 12*mm)

    # Header text
    canvas.setFont(_FONT_BOLD, 7)
    canvas.setFillColor(INDIGO)
    canvas.drawString(15*mm, h - 10.5*mm, 'METRCHECK AI')

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawRightString(w - 15*mm, h - 10.5*mm, 'AI-Assisted Compliance Screening Report')

    # Footer
    canvas.setStrokeColor(SLATE_200)
    canvas.setLineWidth(0.5)
    canvas.line(15*mm, 12*mm, w - 15*mm, 12*mm)

    canvas.setFont(_FONT_REGULAR, 7)
    canvas.setFillColor(SLATE_400)
    canvas.drawString(15*mm, 7*mm, 'MetrCheck AI — Multilingual Statutory Compliance Screening')
    canvas.drawRightString(w - 15*mm, 7*mm, f'Page {doc.page}')

    canvas.restoreState()


# ── Helper: Safe image load ────────────────────────────────────
def _load_image(image_url: str, max_width: float, max_height: float) -> Optional[RLImage]:
    """Load image from uploads directory. Returns None on failure."""
    try:
        if not image_url:
            return None

        filename = image_url.split('/')[-1] if '/' in image_url else image_url
        filepath = os.path.join(settings.UPLOAD_DIR, filename)

        if not os.path.isfile(filepath):
            logger.warning(f"Image file not found: {filepath}")
            return None

        img = RLImage(filepath)
        iw, ih = img.imageWidth, img.imageHeight
        if iw <= 0 or ih <= 0:
            return None
        ratio = min(max_width / iw, max_height / ih, 1.0)
        img.drawWidth = iw * ratio
        img.drawHeight = ih * ratio
        return img
    except Exception as e:
        logger.warning(f"Failed to load image {image_url}: {e}")
        return None


def _safe_str(val, fallback='Not detected'):
    """Safe string conversion for PDF text."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate long text for table cells."""
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + '...'


# ── Main PDF Generator ────────────────────────────────────────
def generate_pdf_report(
    analysis: AnalysisResponse,
    lang: str = "en",
    language: Optional[str] = None,
    target_language: Optional[str] = None
) -> bytes:
    """
    Generate a professional multi-page PDF report from an existing AnalysisResponse in any of 10 languages.
    Returns the PDF as bytes.
    """
    effective_lang = target_language or language or lang or "en"
    canon_lang = normalize_language_code(effective_lang)
    ui_labels = get_report_ui_labels(canon_lang)

    buf = io.BytesIO()
    styles = _build_styles()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=18*mm,
        bottomMargin=18*mm,
        leftMargin=15*mm,
        rightMargin=15*mm,
        title=f'MetrCheck AI Report — {analysis.product_name}',
        author='MetrCheck AI',
    )

    story = []
    w_avail = A4[0] - 30*mm  # Available content width

    cr = analysis.compliance_result
    product_info = analysis.product_info
    images_list = analysis.images or []
    recommendations = analysis.recommendations or cr.recommendations or []

    # ══════════════════════════════════════════════════════════════
    # PAGE 1 — EXECUTIVE SUMMARY
    # ══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('METRCHECK AI', styles['ReportTitle']))
    story.append(Paragraph(
        ui_labels.get("report_title", 'Legal Metrology Compliance Screening Report'),
        styles['ReportSubtitle']
    ))

    story.append(HRFlowable(
        width='100%', thickness=1, color=INDIGO, spaceAfter=3*mm
    ))

    story.append(Paragraph(ui_labels.get("statutory_declarations", 'EXECUTIVE SUMMARY & ANALYSIS OVERVIEW'), styles['SectionHeading']))

    # Metadata table
    date_str = format_ist_datetime(analysis.created_at, '%d %B %Y, %H:%M')

    # Detect packaging languages from analysis
    detected_lang_str = "English (Latin)"
    multi_meta = getattr(analysis, 'multilingual', None) or getattr(product_info, 'multilingual', None)
    if multi_meta and hasattr(multi_meta, 'detected_languages') and multi_meta.detected_languages:
        parts = [f"{l.name} ({round(l.confidence*100)}%)" for l in multi_meta.detected_languages]
        detected_lang_str = ", ".join(parts)

    meta_data = [
        ['Analysis ID:', analysis.id],
        [f'{ui_labels.get("generated_at", "Date / Time")}:', date_str],
        [f'{ui_labels.get("product_name", "Product")}:', _safe_str(analysis.product_name, 'Unknown Product')],
        ['Images Analyzed:', str(len(images_list))],
        [f'{ui_labels.get("detected_languages", "Packaging Languages")}:', detected_lang_str]
    ]
    meta_table = Table(meta_data, colWidths=[42*mm, w_avail - 42*mm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), _FONT_BOLD),
        ('FONTNAME', (1, 0), (1, -1), _FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (0, -1), SLATE_600),
        ('TEXTCOLOR', (1, 0), (1, -1), SLATE_800),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3*mm))

    # ── Screening Result Table ─────────────────────────────────────
    fg, _ = _status_color(cr.status)
    loc_status = localize_status(cr.status, canon_lang)

    breakdown_cells = [
        Paragraph(f'<b>{cr.passed_rules}</b> {localize_status("PASS", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{cr.needs_review_rules}</b> {localize_status("NEEDS_REVIEW", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{cr.warning_rules}</b> {localize_status("WARNING", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{cr.failed_rules}</b> {localize_status("FAIL", canon_lang)}', styles['TableCellCenter']),
        Paragraph(f'<b>{cr.not_applicable_rules}</b> {localize_status("NOT_APPLICABLE", canon_lang)}', styles['TableCellCenter']),
    ]
    bd_w = (w_avail - 12*mm) / 5
    inner_breakdown = Table([breakdown_cells], colWidths=[bd_w]*5)
    inner_breakdown.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, 0), EMERALD_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), AMBER_LIGHT),
        ('BACKGROUND', (2, 0), (2, 0), AMBER_LIGHT),
        ('BACKGROUND', (3, 0), (3, 0), RED_LIGHT),
        ('BACKGROUND', (4, 0), (4, 0), SLATE_100),
        ('BOX', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))

    card_header = Paragraph(
        f'<b>{ui_labels.get("overall_status", "STATUTORY COMPLIANCE SCREENING RESULT").upper()}</b>',
        ParagraphStyle(
            'CardHead', parent=styles['Normal'], fontName=_FONT_BOLD,
            fontSize=9, leading=11, textColor=INDIGO_DARK, alignment=TA_CENTER
        )
    )
    score_para = Paragraph(
        f'<b>{cr.score}</b> <font size=12 color="{SLATE_500.hexval()}">/ 100</font>',
        styles['ScoreText']
    )
    status_para = Paragraph(
        f'<b>{loc_status}</b>',
        ParagraphStyle('CardStat', parent=styles['StatusText'], textColor=fg)
    )

    card_table = Table([
        [card_header],
        [score_para],
        [status_para],
        [inner_breakdown],
    ], colWidths=[w_avail])
    card_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), SLATE_50),
        ('BOX', (0, 0), (-1, -1), 1, INDIGO_LIGHT),
        ('TOPPADDING', (0, 0), (0, 0), 4),
        ('BOTTOMPADDING', (0, 0), (0, 0), 2),
        ('TOPPADDING', (0, 1), (0, 1), 2),
        ('BOTTOMPADDING', (0, 1), (0, 1), 2),
        ('TOPPADDING', (0, 2), (0, 2), 2),
        ('BOTTOMPADDING', (0, 2), (0, 2), 4),
        ('TOPPADDING', (0, 3), (0, 3), 3),
        ('BOTTOMPADDING', (0, 3), (0, 3), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4*mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4*mm),
    ]))
    story.append(card_table)
    story.append(Spacer(1, 2.5*mm))

    # ══════════════════════════════════════════════════════════════
    # PACKAGE INFORMATION
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("statutory_declarations", 'PACKAGE INFORMATION'), styles['SectionHeading']))

    pi = product_info
    info_rows = [
        ['Product Name', _safe_str(pi.product_name)],
        ['Brand', _safe_str(pi.brand)],
        ['Manufacturer / Packer', _safe_str(pi.manufacturer)],
        ['Marketed By', _safe_str(pi.marketed_by)],
        ['Net Quantity', _safe_str(pi.net_quantity)],
        ['MRP', _safe_str(pi.mrp)],
        ['Country of Origin', _safe_str(pi.country_of_origin)],
        ['FSSAI Licence No.', _safe_str(pi.fssai_license)],
        ['Manufacture Date', _safe_str(pi.manufacturing_date or pi.manufacture_date)],
        ['Best Before', _safe_str(pi.best_before or pi.relative_shelf_life)],
        ['Expiry / Use By', _safe_str(pi.expiry_date or pi.use_by_date)],
        ['Batch Number', _safe_str(pi.batch_number)],
        ['Consumer Care', _safe_str(pi.consumer_care)],
        ['Ingredients', _safe_str(_truncate(pi.ingredients, 180) if pi.ingredients else None)],
    ]

    info_table_data = []
    for label, val in info_rows:
        info_table_data.append([
            Paragraph(f'<b>{label}</b>', styles['TableCell']),
            Paragraph(val, styles['TableCell']),
        ])

    info_table = Table(info_table_data, colWidths=[42*mm, w_avail - 42*mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
        ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
        ('TOPPADDING', (0, 0), (-1, -1), 1.8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.8),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 2.5*mm))

    # ── Disclaimer ─────────────────────────────────────────────
    disclaimer_text = f"<b>Disclaimer:</b> {ui_labels.get('disclaimer', 'AI-assisted screening only. Physical verification required.')}"
    story.append(Paragraph(disclaimer_text, styles['Disclaimer']))

    # ══════════════════════════════════════════════════════════════
    # PACKAGE IMAGES & EVIDENCE
    # ══════════════════════════════════════════════════════════════
    if images_list:
        story.append(PageBreak())
        story.append(Paragraph('PACKAGE IMAGES & VISUAL EVIDENCE', styles['SectionHeading']))

        for img_ev in images_list:
            img_url = img_ev.get('image_url', '') if isinstance(img_ev, dict) else getattr(img_ev, 'image_url', '')
            img_label = img_ev.get('label', 'Image') if isinstance(img_ev, dict) else getattr(img_ev, 'label', 'Image')
            word_count = img_ev.get('word_count', 0) if isinstance(img_ev, dict) else getattr(img_ev, 'word_count', 0)

            img_items = []
            img_items.append(Paragraph(
                f'<b>Panel: {img_label}</b> <font color="{SLATE_400.hexval()}">({word_count} OCR tokens detected)</font>',
                styles['SubHeading']
            ))

            rl_img = _load_image(img_url, max_width=w_avail * 0.85, max_height=95*mm)
            if rl_img:
                img_items.append(rl_img)
            else:
                img_items.append(Paragraph(
                    '<i>Image unavailable</i>', styles['SmallText']
                ))

            img_items.append(Spacer(1, 3*mm))
            story.append(KeepTogether(img_items))

    # ══════════════════════════════════════════════════════════════
    # COMPLIANCE SUMMARY TABLE
    # ══════════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph(ui_labels.get("rule_evaluations", 'COMPLIANCE SUMMARY'), styles['SectionHeading']))

    checks = cr.checks or []
    lm_checks = [c for c in checks if (c.domain or '').upper() != 'FSSAI']
    fssai_checks = [c for c in checks if (c.domain or '').upper() == 'FSSAI']

    def _build_checks_table(check_list, domain_label):
        if not check_list:
            return []

        elements = []
        elements.append(Paragraph(f'<b>{domain_label}</b>', styles['SubHeading']))

        header = [
            Paragraph(f'<b>{ui_labels.get("field_header", "Rule / Field")}</b>', styles['TableCellBold']),
            Paragraph(f'<b>Requirement</b>', styles['TableCellBold']),
            Paragraph(f'<b>{ui_labels.get("status_header", "Status")}</b>', styles['TableCellBoldCenter']),
            Paragraph(f'<b>{ui_labels.get("detected_value_header", "Detected Evidence")}</b>', styles['TableCellBold']),
            Paragraph('<b>Confidence</b>', styles['TableCellBoldCenter']),
        ]
        rows = [header]

        for c in check_list:
            status_str = c.status or 'UNKNOWN'
            fg, bg = _status_color(status_str)
            loc_st = localize_status(status_str, canon_lang)
            status_para = Paragraph(
                f'<font color="{fg.hexval()}"><b>{loc_st}</b></font>',
                styles['TableCellCenter']
            )

            det_val = _safe_str(c.detected_value, 'Not detected')
            conf = f'{round(c.confidence)}%' if c.confidence is not None else '—'
            loc_lbl = localize_rule_label(c.rule_id, canon_lang)

            rows.append([
                Paragraph(f'<b>{c.rule_id}</b>', styles['TableCell']),
                Paragraph(_truncate(loc_lbl, 60), styles['TableCell']),
                status_para,
                Paragraph(_truncate(det_val, 80), styles['TableCell']),
                Paragraph(conf, styles['TableCellCenter']),
            ])

        tbl = Table(rows, colWidths=[18*mm, 52*mm, 30*mm, 56*mm, 24*mm])
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, 0), INDIGO_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2.5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2.5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, SLATE_50]),
        ]))
        elements.append(tbl)
        elements.append(Spacer(1, 3*mm))
        return elements

    story.extend(_build_checks_table(lm_checks, 'LEGAL METROLOGY'))
    story.extend(_build_checks_table(fssai_checks, 'FSSAI (Food Safety)'))

    # ══════════════════════════════════════════════════════════════
    # DETAILED STATUTORY FINDINGS
    # ══════════════════════════════════════════════════════════════
    story.append(Paragraph(ui_labels.get("finding_header", 'DETAILED STATUTORY FINDINGS'), styles['SectionHeading']))

    for c in checks:
        status_str = c.status or 'UNKNOWN'
        loc_st = localize_status(status_str, canon_lang)
        loc_lbl = localize_rule_label(c.rule_id, canon_lang)
        loc_expl = localize_explanation(c.rule_id, status_str, c.detected_value, canon_lang)

        finding_items = []
        finding_items.append(Paragraph(
            f'<b>{c.rule_id}</b> — {loc_lbl}',
            styles['SubHeading']
        ))

        detail_rows = [
            ['Domain', (c.domain or 'LEGAL_METROLOGY').replace('_', ' ')],
            [ui_labels.get("status_header", 'Status'), loc_st],
            [ui_labels.get("detected_value_header", 'Detected Value'), _safe_str(c.detected_value, 'Not detected')],
            [ui_labels.get("finding_header", 'Finding'), loc_expl],
        ]
        if c.confidence is not None:
            detail_rows.append(['Confidence', f'{round(c.confidence)}%'])
        if c.evidence_image_label or c.evidence_region:
            loc = f'{c.evidence_image_label or "Package"} → {c.evidence_region or "label"}'
            detail_rows.append(['Evidence Location', loc])

        detail_table_data = []
        for label, val in detail_rows:
            detail_table_data.append([
                Paragraph(f'<b>{label}</b>', styles['TableCell']),
                Paragraph(str(val), styles['TableCell']),
            ])

        dtbl = Table(detail_table_data, colWidths=[38*mm, w_avail - 38*mm])
        dtbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (0, -1), SLATE_50),
            ('GRID', (0, 0), (-1, -1), 0.4, SLATE_200),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        finding_items.append(dtbl)
        finding_items.append(Spacer(1, 3*mm))
        story.append(KeepTogether(finding_items))

    # Build document
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return buf.getvalue()
