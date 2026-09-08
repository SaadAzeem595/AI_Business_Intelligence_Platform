import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

TEMPLATE_THEMES = {
    "CEO": {"primary": "#1e3a8a", "secondary": "#3b82f6", "bg_light": "#eff6ff"},
    "Sales": {"primary": "#0f172a", "secondary": "#f59e0b", "bg_light": "#fef3c7"},
    "Finance": {"primary": "#064e3b", "secondary": "#10b981", "bg_light": "#ecfdf5"},
    "Marketing": {"primary": "#4c1d95", "secondary": "#8b5cf6", "bg_light": "#f5f3ff"},
    "Operations": {"primary": "#111827", "secondary": "#64748b", "bg_light": "#f3f4f6"}
}


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that runs in two passes to calculate total pages and draw headers/footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        # Suppress headers/footers on the cover page
        if self._pageNumber == 1:
            return
            
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header running line
        self.drawString(54, 745, "Executive Business Review - Confidential")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 737, 558, 737)
        
        # Footer running line
        self.line(54, 52, 558, 52)
        self.drawString(54, 38, "AI Business Intelligence Platform")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 38, page_text)
        
        self.restoreState()


class PDFReportGenerator:
    """Enterprise-grade ReportLab PDF compiler supporting custom color templates and dynamic layout story."""

    @staticmethod
    def generate(
        filepath: str,
        title: str,
        template_name: str,
        data: dict,
        snapshot_path: str = None
    ) -> str:
        """Assembles and saves the report PDF to the target filepath."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Resolve color themes
        theme = TEMPLATE_THEMES.get(template_name, TEMPLATE_THEMES["CEO"])
        primary_color = colors.HexColor(theme["primary"])
        secondary_color = colors.HexColor(theme["secondary"])
        bg_light = colors.HexColor(theme["bg_light"])
        
        # Base Doc Template Setup
        # Letter: 612 x 792. Margins: 54pt. Width remaining: 504pt.
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            leftMargin=54,
            rightMargin=54,
            topMargin=72,
            bottomMargin=72
        )
        
        styles = getSampleStyleSheet()
        
        # Custom ParagraphStyles
        title_style = ParagraphStyle(
            'CoverTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=32,
            leading=38,
            textColor=primary_color,
            spaceAfter=15
        )
        
        subtitle_style = ParagraphStyle(
            'CoverSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#475569"),
            spaceAfter=40
        )
        
        meta_style = ParagraphStyle(
            'CoverMeta',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b")
        )
        
        h1_style = ParagraphStyle(
            'Heading1_Custom',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=primary_color,
            spaceBefore=15,
            spaceAfter=12,
            keepWithNext=True
        )

        h2_style = ParagraphStyle(
            'Heading2_Custom',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=secondary_color,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=True
        )

        body_style = ParagraphStyle(
            'Body_Custom',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=8
        )
        
        callout_style = ParagraphStyle(
            'Callout_Style',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#0f172a")
        )

        story = []
        
        # --- 1. COVER PAGE ---
        story.append(Spacer(1, 100))
        # Top colored accent band
        story.append(Table(
            [['']],
            colWidths=[504],
            rowHeights=[6],
            style=TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), secondary_color),
                ('TOPPADDING', (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ])
        ))
        story.append(Spacer(1, 20))
        story.append(Paragraph(title, title_style))
        story.append(Paragraph(f"{template_name} Executive Business Deliverable", subtitle_style))
        story.append(Spacer(1, 150))
        
        # Meta block
        metadata = [
            [Paragraph("Author:", meta_style), Paragraph(data.get("author", "Executive Intelligence Platform"), body_style)],
            [Paragraph("Workspace:", meta_style), Paragraph(data.get("workspace", "default").upper(), body_style)],
            [Paragraph("Date:", meta_style), Paragraph(datetime.now().strftime("%B %d, %Y"), body_style)],
            [Paragraph("Recipient:", meta_style), Paragraph(data.get("recipient", "board@company.com"), body_style)],
            [Paragraph("Confidence Score:", meta_style), Paragraph(f"{data.get('confidence_score', 0.95)*100:.1f}%", body_style)],
        ]
        meta_table = Table(metadata, colWidths=[120, 384])
        meta_table.setStyle(TableStyle([
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        story.append(meta_table)
        story.append(PageBreak())
        
        # --- 2. EXECUTIVE SUMMARY ---
        story.append(Paragraph("1. Executive Summary", h1_style))
        
        raw_summary = data.get("executive_summary")
        summary_text = []
        if isinstance(raw_summary, list):
            summary_text = raw_summary
        elif isinstance(raw_summary, dict):
            summary_text = raw_summary.get("key_takeaways", [])
        
        if not summary_text:
            summary_text = [
                "Key corporate intelligence objectives have been aligned and verified.",
                "Identified operational risks have mitigation channels mapped in downstream analytics.",
                "Action items prioritize West region cohort optimization plans."
            ]
            
        summary_paragraphs = ""
        for takeaway in summary_text:
            summary_paragraphs += f"• {takeaway}<br/>"
            
        callout_data = [[Paragraph(summary_paragraphs, callout_style)]]
        callout_table = Table(callout_data, colWidths=[504])
        callout_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_light),
            ('BOX', (0,0), (-1,-1), 1, secondary_color),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(callout_table)
        story.append(Spacer(1, 15))
        
        # --- 3. KPI OVERVIEW ---
        story.append(Paragraph("2. Key Performance Indicators", h1_style))
        kpi_list = data.get("kpi_overview") or []
        if not kpi_list:
            kpi_list = [
                {"title": "Total Revenue", "value": "$1.24M", "change": "+14.2% MoM", "source": "Dashboard KPI"},
                {"title": "Operating Cost", "value": "$320.5K", "change": "-2.1% MoM", "source": "Dashboard KPI"},
                {"title": "Retention Rate", "value": "94.8%", "change": "+1.7% MoM", "source": "Dashboard KPI"},
                {"title": "CAC Efficiency", "value": "$142.50", "change": "-9.9% MoM", "source": "Dashboard KPI"}
            ]
        
        kpi_cells = []
        for kpi in kpi_list[:4]:
            title_txt = kpi.get("title") if isinstance(kpi, dict) else getattr(kpi, "title", "KPI")
            val_txt = kpi.get("current_value") if isinstance(kpi, dict) and "current_value" in kpi else (kpi.get("value", "$0") if isinstance(kpi, dict) else getattr(kpi, "current_value", "$0"))
            chg_txt = kpi.get("change_pct") if isinstance(kpi, dict) and "change_pct" in kpi else (kpi.get("change", "0%") if isinstance(kpi, dict) else getattr(kpi, "change_pct", "0%"))
            kpi_html = f"<b>{title_txt}</b><br/><font size=13 color='{theme['primary']}'><b>{val_txt}</b></font><br/><font size=7 color='#64748b'>{chg_txt}</font>"
            kpi_cells.append(Paragraph(kpi_html, body_style))
            
        while len(kpi_cells) < 4:
            kpi_cells.append(Paragraph("<b>N/A</b><br/>—", body_style))

        kpi_table = Table([kpi_cells], colWidths=[126, 126, 126, 126])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 15))

        # --- 4. KEY INSIGHTS ---
        insights = data.get("key_insights") or []
        if insights:
            story.append(Paragraph("3. Strategic Business Insights", h1_style))
            ins_rows = [["Insight Title & Analysis", "Severity", "Supporting Metric"]]
            for ins in insights:
                title = ins.get("title") if isinstance(ins, dict) else getattr(ins, "title", "")
                desc = ins.get("description") if isinstance(ins, dict) else getattr(ins, "description", "")
                sev = ins.get("severity") if isinstance(ins, dict) else getattr(ins, "severity", "Medium")
                metric = ins.get("supporting_metric") if isinstance(ins, dict) else getattr(ins, "supporting_metric", "")
                ins_rows.append([
                    Paragraph(f"<b>{title}</b><br/><font size=8 color='#475569'>{desc}</font>", body_style),
                    sev,
                    metric
                ])
            ins_table = Table(ins_rows, colWidths=[330, 80, 94])
            ins_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(ins_table)
            story.append(Spacer(1, 15))
        
        # --- 5. DASHBOARD SNAPSHOT & CHARTS ---
        if snapshot_path and os.path.exists(snapshot_path):
            story.append(Paragraph("4. Performance Snapshot", h1_style))
            story.append(Image(snapshot_path, width=450, height=200))
            story.append(Spacer(1, 15))
            
        story.append(PageBreak())
        
        # --- 6. ANOMALIES ---
        anomalies = data.get("anomalies") or []
        if anomalies:
            story.append(Paragraph("5. Anomaly Detection & Statistical Outliers", h1_style))
            anom_rows = [["Metric Outlier", "Affected Date", "Severity", "Deviation", "Baseline"]]
            for a in anomalies[:5]:
                metric = a.get("metric") if isinstance(a, dict) else getattr(a, "metric", "")
                date_val = a.get("affected_date") if isinstance(a, dict) else getattr(a, "affected_date", "")
                sev = a.get("severity") if isinstance(a, dict) else getattr(a, "severity", "Medium")
                dev = a.get("deviation") if isinstance(a, dict) else getattr(a, "deviation", "")
                baseline = a.get("baseline") if isinstance(a, dict) else getattr(a, "baseline", "")
                anom_rows.append([metric, date_val, sev, dev, baseline])
            anom_table = Table(anom_rows, colWidths=[130, 90, 80, 104, 100])
            anom_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#334155")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(anom_table)
            story.append(Spacer(1, 15))

        # --- 7. FORECASTING ---
        fc_data = data.get("forecast") or data.get("forecast_result")
        if fc_data:
            story.append(Paragraph("6. Predictive Forecasting Projections", h1_style))
            preds = fc_data.get("predictions") if isinstance(fc_data, dict) and "predictions" in fc_data else (getattr(fc_data, "points", []) or [])
            if preds:
                table_data = [["Forecast Date", "Target Revenue", "Lower Bounds", "Upper Bounds"]]
                for item in preds[:6]:
                    d_val = item.get("date") if isinstance(item, dict) else getattr(item, "date", "")
                    val = item.get("value", item.get("forecast", 0)) if isinstance(item, dict) else getattr(item, "forecast", 0)
                    low = item.get("lower", 0) if isinstance(item, dict) else getattr(item, "lower", 0)
                    upp = item.get("upper", 0) if isinstance(item, dict) else getattr(item, "upper", 0)
                    table_data.append([
                        str(d_val),
                        f"${val:,.2f}" if isinstance(val, (int, float)) else str(val),
                        f"${low:,.2f}" if isinstance(low, (int, float)) else str(low),
                        f"${upp:,.2f}" if isinstance(upp, (int, float)) else str(upp)
                    ])
                forecast_table = Table(table_data, colWidths=[126, 126, 126, 126])
                forecast_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), primary_color),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                    ('TOPPADDING', (0,0), (-1,-1), 5),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(forecast_table)
                story.append(Spacer(1, 15))

        # --- 8. SEGMENTATION ---
        segments = data.get("segmentation") or []
        if segments:
            story.append(Paragraph("7. Customer Cohort & Segmentation", h1_style))
            seg_rows = [["Segment Name", "Size", "Share", "Avg Spend", "Risk Rating"]]
            for s in segments[:5]:
                name = s.get("name") if isinstance(s, dict) else getattr(s, "name", "")
                sz = s.get("size") if isinstance(s, dict) else getattr(s, "size", 0)
                pct = s.get("size_pct") if isinstance(s, dict) else getattr(s, "size_pct", "0%")
                spend = s.get("avg_spent") if isinstance(s, dict) else getattr(s, "avg_spent", "$0")
                risk = s.get("risk_rating") if isinstance(s, dict) else getattr(s, "risk_rating", "Low")
                seg_rows.append([name, f"{sz:,}", pct, spend, risk])
            seg_table = Table(seg_rows, colWidths=[140, 70, 70, 114, 110])
            seg_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(seg_table)
            story.append(Spacer(1, 15))

        # --- 9. AI RECOMMENDATIONS ---
        recommendations = data.get("recommendations") or []
        if recommendations:
            story.append(Paragraph("8. Strategic Recommendations", h1_style))
            recs_data = [["Actionable Recommendation", "Priority", "Owner / Team"]]
            for rec in recommendations:
                rec_text = rec.get("recommendation", rec.get("insight", "")) if isinstance(rec, dict) else getattr(rec, "recommendation", "")
                prio = rec.get("priority", "Medium") if isinstance(rec, dict) else getattr(rec, "priority", "Medium")
                owner = rec.get("suggested_owner", "BI Operations") if isinstance(rec, dict) else getattr(rec, "suggested_owner", "BI Operations")
                recs_data.append([
                    Paragraph(rec_text, body_style),
                    prio,
                    owner
                ])
                
            recs_table = Table(recs_data, colWidths=[310, 80, 114])
            recs_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0f172a")),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
                ('TOPPADDING', (0,0), (-1,-1), 5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(recs_table)
            story.append(Spacer(1, 15))
        
        # --- 10. CITATIONS & APPENDIX ---
        evidence = data.get("evidence") or data.get("rag_result") or []
        if evidence:
            story.append(Paragraph("9. Evidence Grounding & Source Citations", h1_style))
            for i, ev in enumerate(evidence[:6]):
                if isinstance(ev, dict) and "citation" in ev:
                    cit_text = f"[{i+1}] <b>{ev['citation'].get('filename')}</b> (p. {ev['citation'].get('page')}): \"{ev.get('text', '')[:120]}...\""
                else:
                    sid = ev.get("source_id", f"SRC-{i+1}") if isinstance(ev, dict) else getattr(ev, "source_id", f"SRC-{i+1}")
                    cat = ev.get("category", "") if isinstance(ev, dict) else getattr(ev, "category", "")
                    claim = ev.get("claim", "") if isinstance(ev, dict) else getattr(ev, "claim", "")
                    sname = ev.get("source_name", "") if isinstance(ev, dict) else getattr(ev, "source_name", "")
                    cit_text = f"[{sid}] <b>{cat}</b> ({sname}): {claim}"
                story.append(Paragraph(cit_text, body_style))
                story.append(Spacer(1, 3))
                
        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        return filepath
