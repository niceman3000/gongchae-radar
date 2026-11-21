"""공채레이더 진입점: 화면 1 공고 목록(조건 입력 + 결과) → 화면 2 공고 상세(판정·달라진 점·일정·질문·원문 대조).

11-21 구조 개편: 기능별 메뉴 4개(입력·맞춤·비교·질문) → 화면 2개. 위쪽 메뉴는 화면 안의 '공채레이더 / 공고 찾기'.
"""

import os
import sys

import streamlit as st

# PC 개발용(run_streamlit.bat이 GONGCHAE_DEV=1을 켬): 실행할 때마다 프로젝트 코드(app·src)를 새로 불러온다.
# Streamlit은 화면이 닫혀 있을 때 바뀐 파일을 놓치고 예전 코드를 계속 쓰는 경우가 있어서
# (2026-11-18 확인), Claude·Codex가 번갈아 고쳐도 껐다 켜지 않게 한다.
# 배포 서버에서는 끈다 (11-20 Streamlit Cloud Python 3.14: 지운 모듈을 다시 읽다가 dataclass 오류로 '공고 찾기'가 멈춤)
if os.environ.get("GONGCHAE_DEV") == "1":
    for _name in [name for name in sys.modules if name.split(".")[0] in {"app", "src"}]:
        del sys.modules[_name]


st.set_page_config(
    page_title="공채레이더",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

pages = [
    st.Page("app/pages/search.py", title="공고 찾기", icon=":material/search:", default=True),
    st.Page("app/pages/detail.py", title="공고 상세", icon=":material/description:", url_path="detail"),
]
st.navigation(pages, position="hidden").run()
