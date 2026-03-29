# 프로젝트 명세서 (클라우드 서버 배포 전략)
**버전:** v1.0
**날짜:** 2026-03-19

## 1. 개요
* 완성된 DC_search 프로젝트(스케줄러 기반)를 24시간 무중단 서비스가 가능하도록 클라우드 환경(Render)에 배포한다.

## 2. 서버 구성 요소
본 프로젝트의 로컬 아키텍처는 두 가지 특징을 지니며, 이를 클라우드에 각각 배포한다.
1. **웹 프론트 (Web Service)**: `server.py`를 HTTP로 서빙하여 사용자 화면을 제공. Gunicorn 적용.
2. **수집 봇 (Github Actions)**: `scheduler.py`를 깃허브 클라우드에서 30분 주기로 크론(Cron) 구동하여 웹크롤링 및 AI 분석. 

## 3. 핵심 변경 요구 사항 (개발 목표)
### 3-1. Supabase 원격 DB 연동
* 렌더(Render) 클라우드의 임시(Ephemeral) 디스크 특성상 SQLite 파일이 매번 소실되므로, Supabase 기반의 클라우드 PostgreSQL 형태로 데이터베이스 통신 레이어(`db_manager.py`)를 재구축한다.

### 3-2. 환경변수(.env) 은닉화
* 코드에 하드코딩될 위험이 있는 API Key(OpenAI), DB URL, Secret Key 등을 모두 `os.environ.get()` 형태로 치환한다. 

### 3-3. 서비스 분산 운영 (Render + Github)
* 클라우드 리소스를 100% 무상으로 다각화하여 분산 운영:
  - **Render Web Service**: `gunicorn server:app` 명령어로 사용자 화면 대시보드 실시간 무중단 제공.
  - **Github Actions**: 30분 단위 Cron 스케줄러를 통해 `scheduler.py`를 1회성 구동하고 데이터 푸시 후 자동 종료.

## 4. 작업 진척 및 투두 리스트
- [x] 1. 계획 및 명세서 수립 완료
- [x] 2. 데이터베이스 마이그레이션 로직 구현 (`Supabase`)
- [x] 3. `requirements.txt` 업데이트 (gunicorn 등)
- [x] 4. 환경 변수 처리 모듈 반영
- [x] 5. 로컬 최종 테스트 및 Github Actions + Render 연동 배포 완료
