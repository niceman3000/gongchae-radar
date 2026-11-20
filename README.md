# 공채레이더 — 공기업 공채, 작년과 뭐가 달라졌고 나는 지원할 수 있나

2026 대한민국 청년 CAREER FAIR AI 해커톤 (대한상공회의소) · 제출 마감 2026-11-23(월) 17:00

**서비스 주소: https://gongchae-radar.streamlit.app** (로그인 없이 사용)

> 지금 상태·진행률: [`STATUS.md`](STATUS.md) · 날짜별 작업일지: [`docs/worklog/`](docs/worklog/) · 첫날(11-16) 개발 가이드: [`docs/초기_개발가이드.md`](docs/초기_개발가이드.md)

## 무엇을 하나

공기업 30곳의 신입 공채 공고를 **정부 공식 API**로 모아서

1. **작년 같은 공고와 비교**해 바뀐 점(인원·배수·배점·가점·자격)을 쪽수·원문 인용과 함께 보여 준다
2. 사용자가 **직렬·지역·자격증**만 고르면 공고마다 **지원 가능 / 애매 / 지원 불가**와 내 자격증 **가점**을 알려 준다
3. 공고문에 대해 물으면 **그 공고문 안에서만** 답한다 (없으면 "공고문에 명시 없음")
4. 결과를 **PDF로 받을 수 있다**

이름·연락처 같은 개인정보는 받지 않는다. 합격 가능성·순위는 만들지 않는다.

## 화면 (4개)

| 화면 | 하는 일 |
|---|---|
| ① 내 조건 입력 | 희망 직렬·근무 지역·보유 자격증 |
| ② 맞춤 공고 | 30곳 중 관련 공고, 판정·판단 이유·가점·근거, **결과 PDF 받기** |
| ③ 공고 비교 | 작년 대비 변경 후보, 이번 공고 한눈에 보기, 원문 인용 |
| ④ 공고문에 물어보기 | 공고문 근거 안에서만 AI 답변 (AI가 생성한 답변 표시) |

## 어떻게 만드나 (코드와 AI 역할)

```
정부 API (data.go.kr) ──▶ 공고 고르기·작년 짝짓기 ──▶ 공고문 받기 (PDF / 그림·스캔·한글)
        [코드]                     [코드]                    [코드]
                                                              │
        ┌─────────────────────────────────────────────────────┤
        ▼                                                     ▼
작년 대비 비교·같은 변경 묶기 [코드]          공고문 글자 만들기: PDF는 코드, 그림·스캔은 AI(Haiku)가 그대로 옮겨 적음
        │                                                     ▼
        │                                  지원 자격·가점 정리: AI(Sonnet)가 정해진 칸을 채움
        │                                  → 모든 칸에 쪽수+원문 인용, 코드가 원문에 진짜 있는지 대조, 없는 건 버림
        ▼                                                     ▼
   리포트 JSON 30개 (미리 만들어 저장) ◀──────────────────────────┘
        │
        ▼
   화면: 판정 [코드] · 질문 답변 [코드가 원문을 고르고 AI(Sonnet)가 그 안에서만 답, 인용 대조]
```

- 판정·숫자 비교·가점 계산은 **코드**. 확정할 수 없으면 기본값은 **애매**
- 실시간 AI 호출은 질문 기능뿐 (접속당 20회). 나머지는 미리 계산해 저장
- 규칙 전체: [`docs/전처리_규칙.md`](docs/전처리_규칙.md) · 정확도와 개선 과정: [`evaluation/정확도_개선_기록.md`](evaluation/정확도_개선_기록.md) · 최종 측정: [`evaluation/final-report.md`](evaluation/final-report.md)

## 정확도 (3곳 정답지 대비, 2026-11-20)

| 지표 | 값 |
|---|---|
| 화면 판정 일치 (직렬 × 자격증 600조건) | 96% (578/600) |
| 자격증 가점 재현율 · 정밀도 | 75% · 83% |
| 근거 질문 (평가표 10문항) | 10/10 |
| 작년 대비 변경 후보 정밀도 (한전 원문 대조) | 72% (13/18) |

정답지는 한전·한수원·중부발전 3곳뿐이라 나머지 27곳은 직접 잰 값이 아니다.

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py     # 또는 run_streamlit.bat
```

- 질문 기능에 AI 답을 쓰려면 `ANTHROPIC_API_KEY`가 필요하다. 없으면 관련 원문 발췌만 보여 주고 나머지 화면은 그대로 된다
  - 로컬: 같은 PowerShell 창에서 `$env:ANTHROPIC_API_KEY = "키"` 후 실행, 또는 `.streamlit\secrets.toml` (Git에 안 올라감)
  - 배포: Streamlit Community Cloud의 Secrets
- 테스트: `.\.venv\Scripts\python.exe -m pytest -q`
- 최종 측정: `.\.venv\Scripts\python.exe evaluation\evaluate.py --all` → `evaluation/final-report.md`
- 키 노출 점검: `.\.venv\Scripts\python.exe tools\check_secrets.py`
- 배포 방법: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)

## 데이터 다시 만들기 (필요할 때만)

```powershell
$env:JOB_API_KEY = "data.go.kr 인증키"         # 공고 다시 모을 때만
.\.venv\Scripts\python.exe tools\collect_institutions.py      # 30곳 공고 수집·짝짓기
.\.venv\Scripts\python.exe tools\redownload_pdfs.py           # 공고문 PDF (키 불필요)
.\.venv\Scripts\python.exe tools\ocr_notices.py               # 그림·스캔 공고: 비용 계산 → --run
$env:ANTHROPIC_API_KEY = "키"
.\.venv\Scripts\python.exe tools\extract_requirements.py      # 지원 자격 추출: 비용 계산 → --run
.\.venv\Scripts\python.exe tools\build_auto_reports.py        # 리포트 30개
```

AI 단계는 모두 **기본이 비용 계산만**이고 `--run`을 붙여야 돈이 든다. 비용 기록: `evaluation/ai_extracted/usage.json`, `data/ocr/usage.json`.

## 지킬 것

- API 키를 코드·Git·영상·발표자료에 넣지 않는다 (환경변수·Secrets만). 제출 전 `tools/check_secrets.py`
- 실제 개인정보를 외부 AI에 보내지 않는다 (입력은 직렬·지역·자격증뿐)
- 로그인 없이 접속 가능, 11/30(본선 시 12/7)까지 작동. Anthropic 콘솔에 월 사용 한도 설정
- 사용한 데이터·오픈소스·AI 도구와 팀 역할: [`docs/SOURCES_AND_AI_USAGE.md`](docs/SOURCES_AND_AI_USAGE.md)

## 알려진 한계

- 그림·스캔 공고 7곳은 AI가 옮겨 적은 글자를 원문으로 쓴다 (옮길 때 생긴 오타는 인용 대조로 못 잡음, 화면에 안내)
- 기관에 따라 API에 모집단위별 인원이 없다 (예: 한전) → 직렬별 인원 비교는 원문 확인 필요
- 22곳은 지시문 개선 전에 지원 자격을 뽑았다 (다시 뽑으면 좋아질 수 있음, 약 $3)
- 자세한 목록: `evaluation/정확도_개선_기록.md` 6절
