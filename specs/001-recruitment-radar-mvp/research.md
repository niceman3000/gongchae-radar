# Research: 공채레이더 MVP

## Decision 1: Streamlit 단일 앱과 공식 다중 페이지 방식

- **Decision**: Python 기반 Streamlit 앱을 사용하고 `st.Page`와 `st.navigation`으로 네 화면을
  구성한다. 직렬·지역·자격증과 선택 공고는 세션 상태로 페이지 사이에 전달한다.
- **Rationale**: 기존 데이터 파이프라인이 Python이고 마감까지 별도 웹 프론트엔드와 API 서버를
  구축할 필요가 없다. Streamlit은 새 앱에 `st.Page`·`st.navigation`을 권장하고 다중 페이지에서
  세션 상태를 유지할 수 있다.
- **Alternatives considered**: React와 FastAPI는 UI 자유도는 높지만 프로젝트 두 개와 배포 지점이
  생긴다. Gradio는 대화형 AI에는 편하지만 공고 목록·필터·근거 리포트의 네 화면 흐름에는 덜 맞다.
- **Source**: https://docs.streamlit.io/develop/concepts/multipage-apps/overview

## Decision 2: 통합 JSON을 유일한 화면 데이터 계약으로 사용

- **Decision**: 배치 결과를 `report.schema.json`에 맞춘 3개의 통합 리포트로 만들고 화면은 이
  파일만 읽는다. 데이터베이스는 사용하지 않는다.
- **Rationale**: 데이터가 3쌍으로 작고 제출 후 동결해야 하므로 검색·갱신용 DB보다 파일 계약이
  단순하고 재현하기 쉽다. 외부 API·모델 장애와 관계없이 핵심 시연도 가능하다.
- **Alternatives considered**: SQLite는 향후 다수 기관 검색에는 유용하지만 현재 범위에서는
  마이그레이션과 동기화만 추가한다. 화면이 stage1·stage2 중간 파일을 직접 읽으면 형식 변경이
  UI 전체에 전파되므로 제외한다.

## Decision 3: 코드 판정과 AI 판정의 경계를 분리

- **Decision**: 숫자·날짜·목록 비교, 지원 상태, 인용문 일치는 코드가 처리한다. AI는 PDF 비정형
  구조화, 문구의 실질·표현 분류, 검증된 근거를 바탕으로 한 답변만 처리한다.
- **Rationale**: 같은 입력의 결과를 재현하고, 근거가 없을 때 확정적으로 중단할 수 있다.
- **Alternatives considered**: 공고 전체를 한 번에 모델에 보내 비교시키는 방식은 구현은 짧지만
  누락·환각을 항목별로 검증하기 어렵고 매 실행 결과가 달라질 수 있다.

## Decision 4: 기존 Claude 모델 구성 유지

- **Decision**: PDF 구조화에는 `claude-sonnet-5-5`, 문구 분류와 짧은 근거 질문에는
  `claude-haiku-5-5`를 기본으로 사용하되 환경변수로 교체할 수 있게 한다.
- **Rationale**: 기존 코드와 가이드의 역할 분리가 이미 구현되어 있고 두 모델 ID는 현재 공식
  모델 목록에 포함된다. 모델명을 코드 여러 곳에 반복하지 않고 실행 환경에서 고정한다.
- **Alternatives considered**: 모델 공급자 변경은 현재 결과와 프롬프트를 다시 검증해야 하므로
  마감 전에는 하지 않는다. 모든 작업에 상위 모델을 쓰는 것은 분류·짧은 답변 비용 대비 이점이 작다.
- **Source**: https://platform.claude.com/docs/en/models/overview

## Decision 5: 근거 우선 질문 처리

- **Decision**: 질문에서 관련된 검증 근거를 먼저 선택하고, 관련 근거가 없으면 모델 호출 없이
  `공고문에 명시 없음`을 반환한다. 모델 입력에는 선택 공고의 검증된 인용과 질문만 포함한다.
- **Rationale**: 원문 밖 지식 유입을 줄이고 답변의 쪽수·인용을 그대로 사용자에게 돌려줄 수 있다.
- **Alternatives considered**: 공고 PDF 전체 전송은 비용과 지연이 크고, 일반 웹검색 결합은 공식
  공고 근거만 사용한다는 서비스 약속을 깨므로 제외한다.

## Decision 6: 계약·로직·화면을 분리해 테스트

- **Decision**: JSON Schema 계약 검사, 인용 검증, 조건 판정, 리포트 통합은 pytest 단위·계약
  테스트로 확인한다. 네 화면의 핵심 흐름은 Streamlit `AppTest`로 브라우저 없이 검사한다.
- **Rationale**: 로직 오류와 화면 오류를 분리해 마감 직전 수정 범위를 줄일 수 있다. Streamlit은
  `AppTest`와 pytest를 이용한 다중 페이지 테스트를 공식 지원한다.
- **Alternatives considered**: 수동 시연만으로 확인하면 같은 입력의 회귀 오류를 놓칠 수 있다.
  Selenium·Playwright는 현재 UI 범위에 비해 설정이 무겁다.
- **Source**: https://docs.streamlit.io/develop/concepts/app-testing

## Decision 7: Community Cloud 배포와 비밀값 분리

- **Decision**: GitHub 저장소의 `streamlit_app.py`를 Community Cloud에 배포한다. 로컬 비밀 파일은
  저장소에서 제외하고 배포 키는 플랫폼의 Secrets 설정에 넣는다.
- **Rationale**: 로그인 없는 공유 URL을 빠르게 만들 수 있고 별도 서버 관리가 필요 없다.
- **Alternatives considered**: 로컬 터널은 심사 기간 안정성이 낮고, 범용 클라우드 VM은 운영 부담이 크다.
- **Source**: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

## Resolved Unknowns

- 화면 스택: Streamlit
- 앱 상태 전달: 세션 상태
- 저장소: JSON 파일
- 데이터베이스: 사용하지 않음
- 핵심 장애 대응: 사전 생성 리포트 열람 유지
- 테스트: pytest + JSON Schema + Streamlit AppTest
- 배포: Streamlit Community Cloud
- 모델: 기존 Sonnet 5.5/Haiku 5.5 역할 분리 유지
