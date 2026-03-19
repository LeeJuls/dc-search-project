# 프로젝트 명세서 (전체 코드 리뷰 및 버그 수정)
**버전:** v1.0
**날짜:** 2026-03-19

## 1. 개요
라이브 서버(Render)에서 "데이터를 수집 및 집계 중입니다." 메시지만 표시되는 문제를 포함한
전반적인 버그 수정, 하드코딩 제거, 레거시 정리, 감성 분석 품질 개선을 진행한다.

---

## 2. 수정 항목 목록

### 2-1. KST 시간대 전면 적용
**문제**: Render 서버는 UTC 기준으로 동작하여 `datetime.now()`가 한국 시간보다 9시간 느림.
날짜 기반 필터링/비교 시 당일 데이터가 전날 데이터로 분류되는 오류 발생.

**수정 파일**: `dc_crawler.py`, `main.py`, `report_generator.py`, `sentiment_analyzer.py`, `server.py`

**적용 방식**:
```python
from datetime import datetime, timedelta, timezone
KST = timezone(timedelta(hours=9))
datetime.now(KST)  # 모든 datetime.now() 호출 대체
```

---

### 2-2. 레거시 파라미터 제거 (`db_name`)
**문제**: `ReportGenerator(db.db_name)` 호출 시 `DBManager`에 `db_name` 속성이 없어 `AttributeError` 크래시 발생.

**수정 파일**: `main.py`, `report_generator.py`

**수정 내용**:
- `ReportGenerator.__init__`에서 `db_name` 파라미터 완전 제거
- 호출부도 `ReportGenerator()` 인수 없이 변경

---

### 2-3. Supabase 1000행 기본 페이지네이션 한계 해결
**문제**: Supabase는 기본적으로 쿼리 결과를 1000행으로 제한함. 데이터가 1000개 이상이면 누락 발생.

**수정 파일**: `server.py`, `report_generator.py`, `sentiment_analyzer.py`

**수정 내용**: 모든 Supabase SELECT 쿼리에 `.limit(5000)` 명시적 추가

---

### 2-4. 감성 분석 upsert → update 변경
**문제**: `process_all_unbound_posts()`에서 `upsert` 사용 시,
`gallery_id` NOT NULL 제약 조건 위반으로 INSERT 실패.
(upsert는 행이 없으면 INSERT를 시도하는데, `id`와 `sentiment_score`만 넘겨 `gallery_id` 누락)

**수정 파일**: `sentiment_analyzer.py`

**수정 내용**:
```python
# Before: 일괄 upsert (NOT NULL 오류 발생)
self.db.client.table('posts').upsert(updates).execute()

# After: 개별 update (기존 행만 수정, INSERT 시도 없음)
self.db.client.table('posts').update({
    'sentiment_score': score,
    'analyzed_at': datetime.now(KST).isoformat()
}).eq('id', row['id']).execute()
```

---

### 2-5. 감성 사전 전면 개편 (욕설 기반 → 게임 경험 기반)
**문제**: 기존 감성 사전이 욕설 포함 여부로 긍/부정을 판단하여 정확도 낮음.
게임 커뮤니티 특성상 "사기캐", "갓겜", "무과금" 등 경험적 키워드가 핵심.

**수정 파일**: `sentiment_analyzer.py` (lexicon 초기값 및 LLM 프롬프트)

**주요 키워드 분류**:
| 분류 | 예시 키워드 | 점수 범위 |
|------|------------|---------|
| 강한 부정 | 사기캐, 밸붕, ㅈ망겜, 핵과금 | -0.8 ~ -1.0 |
| 부정 | 과금, 안뜨, 안나옴, 너프 | -0.4 ~ -0.7 |
| 강한 긍정 | 갓겜, 혜자, 꿀잼, 버프 | +0.7 ~ +0.9 |
| 긍정 | 득템, 행복, 뽑기성공 | +0.4 ~ +0.6 |

**LLM 프롬프트 개선**: `gallery_name` 파라미터를 동적으로 주입하여 갤러리별 맥락 반영.
욕설 기반 판단 금지 가이드라인 명시.

---

### 2-6. 긴 키워드 우선 매칭 (오매칭 방지)
**문제**: "무과금"을 분석 시 "과금"이 먼저 매칭되어 부정으로 잘못 분류.

**수정 파일**: `sentiment_analyzer.py`

**수정 내용**: lexicon 키워드를 길이 내림차순 정렬 후 순차 매칭
```python
sorted_lexicon = sorted(lexicon.items(), key=lambda x: len(x[0]), reverse=True)
```

---

### 2-7. 마이너/메이저 갤러리 링크 분기
**문제**: 마이너 갤러리(`mgallery`)와 메이저 갤러리(`board`) URL 경로가 다른데 하드코딩.

**수정 파일**: `server.py`, `templates/dashboard.html`

**수정 내용**:
- `server.py`: `is_minor` 플래그를 데이터 딕셔너리에 포함하여 템플릿에 전달
- `dashboard.html`: `{{ 'mgallery/board/view/' if data.is_minor else 'board/view/' }}`로 동적 처리

---

### 2-8. 날짜 필터 자정 기준 변경
**문제**: `days=1` 조회 시 `datetime.now() - timedelta(days=1)`은 현재 시각 기준 24시간 전.
예: 오전 10시 조회 → 어제 오전 10시 이후만 조회 → 어제 오전 10시 이전 게시글 누락.

**수정 파일**: `server.py`

**수정 내용**:
```python
# Before: 롤링 24시간
target_date = (datetime.now(KST) - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

# After: 자정 기준
target_date = (datetime.now(KST) - timedelta(days=days)).replace(
    hour=0, minute=0, second=0, microsecond=0
).strftime('%Y-%m-%d %H:%M:%S')
```

---

## 3. 삭제된 레거시 파일
- `migrate_db.py` — SQLite→Supabase 마이그레이션 스크립트 (완료 후 불필요)
- `check_struct.py` — DB 구조 점검용 임시 스크립트
- `dc_sentiment.db` — 로컬 SQLite DB 파일 (Supabase 전환 후 불필요)
- `crawl_result_test.csv` — 크롤러 테스트 출력 임시 파일

---

## 4. 인프라 관련 발견 사항

### Supabase 이중 프로젝트 이슈
- Supabase에 구글 로그인 / 깃허브 로그인으로 각각 별도 프로젝트가 생성되어 있었음
- `.env` 파일의 `SUPABASE_URL`이 실제 사용 프로젝트(`iwyadjubhywkbzgtrlwr`)를 정확히 가리키고 있음을 확인
- Render 환경변수도 동일 프로젝트를 가리키고 있음을 확인

### GitHub Actions DC 크롤링 제한
- GitHub Actions 러너(ubuntu-latest)에서 gall.dcinside.com 접속 시 `ConnectTimeoutError` 발생
- DC Inside 측에서 클라우드 IP를 차단하는 것으로 추정
- 크롤링 실패 시 기존 DB 데이터로 대시보드 정상 서비스는 유지됨
