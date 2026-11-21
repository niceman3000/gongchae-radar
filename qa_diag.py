# 질문 화면 시험이 PC에서만 실패하는 이유 확인용 (AI 호출 없음, 키 안 읽음)
import os, sys
from pathlib import Path
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ["GONGCHAE_IGNORE_SECRETS"] = "1"
from streamlit.testing.v1 import AppTest
app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
app.session_state["selected_pair_id"] = "kepco-2025-2026-h2"
app = app.switch_page("app/pages/qa.py").run()
print("exception:", [e.value for e in app.exception])
print("selectbox:", [s.value for s in app.selectbox])
app.text_input(key="qa_question").set_value("토익 몇 점 필요해?")
print("buttons:", [b.label for b in app.button])
[b for b in app.button if b.label == "물어보기"][0].click().run()
print("exception:", [e.value for e in app.exception])
for name in ("warning", "info", "error", "markdown", "caption"):
    print(name, ":", [str(x.value)[:120] for x in getattr(app, name)])
