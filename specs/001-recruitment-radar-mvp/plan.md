# Implementation Plan: 공채레이더 MVP

**Branch**: `001-recruitment-radar-mvp` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-recruitment-radar-mvp/spec.md`

## Summary

기존의 공식 공고 수집, 코드 기반 1차 비교, PDF 관련 쪽 추출, AI 구조화·인용 검증 코드를
재사용한다. 새 구현은 1·2단계 결과를 단일 리포트 계약으로 합치는 배치 처리, 사용자 조건을
규칙으로 판정하는 서비스, 검증된 근거만 사용하는 질문 서비스, 네 화면의 Streamlit 앱에
집중한다. 핵심 리포트는 미리 생성한 JSON 파일로 제공하여 외부 API나 모델 장애 중에도
목록과 변경점 시연이 가능하게 한다.

## Technical Context

**Language/Version**: Python 3.12; 배포 하한은 Python 3.11

**Primary Dependencies**: Streamlit, pdfplumber, jsonschema; 모델 호출은 기존 표준 라이브러리
HTTP 방식을 재사용하고 Claude Sonnet 5.5·Haiku 5.5 모델명은 환경변수로 교체 가능하게 유지

**Storage**: 버전 관리되는 JSON 파일. 원본은 `data/api`, `data/pdf`, 중간 결과는 `results`,
`stage2`, 화면용 통합 결과는 `data/reports`; 데이터베이스 없음

**Testing**: pytest, Streamlit `AppTest`, JSON Schema 계약 검사, PDF 인용문 쪽 일치 검사

**Target Platform**: Streamlit Community Cloud의 공개 웹 앱과 Windows 로컬 개발 환경

**Project Type**: 단일 Python 데이터·AI 웹 애플리케이션과 오프라인 배치 스크립트

**Performance Goals**: 저장된 3개 리포트의 목록·필터·상세 화면은 일반적인 네트워크 환경에서
사용자 조작 후 2초 안에 표시; 자연어 질문은 15초 안에 성공 또는 명확한 오류·대체 문구 표시

**Constraints**: 로그인 없음, 개인 식별 정보 수집 금지, 핵심 화면은 외부 서비스 없이 동작,
모든 확정 변경점은 검증된 쪽수·원문 인용 보유, 비밀값은 환경변수 또는 배포 비밀 저장소,
2026-11-23 17:00 제출 후 기능·프롬프트·데이터 동결

**Scale/Scope**: 3개 기관의 공고 3쌍·총 6개 원문, 전기 직렬 중심의 시연 데이터, 화면 4개,
해커톤 심사·시연 수준의 동시 사용자; 자동 기관 확장은 제외

## Constitution Check

*GATE: Phase 0 시작 전 통과. Phase 1 설계 후 동일 항목을 다시 확인한다.*

| Gate | 판정 | 설계 근거 |
|---|---|---|
| 공식 데이터와 원문 우선 | PASS | 공식 API 원본과 공고문 PDF를 보존하고 리포트가 출처를 참조한다. |
| 코드 우선, AI 최소 사용 | PASS | 수치 비교·조건 판정·검증은 코드, 비정형 추출·문구 분류·질문만 AI를 사용한다. |
| 근거 없는 결과 금지 | PASS | 계약상 확정 변경과 답변은 검증된 Evidence를 요구한다. |
| 사전 계산과 고정 데이터 | PASS | 화면은 `data/reports`의 고정 JSON을 읽고 질문만 선택적으로 실시간 호출한다. |
| 개인정보·비밀·라이선스 보호 | PASS | 개인 식별 입력이 없고 키는 환경변수·비밀 저장소로 제한한다. pdfplumber를 유지한다. |
| 범위와 마감 준수 | PASS | 3쌍·4화면을 MVP로 고정하고 자동 확장은 제외한다. |

## Project Structure

### Documentation (this feature)

```text
specs/001-recruitment-radar-mvp/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── report.schema.json
│   └── qa-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
streamlit_app.py                    # 앱 진입점과 st.navigation 라우팅
app/
├── pages/
│   ├── conditions.py              # ① 직렬·지역·자격증 입력
│   ├── matches.py                 # ② 맞춤 공고와 지원 상태
│   ├── report.py                  # ③ 변경점·근거 상세
│   └── qa.py                      # ④ 근거 질문
└── ui_components.py               # 상태 배지·근거 카드·공통 안내

src/
├── diff_stage1.py                 # 기존: API 텍스트 1차 비교
├── build_bundle.py                # 기존: PDF 관련 쪽·표 추출
├── report_builder.py              # 신규: 1·2단계 결과를 report v1으로 통합
├── report_repository.py           # 신규: 리포트 로드·목록·식별자 조회
├── eligibility.py                 # 신규: 직렬·지역·자격증 규칙 판정
├── evidence.py                    # 신규: 쪽수·인용 검증과 표시 가능 여부 판정
├── qa_service.py                  # 신규: 검증 근거 선택·질문·명시 없음 처리
└── schemas/
    └── report.schema.json         # 실행 시 사용하는 계약 사본

stage2/
└── stage2.py                      # 기존: AI 추출·문구 분류·인용 검증

data/
├── api/                           # 기존 공식 API 원본
├── pdf/                           # 기존 공식 공고문
└── reports/                       # 신규 화면용 report_<pair_id>.json 3개

evaluation/
├── ground_truth/                  # 팀원이 원문으로 만든 정답지
└── evaluate.py                    # 신규 영역별 일치·누락·오류 집계

tests/
├── contract/test_report_schema.py
├── unit/test_evidence.py
├── unit/test_eligibility.py
├── unit/test_report_builder.py
├── unit/test_qa_service.py
└── integration/test_streamlit_flow.py
```

**Structure Decision**: 기존 단일 Python 저장소 구조를 유지한다. `src`에는 데이터 처리와
판정 로직을 두고 `app`에는 표시만 둔다. 화면은 중간 산출물을 직접 읽지 않고
`src/report_repository.py`를 통해 통합 리포트만 읽는다. 별도 백엔드·데이터베이스·프론트엔드
프로젝트는 만들지 않는다.

## Phase 0 Research Result

모든 기술 선택과 대안은 [research.md](research.md)에 기록했다. 미해결 기술 질문은 없다.

## Phase 1 Design Result

- 데이터와 상태 규칙: [data-model.md](data-model.md)
- 통합 리포트 계약: [contracts/report.schema.json](contracts/report.schema.json)
- 근거 질문 계약: [contracts/qa-contract.md](contracts/qa-contract.md)
- 전체 검증 절차: [quickstart.md](quickstart.md)

### Post-Design Constitution Re-check

| Gate | 판정 | 설계 결과 |
|---|---|---|
| 공식 데이터 추적 | PASS | NoticeRef와 Evidence가 원본 공고·쪽수·인용을 보존한다. |
| 결정적 처리 우선 | PASS | ReportBuilder·Eligibility·EvidenceValidator가 코드 경계를 가진다. |
| 확정 결과의 근거 | PASS | `confirmed` 상태는 의미 검증에서 필요한 Evidence가 모두 통과해야 한다. |
| 장애 중 핵심 시연 | PASS | 저장된 리포트 조회와 질문 서비스가 분리되어 있다. |
| 개인정보·비밀 보호 | PASS | 사용자 조건은 세션 범위이며 계약에 개인 식별 필드가 없다. |
| 단순성 | PASS | 단일 Streamlit 앱·파일 저장만 사용하며 별도 API 서버와 DB를 두지 않는다. |

## Complexity Tracking

Constitution 위반이 없으므로 예외 추적 항목은 없다.
