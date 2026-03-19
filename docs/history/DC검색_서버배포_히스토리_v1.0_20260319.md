# 프로젝트 히스토리 (Supabase 마이그레이션 및 클라우드 배포 세팅)
**버전:** v1.0
**날짜:** 2026-03-19

## 1. 개요 및 의사 결정 논의 사항
* **논의**: 다중 갤러리 스케줄러 구조를 확립한 뒤 서버(Render 클라우드)에 올리려는 구상.
* **이슈 식별 1**: Render 디스크는 Ephemeral 성질로 `sqlite3` 파일이 증발함.
* **의사 결정 1**: 로컬 SQLite에서 벗어나 **수파베이스(Supabase) 클라우드 DB**로 영구 저장소 확립.
* **이슈 식별 2**: Render의 Background Worker는 무료 티어가 제공되지 않아, 24시간 수집 봇을 무료로 돌릴 수 없음.
* **의사 결정 2**: 완벽한 무상 운영 및 "투트랙 아키텍처" 유지를 위해 수집 봇을 **Github Actions (Cron 스케줄러)** 로 이관.
* **이슈 식별 3**: Render 웹 서버에서 Gunicorn 배포 시 오류 발생 시, 버퍼링으로 인해 원인 파악이 로그상 어려움.
* **의사 결정 3**: `server.py`에 에러 추적기를 삽입하여 데이터 조회 예외 발생 시 빈 화면이 아닌 디버깅용 붉은색 문자열을 웹 화면에 강제 출력하도록 조치.

## 2. 세부 개발 및 코드 변경 기록
1. **[MODIFY] `db_manager.py`**: SQLite3 완전 대체. `supabase.create_client` 기반의 연결 수립 구조로 재설계하여, `.upsert()`, `.select()` 등의 NoSQL 친화적 SDK 체인 사용 코드로 탈바꿈함.
2. **[MODIFY] 전체 주요 모듈**: `sentiment_analyzer.py`, `server.py`, `main.py`, `report_generator.py` 내에 잔존하던 `import sqlite3` 구문과 `pandas.read_sql` 하드코딩 구문을 Supabase SDK와 호환되게 전부 치환. 
3. **[NEW] `.env.example`**: API 연동에 필수적인 `SUPABASE_URL`, `SUPABASE_KEY`, `OPENROUTER_API_KEY` 구성 요소 템플릿 신규 추가. 
4. **[MODIFY] `requirements.txt`**: 배포용 파이썬 환경 구축을 위해 `gunicorn` 및 `supabase`를 의존성 리스트에 추가함.

## 3. 결과 및 검증
* 컴파일 검증을 통해 클래스와 메서드 체인이 모두 올바르게 구현되었음을 확인.
* `.env` 연동 시 곧바로 클라우드에서 다중 갤러리를 24시간 실시간 무인 서빙할 수 있도록 체계화.
