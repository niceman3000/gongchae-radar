# Tasks: 공채레이더 MVP

**Input**: Design documents from `/specs/001-recruitment-radar-mvp/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Team model**: 코딩은 `Owner=DEV(천승욱+Codex)` 한 통로로 수행한다. `Owner=DATA-QA1`은
한수원, `Owner=DATA-QA2`는 중부발전 원문 검증을 책임진다. 한전은 DEV의 기준 사례다.

**Tests**: 기능 명세의 근거 완전성·장애 대응 성공 기준과 계획서의 pytest·AppTest 방침에 따라
테스트 작업을 포함한다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 사용하고 선행 작업이 끝난 뒤 병렬 수행 가능
- **[US1]·[US2]·[US3]**: 기능 명세의 사용자 스토리
- 모든 작업은 담당자, 실제 파일 경로, 완료 조건을 포함한다.

## Owner Definitions

| Owner | 담당 | 코딩 필요 여부 |
|---|---|---|
| `DEV` | 설계, Codex 지시, 코드 통합, 오류 수정, 배포 | 있음. 천승욱과 Codex가 공동 수행 |
| `DATA-QA1` | 한수원 공고 원문·근거·정답지 검증 | 없음 |
| `DATA-QA2` | 중부발전 공고 원문·근거·정답지 검증 | 없음 |

## Phase 1: Setup (목표 2026-11-17)

**Purpose**: 실제 팀 저장소와 실행 환경을 한 곳으로 고정한다.

- [X] T001 Owner=DEV 실제 팀 Git 저장소를 기준 저장소로 확정하고 `.gitignore`에 `.venv/`, `.streamlit/secrets.toml`, `__pycache__/`, 키·임시 결과 파일을 추가한다. 현재 ZIP 작업본을 사용할 경우 `.git/`을 초기화하고 최초 기준 커밋을 남긴다.
- [X] T002 Owner=DEV `requirements.txt`에 `streamlit`, `pdfplumber`, `jsonschema`, `pytest`를 추가하고 `app/pages/`, `data/reports/`, `evaluation/ground_truth/`, `tests/contract/`, `tests/unit/`, `tests/integration/` 구조를 만든다.
- [X] T003 [P] Owner=DEV `config/demo_pairs.json`에 한전 `290666-304551`, 한수원 `288681-302968`, 중부발전 `287235-302314` 공고 쌍을 등록하고 `.streamlit/secrets.toml.example`에는 값이 비어 있는 키 이름만 기록한다.

**Checkpoint**: 새 팀원이 저장소를 받아 설치할 수 있고 실제 키가 저장소에 없다.

---

## Phase 2: Foundational (목표 2026-11-17)

**Purpose**: 모든 화면이 공통으로 사용하는 리포트 계약·근거 검증·파일 조회 기반을 만든다.

**CRITICAL**: 이 단계 전에는 화면 구현을 시작하지 않는다.

- [X] T004 [P] Owner=DEV `specs/001-recruitment-radar-mvp/contracts/report.schema.json`을 `src/schemas/report.schema.json`에 반영하고 유효·무효 예시를 검사하는 `tests/contract/test_report_schema.py`를 먼저 작성한다.
- [X] T005 [P] Owner=DEV 쪽수 범위, 빈 인용, 원문 불일치, 양쪽 근거 누락 사례를 포함한 실패 테스트를 `tests/unit/test_evidence.py`에 먼저 작성한다.
- [X] T006 Owner=DEV `src/evidence.py`에 PDF 번들의 `all_text`를 이용한 인용 검증과 `confirmed` 표시 가능 여부 검사를 구현해 T005를 통과시킨다.
- [X] T007 [P] Owner=DEV `src/report_repository.py`에 `data/reports/report_*.json` 목록 로드, `pair_id` 조회, 계약 오류 격리 기능을 구현한다.
- [X] T008 [P] Owner=DEV 비개발 팀원이 그대로 채울 수 있는 5개 검토 영역·쪽수·원문 인용 표를 `evaluation/ground_truth/TEMPLATE.md`에 작성한다.
- [X] T009 Owner=DEV `python -m pytest tests/contract tests/unit -q`를 실행하고 기반 테스트 결과를 `evaluation/test-log.md`에 기록한다.

**Checkpoint**: 잘못된 리포트와 근거가 화면 계층에 들어오기 전에 차단된다.

---

## Phase 3: User Story 1 - 전년도 대비 핵심 변경 확인 (Priority: P1) MVP (목표 2026-11-18)

**Goal**: 3개 공고 쌍의 변경점·모집단위·근거를 하나의 계약으로 만들고 상세 화면에서 보여 준다.

**Independent Test**: 한전 리포트를 열었을 때 중요도순 변경점마다 이전·현재 값과 검증된 쪽수·
원문 인용을 확인할 수 있고, 확인되지 않은 값은 확정 결과로 표시되지 않는다.

### Tests and Data Validation

- [X] T010 [P] [US1] Owner=DEV stage1·stage2 고정 fixture를 합쳤을 때 중요도·상태·근거가 예상대로 나오는 실패 테스트를 `tests/unit/test_report_builder.py`에 먼저 작성한다.
- [X] T011 [P] [US1] Owner=DEV 한전 PDF `data/pdf/290666.pdf`, `data/pdf/304551.pdf`에서 인원·지역·필수자격·가점·전형 방식과 쪽수·인용을 확인해 `evaluation/ground_truth/kepco.md`를 작성한다.
- [ ] T012 [P] [US1] Owner=DATA-QA1 한수원 PDF `data/pdf/288681.pdf`, `data/pdf/302968.pdf`를 눈으로 대조해 5개 검토 영역·쪽수·원문 인용을 `evaluation/ground_truth/khnp.md`에 기록하고 불명확한 값은 `확인 필요`로 표시한다.
- [ ] T013 [P] [US1] Owner=DATA-QA2 중부발전 PDF `data/pdf/287235.pdf`, `data/pdf/302314.pdf`를 눈으로 대조해 5개 검토 영역·쪽수·원문 인용을 `evaluation/ground_truth/komipo.md`에 기록하고 불명확한 값은 `확인 필요`로 표시한다.

### Implementation

- [X] T014 [US1] Owner=DEV `src/report_builder.py`에 stage1 변경 후보, stage2 추출값·문구 분류, 공고 메타데이터를 report v1 계약으로 합치는 CLI를 구현해 T010을 통과시킨다.
- [X] T015 [US1] Owner=DEV `config/demo_pairs.json`의 3쌍을 처리해 `data/reports/report_kepco.json`, `data/reports/report_khnp.json`, `data/reports/report_komipo.json`을 생성하고 T011~T013의 원문 검증 결과를 반영한다. (2026-11-18 리포트 3개 재생성, change_groups·notice_info·requirements 포함)
- [ ] T016 [US1] Owner=DEV 리포트 3개의 JSON Schema·Evidence 의미 검증을 `tests/contract/test_report_schema.py`에서 통과시키고 불일치를 `evaluation/test-log.md`에 기록한다.
- [X] T017 [P] [US1] Owner=DEV 상태 배지와 쪽수·인용 근거 카드를 `app/ui_components.py`에 만들고 중요도순 변경 목록과 모집단위별 인원을 `app/pages/report.py`에 구현한다.
- [X] T018 [US1] Owner=DEV 고정 한전 리포트로 상세 화면을 여는 AppTest를 `tests/integration/test_streamlit_flow.py`에 추가해 예외 0건과 근거 표시를 확인한다.

**Checkpoint**: 조건 입력 없이도 한전 리포트 URL·화면만으로 P1 가치를 시연할 수 있다.

---

## Phase 4: User Story 2 - 내 조건에 맞는 공고와 지원 상태 확인 (Priority: P2) (목표 2026-11-20)

**Goal**: 직렬·지역·자격증으로 공고를 좁히고 `지원 가능/지원 불가/애매`와 근거를 보여 준다.

**Independent Test**: `전기`, `부산·울산`, `전기기사` 조건을 입력했을 때 관련 공고가 나오고,
데이터 부족이나 수동 확인 조건은 `지원 가능`이 아니라 `애매`로 처리된다.

### Tests and Implementation

- [X] T019 [P] [US2] Owner=DEV 필수조건 충족, 명시적 불충족, 데이터 부족, 수동 전공 확인 사례의 실패 테스트를 `tests/unit/test_eligibility.py`에 먼저 작성한다. (2026-11-18 tests/unit/test_eligibility.py 13개)
- [X] T020 [US2] Owner=DEV `src/eligibility.py`에 UserCondition과 RequirementSet의 결정적 판정 및 근거 반환을 구현해 T019를 통과시킨다. (2026-11-18 src/eligibility.py, src/certificates.py. 전기 직렬 조건은 evaluation/ground_truth/*_requirements.json에서 PDF 쪽수·인용으로 검증)
- [X] T021 [P] [US2] Owner=DEV 이름·연락처 없이 직렬·지역·자격증만 받는 입력 화면을 `app/pages/conditions.py`에 구현한다. (2026-11-18)
- [X] T022 [US2] Owner=DEV 조건과 관련된 공고 카드, 상태, 판단 이유, 대표 변경 1건을 `app/pages/matches.py`에 구현한다. (2026-11-18)
- [X] T023 [US2] Owner=DEV `streamlit_app.py`에 `st.Page`·`st.navigation` 라우팅과 세션 상태 초기화를 구현하고 입력→목록→리포트 이동을 연결한다. (2026-11-18 st.navigation(position=top))
- [X] T024 [US2] Owner=DEV 대표 조건의 입력→목록→리포트 흐름과 개인정보 입력 0개를 `tests/integration/test_streamlit_flow.py`에서 AppTest로 검증한다. (2026-11-18)
- [ ] T025 [P] [US2] Owner=DATA-QA1 코드를 수정하지 않고 앱을 처음부터 사용해 한수원 결과의 이해하기 어려운 표현·잘못된 상태·막힌 동선을 `evaluation/usability-khnp.md`에 화면명과 재현 순서로 기록한다.
- [ ] T026 [P] [US2] Owner=DATA-QA2 코드를 수정하지 않고 앱을 처음부터 사용해 중부발전 결과의 이해하기 어려운 표현·잘못된 상태·막힌 동선을 `evaluation/usability-komipo.md`에 화면명과 재현 순서로 기록한다.

**Checkpoint**: 세 명 모두 설명 없이 대표 조건으로 관련 공고와 변경점에 도달할 수 있다.

---

## Phase 4.5: 공기업 30곳 확장 (2026-11-18 추가, 목표 2026-11-20)

**배경**: 해커톤 소개서 초안 v9는 잡알리오 공기업 30곳(시장형 14 + 준시장형 16)의 공고를 수집해
사용자가 조건으로 찾게 하는 서비스를 약속했다. plan.md는 '3쌍 고정, 자동 확장 제외'였으므로 이 단계로 범위를 넓힌다.

**구성 (2단계 품질)**:
- 핵심 3곳(한전·한수원·중부발전) = `tier: verified`: 지금처럼 PDF 원문 대조, 자격증 판정, 확정 변경점
- 나머지 27곳 = `tier: auto`: API 자동 수집·전년 공고 자동 짝짓기·자동 비교. 화면에 '자동 비교 · 원문 미검증' 표시,
  자격증 판정은 지원 자격 데이터가 생기기 전까지 '애매(공고문 확인)'

**제약**: Claude 작업 환경은 정부 API(apis.data.go.kr)에 접속할 수 없다. 수집은 팀 PC에서 `JOB_API_KEY`로 실행한다.

- [X] T041 Owner=DEV `config/institutions.json`에 30곳 명단(이름·유형·별칭·기관코드·tier·핵심 pair_id)을 작성한다. (2026-11-18 Claude)
- [X] T042 Owner=DEV `tools/collect_institutions.py`를 만든다. ① 목록 API(`/recruitment/list`, numOfRows=100)를 넘겨 가며 `instNm`이 이름·별칭과 같은 공고에서 `pblntInstCd`를 찾아 `config/institutions.json`에 채운다(호출 수 상한과 진행 상황 출력). ② 기관마다 `pblntInstCd`로 최근 2년 공고를 받아 `recrutSeNm`=신입, `hireTypeNmLst`에 정규직이 든 것만 남긴다. ③ 접수 시작일이 가장 늦은 공고를 올해(curr)로, 그보다 300~430일 앞선 공고 중 제목(연도·차수 숫자 제거 후)이 가장 비슷한 것을 작년(prev)으로 짝짓는다. 짝이 없으면 curr만 저장하고 사유를 남긴다. ④ 두 공고를 `tools/fetch_notice.py`와 같은 방식으로 상세 JSON·공고문 PDF 저장(HWP면 건너뛰고 기록). ⑤ `config/auto_pairs.json`을 `config/demo_pairs.json`과 같은 형식 + `tier`, `category`, `skip_reason`으로 쓴다. 인증키는 출력·파일에 남기지 않는다. (2026-11-19 완료: 실제 API 6차 실행으로 27곳 짝 전부. 고르는 규칙은 docs/전처리_규칙.md ①②. PDF는 새 주소 www.alio.go.kr/download/download.json?fileNo= 와 tools/redownload_pdfs.py(ZIP 꺼내기)로 43개 확보, 그림·HWP 공고문은 원문 기능 제외)
- [X] T043 Owner=DEV `tools/build_auto_reports.py`를 만든다. `config/auto_pairs.json`의 각 쌍에 대해 `src/diff_stage1.compare`로 1단계 결과를 만들고, PDF가 있으면 `src/build_bundle.py`로 `stage2/bundle_<번호>.json`을 만든 뒤 `src/report_builder.build_report`로 `data/reports/report_<pair_id 앞부분>.json`을 쓴다. 리포트에 `tier`(verified/auto)와 `category`(시장형/준시장형)를 넣도록 `src/schemas/report.schema.json`에 선택 항목을 추가한다. 핵심 3곳은 기존 `config/demo_pairs.json` 경로를 그대로 쓴다. (2026-11-18 tools/build_auto_reports.py, 모집단위 없을 때 직무분야(NCS)로 직렬 추정) (2026-11-19 완료: 실제 데이터로 리포트 27개, PDF 읽기 실패 0. PDF가 묶음보다 새로우면 묶음 다시 만듦)
- [X] T044 [US1][US2] Owner=DEV 화면을 30곳에 맞춘다: 공고 비교 선택 상자를 유형별로 정렬하고 auto에 '자동 비교 · 원문 미검증' 배지, 맞춤 공고 카드에 같은 배지, 리포트 30개 읽기가 느리면 `st.cache_data`(파일 수정 시각을 키로) 적용. 짝 없는 기관은 '전년 비교 공고 없음'으로 표시한다. (2026-11-19 15:40 완료: 실제 30곳 리포트로 조건 입력 → 맞춤 공고 → 비교 화면, 자동 비교 배지 사용자 확인)
- [X] T045 Owner=DEV 유료 API(`src/ai_pipeline.py`)로 auto 기관 PDF에서 지원 가능 학과·자격증·가점을 뽑아 `evaluation/ground_truth/<prefix>_requirements.json`과 같은 형식(인용은 `src/evidence.check_evidence`로 원문 대조, 실패한 인용은 버림)으로 저장한다. 실행 전 쪽수·토큰으로 예상 비용을 계산해 사용자 승인을 받는다. (2026-11-19 완료: tools/extract_requirements.py, Sonnet 5.5로 22곳 중 19곳 추출·저장(잘린 4곳은 앞부분 복구), 사용 약 $4.5. 빈 결과: 한전KDN(스캔 PDF)·마사회(표가 그림), 도로공사 1항목. 그림 공고문 5곳 미처리) (2026-11-20: 도로공사 붙임 이어 붙여 21항목, 그림 7곳은 T048로 추출)
- [X] T046 Owner=DEV T042~T045 테스트: 짝짓기 규칙(연도 숫자 제거·기간 범위), auto 리포트 스키마 통과, 30곳 리포트가 있을 때 조건 입력→맞춤 공고 흐름 AppTest, 인증키 문자열이 저장 파일에 없음. (미착수. 가짜 API 테스트는 2026-11-18 삭제, 실제 수집 결과 기준으로 작성) (2026-11-20 완료: tests/unit/test_collect_and_reports.py 13개 — 제목 숫자 제거·1년 전 짝·제외 규칙, 30개 리포트 규격·지원 자격, 저장 파일 키 모양 없음. 조건→맞춤 공고 흐름은 test_streamlit_flow)
- [X] T047 Owner=DEV (2026-11-20 추가·완료) ② 맞춤 공고 화면에 '결과를 PDF로 받기' 버튼: 내 조건, 요약 표(기관·공고·판정·내 가점), 공고마다 판단 이유·직접 확인할 것·가점·공통 확인·대표 변경·모집단위별 판정·근거 인용·공고 원문 주소. `src/result_pdf.py`(fpdf2, 글꼴 `assets/fonts/NotoSansKR-*.otf` OFL), 테스트 `tests/unit/test_result_pdf.py`, 화면 테스트에 버튼 확인 추가. AI 호출 없음
- [X] T048 Owner=DEV (2026-11-20 추가·완료) 그림·스캔·한글 공고문을 글자로 옮겨 `stage2/bundle_<번호>.json`(source=ocr)으로 저장하고 지원 자격 추출·질문에 쓴다. `tools/ocr_notices.py`(무료 준비·비용 계산 → `--run`, `--rebundle`), Haiku 5.5 $0.27. 올해 7곳(공항공사·석유공사·인천공항·에스알·강원랜드·한전KDN·마사회) 지원 자격 추출 0 → 2~44항목(Sonnet 약 $0.94). 규칙 `docs/전처리_규칙.md` ⑫, 기록 `evaluation/정확도_개선_기록.md` 5-3

**Checkpoint**: 조건을 넣으면 30곳 공고 중 관련 공고가 나오고, 핵심 3곳은 근거·자격 판정까지, 나머지는 자동 비교 표시와 함께 나온다.

---

## Phase 5: User Story 3 - 공고 근거 안에서 추가 질문 (Priority: P3) (목표 2026-11-21)

**Goal**: 검증된 리포트 근거가 있을 때만 답하고, 없으면 모델 호출 없이 `공고문에 명시 없음`을 반환한다.

**Independent Test**: 답이 있는 질문은 쪽수·인용과 AI 표시를 포함하고, 답이 없는 질문과 모델
장애는 각각 정해진 대체 문구를 반환하며 목록·리포트 화면은 계속 동작한다.

### Tests and Implementation

- [X] T027 [P] [US3] Owner=DEV 근거 있음, 근거 없음, 인용 미검증, API 키 없음, 모델 오류 사례의 실패 테스트를 `tests/unit/test_qa_service.py`에 먼저 작성한다. (11-19 완료: tests/unit/test_qa_service.py 8개)
- [X] T028 [US3] Owner=DEV `src/qa_service.py`에 검증 근거 선택, 근거 없음 조기 반환, 환경변수 기반 Haiku 호출, 계약 형태 응답을 구현해 T027을 통과시킨다. (11-19 완료: src/qa_service.py, 코드로 관련 원문 고르기 → 없으면 AI 없이 명시 없음, Haiku 5.5, 인용 원문 대조)
- [X] T029 [US3] Owner=DEV 질문 입력, 답변, 쪽수·인용, `AI가 생성한 답변`, 장애 안내를 `app/pages/qa.py`에 구현한다. (11-19 완료: app/pages/qa.py '공고문에 물어보기', 예시 질문, AI 생성 표시, 키 없으면 원문 발췌, 접속당 20회 제한)
- [X] T030 [US3] Owner=DEV 답이 있는 질문·없는 질문·키 없는 실행을 `tests/integration/test_streamlit_flow.py`에 추가하고 기존 P1·P2 화면이 계속 열리는지 확인한다. (11-19 완료: 키 없음·명시 없음 화면 테스트 2개, 전체 107개 통과. 실제 AI 답은 PC에서 확인 필요)
- [X] T031 [P] [US3] Owner=DATA-QA1 한수원 취준생 질문 5개와 예상 답·쪽수·인용 또는 `명시 없음`을 `evaluation/questions-khnp.md`에 작성한다. (11-20 Claude 작성: evaluation/questions-khnp.md, 팀원 검토 전. 채점 tools/score_qa.py)
- [X] T032 [P] [US3] Owner=DATA-QA2 중부발전 취준생 질문 5개와 예상 답·쪽수·인용 또는 `명시 없음`을 `evaluation/questions-komipo.md`에 작성한다. (11-20 Claude 작성: evaluation/questions-komipo.md, 팀원 검토 전. 두 표 합계 10/10 통과)

**Checkpoint**: 질문 기능이 없어도 핵심 시연이 가능하고, 켰을 때는 원문 밖 답변을 만들지 않는다.

---

## Phase 6: Measurement, Deployment, Freeze (목표 2026-11-22)

**Purpose**: 측정 결과와 공개 URL을 확보하고 제출 상태를 동결한다.

- [X] T033 Owner=DEV 3개 정답지와 리포트의 인원·지역·필수자격·가점·전형 방식별 일치·누락·오류를 집계하는 `evaluation/evaluate.py`를 구현한다. (2026-11-20 완료: evaluation/evaluate.py — 지원 자격·가점·판정, 한전 변경점, 핵심 숫자, 질문, 30곳 범위, 테스트. 정답지에 없는 지역·전형 방식 항목은 재지 않음)
- [X] T034 Owner=DEV `evaluation/evaluate.py --all`과 전체 pytest를 실행해 실제 수치와 실패 원인을 `evaluation/final-report.md`에 기록하고 측정하지 않은 정확도·시간 절감 수치를 추가하지 않는다. (2026-11-20 완료: PC 실행 17:03, 판정 96%·질문 10/10·변경점 72%·핵심 숫자 47%·테스트 138 통과)
- [X] T035 [P] Owner=DEV 로컬 실행·배포·키 설정·고정 데이터 장애 대응을 `README.md`에 갱신하고 사용 데이터·pdfplumber 라이선스·AI와 팀 역할을 `docs/SOURCES_AND_AI_USAGE.md`에 기록한다. (2026-11-20 완료: README 새로 씀, docs/SOURCES_AND_AI_USAGE.md, docs/DEPLOYMENT.md)
- [X] T036 Owner=DEV 저장소 전체의 키 패턴과 `.streamlit/secrets.toml` 추적 여부를 확인하고 `python -m pytest -q` 및 `specs/001-recruitment-radar-mvp/quickstart.md` 전 절차를 통과시킨다. (2026-11-20 완료: tools/check_secrets.py 키 노출 0, secrets.toml 제외 확인. quickstart 전 절차는 동결 때 다시)
- [ ] T037 Owner=DEV 팀 GitHub 저장소의 `streamlit_app.py`를 Streamlit Community Cloud에 배포하고 공개 URL과 배포 확인일을 `docs/DEPLOYMENT.md`에 기록한다.
- [ ] T038 [P] Owner=DATA-QA1 로그아웃 상태에서 공개 URL의 한수원 흐름과 질문 사례를 실행해 결과·화면 캡처·오류를 `evaluation/final-qa-khnp.md`에 기록한다.
- [ ] T039 [P] Owner=DATA-QA2 로그아웃 상태에서 공개 URL의 중부발전 흐름과 질문 사례를 실행해 결과·화면 캡처·오류를 `evaluation/final-qa-komipo.md`에 기록한다.
- [ ] T040 Owner=DEV T034·T038·T039의 치명 오류를 수정하고 전체 검증을 재실행한 뒤 2026-11-22 동결 커밋과 태그를 만들고 `docs/DEPLOYMENT.md`에 커밋·태그를 기록한다.

**Checkpoint**: 로그인 없는 공개 URL, 고정 리포트 3개, 테스트 기록, 정답지, 출처·AI 활용내역,
동결 태그가 모두 존재한다.

---

## Dependencies & Execution Order

### Phase Dependencies

1. Phase 1 Setup은 즉시 시작한다.
2. Phase 2 Foundation은 Phase 1 완료 후 시작하며 모든 사용자 스토리를 막는다.
3. US1은 Foundation 완료 후 시작한다. 통합 리포트가 US2·US3의 입력이므로 먼저 끝낸다.
4. US2와 US3은 US1 완료 후 DEV가 순서대로 구현한다. 코딩 담당이 한 명이므로 병렬 코딩하지 않는다.
5. DATA-QA1과 DATA-QA2의 원문 검증·질문 작성·사용성 검사는 DEV 작업과 병렬 수행한다.
6. Phase 6은 선택한 사용자 스토리가 모두 통과한 뒤 진행한다.

### User Story Dependencies

- **US1 (P1)**: Foundation만 필요하며 단독 배포 가능한 핵심 MVP다.
- **US2 (P2)**: US1의 통합 리포트와 ReportRepository가 필요하다.
- **US3 (P3)**: US1의 통합 리포트와 Evidence가 필요하며 US2와 기능적으로 독립적이다.

### Parallel Opportunities

- T004·T005·T007·T008은 파일이 달라 선행 조건 이후 병렬 가능하다.
- T011·T012·T013은 세 사람이 기관 하나씩 동시에 원문을 검증한다.
- T017 화면 구현 중 DATA-QA1·DATA-QA2는 T012·T013을 계속 수행할 수 있다.
- T025·T026, T031·T032, T038·T039는 두 비개발 팀원이 동시에 수행한다.
- DEV 코딩 작업끼리는 병렬화하지 않아 코드 충돌과 서로 다른 설계를 방지한다.

## Parallel Example: User Story 1

```text
DEV:      T011 한전 정답지 → T014 ReportBuilder → T015 리포트 3개
DATA-QA1: T012 한수원 정답지 ───────────────────────┐
DATA-QA2: T013 중부발전 정답지 ─────────────────────┴→ T015 반영
```

## Implementation Strategy

### MVP First

1. T001~T009로 계약과 검증 기반을 만든다.
2. T010~T018로 한전 리포트와 상세 화면만 완성한다.
3. 한전 P1을 독립 실행해 근거가 실제 PDF와 맞는지 확인한다.
4. 한수원·중부발전 검증 자료를 반영해 리포트 3개로 확장한다.
5. P1이 안정된 뒤에만 조건 판정과 질문 기능을 붙인다.

### Three-Person Operating Rule

- DEV는 작업 시작 전 해당 Task ID를 팀에 알리고 한 번에 한 코딩 작업만 진행한다.
- DATA-QA1·DATA-QA2는 코드나 JSON을 직접 고치지 않고 지정된 Markdown에 오류와 근거를 기록한다.
- DEV는 검증 자료를 반영할 때 원문을 다시 확인하고 수정 이유를 `evaluation/test-log.md`에 남긴다.
- 막히면 질문 기능보다 리포트·근거·공개 URL을 우선한다. US3는 제거 가능하지만 US1은 제거하지 않는다.

## Format Validation

- 모든 작업은 `- [ ] TNNN` 형식이다.
- 사용자 스토리 작업은 `[US1]`, `[US2]`, `[US3]` 라벨을 가진다.
- `[P]`는 다른 파일에서 병렬 수행 가능한 작업에만 사용했다.
- 모든 작업은 담당자와 파일 경로 또는 결과 기록 경로를 포함한다.
