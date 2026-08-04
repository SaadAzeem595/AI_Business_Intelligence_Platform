# Demo Script & Presentation Guide

This guide is designed for recruiters, hiring managers, and senior engineers reviewing this portfolio project. It outlines a structured demo script, a showcase screenshots checklist, and guidelines for recording presentation GIFs.

---

## 📸 Screenshots Checklist

Capture and include these key screens in your portfolio to showcase UI/UX quality:

1. **Dashboard KPI Panel**:
   * View showing aggregated KPIs (Revenue, costs, churn, and accuracy indicators) with monthly trend cards.
2. **Dataset Management**:
   * Drag-and-drop file upload component demonstrating active schema details, row count, health metrics, and null/duplicate percentages.
3. **Agent Conversational Workspace**:
   * Multi-agent conversation view showing intermediate node execution logs, conversational reasoning steps, and dynamically rendered Recharts charts.
4. **SQL Sandbox Workbench**:
   * Full SQL editor showing query syntax highlight, execution timings (in milliseconds), columns header validation, and scrollable results table.
5. **Machine Learning Forecasting View**:
   * Statistical visualization plot showing actual values vs. forecasted trend line, along with ARIMA model performance metrics.
6. **Executive Reporting Logs**:
   * History of generated PDF/PowerPoint report deliverables showing compile status logs, target emails, and download/delete action buttons.

---

## 🎬 Step-by-Step Demo Script

Follow this narrative arc to showcase the full product value in under 5 minutes:

### Phase 1: Authentication & Data Ingestion
1. **Sign Up & Log In**:
   * Go to `http://localhost:3000` and sign up a new account (or use mock credentials).
2. **Ingest Tabular Data**:
   * Navigate to the **Datasets** view from the side navigation.
   * Drag the sample file `sample_data/sales_data.csv` into the upload zone and click **Upload**.
   * Observe the auto-profiler displaying row statistics, duplicate rows, missing entries, and column types.

### Phase 2: Autonomous Analytics & Chat
3. **Trigger Multi-Agent Query**:
   * Go to the **AI Chat** workspace.
   * Enter the query: `"Compare monthly revenue trends between the North and South regions"` and submit.
   * Observe the agent execution logs expanding: planner parses requirements -> router triggers SQL execution -> generator displays a comparative line chart.

### Phase 3: Machine Learning & Forecasting
4. **Forecast Future Trends**:
   * Navigate to the **Forecasting** page.
   * Select `sales_data.csv` and set the target column to `revenue`.
   * select `prophet` or `arima` as the target model.
   * Click **Execute Forecast** to render the predicted time series graph.

### Phase 4: Executive Compilation
5. **Download PDF Report Brief**:
   * Navigate to **Executive Reports**.
   * Click **Generate Report**, select the PDF template type, enter a title, and queue the background worker.
   * Once status changes to `Completed`, click **Download Report** to open the generated PDF brief showing KPI cards and visualizations.

---

## 📹 GIF Recording Plan

When recording animated showcase GIFs, follow these practices:
* **Resolution**: Keep capture window at `1280x720` (720p) for high text readability and small file size.
* **Recording Length**: Limit individual GIFs to 10–15 seconds to prevent performance lag.
* **Capture Focus**:
  * *GIF 1*: Uploading a dataset and viewing health metrics (5 seconds).
  * *GIF 2*: AI Agent thinking and rendering a dynamic chart (8 seconds).
  * *GIF 3*: Typing and running a query in the SQL workbench (6 seconds).
