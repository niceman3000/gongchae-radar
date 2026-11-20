# Quickstart Validation: 공채레이더 MVP

이 문서는 구현 완료 후 공채레이더의 배치 결과와 네 화면을 처음부터 검증하는 절차다.

## 1. Prerequisites

- Python 3.11 이상
- 프로젝트 루트에서 실행
- 이미 확보한 공식 공고 JSON 6개와 PDF 6개
- AI 추출을 다시 실행할 때만 `ANTHROPIC_API_KEY`
- 공식 데이터를 다시 받을 때만 `JOB_API_KEY`

키는 환경변수 또는 Streamlit 배포 Secrets로만 설정한다. 명령 기록, 소스, JSON 결과에 키를
복사하지 않는다.

## 2. Install

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Expected: Streamlit, pdfplumber, jsonschema, pytest가 오류 없이 설치된다.

## 3. Build the frozen reports

기존 `docs/초기_개발가이드.md`(11-16 첫날 가이드)의 Step 3~5를 실행해 공고 쌍별 stage1·stage2 결과를 준비한 뒤 통합한다.

```powershell
.\.venv\Scripts\python.exe src\report_builder.py --all-demo-pairs
```

Expected:

- `data/reports/`에 한전·한수원·중부발전 리포트 3개가 생성된다.
- 각 파일은 `schema_version=1.0.0`이다.
- 계약 검사와 의미 검증을 모두 통과한다.
- 확인되지 않은 인용이 있으면 성공으로 종료하지 않고 해당 change가 `review_required`가 된다.

## 4. Validate contracts and evidence

```powershell
.\.venv\Scripts\python.exe -m pytest tests\contract tests\unit -q
```

Expected:

- 리포트 3개 모두 JSON Schema를 통과한다.
- `confirmed` 변경점은 필요한 쪽의 검증 근거를 가진다.
- 근거가 없거나 수동 확인 조건이 있으면 지원 상태가 `애매`다.
- 근거가 없는 질문은 모델 호출 없이 `공고문에 명시 없음`이다.

## 5. Run locally

```powershell
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

Expected flow:

1. `전기`, `부산·울산`, `전기기사` 조건을 선택한다.
2. 맞춤 목록에서 공고 카드와 `지원 가능/지원 불가/애매` 상태를 확인한다.
3. 한전 리포트를 열어 중요도순 변경점과 전년도·당해 연도 근거를 확인한다.
4. 근거가 있는 질문과 없는 질문을 각각 입력해 답변 계약을 확인한다.

## 6. Run the four-screen smoke test

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_streamlit_flow.py -q
```

Expected: 앱 예외가 없고 조건 입력, 목록, 리포트, 질문 화면이 고정 리포트로 열린다.

## 7. Evaluate against team ground truth

```powershell
.\.venv\Scripts\python.exe evaluation\evaluate.py --all
```

Expected: 기관별로 인원·지역·필수자격·가점·전형 방식의 일치, 누락, 오류 건수를 출력한다.
측정 결과는 그대로 기록하며 목표에 맞추기 위해 정답지나 결과를 임의 수정하지 않는다.

## 8. Deployment check

Community Cloud에서 GitHub 저장소, 브랜치, `streamlit_app.py`를 선택한다. 질문 기능을 사용할
경우에만 Secrets에 모델 키를 등록한다. 배포 후 로그아웃 또는 시크릿 브라우저에서 다음을 확인한다.

- 로그인 없이 URL 접속 가능
- 외부 모델 키가 없어도 목록·리포트 열람 가능
- 화면이나 로그에 키가 노출되지 않음
- 공고 3쌍과 근거가 로컬 결과와 동일함
- 질문 답변에 AI 생성 표시가 있음

## 9. Freeze

2026-11-22에 전체 검증을 한 번 더 실행하고 데이터·프롬프트·코드 버전을 기록한다.
2026-11-23 17:00 제출 후에는 접속 복구와 키 교체를 제외한 변경을 하지 않는다.
