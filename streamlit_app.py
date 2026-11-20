"""공채레이더 로컬 실행 진입점: ① 내 조건 입력 → ② 맞춤 공고 → ③ 공고 비교 → ④ 공고문에 물어보기."""

import sys

import streamlit as st

# 실행할 때마다 프로젝트 코드(app·src)를 새로 불러온다.
# Streamlit은 화면이 닫혀 있을 때 바뀐 파일을 놓치고 예전 코드를 계속 쓰는 경우가 있어서
# (2026-11-18 확인), Claude·Codex가 번갈아 고쳐도 껐다 켜지 않게 한다.
for _name in [name for name in sys.modules if name.split(".")[0] in {"app", "src"}]:
    del sys.modules[_name]


st.set_page_config(
    page_title="공채레이더",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

pages = [
    st.Page("app/pages/conditions.py", title="내 조건 입력", icon="📝", default=True),
    st.Page("app/pages/matches.py", title="맞춤 공고", icon="🔎"),
    st.Page("app/pages/report.py", title="공고 비교", icon="📊"),
    st.Page("app/pages/qa.py", title="공고문에 물어보기", icon="💬"),
]
st.navigation(pages, position="top").run()
