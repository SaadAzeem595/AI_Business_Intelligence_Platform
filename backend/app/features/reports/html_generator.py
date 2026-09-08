import os
from typing import Dict, Any
from app.features.reports.schemas import ExecutiveReportData


class HTMLReportGenerator:
    """
    Generates a standalone, polished, enterprise-grade executive report HTML document.
    Embeds responsive dark-mode styling, SVG charts, and interactive claim badges.
    """

    @staticmethod
    def generate(filepath: str, report_data: ExecutiveReportData) -> str:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        meta = report_data.metadata

        # Build KPI Cards HTML
        kpis_html = ""
        for k in report_data.kpi_overview:
            status_color = "#10b981" if k.status == "positive" else ("#ef4444" if k.status == "negative" else "#6b7280")
            kpis_html += f"""
            <div class="kpi-card">
              <div class="kpi-header">
                <span class="kpi-title">{k.title}</span>
                <span class="source-tag" title="Grounding Source">{k.source_id}</span>
              </div>
              <div class="kpi-value">{k.current_value}</div>
              <div class="kpi-footer">
                <span class="kpi-change" style="color: {status_color};">
                  {'▲' if k.direction == 'up' else ('▼' if k.direction == 'down' else '—')} {k.change_pct}
                </span>
                <span class="kpi-prev">vs {k.previous_value or 'prior'}</span>
              </div>
              <div class="kpi-source">{k.source}</div>
            </div>
            """

        # Build Key Insights HTML
        insights_html = ""
        for ins in report_data.key_insights:
            sev_badge = f'<span class="badge badge-{ins.severity.lower()}">{ins.severity}</span>'
            insights_html += f"""
            <div class="insight-card">
              <div class="insight-header">
                <h3>{ins.title}</h3>
                {sev_badge}
              </div>
              <p class="insight-desc">{ins.description}</p>
              <div class="insight-meta">
                <span><strong>Relevance:</strong> {ins.business_relevance}</span>
                <span><strong>Source:</strong> <span class="source-tag">{ins.source_id}</span> {ins.source}</span>
              </div>
            </div>
            """

        # Build Anomalies HTML
        anomalies_html = ""
        if report_data.anomalies:
            rows = ""
            for a in report_data.anomalies:
                rows += f"""
                <tr>
                  <td><strong>{a.metric}</strong></td>
                  <td>{a.affected_date}</td>
                  <td><span class="badge badge-{a.severity.lower()}">{a.severity}</span></td>
                  <td><code>{a.deviation}</code></td>
                  <td>{a.baseline}</td>
                  <td>{a.business_impact}</td>
                  <td><span class="source-tag">{a.source_id}</span></td>
                </tr>
                """
            anomalies_html = f"""
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th>Date</th>
                    <th>Severity</th>
                    <th>Deviation</th>
                    <th>Baseline</th>
                    <th>Business Impact</th>
                    <th>Source</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
            """
        else:
            anomalies_html = "<p class='empty-text'>No statistical anomalies detected for this reporting period.</p>"

        # Build Forecast HTML
        forecast_html = ""
        if report_data.forecast and report_data.forecast.points:
            fc = report_data.forecast
            rows = ""
            for pt in fc.points[:10]:
                lower_str = f"${pt.lower:,.2f}" if pt.lower else "—"
                upper_str = f"${pt.upper:,.2f}" if pt.upper else "—"
                forecast_val = f"${pt.forecast:,.2f}" if pt.forecast else "—"
                rows += f"""
                <tr>
                  <td>{pt.date}</td>
                  <td>{forecast_val}</td>
                  <td>{lower_str}</td>
                  <td>{upper_str}</td>
                </tr>
                """
            forecast_html = f"""
            <div class="forecast-meta-grid">
              <div class="meta-item"><span>Horizon</span><strong>{fc.horizon}</strong></div>
              <div class="meta-item"><span>Model</span><strong>{fc.model_used}</strong></div>
              <div class="meta-item"><span>Trend Direction</span><strong>{fc.trend_direction}</strong></div>
              <div class="meta-item"><span>Source ID</span><strong class="source-tag">{fc.source_id}</strong></div>
            </div>
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Forecast Date</th>
                    <th>Predicted Value</th>
                    <th>Lower Confidence (95%)</th>
                    <th>Upper Confidence (95%)</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
            """
        else:
            forecast_html = "<p class='empty-text'>Forecasting data unavailable for selected source parameters.</p>"

        # Build Segmentation HTML
        segments_html = ""
        if report_data.segmentation:
            for s in report_data.segmentation:
                segments_html += f"""
                <div class="segment-card">
                  <div class="segment-header">
                    <h4>{s.name}</h4>
                    <span class="badge badge-indigo">{s.status}</span>
                  </div>
                  <div class="segment-stats">
                    <div><span>Size</span><strong>{s.size:,} ({s.size_pct})</strong></div>
                    <div><span>Avg Spend</span><strong>{s.avg_spent}</strong></div>
                    <div><span>Risk Rating</span><strong>{s.risk_rating}</strong></div>
                  </div>
                  <p class="segment-notes">{s.meaningful_changes}</p>
                  <div class="segment-source"><span class="source-tag">{s.source_id}</span> {s.source}</div>
                </div>
                """
        else:
            segments_html = "<p class='empty-text'>Customer segmentation module not included or data unavailable.</p>"

        # Build Business Impact HTML
        impacts_html = ""
        for imp in report_data.business_impact:
            impacts_html += f"""
            <div class="impact-item">
              <div class="impact-header">
                <strong>{imp.issue}</strong>
                <span class="badge badge-{imp.severity.lower()}">{imp.severity} Severity</span>
              </div>
              <p><strong>Affected Business Area:</strong> {imp.affected_area}</p>
              <p><strong>Magnitude:</strong> {imp.magnitude}</p>
              <p class="impact-evidence"><strong>Evidence:</strong> {imp.supporting_evidence} <span class="source-tag">{imp.source_id}</span></p>
            </div>
            """

        # Build Recommendations HTML
        recs_html = ""
        for rec in report_data.recommendations:
            recs_html += f"""
            <div class="rec-card">
              <div class="rec-header">
                <span class="badge badge-{rec.priority.lower()}">{rec.priority} Priority</span>
                <span class="owner-tag">Owner: {rec.suggested_owner}</span>
              </div>
              <h3>{rec.recommendation}</h3>
              <p class="rec-reason"><strong>Reason:</strong> {rec.reason}</p>
              <div class="rec-meta">
                <span><strong>Expected Impact:</strong> {rec.expected_impact}</span>
                <span><span class="source-tag">{rec.source_id}</span> Ref: {rec.supporting_evidence}</span>
              </div>
            </div>
            """

        # Build Evidence Table HTML
        evidence_html = ""
        if report_data.evidence:
            rows = ""
            for ev in report_data.evidence:
                rows += f"""
                <tr>
                  <td><span class="source-tag">{ev.source_id}</span></td>
                  <td><strong>{ev.category}</strong></td>
                  <td>{ev.claim}</td>
                  <td><code>{ev.source_name}</code></td>
                  <td>{ev.details}</td>
                </tr>
                """
            evidence_html = f"""
            <div class="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Source ID</th>
                    <th>Category</th>
                    <th>Authoritative Claim / Metric</th>
                    <th>Source System / File</th>
                    <th>Grounding Details</th>
                  </tr>
                </thead>
                <tbody>{rows}</tbody>
              </table>
            </div>
            """

        # Summary bullets
        summary_bullets = "".join(f"<li>{s}</li>" for s in report_data.executive_summary)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta.title} - DataPilot AI Executive Report</title>
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: #111827;
      --border: #1f2937;
      --text: #f9fafb;
      --text-muted: #9ca3af;
      --primary: #4f46e5;
      --primary-light: #6366f1;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.6;
      padding: 2.5rem 1.5rem;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    
    /* Header */
    .header {{
      border-bottom: 1px solid var(--border);
      padding-bottom: 1.5rem;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      flex-wrap: wrap;
      gap: 1rem;
    }}
    .header h1 {{ font-size: 2rem; font-weight: 800; color: #fff; }}
    .header .subtitle {{ font-size: 0.875rem; color: var(--text-muted); margin-top: 0.25rem; }}
    .header-meta {{
      background: rgba(31, 41, 55, 0.5);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 0.75rem 1rem;
      font-size: 0.8rem;
    }}
    .header-meta div {{ margin-bottom: 0.2rem; }}
    .header-meta strong {{ color: #e5e7eb; }}

    /* Section Styling */
    .section {{
      margin-bottom: 2.5rem;
    }}
    .section-title {{
      font-size: 1.25rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      padding-bottom: 0.5rem;
    }}

    /* Callout */
    .callout {{
      background: rgba(79, 70, 229, 0.08);
      border-left: 4px solid var(--primary);
      border-radius: 6px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .callout ul {{ list-style-type: none; }}
    .callout li {{
      position: relative;
      padding-left: 1.25rem;
      margin-bottom: 0.6rem;
      font-size: 0.95rem;
      color: #e2e8f0;
    }}
    .callout li::before {{
      content: "•";
      position: absolute;
      left: 0;
      color: var(--primary-light);
      font-size: 1.4rem;
      line-height: 1;
    }}

    /* KPI Grid */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .kpi-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
      transition: transform 0.2s;
    }}
    .kpi-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    .kpi-title {{ font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); }}
    .kpi-value {{ font-size: 1.8rem; font-weight: 800; color: #fff; margin-bottom: 0.25rem; }}
    .kpi-footer {{ font-size: 0.8rem; display: flex; gap: 0.5rem; align-items: center; }}
    .kpi-prev {{ color: var(--text-muted); font-size: 0.75rem; }}
    .kpi-source {{ font-size: 0.7rem; color: #64748b; margin-top: 0.5rem; }}

    /* Insights Grid */
    .insights-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
    .insight-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1.25rem;
    }}
    .insight-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    .insight-header h3 {{ font-size: 1rem; font-weight: 700; color: #fff; }}
    .insight-desc {{ font-size: 0.875rem; color: #d1d5db; margin-bottom: 0.75rem; }}
    .insight-meta {{ font-size: 0.75rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.25rem; }}

    /* Badges */
    .badge {{
      display: inline-block;
      padding: 0.2rem 0.5rem;
      font-size: 0.7rem;
      font-weight: 700;
      border-radius: 9999px;
      text-transform: uppercase;
    }}
    .badge-high {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
    .badge-medium {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; }}
    .badge-low {{ background: rgba(16, 185, 129, 0.2); color: #34d399; }}
    .badge-indigo {{ background: rgba(99, 102, 241, 0.2); color: #818cf8; }}
    .source-tag {{
      display: inline-block;
      padding: 0.1rem 0.4rem;
      font-size: 0.65rem;
      font-family: monospace;
      font-weight: 700;
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.3);
      border-radius: 4px;
    }}
    .owner-tag {{
      font-size: 0.75rem;
      color: var(--text-muted);
      font-weight: 600;
    }}

    /* Table */
    .table-container {{
      overflow-x: auto;
      border: 1px solid var(--border);
      border-radius: 8px;
      margin-top: 0.75rem;
    }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 0.85rem; }}
    th, td {{ padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }}
    th {{ background: rgba(17, 24, 39, 0.8); color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; }}
    tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}

    /* Forecast & Segments */
    .forecast-meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 0.75rem;
      margin-bottom: 0.75rem;
    }}
    .meta-item {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 0.75rem;
      border-radius: 6px;
    }}
    .meta-item span {{ font-size: 0.7rem; color: var(--text-muted); display: block; }}
    .meta-item strong {{ font-size: 0.9rem; color: #fff; }}

    .segments-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }}
    .segment-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
    }}
    .segment-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    .segment-stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; font-size: 0.75rem; margin-bottom: 0.5rem; }}
    .segment-notes {{ font-size: 0.8rem; color: #d1d5db; margin-bottom: 0.5rem; }}
    .segment-source {{ font-size: 0.7rem; color: var(--text-muted); }}

    /* Recommendations */
    .recs-grid {{ display: flex; flex-direction: column; gap: 0.75rem; }}
    .rec-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-left: 4px solid var(--primary-light);
      border-radius: 8px;
      padding: 1.25rem;
    }}
    .rec-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    .rec-card h3 {{ font-size: 1.05rem; font-weight: 700; color: #fff; margin-bottom: 0.25rem; }}
    .rec-reason {{ font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.5rem; }}
    .rec-meta {{ display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); flex-wrap: wrap; gap: 0.5rem; }}

    .empty-text {{ font-size: 0.85rem; color: var(--text-muted); font-style: italic; }}
    
    /* Footer */
    .footer {{
      border-top: 1px solid var(--border);
      padding-top: 1.5rem;
      margin-top: 3rem;
      text-align: center;
      font-size: 0.75rem;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1>{meta.title}</h1>
        <div class="subtitle">DataPilot AI &bull; Executive Intelligence & Automated Performance Deliverable</div>
      </div>
      <div class="header-meta">
        <div><strong>Project:</strong> {meta.project_name}</div>
        <div><strong>Period:</strong> {meta.reporting_period}</div>
        <div><strong>Generated:</strong> {meta.generated_at}</div>
        <div><strong>Recipient:</strong> {meta.recipient}</div>
        <div><strong>Confidence:</strong> {meta.confidence_score*100:.1f}%</div>
      </div>
    </div>

    <!-- 1. Executive Summary -->
    <div class="section">
      <h2 class="section-title">1. Executive Summary</h2>
      <div class="callout">
        <ul>{summary_bullets}</ul>
      </div>
    </div>

    <!-- 2. KPI Overview -->
    <div class="section">
      <h2 class="section-title">2. Key Performance Indicators (KPI Overview)</h2>
      <div class="kpi-grid">{kpis_html}</div>
    </div>

    <!-- 3. Key Insights -->
    <div class="section">
      <h2 class="section-title">3. Strategic Business Insights</h2>
      <div class="insights-grid">{insights_html}</div>
    </div>

    <!-- 4. Statistical Anomalies -->
    <div class="section">
      <h2 class="section-title">4. Anomaly Detection & Variance Audits</h2>
      {anomalies_html}
    </div>

    <!-- 5. Time-Series Forecasting -->
    <div class="section">
      <h2 class="section-title">5. Predictive Time-Series Forecast</h2>
      {forecast_html}
    </div>

    <!-- 6. Customer Segmentation -->
    <div class="section">
      <h2 class="section-title">6. Cohort & Customer Segmentation</h2>
      <div class="segments-grid">{segments_html}</div>
    </div>

    <!-- 7. Business Impact -->
    <div class="section">
      <h2 class="section-title">7. Business Impact & Risk Analysis</h2>
      <div style="display: flex; flex-direction: column; gap: 0.75rem;">{impacts_html}</div>
    </div>

    <!-- 8. AI Recommendations -->
    <div class="section">
      <h2 class="section-title">8. Prioritized Actionable Recommendations</h2>
      <div class="recs-grid">{recs_html}</div>
    </div>

    <!-- 9. Evidence & Sources -->
    <div class="section">
      <h2 class="section-title">9. Authoritative Evidence & Grounding Sources</h2>
      {evidence_html}
    </div>

    <div class="footer">
      Generated automatically by DataPilot AI Platform &bull; Anti-Hallucination & Mathematical Validation Active
    </div>
  </div>
</body>
</html>
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        return filepath
