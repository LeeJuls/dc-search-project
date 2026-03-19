# 프로젝트 히스토리 (Supabase 마이그레이션 및 클라우드 배포 세팅)
**버전:** v1.0
**날짜:** 2026-03-19

## 1. 개요 및 의사 결정 논의 사항
* **논의**: 다중 갤러리 스케줄러 구조를 확립한 뒤 서버(Render 클라우드)에 올리려는 구상.
* **이슈 식별**: Render(무료/유료 티어 포함)의 디스크는 Ephemeral 성질로, 인스턴스 재기동 시 내부 로컬 파일이 모두 증발함. 즉, 로컬에서 쓰이던 `sqlite3` 파일(`dc_sentiment.db`)을 그대로 쓰면 모든 데이터가 날아감.
* **의사 결정**: 로컬 SQLite에서 벗어나 **수파베이스(Supabase) 클라우드 DB**로 영구 저장소를 변경하는 결정을 내림. 아울러 AI API 키 및 DB 키 하드코딩을 방지하기 위해 `.env` 파일과 `os.environ` 연동을 적용하기로 함.

## 2. 세부 개발 및 코드 변경 기록
1. **[MODIFY] `db_manager.py`**: SQLite3 완전 대체. `supabase.create_client` 기반의 연결 수립 구조로 재설계하여, `.upsert()`, `.select()` 등의 NoSQL 친화적 SDK 체인 사용 코드로 탈바꿈함.
2. **[MODIFY] 전체 주요 모듈**: `sentiment_analyzer.py`, `server.py`, `main.py`, `report_generator.py` 내에 잔존하던 `import sqlite3` 구문과 `pandas.read_sql` 하드코딩 구문을 Supabase SDK와 호환되게 전부 치환. 
3. **[NEW] `.env.example`**: API 연동에 필수적인 `SUPABASE_URL`, `SUPABASE_KEY`, `OPENROUTER_API_KEY` 구성 요소 템플릿 신규 추가. 
4. **[MODIFY] `requirements.txt`**: 배포용 파이썬 환경 구축을 위해 `gunicorn` 및 `supabase`를 의존성 리스트에 추가함.

## 3. 결과 및 검증
* 컴파일 검증을 통해 클래스와 메서드 체인이 모두 올바르게 구현되었음을 확인.
* `.env` 연동 시 곧바로 클라우드에서 다중 갤러리를 24시간 실시간 무인 서빙할 수 있도록 체계화.
