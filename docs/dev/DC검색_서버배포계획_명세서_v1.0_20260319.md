# 프로젝트 명세서 (클라우드 서버 배포 전략)
**버전:** v1.0
**날짜:** 2026-03-19

## 1. 개요
* 완성된 DC_search 프로젝트(스케줄러 기반)를 24시간 무중단 서비스가 가능하도록 클라우드 환경(Render)에 배포한다.

## 2. 서버 구성 요소
본 프로젝트의 로컬 아키텍처는 두 가지 특징을 지니며, 이를 클라우드에 각각 배포한다.
1. **웹 프론트 (Web Service)**: `server.py`를 HTTP로 서빙하여 사용자 화면을 제공. Gunicorn 적용.
2. **수집 봇 (Background Worker)**: `scheduler.py`를 터미널 데몬 형태로 띄워 30분 주기로 웹크롤링 및 AI 분석. 

## 3. 핵심 변경 요구 사항 (개발 목표)
### 3-1. Supabase 원격 DB 연동
* 렌더(Render) 클라우드의 임시(Ephemeral) 디스크 특성상 SQLite 파일이 매번 소실되므로, Supabase 기반의 클라우드 PostgreSQL 형태로 데이터베이스 통신 레이어(`db_manager.py`)를 재구축한다.

### 3-2. 환경변수(.env) 은닉화
* 코드에 하드코딩될 위험이 있는 API Key(OpenAI), DB URL, Secret Key 등을 모두 `os.environ.get()` 형태로 치환한다. 

### 3-3. 서비스 분산 운영 (Render 플랫폼)
* Github에 소스 코드를 Push하고, Render 플랫폼 내에서:
  - `Web Service` 생성: `gunicorn server:app` 명령어로 실행
  - `Background Worker` 생성: `python scheduler.py` 명령어로 실행

## 4. 작업 진척 및 투두 리스트
- [ ] 1. 계획 및 명세서 수립 완료
- [ ] 2. 데이터베이스 마이그레이션 로직 구현 (`Supabase`)
- [ ] 3. `requirements.txt` 업데이트 (gunicorn 등)
- [ ] 4. 환경 변수 처리 모듈 반영
- [ ] 5. 로컬 최종 테스트 후 Github Push 및 플랫폼 세팅 가이드
