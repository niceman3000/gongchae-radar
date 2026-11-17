# 공채레이더 테스트 기록

## 2026-11-17 - Foundation baseline

- Command: `.\.venv\Scripts\python.exe -m pytest tests\contract tests\unit -q`
- Result: `14 passed, 1 skipped in 0.47s`
- Passed: JSON Schema 자체 검사, 최소 리포트, 알 수 없는 필드 차단, 쪽수·인용 검증,
  양쪽 근거 요구, 추가 항목 단일 근거, 의미 검증, 리포트 목록·조회·오류 격리
- Skipped: `data/reports/report_*.json`이 아직 생성되지 않아 생성 결과 계약 검사를 건너뜀
- Secrets: 실제 API 키 없이 실행

다음 기준점은 한전 통합 리포트 생성 후 동일 명령을 다시 실행해 skip이 사라지는지 확인한다.

## 2026-11-17 - ReportBuilder first output

- Command: `.\.venv\Scripts\python.exe src\report_builder.py --all-demo-pairs --checked-at 2026-11-17`
- Output: `report_kepco.json`, `report_khnp.json`, `report_komipo.json`
- Test result: `21 passed in 1.12s`
- Repository result: 리포트 3개 로드, 계약 오류 0개
- Current evidence state: 한전 18건, 한수원 14건, 중부발전 23건이 모두 `review_required`
- Interpretation: 파일 형식과 변환 코드는 통과했지만 PDF 쪽수·인용 검증 전이므로 확정 변경점은 0건이다.

## 2026-11-17 - KEPCO manual ground truth

- Sources: `data/pdf/290666.pdf`, `data/pdf/304551.pdf`
- Visual review: 모집인원·지역/직렬 인원·필수자격·자격증 가점·전형 방식의 관련 쪽을 이미지로 확인
- Ground truth: `evaluation/ground_truth/kepco.md`
- Machine-readable evidence: `evaluation/ground_truth/kepco_evidence.json`
- Report result: 한전 후보 18건 중 13건 `confirmed`, 5건 `review_required`
- Guardrail check: 사람이 고른 인용도 PDF 번들 같은 쪽에 실제 존재할 때만 `verified=true`가 되도록 재검증
- Rejected candidate example: API의 `광주/전남 → 전남광주` 표시는 PDF 원문상 실제 지역 변경으로 확인되지 않아 확정하지 않음
- Test command: `.\.venv\Scripts\python.exe -m pytest -q`
- Test result: `22 passed`
