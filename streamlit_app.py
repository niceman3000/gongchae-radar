"""공채레이더 로컬 실행 진입점."""

import streamlit as st

from app.pages.report import render_report_page


st.set_page_config(
    page_title="공채레이더",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_report_page()
