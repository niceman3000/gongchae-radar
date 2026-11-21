"""공채레이더 진입점: ① 내 조건 입력 → ② 맞춤 공고 → ③ 공고 비교 → ④ 공고문에 물어보기.

11-21 저녁 절충안: 구조 개편(화면 2개)을 써 보니 메뉴가 안 보이고 이동이 느려서, 위 메뉴 4개는 오전 구조로 되돌리고
새로 만든 '작년과 달라진 점' 5줄·올해 일정·원문 대조 접기는 '공고 비교' 화면에 남겼다. 화면 이동은 st.switch_page.
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
    st.Page("app/pages/conditions.py", title="내 조건 입력", icon=":material/tune:", default=True),
    st.Page("app/pages/matches.py", title="맞춤 공고", icon=":material/fact_check:"),
    st.Page("app/pages/detail.py", title="공고 비교", icon=":material/compare_arrows:", url_path="detail"),
    st.Page("app/pages/qa.py", title="공고문에 물어보기", icon=":material/forum:"),
]
st.navigation(pages, position="top").run()
