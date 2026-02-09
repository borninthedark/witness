import copy
from pathlib import Path
from typing import Any

import yaml
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from fitness.config import settings

# Accent & output filename
DEFAULT_ACCENT = colors.HexColor("#2C3E50")  # Dark slate
DEFAULT_PAGE_COLOR = colors.white  # Pure white background
RESUME_FILENAME = "PAS-Resume.pdf"

# Fallback data used if YAML is missing
FALLBACK_RESUME_DATA: dict[str, Any] = {
    "personal": {
        "name": "Princeton A. Strong",
        "phone": "206-666-5568",
        "email": "info@princetonstrong.com",
        "website": "https://princetonstrong.com",
    },
    "summary": (
        "Platform Engineer specializing in secure hybrid cloud & on-prem solutions."
    ),
    "education": "G.E.D., State of Ohio",
    "certifications": [],
    "roles": [],
    "stars": [],
}


def sanitize(value: Any) -> Any:
    """Normalize punctuation, whitespace, and odd characters."""
    if not isinstance(value, str):
        return value

    repl = {
        "–": "-",
        "—": "-",
        "−": "-",
        """: '"',
        """: '"',
        "'": "'",
        "'": "'",
        "…": "...",
        "\u00a0": " ",
        "\u202f": " ",
        "\u2007": " ",
        "Wi‑Fi": "Wi-Fi",
    }
    for old, new in repl.items():
        value = value.replace(old, new)
    return value.strip()


def _coerce_newlines(s: str) -> str:
    """If the YAML stored literal '\\n', turn them into real newlines."""
    return s.replace("\\n", "\n") if isinstance(s, str) and "\\n" in s else s


def _sanitize_personal(personal: dict[str, Any]) -> None:
    """Sanitize personal information fields in-place."""
    for key in ("name", "phone", "email", "website"):
        if personal.get(key):
            personal[key] = sanitize(personal[key])


def _sanitize_certifications(certifications: list[dict[str, Any]]) -> None:
    """Sanitize certification entries in-place."""
    for cert in certifications:
        if "issuer" in cert and cert["issuer"] is not None:
            cert["issuer"] = sanitize(cert["issuer"])
        if "certification" in cert and cert["certification"] is not None:
            cert["certification"] = sanitize(cert["certification"])


def _sanitize_roles(roles: list[dict[str, Any]]) -> None:
    """Sanitize role entries and their bullets in-place."""
    for role in roles:
        for key in ("title", "dates", "company", "agency", "location"):
            if key in role and role[key] is not None:
                role[key] = sanitize(role[key])
        if "bullets" in role and isinstance(role["bullets"], list):
            role["bullets"] = [sanitize(b) for b in role["bullets"]]


def load_data(path: Path) -> dict[str, Any]:
    """Load YAML resume data and normalize + sanitize it."""
    raw = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        # Fallback for literal '\n' inside YAML
        try:
            data = yaml.safe_load(_coerce_newlines(raw))
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file: {e}") from e

    data = data or {}

    # Personal block with website support
    personal = data.setdefault("personal", {})
    personal.setdefault("name", "")
    personal.setdefault("phone", "")
    personal.setdefault("email", "")
    personal.setdefault("website", "")

    # Core fields
    data.setdefault("summary", "")
    data.setdefault("education", "")
    data.setdefault("certifications", [])
    data.setdefault("roles", [])

    # Backward-compat: support "star" -> "stars"
    if "star" in data and "stars" not in data:
        data["stars"] = data.pop("star")
    data.setdefault("stars", [])

    # Sanitize all data
    _sanitize_personal(personal)
    data["summary"] = sanitize(data["summary"])
    data["education"] = sanitize(data["education"])
    _sanitize_certifications(data.get("certifications", []))
    _sanitize_roles(data.get("roles", []))

    return data


def get_fonts() -> tuple[str, str]:
    """Return (regular_font_name, bold_font_name)."""
    return "Helvetica", "Helvetica-Bold"


