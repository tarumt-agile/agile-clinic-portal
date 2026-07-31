from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from html import escape
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agile_ci_demo.appointments.models import Appointment
from agile_ci_demo.reports.schemas import (
    AppointmentActivityReport,
    DailyAppointmentTotal,
)


class InvalidReportDateRangeError(ValueError):
    """Raised when report date parameters do not form a complete, valid range."""


@dataclass(frozen=True)
class ReportDateRange:
    from_date: dt.date
    to_date: dt.date


def current_week(today: dt.date | None = None) -> ReportDateRange:
    reference_date = today or dt.date.today()
    monday = reference_date - dt.timedelta(days=reference_date.weekday())
    return ReportDateRange(
        from_date=monday,
        to_date=monday + dt.timedelta(days=6),
    )


def resolve_report_date_range(
    from_date: dt.date | None,
    to_date: dt.date | None,
    *,
    today: dt.date | None = None,
) -> ReportDateRange:
    if from_date is None and to_date is None:
        return current_week(today)

    if from_date is None or to_date is None:
        raise InvalidReportDateRangeError(
            "Both 'from' and 'to' dates are required when selecting a custom range."
        )

    if from_date > to_date:
        raise InvalidReportDateRangeError("The 'from' date must be on or before the 'to' date.")

    return ReportDateRange(
        from_date=from_date,
        to_date=to_date,
    )


def format_range_label(date_range: ReportDateRange) -> str:
    if date_range.from_date == date_range.to_date:
        return date_range.from_date.strftime("%d %b %Y")
    return (
        f"{date_range.from_date.strftime('%d %b %Y')} - "
        f"{date_range.to_date.strftime('%d %b %Y')}"
    )


def build_appointment_activity_report(
    db: Session,
    date_range: ReportDateRange,
) -> AppointmentActivityReport:
    rows = db.execute(
        select(
            Appointment.appointment_date,
            func.count(Appointment.id),
        )
        .where(
            Appointment.appointment_date >= date_range.from_date,
            Appointment.appointment_date <= date_range.to_date,
        )
        .group_by(Appointment.appointment_date)
        .order_by(Appointment.appointment_date)
    ).all()

    totals_by_date = {appointment_date: int(total) for appointment_date, total in rows}

    number_of_days = (date_range.to_date - date_range.from_date).days + 1
    daily_totals = [
        DailyAppointmentTotal(
            date=current_date,
            total=totals_by_date.get(current_date, 0),
        )
        for offset in range(number_of_days)
        for current_date in [date_range.from_date + dt.timedelta(days=offset)]
    ]

    return AppointmentActivityReport(
        from_date=date_range.from_date,
        to_date=date_range.to_date,
        selected_range_label=format_range_label(date_range),
        total_appointments=sum(item.total for item in daily_totals),
        daily_totals=daily_totals,
    )


def _build_bar_chart(
    daily_totals: list[DailyAppointmentTotal],
) -> Drawing:
    drawing = Drawing(245 * mm, 78 * mm)
    chart = VerticalBarChart()
    chart.x = 18 * mm
    chart.y = 15 * mm
    chart.width = 218 * mm
    chart.height = 52 * mm

    values = [item.total for item in daily_totals]
    maximum = max(values, default=0)
    chart.data = [values]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1, maximum)
    chart.valueAxis.valueStep = max(
        1,
        math.ceil(maximum / 5),
    )
    chart.valueAxis.labelTextFormat = "%d"
    chart.categoryAxis.categoryNames = [item.date.strftime("%d %b") for item in daily_totals]
    chart.categoryAxis.labels.angle = 30
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    chart.bars[0].fillColor = colors.HexColor("#2463A8")
    chart.bars[0].strokeColor = colors.HexColor("#174A7E")
    chart.bars[0].strokeWidth = 0.5
    chart.barSpacing = 2
    chart.groupSpacing = 4

    drawing.add(chart)
    return drawing


def generate_appointment_activity_pdf(
    report: AppointmentActivityReport,
    *,
    clinic_name: str,
    clinic_address: str,
    clinic_phone: str,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=17 * mm,
        title="Daily Appointment Activity Report",
        author=clinic_name,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#17395C"),
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        spaceAfter=4 * mm,
    )
    range_style = ParagraphStyle(
        "RangeLabel",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#40566D"),
        fontSize=11,
        leading=14,
        spaceAfter=5 * mm,
    )
    section_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#17395C"),
        fontSize=13,
        leading=16,
        spaceBefore=3 * mm,
        spaceAfter=2 * mm,
    )

    clinic_lines = [escape(clinic_name)]
    if clinic_address:
        clinic_lines.append(escape(clinic_address))
    if clinic_phone:
        clinic_lines.append(f"Telephone: {escape(clinic_phone)}")

    story = [
        Paragraph("<br/>".join(clinic_lines), styles["Normal"]),
        Spacer(1, 4 * mm),
        Paragraph("Daily Appointment Activity Report", title_style),
        Paragraph(report.selected_range_label, range_style),
        Table(
            [
                [
                    Paragraph("<b>Total appointments</b>", styles["BodyText"]),
                    Paragraph(
                        f"<b>{report.total_appointments}</b>",
                        styles["BodyText"],
                    ),
                ]
            ],
            colWidths=[55 * mm, 25 * mm],
            hAlign="CENTER",
            style=TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, -1),
                        colors.HexColor("#EAF2FA"),
                    ),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        0.75,
                        colors.HexColor("#8CB2D9"),
                    ),
                    ("ALIGN", (1, 0), (1, 0), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            ),
        ),
        Spacer(1, 4 * mm),
    ]

    chart_chunk_size = 14
    for chunk_index in range(
        0,
        len(report.daily_totals),
        chart_chunk_size,
    ):
        chunk = report.daily_totals[chunk_index : chunk_index + chart_chunk_size]
        if chunk_index > 0:
            story.append(PageBreak())
        story.extend(
            [
                Paragraph(
                    "Daily appointment totals "
                    f"({chunk[0].date.strftime('%d %b %Y')} - "
                    f"{chunk[-1].date.strftime('%d %b %Y')})",
                    section_style,
                ),
                _build_bar_chart(chunk),
            ]
        )

    story.extend(
        [
            PageBreak(),
            Paragraph("Daily breakdown", section_style),
        ]
    )

    table_rows = [["Date", "Day", "Total appointments"]]
    table_rows.extend(
        [
            item.date.strftime("%d %b %Y"),
            item.date.strftime("%A"),
            str(item.total),
        ]
        for item in report.daily_totals
    )

    breakdown_table = LongTable(
        table_rows,
        repeatRows=1,
        colWidths=[55 * mm, 70 * mm, 45 * mm],
        hAlign="LEFT",
    )
    breakdown_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#17395C"),
                ),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B6C4D2")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(breakdown_table)

    def add_page_footer(canvas, doc) -> None:
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#C9D4DF"))
        canvas.line(
            doc.leftMargin,
            12 * mm,
            landscape(A4)[0] - doc.rightMargin,
            12 * mm,
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5C6F82"))
        canvas.drawString(
            doc.leftMargin,
            7.5 * mm,
            f"{clinic_name} - Daily Appointment Activity Report",
        )
        canvas.drawRightString(
            landscape(A4)[0] - doc.rightMargin,
            7.5 * mm,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_footer,
        onLaterPages=add_page_footer,
    )
    return buffer.getvalue()
