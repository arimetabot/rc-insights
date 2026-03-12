"""RC Insights — Streamlit Web Dashboard.

Run: streamlit run app.py
"""

from __future__ import annotations

import html
import os

import streamlit as st

st.set_page_config(
    page_title="RC Insights — Subscription Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .metric-card {
        background: #1a1d27;
        border: 1px solid #2d3148;
        border-radius: 12px;
        padding: 1.25rem;
        text-align: center;
    }
    .health-score {
        font-size: 4rem;
        font-weight: 700;
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .insight-card {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .insight-critical { background: #1a1d27; border-color: #ef4444; }
    .insight-warning { background: #1a1d27; border-color: #eab308; }
    .insight-positive { background: #1a1d27; border-color: #22c55e; }
    .insight-info { background: #1a1d27; border-color: #3b82f6; }
</style>
""", unsafe_allow_html=True)


def main() -> None:
    """Main Streamlit application."""
    st.title("📊 RC Insights")
    st.caption("AI-powered subscription analytics for RevenueCat")

    # --- Sidebar ---
    with st.sidebar:
        st.header("⚙️ Configuration")

        api_key = st.text_input(
            "RevenueCat API Key",
            value=os.getenv("RC_API_KEY", ""),
            type="password",
            help="Your RevenueCat secret API key (sk_...)",
        )
        project_id = st.text_input(
            "Project ID",
            value=os.getenv("RC_PROJECT_ID", ""),
            help="Your RevenueCat project ID (proj...)",
        )
        openai_key = st.text_input(
            "OpenAI API Key (optional)",
            value=os.getenv("OPENAI_API_KEY", ""),
            type="password",
            help="For AI-powered insights. Leave blank for heuristic mode.",
        )

        st.divider()

        days = st.slider("Analysis Period (days)", 7, 90, 30)
        resolution = st.selectbox(
            "Resolution",
            ["day", "week", "month", "quarter", "year"],
            index=0,
        )
        use_ai = st.checkbox("Enable AI Analysis", value=bool(openai_key))

        generate = st.button("🚀 Generate Report", type="primary", use_container_width=True)

    # --- Main Content ---
    if not api_key or not project_id:
        st.info(
            "👋 Welcome to RC Insights! Enter your RevenueCat API key and project ID "
            "in the sidebar to get started."
        )

        # Show demo mode
        st.subheader("How It Works")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("### 1. Connect")
            st.markdown("Enter your RevenueCat API key and project ID.")
        with col2:
            st.markdown("### 2. Analyze")
            st.markdown("We pull all 9 core chart types and run AI analysis.")
        with col3:
            st.markdown("### 3. Act")
            st.markdown("Get actionable insights to grow your subscription business.")

        st.divider()

        st.subheader("Available Charts")
        chart_categories = {
            "💰 Revenue": ["Revenue", "MRR", "MRR Movement"],
            "👥 Subscribers": ["Active Subscriptions", "New Paid Subscriptions", "New Customers", "Active Customers"],
            "📉 Health": ["Churn Rate", "Refund Rate"],
        }

        cols = st.columns(3)
        for idx, (category, charts) in enumerate(chart_categories.items()):
            with cols[idx % 3]:
                st.markdown(f"**{category}**")
                for c in charts:
                    st.markdown(f"- {c}")

        return

    if generate:
        _run_analysis(api_key, project_id, openai_key if use_ai else None, days, resolution)


def _run_analysis(
    api_key: str,
    project_id: str,
    openai_key: str | None,
    days: int,
    resolution: str,
) -> None:
    """Run the full analysis pipeline and display results."""
    from rc_insights.analyzer import SubscriptionAnalyzer
    from rc_insights.models import Resolution

    res_map = {
        "day": Resolution.DAY,
        "week": Resolution.WEEK,
        "month": Resolution.MONTH,
        "quarter": Resolution.QUARTER,
        "year": Resolution.YEAR,
    }
    res = res_map.get(resolution, Resolution.DAY)

    with st.spinner("🔍 Fetching metrics from RevenueCat..."):
        try:
            analyzer = SubscriptionAnalyzer(
                rc_api_key=api_key,
                rc_project_id=project_id,
                openai_api_key=openai_key,
            )
            report = analyzer.generate_report(
                days=days,
                resolution=res,
                include_ai=bool(openai_key),
            )
            analyzer.close()
        except Exception as e:
            st.error(f"❌ Error: {e}")
            return

    # --- Health Score ---
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        score = report.overall_health_score
        if score >= 70:
            color, grade = "#22c55e", "Healthy ✅"
        elif score >= 40:
            color, grade = "#eab308", "Mixed ⚠️"
        else:
            color, grade = "#ef4444", "Critical 🚨"

        st.markdown(
            f'<div style="text-align:center; padding: 2rem;">'
            f'<div class="health-score">{score:.0f}</div>'
            f'<div style="color: {color}; font-size: 1.2rem; font-weight: 600;">{grade}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Progress bar
        st.progress(score / 100)

    st.markdown(
        f'<div style="background: #1a1d27; padding: 1rem; border-radius: 8px; '
        f'border-left: 4px solid #6366f1; margin: 1rem 0;">{html.escape(report.summary)}</div>',
        unsafe_allow_html=True,
    )

    # --- Overview Metrics ---
    if report.overview and report.overview.metrics:
        st.subheader("📋 Key Metrics")
        cols = st.columns(min(len(report.overview.metrics), 4))
        for idx, m in enumerate(report.overview.metrics[:8]):
            with cols[idx % len(cols)]:
                unit = "$" if m.unit == "$" else ""
                suffix = "%" if m.unit == "%" else ""
                st.metric(
                    label=m.name,
                    value=f"{unit}{m.value:,.2f}{suffix}",
                    help=m.description if hasattr(m, "description") else None,
                )

    # --- AI Insights ---
    if report.insights:
        st.subheader("🧠 AI Insights")

        severity_emoji = {"critical": "🔴", "warning": "🟡", "positive": "🟢", "info": "🔵"}

        for insight in report.insights:
            emoji = severity_emoji.get(insight.severity, "·")
            css_class = f"insight-{insight.severity}"
            metric = f" ({insight.metric_value})" if insight.metric_value else ""
            trend = " 📈" if insight.trend == "up" else (" 📉" if insight.trend == "down" else "")

            st.markdown(
                f'<div class="insight-card {css_class}">'
                f'<strong>{emoji} {html.escape(insight.title)}{html.escape(metric)}{trend}</strong><br>'
                f'<span style="color: #8b8fa3;">{html.escape(insight.description)}</span><br>'
                f'<div style="background: #242833; padding: 0.5rem; border-radius: 4px; '
                f'margin-top: 0.5rem; font-size: 0.9rem;">💡 {html.escape(insight.recommendation)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # --- Charts ---
    if report.charts_data:
        st.subheader("📈 Charts")

        try:
            import plotly.graph_objects as go

            tabs = st.tabs(list(report.charts_data.keys()))
            for tab, (_name, chart) in zip(tabs, report.charts_data.items(), strict=False):
                with tab:
                    points = chart.data_points
                    if not points:
                        st.warning("No data available for this chart.")
                        continue

                    dates = [ts for ts, _ in points if ts]
                    values = [v for _, v in points]

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=dates,
                        y=values,
                        mode="lines+markers",
                        name=chart.display_name,
                        line=dict(color="#6366f1", width=2),
                        marker=dict(size=4),
                        fill="tozeroy",
                        fillcolor="rgba(99, 102, 241, 0.1)",
                    ))

                    fig.update_layout(
                        title=chart.display_name,
                        xaxis_title="Date",
                        yaxis_title=chart.yaxis or "Value",
                        template="plotly_dark",
                        paper_bgcolor="#0f1117",
                        plot_bgcolor="#0f1117",
                        height=400,
                        margin=dict(l=40, r=20, t=60, b=40),
                    )

                    st.plotly_chart(fig, use_container_width=True)

        except ImportError:
            st.warning("Install plotly and pandas for interactive charts: pip install plotly pandas")

    # --- Export ---
    st.divider()
    col1, col2 = st.columns(2)

    from rc_insights.report import render_html, render_markdown

    with col1:
        md = render_markdown(report)
        st.download_button(
            "📄 Download Markdown Report",
            md,
            file_name="subscription_health_report.md",
            mime="text/markdown",
        )

    with col2:
        html = render_html(report)
        st.download_button(
            "🌐 Download HTML Report",
            html,
            file_name="subscription_health_report.html",
            mime="text/html",
        )


if __name__ == "__main__":
    main()