class BulletIcon(Flowable):
    """Small round bullet used in experience section."""

    def __init__(self, size: float = 4.5, color=DEFAULT_ACCENT):
        super().__init__()
        self.size = size
        self.color = color
        self.width = size
        self.height = size

    def draw(self):
        self.canv.setFillColor(self.color)
        r = self.size / 2
        self.canv.circle(r, r, r, fill=1, stroke=0)


def bullets_table(
    styles,
    lines,
    total_width: float = 6.7 * inch,
    icon_col: float = 0.16 * inch,
    accent=None,
):
    """Create a two-column table: [icon] [bullet text]."""
    if accent is None:
        accent = DEFAULT_ACCENT
    rows = [
        [BulletIcon(color=accent), Paragraph(line, styles["BulletText"])]
        for line in lines
    ]
    tbl = Table(rows, colWidths=[icon_col, total_width - icon_col])
    tbl.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    return tbl


def certs_table_better(
    data,
    reg: str,
    bold: str,
    accent=None,
    total_width: float = 6.7 * inch,
):
    """Two-column header table for certifications (Issuer | Certification)."""
    if accent is None:
        accent = DEFAULT_ACCENT
    rows = [["Issuer", "Certification"]] + [list(x) for x in data]
    col_issuer = 2.6 * inch
    tbl = Table(rows, colWidths=[col_issuer, total_width - col_issuer])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("LINEBELOW", (0, 0), (-1, 0), 1, accent),
                ("FONTNAME", (0, 1), (-1, -1), reg),
                ("FONTSIZE", (0, 1), (-1, -1), 11),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#111827")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.whitesmoke, colors.Color(0.98, 0.99, 1.0)],
                ),
            ]
        )
    )
    return tbl


def _draw_page_background(canvas, page_color):
    """Fill the whole page with the configured background color."""
    canvas.saveState()
    canvas.setFillColor(page_color)
    width, height = canvas._pagesize
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.restoreState()


def draw_left_stripe_and_header(
    canvas,
    doc,
    styles,
    reg: str,
    bold: str,
    name: str,
    phone: str,
    email: str,
    website: str,
    accent,
    page_color,
):
    """Render LCARS-style left stripe and the header with contact info."""
    _draw_page_background(canvas, page_color)

    # Left accent stripe
    canvas.saveState()
    canvas.setFillColor(accent)
    canvas.rect(
        0,
        0,
        8,
        doc.height + doc.topMargin + doc.bottomMargin,
        fill=1,
        stroke=0,
    )
    canvas.restoreState()

    # Header text
    w, h = doc.pagesize
    rm, lm = doc.rightMargin, doc.leftMargin
    y = h - 36

    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.setFont(bold, 16)
    canvas.drawRightString(w - rm, y, name)

    canvas.setFont(reg, 11)
    y -= 16
    canvas.setFillColor(colors.HexColor("#111827"))

    contact_bits = [phone, email]
    if website:
        contact_bits.append(website)
    canvas.drawRightString(w - rm, y, " | ".join(contact_bits))

    y -= 10
    canvas.setStrokeColor(accent)
    canvas.setLineWidth(1.0)
    canvas.line(lm, y, w - rm, y)
    canvas.restoreState()


def create_styles(accent, reg: str, bold: str):
    """Paragraph styles used throughout the document."""
    styles = getSampleStyleSheet()

    # Base normal text
    styles["Normal"].fontName = reg
    styles["Normal"].fontSize = 11
    styles["Normal"].leading = 14

    # Section header
    styles.add(
        ParagraphStyle(
            "H2",
            parent=styles["Normal"],
            fontName=bold,
            fontSize=13,
            leading=16,
            spaceBefore=8,
            spaceAfter=4,
            textColor=accent,
        )
    )

    # Small meta text (company/location, etc.)
    styles.add(
        ParagraphStyle(
            "Small",
            parent=styles["Normal"],
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#374151"),
        )
    )

    # Bulleted lines
    styles.add(
        ParagraphStyle(
            "BulletText",
            parent=styles["Normal"],
            leftIndent=0,
            spaceBefore=1,
            spaceAfter=1,
        )
    )

    # Summary paragraph
    styles.add(
        ParagraphStyle(
            "Summary",
            parent=styles["Normal"],
            fontSize=11.5,
            leading=15.6,
            spaceAfter=4,
        )
    )

    return styles


