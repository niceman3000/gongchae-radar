# 배포 기록 (Streamlit Community Cloud)

**마지막 갱신**: 2026-11-20 (Claude) · T037

## 공개 주소

- 주소: (배포 후 적기)
- 배포 확인일: (적기)
- 배포한 커밋·태그: (11-22 동결 때 적기)

## 배포 전 점검 (PC, PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pytest -q                     # 전부 통과
.\.venv\Scripts\python.exe tools\check_secrets.py           # 키 노출 0 (키를 넣은 창에서 돌리면 진짜 값까지 검사)
.\.venv\Scripts\python.exe evaluation\evaluate.py --all     # 최종 측정 갱신
git status                                                  # 올릴 것이 다 커밋됐는지
```

배포에 필요한 파일이 Git에 있어야 한다: `streamlit_app.py`, `app/`, `src/`, `data/reports/`, `stage2/bundle_*.json`(질문 기능), `config/`, `data/api/collect_log.json`, `assets/fonts/`, `requirements.txt`

## 1. GitHub에 올리기 (처음 한 번)

1. github.com에서 새 저장소 만들기 (예: `gongchae-radar`). README·.gitignore는 만들지 않음 (이미 있음)
   - 대회 제출용이면 공개(Public). 비공개로 해도 Streamlit Cloud는 GitHub 로그인으로 읽을 수 있음
2. PC에서:
   ```powershell
   git remote add origin https://github.com/<계정>/gongchae-radar.git
   git push -u origin main
   ```
   처음 push할 때 GitHub 로그인 창이 뜬다.
3. GitHub 저장소 화면에서 `.streamlit/secrets.toml`, `.env`가 **없는지** 확인

## 2. Streamlit Community Cloud

1. https://share.streamlit.io 에 GitHub 계정으로 로그인
2. **Create app** → "Deploy a public app from GitHub"
   - Repository: `<계정>/gongchae-radar`, Branch: `main`, Main file path: `streamlit_app.py`
   - App URL: 원하는 이름 (예: `gongchae-radar`)
3. **Advanced settings**
   - Python version: 3.12
   - Secrets 칸에 한 줄 (키 값은 여기만, 채팅·파일에 적지 않음):
     ```toml
     ANTHROPIC_API_KEY = "키"
     ```
4. Deploy → 설치에 몇 분 걸림

키를 넣지 않아도 조건 입력·맞춤 공고·비교·PDF 받기는 된다. 질문은 원문 발췌만 나온다.

## 3. 배포 후 확인 (로그아웃 또는 시크릿 창)

- [ ] 로그인 없이 주소가 열린다
- [ ] 전기 · 부산·울산 · 전기기사 → 맞춤 공고 목록, 판정, 가점이 PC와 같다
- [ ] "결과를 PDF로 받기" → PDF에 한글이 깨지지 않는다
- [ ] 공고 비교 화면에서 한전·한수원·중부발전이 열린다
- [ ] 질문 "토익 몇 점 필요해?" → "AI가 생성한 답변" 표시와 근거 쪽수, "기숙사 제공돼?" → 공고문에 명시 없음
- [ ] 화면·오류 메시지에 키가 보이지 않는다
- [ ] Anthropic 콘솔에 월 사용 한도가 걸려 있다

## 4. 운영 (제출 후)

- 제출(11-23 17:00) 후에는 접속 복구와 키 교체 말고는 바꾸지 않는다
- 앱이 잠들면(오래 접속 없음) 첫 접속에 깨우는 시간이 걸린다 → 심사 기간에는 하루 한 번 열어 둔다
- 키 교체: Streamlit Cloud → 앱 Settings → Secrets 수정 (코드 수정·재배포 필요 없음)
