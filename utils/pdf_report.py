import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from db.models import Pathologist
from utils.helpers import get_settings_dict


def generate_report_pdf_bytes(session, tenant_id, sample):
    """sample: db.models.Sample with .patient and its .orders (loaded by caller)."""
    cfg = get_settings_dict(session, tenant_id)
    lab_name = cfg.get("lab_name") or "Your Pathology Laboratory"
    lab_address = cfg.get("lab_address", "")
    lab_phone = cfg.get("lab_phone", "")
    lab_email = cfg.get("lab_email", "")
    disclaimer = cfg.get(
        "report_disclaimer",
        "This report is generated electronically and is valid for the tests performed on the sample "
        "received. Results should be correlated clinically.",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("LabTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=18,
                                  textColor=colors.HexColor("#0b5394"))
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9,
                                   textColor=colors.grey)
    section = ParagraphStyle("Section", parent=styles["Heading3"], textColor=colors.white,
                              backColor=colors.HexColor("#0b5394"), leftIndent=4, spaceAfter=4, spaceBefore=4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    story = []

    header_text = f"<b>{lab_name}</b><br/>{lab_address}<br/>Phone: {lab_phone} | Email: {lab_email}"
    story.append(Paragraph(header_text, styles["Normal"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#0b5394"), thickness=1.5, spaceBefore=4, spaceAfter=8))
    story.append(Paragraph("LABORATORY TEST REPORT", title_style))
    story.append(Spacer(1, 8))

    p = sample.patient
    rows = [
        ["Patient Name:", p.name, "Patient ID:", p.patient_code],
        ["Age / Gender:", f"{p.age or '-'} / {p.gender or '-'}", "Mobile:", p.mobile or "-"],
        ["Referring Doctor:", (p.referring_doctor.name if p.referring_doctor else "-"), "Sample No.:", sample.sample_number],
        ["Collection Date:", sample.collection_datetime.strftime("%d-%b-%Y %H:%M") if sample.collection_datetime else "-",
         "Report Date:", datetime.now().strftime("%d-%b-%Y %H:%M")],
    ]
    pt_table = Table(rows, colWidths=[32 * mm, 60 * mm, 32 * mm, 58 * mm])
    pt_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
    ]))
    story.append(pt_table)
    story.append(Spacer(1, 10))

    for order in sample.orders:
        story.append(Paragraph(f"&nbsp;{order.test.name} ({order.test.category or ''})", section))
        result_rows = [["Parameter", "Result", "Unit", "Reference Range", "Flag"]]
        for r in order.results:
            result_rows.append([r.parameter, r.result or "-", r.unit or "-", r.reference_range or "-", r.flag or "Normal"])
        if len(result_rows) == 1:
            result_rows.append(["-", "-", "-", "-", "-"])
        result_table = Table(result_rows, colWidths=[45 * mm, 30 * mm, 20 * mm, 50 * mm, 25 * mm])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for i, r in enumerate(result_rows[1:], start=1):
            if r[4] in ("High", "Critical"):
                style_cmds += [("TEXTCOLOR", (4, i), (4, i), colors.red), ("FONTNAME", (4, i), (4, i), "Helvetica-Bold")]
            elif r[4] == "Low":
                style_cmds += [("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#b8860b")), ("FONTNAME", (4, i), (4, i), "Helvetica-Bold")]
        result_table.setStyle(TableStyle(style_cmds))
        story.append(result_table)
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc"), thickness=0.75))

    pathologist_name, pathologist_qual = "", ""
    report = sample.report
    if report and report.pathologist_id:
        path_obj = session.query(Pathologist).get(report.pathologist_id)
        if path_obj:
            pathologist_name, pathologist_qual = path_obj.name, (path_obj.qualification or "")

    story.append(Spacer(1, 20))
    story.append(Paragraph(f"<b>{pathologist_name or 'Authorized Signatory'}</b><br/>{pathologist_qual}", styles["Normal"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<i>{disclaimer}</i>", small_center))

    doc.build(story)
    return buf.getvalue()


def generate_bill_pdf_bytes(session, tenant_id, bill):
    """bill: db.models.Bill with .patient loaded by caller. Renders a
    printable receipt: lab header, patient/bill info, itemized charges,
    totals, and the payment history."""
    from db.models import BillItem, Payment

    cfg = get_settings_dict(session, tenant_id)
    lab_name = cfg.get("lab_name") or "Your Pathology Laboratory"
    lab_address = cfg.get("lab_address", "")
    lab_phone = cfg.get("lab_phone", "")
    lab_email = cfg.get("lab_email", "")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("BillTitle", parent=styles["Title"], alignment=TA_CENTER, fontSize=16,
                                  textColor=colors.HexColor("#0b5394"))
    small_center = ParagraphStyle("SmallCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9,
                                   textColor=colors.grey)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=15 * mm, bottomMargin=15 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    story = []

    header_text = f"<b>{lab_name}</b><br/>{lab_address}<br/>Phone: {lab_phone} | Email: {lab_email}"
    story.append(Paragraph(header_text, styles["Normal"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#0b5394"), thickness=1.5, spaceBefore=4, spaceAfter=8))
    story.append(Paragraph("PAYMENT RECEIPT", title_style))
    story.append(Spacer(1, 8))

    p = bill.patient
    info_rows = [
        ["Receipt No.:", bill.receipt_number, "Date:", bill.created_at.strftime("%d-%b-%Y %H:%M") if bill.created_at else "-"],
        ["Patient Name:", p.name, "Patient ID:", p.patient_code],
        ["Mobile:", p.mobile or "-", "Status:", bill.status],
    ]
    info_table = Table(info_rows, colWidths=[32 * mm, 60 * mm, 32 * mm, 58 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 12))

    items = session.query(BillItem).filter_by(tenant_id=tenant_id, bill_id=bill.id).all()
    item_rows = [["Description", "Amount (₹)"]]
    for item in items:
        item_rows.append([item.description or "-", f"{item.price:,.0f}"])
    item_table = Table(item_rows, colWidths=[130 * mm, 40 * mm])
    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(item_table)
    story.append(Spacer(1, 10))

    totals_rows = [
        ["Gross Amount:", f"₹{bill.gross_amount:,.0f}"],
        ["Discount:", f"₹{bill.discount:,.0f}"],
        ["Net Amount:", f"₹{bill.net_amount:,.0f}"],
        ["Paid:", f"₹{bill.paid_amount:,.0f}"],
        ["Due:", f"₹{bill.due_amount:,.0f}"],
    ]
    totals_table = Table(totals_rows, colWidths=[130 * mm, 40 * mm])
    totals_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 4), (-1, 4), colors.red if bill.due_amount > 0 else colors.HexColor("#2e7d32")),
        ("LINEABOVE", (0, 2), (-1, 2), 0.5, colors.HexColor("#999999")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 14))

    payments = session.query(Payment).filter_by(tenant_id=tenant_id, bill_id=bill.id).order_by(Payment.date).all()
    if payments:
        story.append(Paragraph("<b>Payment History</b>", styles["Normal"]))
        story.append(Spacer(1, 4))
        pay_rows = [["Date", "Mode", "Amount (₹)"]]
        for pay in payments:
            pay_rows.append([pay.date.strftime("%d-%b-%Y %H:%M") if pay.date else "-", pay.mode or "-", f"{pay.amount:,.0f}"])
        pay_table = Table(pay_rows, colWidths=[60 * mm, 60 * mm, 50 * mm])
        pay_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0fe")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ]))
        story.append(pay_table)
        story.append(Spacer(1, 14))

    story.append(HRFlowable(width="100%", color=colors.HexColor("#cccccc"), thickness=0.75))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<i>This is a system-generated receipt and does not require a signature.</i>", small_center))

    doc.build(story)
    return buf.getvalue()
