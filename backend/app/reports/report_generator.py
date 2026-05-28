from __future__ import annotations

import os
import uuid
from html import escape
from typing import Any

from app.conversation.context_manager import get_conversation_context
from app.core.config import settings


def _escape(value: Any) -> str:
    return escape(str(value), quote=True)


def _get_reportlab():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    return {
        "colors": colors,
        "letter": letter,
        "styles": getSampleStyleSheet,
        "Paragraph": Paragraph,
        "SimpleDocTemplate": SimpleDocTemplate,
        "Spacer": Spacer,
        "Table": Table,
        "TableStyle": TableStyle,
    }


def _paragraph(text: str, style: Any, Paragraph: Any) -> Any:
    return Paragraph(_escape(text), style)


def generate_report(chat_id: str, title: str = "") -> dict[str, Any]:
    try:
        rl = _get_reportlab()
    except ImportError as exc:
        return {
            "error": f"ReportLab is not installed: {exc}",
            "error_type": "ImportError",
            "suggestion": "Install dependencies with pip install -r requirements.txt.",
        }

    try:
        report_id = f"rpt-{uuid.uuid4().hex[:10]}"
        report_title = title or f"Analytics Report - {chat_id[:8]}"
        reports_dir = getattr(settings, "REPORTS_DIR", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        path = os.path.join(reports_dir, f"{report_id}.pdf")

        styles = rl["styles"]()
        doc = rl["SimpleDocTemplate"](path, pagesize=rl["letter"], title=report_title)
        story: list[Any] = []

        story.append(_paragraph(report_title, styles["Title"], rl["Paragraph"]))
        story.append(_paragraph(f"Chat ID: {chat_id}", styles["Normal"], rl["Paragraph"]))
        story.append(rl["Spacer"](1, 14))

        ctx = get_conversation_context(chat_id)
        story.append(_paragraph("Conversation Summary", styles["Heading2"], rl["Paragraph"]))
        if ctx.get("messages"):
            for message in ctx["messages"][-12:]:
                role = str(message.get("role", "message")).title()
                content = str(message.get("content", ""))
                story.append(_paragraph(f"{role}: {content}", styles["BodyText"], rl["Paragraph"]))
                story.append(rl["Spacer"](1, 6))
        else:
            story.append(_paragraph("No conversation messages were found for this chat session.", styles["BodyText"], rl["Paragraph"]))

        if ctx.get("last_sql"):
            story.append(rl["Spacer"](1, 10))
            story.append(_paragraph("Last SQL Query", styles["Heading2"], rl["Paragraph"]))
            story.append(_paragraph(ctx["last_sql"], styles["Code"], rl["Paragraph"]))

        rows = ctx.get("last_rows") or []
        columns = ctx.get("last_columns") or []
        if rows and columns:
            story.append(rl["Spacer"](1, 10))
            story.append(_paragraph("Result Preview", styles["Heading2"], rl["Paragraph"]))
            table_data = [columns]
            for row in rows[:8]:
                table_data.append([str(row.get(col, "")) for col in columns])
            table = rl["Table"](table_data, repeatRows=1)
            table.setStyle(
                rl["TableStyle"](
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].lightgrey),
                        ("GRID", (0, 0), (-1, -1), 0.25, rl["colors"].grey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(table)

        if ctx.get("last_chart_type"):
            story.append(rl["Spacer"](1, 10))
            story.append(_paragraph("Chart", styles["Heading2"], rl["Paragraph"]))
            story.append(_paragraph(f"Last chart generated with: {ctx['last_chart_type']}", styles["BodyText"], rl["Paragraph"]))

        doc.build(story)
        return {"report_id": report_id, "title": report_title, "path": path}
    except Exception as exc:
        return {
            "error": f"Report generation failed: {exc}",
            "error_type": "ReportGenerationError",
            "suggestion": "Check that the reports directory is writable and the chat_id is valid.",
        }
