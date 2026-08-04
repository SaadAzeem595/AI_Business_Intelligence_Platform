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
