# Contract: 근거 질문 서비스

## Purpose

선택한 공고 리포트의 검증된 근거 범위에서만 답한다. 별도 공개 API를 만들기 위한 계약이 아니라
`app/pages/qa.py`와 `src/qa_service.py` 사이의 내부 인터페이스다.

## Input

```json
{
  "pair_id": "kepco-2025-2026-h2",
  "question": "전기 직렬 서류전형 배수가 어떻게 바뀌었어?"
}
```

Validation:

- `pair_id`는 로드된 리포트 식별자여야 한다.
- `question`은 공백 제거 후 2자 이상 300자 이하다.
- 이름·연락처 등 개인 식별 정보 입력을 요구하거나 저장하지 않는다.

## Output: answered

```json
{
  "status": "answered",
  "answer": "전기 직렬의 서류 통과 배수는 15배수에서 10배수로 변경되었습니다.",
  "evidence": [
    {
      "side": "curr",
      "notice_sn": "304551",
      "page": 5,
      "quote": "전기(배전, 송변전) : 10배수",
      "verified": true
    }
  ],
  "ai_generated": true
}
```

## Output: not_found

관련된 검증 근거가 없으면 모델을 호출하지 않는다.

```json
{
  "status": "not_found",
  "answer": "공고문에 명시 없음",
  "evidence": [],
  "ai_generated": false
}
```

## Output: unavailable

모델 호출이 실패해도 리포트 화면은 계속 동작한다.

```json
{
  "status": "unavailable",
  "answer": "현재 질문 답변 기능을 사용할 수 없습니다. 아래 공고 근거를 직접 확인해 주세요.",
  "evidence": [],
  "ai_generated": false
}
```

## Invariants

1. `answered`는 `verified=true` Evidence를 1개 이상 가진다.
2. 모델 입력에는 선택된 리포트의 검증된 Evidence와 질문만 포함한다.
3. 답변에 사용한 쪽수와 인용은 모델이 새로 만들지 않고 입력 Evidence에서 선택한다.
4. 화면은 `ai_generated=true`일 때 `AI가 생성한 답변`을 표시한다.
5. 모델·네트워크 오류는 저장된 목록과 변경점 조회를 실패시키지 않는다.
