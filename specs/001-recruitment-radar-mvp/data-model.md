# Data Model: 공채레이더 MVP

## 1. NoticeRef

비교에 사용된 공식 채용공고 한 건을 나타낸다.

| Field | Type | Rule |
|---|---|---|
| `sn` | string | 공식 공고 식별값. 빈 문자열 금지 |
| `title` | string | 공식 공고 제목 |
| `period.start` | string | `YYYYMMDD` 형식 또는 원문 값 |
| `period.end` | string | `YYYYMMDD` 형식 또는 원문 값 |
| `pdf_path` | string | 저장소 내 공식 공고문 경로 |
| `source_url` | string/null | 공식 원문 URL. 확인하지 못했으면 null |

관계: Report 하나는 `prev`, `curr` 두 NoticeRef를 반드시 가진다.

## 2. Evidence

화면에 표시하는 사실을 공식 공고문에서 추적하기 위한 근거다.

| Field | Type | Rule |
|---|---|---|
| `side` | enum | `prev` 또는 `curr` |
| `notice_sn` | string | 해당 NoticeRef의 `sn`과 일치 |
| `page` | integer | 1 이상 |
| `quote` | string | 빈 문자열 금지, 해당 쪽의 추출 텍스트에 존재 |
| `verified` | boolean | 코드로 쪽수·인용 일치를 확인한 경우에만 true |

검증 규칙:

- `status=confirmed`인 Change는 최소 1개의 `verified=true` Evidence를 가져야 한다.
- `prev_value`와 `curr_value`가 모두 있으면 양쪽 값을 뒷받침하는 prev·curr Evidence를 각각 가져야 한다.
- 검증에 실패한 Evidence는 삭제하지 않고 검토 기록으로 남길 수 있지만 확정 결과에는 사용할 수 없다.

## 3. Change

전년도와 당해 연도 사이의 비교 결과 한 건이다.

| Field | Type | Rule |
|---|---|---|
| `id` | string | 리포트 안에서 유일 |
| `importance` | integer | 1 핵심 숫자, 2 실질 항목, 3 낮은 우선순위 |
| `category` | string | 인원, 지역, 자격, 가점, 서류, 필기, 면접, 일정, 기타 |
| `title` | string | 사용자에게 보여 줄 한 줄 요약 |
| `change_type` | enum | `number`, `added`, `removed`, `list`, `text`, `rename`, `date` |
| `prev_value` | string/number/null | 전년도 내용. 없으면 null |
| `curr_value` | string/number/null | 당해 연도 내용. 없으면 null |
| `source` | enum | `stage1`, `stage2`, `merged` |
| `ai_label` | enum/null | `실질 변경`, `표현 변경`, null |
| `confidence` | enum | `high`, `low`, `not_applicable` |
| `status` | enum | `confirmed`, `review_required`, `not_published` |
| `affected_units` | string[] | 영향받는 모집단위. 전체면 빈 배열 허용 |
| `evidence` | Evidence[] | 확정 상태는 Evidence 규칙 충족 필수 |

상태 전이:

`candidate -> review_required -> confirmed`

- 배치 입력의 변경 후보는 계약에 저장하기 전에 `review_required` 또는 `confirmed`가 된다.
- 근거 검증을 통과하지 못하면 `confirmed`로 전환할 수 없다.
- 기관이 값을 공개하지 않은 경우 `not_published`로 종료한다.

## 4. RecruitmentUnit

실제 지원 단위별 인원과 조건을 나타낸다.

| Field | Type | Rule |
|---|---|---|
| `unit_name` | string | 공고에 적힌 이름 |
| `normalized_name` | string | 연도 비교용 이름, 원문 이름을 대체하지 않음 |
| `track` | string | 전기, 기계, 사무 등 |
| `headcount_prev` | integer/null | 미공시면 null |
| `headcount_curr` | integer/null | 미공시면 null |
| `by_region` | RegionHeadcount[] | 지역별 이전·현재 인원과 근거 |
| `evidence` | Evidence[] | 인원과 모집단위를 뒷받침하는 근거 |

## 5. RequirementSet

지원 상태를 판정할 때 사용하는 명시적 조건이다.

| Field | Type | Rule |
|---|---|---|
| `tracks` | string[] | 공고가 모집하는 직렬 |
| `regions` | string[] | 선택 가능한 지역. 전국은 `전국`으로 표준화 |
| `certificates` | RequirementItem[] | 필수·선택·가점 자격증 구분 |
| `majors` | RequirementItem[] | 인정 전공. 완전한 목록이 아니면 검토 조건 표시 |
| `manual_review_conditions` | string[] | 코드가 확정할 수 없는 조건 |

## 6. UserCondition

한 브라우저 세션에서만 사용하는 필터 조건이다.

| Field | Type | Rule |
|---|---|---|
| `track` | string | 필수 |
| `region` | string | 필수 |
| `certificates` | string[] | 0개 이상 |

이름, 연락처, 생년월일 등 개인 식별 필드는 허용하지 않는다.

## 7. EligibilityResult

UserCondition과 RequirementSet의 결정적 비교 결과다.

| Field | Type | Rule |
|---|---|---|
| `status` | enum | `eligible`, `ineligible`, `ambiguous` |
| `label` | enum | `지원 가능`, `지원 불가`, `애매` |
| `reasons` | string[] | 판정에 사용한 조건 |
| `evidence` | Evidence[] | 공고 근거 |
| `review_items` | string[] | 사용자가 직접 확인할 항목 |

판정 규칙:

1. 명시된 필수조건 불충족이 하나라도 있으면 `ineligible`이다.
2. 필수조건을 모두 충족하고 수동 확인 조건이 없으면 `eligible`이다.
3. 필요한 데이터가 없거나 전공 인정·대체 자격처럼 확정할 수 없으면 `ambiguous`다.
4. 데이터 부족을 `eligible`로 처리하지 않는다.

## 8. Report

화면이 읽는 최상위 집계다.

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | MVP는 `1.0.0` |
| `pair_id` | string | 파일명과 대응하는 유일 식별자 |
| `pair_name` | string | 사람이 읽는 비교 이름 |
| `institution` | string | 기관명 |
| `checked_at` | date | 원본과 근거를 마지막 확인한 날짜 |
| `prev`, `curr` | NoticeRef | 비교 공고 두 건 |
| `tracks` | string[] | 리포트가 다루는 직렬 |
| `changes` | Change[] | importance 오름차순 표시 |
| `units` | RecruitmentUnit[] | 모집단위별 인원 |
| `competition` | object | 공식 공개 여부와 확인 메모 |
| `requirements` | RequirementSet | 지원 상태 판정 입력 |

## 9. GroundedAnswer

질문 서비스의 반환값이다.

| Field | Type | Rule |
|---|---|---|
| `status` | enum | `answered`, `not_found`, `unavailable` |
| `answer` | string | 근거 답변 또는 고정 대체 문구 |
| `evidence` | Evidence[] | `answered`일 때 1개 이상 |
| `ai_generated` | boolean | 모델이 문장을 생성했으면 true |

`not_found`는 모델 호출 없이 `공고문에 명시 없음`을 반환한다. `unavailable`은 질문 기능 장애를
알리되 저장된 리포트 열람에는 영향을 주지 않는다.
