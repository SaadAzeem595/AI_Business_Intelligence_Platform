import os
import matplotlib
matplotlib.use('Agg')  # Ensure non-interactive backend is used
import matplotlib.pyplot as plt

class DashboardSnapshotGenerator:
    """Generates charts, cards, and combined snapshots of analytical dashboards using matplotlib."""

    @staticmethod
    def generate_kpi_card(title: str, value: str, change: str, filepath: str) -> str:
        """Generates a clean standalone KPI card image."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        fig, ax = plt.subplots(figsize=(3, 1.8))
        fig.patch.set_facecolor('#f8fafc')
        ax.set_facecolor('#ffffff')
        
        # Draw border
        rect = plt.Rectangle((0, 0), 1, 1, facecolor='#ffffff', edgecolor='#e2e8f0', transform=ax.transAxes)
        ax.add_patch(rect)
        ax.axis('off')
        
        # Text alignment
        ax.text(0.1, 0.7, title, fontsize=10, color='#64748b', fontweight='bold', transform=ax.transAxes)
        ax.text(0.1, 0.35, value, fontsize=20, color='#0f172a', fontweight='bold', transform=ax.transAxes)
        
        # Change indicator color
        is_positive = not change.startswith('-') and not change.startswith('0')
        change_color = '#10b981' if is_positive else '#ef4444'
        ax.text(0.1, 0.12, change, fontsize=9, color=change_color, fontweight='bold', transform=ax.transAxes)
        
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return filepath

    @staticmethod
    def generate_trend_chart(title: str, labels: list, values: list, filepath: str, chart_type: str = 'line', color: str = '#3b82f6') -> str:
        """Generates a standalone line or bar trend chart."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        fig, ax = plt.subplots(figsize=(6, 3.5))
        fig.patch.set_facecolor('#ffffff')
        ax.set_facecolor('#ffffff')
        
        if chart_type == 'bar':
            ax.bar(labels, values, color=color, width=0.5, edgecolor='none')
        else:
            ax.plot(labels, values, color=color, marker='o', linewidth=2, markersize=5)
            
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.tick_params(colors='#64748b', labelsize=9)
        ax.grid(axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
        ax.set_title(title, fontsize=11, color='#0f172a', fontweight='bold', pad=10)
        
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return filepath

    @staticmethod
    def generate_dashboard_snapshot(kpis: list, chart_data: dict, filepath: str) -> str:
        """Combines multiple KPI cards and a main trend chart into a single high-quality snapshot image."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        fig = plt.figure(figsize=(10, 6), facecolor='#f8fafc')
        
        # Grid layout: 2 rows. Row 0 has KPI cards. Row 1 has the chart.
        num_kpis = len(kpis)
        gs = fig.add_gridspec(2, num_kpis, height_ratios=[1, 2], hspace=0.3, wspace=0.15)
        
        # 1. Draw KPI cards in the top row
        for i, kpi in enumerate(kpis):
            ax = fig.add_subplot(gs[0, i])
            ax.set_facecolor('#ffffff')
            # Outer boundary card border
            rect = plt.Rectangle((0, 0), 1, 1, facecolor='#ffffff', edgecolor='#e2e8f0', transform=ax.transAxes)
            ax.add_patch(rect)
            ax.axis('off')
            
            ax.text(0.1, 0.7, kpi.get('title', ''), fontsize=9, color='#64748b', fontweight='bold', transform=ax.transAxes)
            ax.text(0.1, 0.35, kpi.get('value', ''), fontsize=18, color='#0f172a', fontweight='bold', transform=ax.transAxes)
            
            change = kpi.get('change', '')
            is_positive = not change.startswith('-') and not change.startswith('0')
            change_color = '#10b981' if is_positive else '#ef4444'
            ax.text(0.1, 0.12, change, fontsize=9, color=change_color, fontweight='bold', transform=ax.transAxes)
            
        # 2. Draw Trend Chart in the bottom row
        ax_chart = fig.add_subplot(gs[1, :])
        ax_chart.set_facecolor('#ffffff')
        
        labels = chart_data.get('labels', [])
        values = chart_data.get('values', [])
        chart_type = chart_data.get('type', 'line')
        color = chart_data.get('color', '#3b82f6')
        
        if chart_type == 'bar':
            ax_chart.bar(labels, values, color=color, width=0.5)
        else:
            ax_chart.plot(labels, values, color=color, marker='o', linewidth=2, markersize=5)
            
        ax_chart.spines['top'].set_visible(False)
        ax_chart.spines['right'].set_visible(False)
        ax_chart.spines['left'].set_color('#cbd5e1')
        ax_chart.spines['bottom'].set_color('#cbd5e1')
        ax_chart.tick_params(colors='#64748b', labelsize=9)
        ax_chart.grid(axis='y', linestyle='--', alpha=0.5, color='#cbd5e1')
        ax_chart.set_title(chart_data.get('title', 'Historical Performance Trend'), fontsize=12, color='#0f172a', fontweight='bold', pad=10)
        
        # Leave padding
        plt.subplots_adjust(left=0.08, right=0.92, top=0.9, bottom=0.1)
        plt.savefig(filepath, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return filepath

    @staticmethod
    def generate_forecast_chart(
        historical_points: list,
        forecast_points: list,
        filepath: str,
        title: str = "Predictive Revenue Forecast (ARIMA)",
        confidence_available: bool = True
    ) -> str:
        """
        Generates an enterprise-grade time-series forecasting chart:
        - Historical Actual line with markers
        - Projected Forecast line with distinct markers & styling
        - Shaded 95% Confidence Interval band (when available)
        """
        import matplotlib.ticker as ticker

        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        fig, ax = plt.subplots(figsize=(9, 4.2), facecolor='#ffffff')
        ax.set_facecolor('#ffffff')

        hist_dates = []
        hist_vals = []
        for p in historical_points:
            d = p.get("date", "") if isinstance(p, dict) else getattr(p, "date", "")
            v = p.get("actual") if isinstance(p, dict) else getattr(p, "actual", None)
            if v is None:
                v = p.get("value") if isinstance(p, dict) else getattr(p, "value", None)
            if v is not None:
                hist_dates.append(str(d)[:10])
                hist_vals.append(float(v))

        fc_dates = []
        fc_vals = []
        lower_vals = []
        upper_vals = []
        for p in forecast_points:
            d = p.get("date", "") if isinstance(p, dict) else getattr(p, "date", "")
            v = p.get("forecast") if isinstance(p, dict) else getattr(p, "forecast", None)
            if v is None:
                v = p.get("predicted", p.get("value")) if isinstance(p, dict) else getattr(p, "predicted", getattr(p, "value", None))
            low = p.get("lower") if isinstance(p, dict) else getattr(p, "lower", None)
            upp = p.get("upper") if isinstance(p, dict) else getattr(p, "upper", None)

            if v is not None:
                fc_dates.append(str(d)[:10])
                fc_vals.append(float(v))
                lower_vals.append(float(low) if low is not None else float(v))
                upper_vals.append(float(upp) if upp is not None else float(v))

        all_dates = hist_dates + fc_dates
        x_indices = list(range(len(all_dates)))
        hist_x = x_indices[:len(hist_dates)]
        fc_x = x_indices[len(hist_dates):]

        # Connect last historical point to first forecast point for visual continuity
        if hist_x and fc_x:
            connect_x = [hist_x[-1]] + fc_x
            connect_y = [hist_vals[-1]] + fc_vals
        else:
            connect_x = fc_x
            connect_y = fc_vals

        # 1. Plot Historical Actuals
        if hist_x:
            ax.plot(
                hist_x, hist_vals,
                color='#0f172a',
                marker='o',
                linewidth=2.2,
                markersize=4.5,
                label='Historical Actual Revenue',
                zorder=4
            )

        # 2. Plot Forecast Projections
        if connect_x:
            ax.plot(
                connect_x, connect_y,
                color='#2563eb',
                linestyle='--',
                linewidth=2.2,
                marker='s',
                markersize=5,
                label='Forecast Projection',
                zorder=4
            )

        # 3. Plot Confidence Interval Band if available
        has_ci = (
            confidence_available and
            len(lower_vals) > 0 and
            len(upper_vals) > 0 and
            any(u > l for l, u in zip(lower_vals, upper_vals))
        )
        if has_ci and fc_x:
            # Connect confidence band smoothly from last historical point
            if hist_x:
                band_x = [hist_x[-1]] + fc_x
                band_low = [hist_vals[-1]] + lower_vals
                band_upp = [hist_vals[-1]] + upper_vals
            else:
                band_x = fc_x
                band_low = lower_vals
                band_upp = upper_vals

            ax.fill_between(
                band_x, band_low, band_upp,
                color='#93c5fd',
                alpha=0.35,
                label='95% Confidence Interval',
                zorder=2
            )

        # Formatting axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#cbd5e1')
        ax.spines['bottom'].set_color('#cbd5e1')
        ax.grid(axis='y', linestyle='--', alpha=0.5, color='#e2e8f0')

        # Tick frequency and labels
        step = max(1, len(all_dates) // 10)
        tick_pos = list(range(0, len(all_dates), step))
        if (len(all_dates) - 1) not in tick_pos:
            tick_pos.append(len(all_dates) - 1)
        ax.set_xticks(tick_pos)
        ax.set_xticklabels([all_dates[i] for i in tick_pos], rotation=30, ha='right', fontsize=8.5, color='#475569')

        # Format Y axis as currency
        def currency_formatter(x, pos):
            if abs(x) >= 1_000_000:
                return f"${x*1e-6:.1f}M"
            elif abs(x) >= 1_000:
                return f"${x*1e-3:.0f}K"
            else:
                return f"${x:.0f}"

        ax.yaxis.set_major_formatter(ticker.FuncFormatter(currency_formatter))
        ax.tick_params(colors='#475569', labelsize=8.5)

        ax.set_title(title, fontsize=12, color='#0f172a', fontweight='bold', pad=12)
        ax.legend(loc='upper left', frameon=True, facecolor='#f8fafc', edgecolor='#e2e8f0', fontsize=8.5)

        if not has_ci:
            ax.text(
                0.98, 0.04,
                "Confidence interval not available from the selected forecasting model.",
                transform=ax.transAxes,
                fontsize=7.5,
                color='#64748b',
                fontstyle='italic',
                ha='right',
                va='bottom',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='#f1f5f9', edgecolor='#cbd5e1', alpha=0.8)
            )

        plt.subplots_adjust(left=0.10, right=0.95, top=0.88, bottom=0.20)
        plt.savefig(filepath, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        return filepath

