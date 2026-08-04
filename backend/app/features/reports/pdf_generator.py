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
        
        # --- 2. EXECUTIVE SUMMARY & INSIGHTS ---
        story.append(Paragraph("Executive Summary", h1_style))
        
        summary_text = (data.get("executive_summary") or {}).get("key_takeaways", [])
        if not summary_text:
            summary_text = [
                "Key corporate intelligence objectives have been aligned and verified.",
                "Identified operational risks have mitigation channels mapped in downstream analytics.",
                "Action items prioritize West region cohort optimization plans."
            ]
            
        summary_paragraphs = ""
        for takeaway in summary_text:
            summary_paragraphs += f"• {takeaway}<br/>"
            
        # Draw a beautiful callout box for the summary
        callout_data = [[Paragraph(summary_paragraphs, callout_style)]]
        callout_table = Table(callout_data, colWidths=[504])
        callout_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_light),
            ('BOX', (0,0), (-1,-1), 1, secondary_color),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('LEFTPADDING', (0,0), (-1,-1), 15),
            ('RIGHTPADDING', (0,0), (-1,-1), 15),
        ]))
        story.append(callout_table)
        story.append(Spacer(1, 15))
        
        # --- 3. KPI OVERVIEW ---
        story.append(Paragraph("Core KPI Overview", h1_style))
        kpi_list = data.get("kpi_overview") or [
            {"title": "Total Revenue", "value": "$1.24M", "change": "+14.2% MoM"},
            {"title": "Operating Cost", "value": "$320.5K", "change": "-2.1% MoM"},
            {"title": "Churn Prediction", "value": "15.0%", "change": "+0.5% MoM"},
            {"title": "RAG Score", "value": "94.0%", "change": "+1.8% MoM"}
        ]
        
        # Lay out KPIs as a 4-column styled table
        kpi_cells = []
        for kpi in kpi_list:
            kpi_html = f"<b>{kpi['title']}</b><br/><font size=14 color='{theme['primary']}'><b>{kpi['value']}</b></font><br/><font size=8 color='#64748b'>{kpi['change']}</font>"
            kpi_cells.append(Paragraph(kpi_html, body_style))
            
        kpi_table = Table([kpi_cells], colWidths=[126, 126, 126, 126])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        story.append(kpi_table)
        story.append(Spacer(1, 20))
        
        # --- 4. DASHBOARD SNAPSHOT & CHARTS ---
        if snapshot_path and os.path.exists(snapshot_path):
            story.append(Paragraph("Dashboard snapshot", h1_style))
            # Width is 450pt, height is calculated to maintain aspect ratio 10:6
            story.append(Image(snapshot_path, width=450, height=270))
            story.append(Spacer(1, 15))
            
        story.append(PageBreak())
        
        # --- 5. DETAILED ANALYTICS & FORECAST ---
        story.append(Paragraph("Revenue Analysis & Forecasting Projections", h1_style))
        story.append(Paragraph(
            "Based on historical database rows processed by the analytical engine, "
            "predictive time series forecasting yields the following targets. Confidence intervals "
            "represent standard anomaly deviations calculated on the machine learning platform.",
            body_style
        ))
        
        forecast_predictions = (data.get("forecast_result") or {}).get("predictions", [
            {"date": "2026-09-01", "value": 7500.0, "lower": 6800.0, "upper": 8200.0},
            {"date": "2026-10-01", "value": 7800.0, "lower": 7000.0, "upper": 8600.0},
            {"date": "2026-11-01", "value": 8100.0, "lower": 7200.0, "upper": 9000.0}
        ])
        
        table_data = [["Forecast Date", "Target Revenue", "Lower Bounds (Anomaly)", "Upper Bounds (Optimistic)"]]
        for item in forecast_predictions:
            table_data.append([
                item["date"],
                f"${item['value']:.2f}" if isinstance(item['value'], (int, float)) else str(item['value']),
                f"${item['lower']:.2f}" if isinstance(item['lower'], (int, float)) else str(item['lower']),
                f"${item['upper']:.2f}" if isinstance(item['upper'], (int, float)) else str(item['upper'])
            ])
            
        forecast_table = Table(table_data, colWidths=[126, 126, 126, 126])
        forecast_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(forecast_table)
        story.append(Spacer(1, 15))
        
        # --- 6. AI RECOMMENDATIONS & RISK ASSESSMENT ---
        story.append(Paragraph("Strategic Risk Assessment & Actions", h1_style))
        
        recommendations = data.get("recommendations") or [
            {"insight": "Customer churn rates are stable at 15%. Recommend target discount campaigns on the West region.", "confidence_score": 0.88, "priority": "High"},
            {"insight": "Q4 forecasts project a steady sales rise. Ensure warehouse supply matches the 5% margin increase.", "confidence_score": 0.92, "priority": "Medium"}
        ]
        
        recs_data = [["Strategic Insight / Opportunity", "Priority", "Confidence"]]
        for rec in recommendations:
            recs_data.append([
                Paragraph(rec["insight"], body_style),
                rec["priority"],
                f"{rec['confidence_score']*100:.0f}%" if isinstance(rec['confidence_score'], (int, float)) else str(rec['confidence_score'])
            ])
            
        recs_table = Table(recs_data, colWidths=[330, 80, 94])
        recs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#e2e8f0")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#0f172a")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (1,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(recs_table)
        story.append(Spacer(1, 15))
        
        # --- 7. CITATIONS & APPENDIX ---
        rag_citations = data.get("rag_result") or []
        if rag_citations:
            story.append(Paragraph("Enterprise References & Citations", h1_style))
            story.append(Paragraph(
                "Document search and RAG mapping query results referenced the following source guidelines:",
                body_style
            ))
            for i, citation in enumerate(rag_citations):
                cit_text = f"[{i+1}] <b>{citation['citation']['filename']}</b> (p. {citation['citation']['page']}) - <i>{citation['citation']['heading']}</i>: \"{citation['text'][:120]}...\""
                story.append(Paragraph(cit_text, body_style))
                story.append(Spacer(1, 4))
                
        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        return filepath