def build_resume(
    out_path: Path,
    data: dict[str, Any],
    accent_hex: str,
    page_color_hex: str = "#FFFFFF",
):
    """Assemble the resume PDF using ReportLab."""
    accent = colors.HexColor(accent_hex)
    page_color = colors.HexColor(page_color_hex)
    reg, bold = get_fonts()

    # Personal/contact info, including website
    name = data["personal"]["name"]
    phone = data["personal"]["phone"]
    email = data["personal"]["email"]
    website = data["personal"].get("website") or ""

    summary = data["summary"]
    education = data["education"]
    certs = [(c["issuer"], c["certification"]) for c in data["certifications"]]
    roles = data["roles"]

    styles = create_styles(accent, reg, bold)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=52,
        topMargin=88,
        bottomMargin=56,
    )

    story: list[Any] = []
    story.append(Spacer(1, 4))

    # Professional summary
    story.extend(
        [
            Paragraph("Professional Summary", styles["H2"]),
            Paragraph(summary, styles["Summary"]),
            Spacer(1, 4),
        ]
    )

    # Education
    story.extend(
        [
            Paragraph("Education", styles["H2"]),
            Paragraph(education, styles["Normal"]),
            Spacer(1, 6),
        ]
    )

    # Certifications (if any)
    if certs:
        story.extend(
            [
                Paragraph("Certifications", styles["H2"]),
                certs_table_better(certs, reg, bold, accent=accent),
                Spacer(1, 6),
            ]
        )

    # Experience
    story.append(Paragraph("Experience", styles["H2"]))

    for r in roles:
        company = r.get("company") or r.get("agency") or ""
        location = r.get("location") or ""
        title = r.get("title") or ""
        dates = r.get("dates") or ""

        header = Table(
            [
                [
                    Paragraph(
                        title,
                        ParagraphStyle(
                            "RoleTitle",
                            parent=styles["Normal"],
                            fontName=bold,
                            textColor=colors.HexColor("#111827"),
                        ),
                    ),
                    Paragraph(
                        dates,
                        ParagraphStyle(
                            "Dates",
                            parent=styles["Normal"],
                            alignment=TA_RIGHT,
                            textColor=accent,
                        ),
                    ),
                ],
                [
                    Paragraph(f"{company} - {location}", styles["Small"]),
                    Paragraph("", styles["Normal"]),
                ],
            ],
            colWidths=[5.05 * inch, 2.25 * inch],
        )
        header.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ]
            )
        )

        story.extend(
            [
                header,
                Spacer(1, 3),
                bullets_table(styles, r.get("bullets", []), accent=accent),
                Spacer(1, 6),
            ]
        )

    # Page callbacks wire the LCARS header with website
    def _fp(c, d):
        draw_left_stripe_and_header(
            c, d, styles, reg, bold, name, phone, email, website, accent, page_color
        )

    def _op(c, d):
        draw_left_stripe_and_header(
            c, d, styles, reg, bold, name, phone, email, website, accent, page_color
        )

    doc.build(story, onFirstPage=_fp, onLaterPages=_op)


def _resume_data_path() -> Path:
    """Where the YAML data file is expected to live."""
    return Path(settings.data_dir) / settings.resume_data_file


def load_resume_data() -> dict[str, Any]:
    """Load resume data from YAML or fall back to static data."""
    data_path = _resume_data_path()
    if data_path.exists():
        return load_data(data_path)
    return copy.deepcopy(FALLBACK_RESUME_DATA)


def generate_resume_pdf(
    accent_hex: str | None = None,
    page_color_hex: str | None = None,
) -> Path:
    """Public entrypoint used by the app to render the PDF."""
    data = load_resume_data()
    out_dir = Path(settings.data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / RESUME_FILENAME

    # Dark slate accent, pure white page
    final_accent = accent_hex if accent_hex else "#2C3E50"
    final_page = page_color_hex if page_color_hex else "#FFFFFF"

    build_resume(
        out_path,
        data,
        final_accent,
        final_page,
    )

    return out_path
