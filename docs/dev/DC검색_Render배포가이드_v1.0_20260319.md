# Render 클라우드 배포 가이드라인 (Supabase + 투트랙 아키텍처)
**버전:** v1.0
**날짜:** 2026-03-19

본 코드는 Render 클라우드에서 24시간 가동되도록 코드가 모두 준비(Supabase 마이그레이션 완비)되어 있습니다. 아래 절차에 따라 플랫폼에 등록만 하시면 됩니다.

## 1. 사전 준비
- **Github 저장소 생성:** 현재 로컬 폴더(`.env` 파일 제외)를 깃허브 레포지토리에 커밋 및 푸시합니다.
- **Supabase 회원가입 및 테이블 생성:** 프로젝트 생성 후 SQL Editor에서 `posts` 테이블과 `lexicon` 테이블을 생성하세요.

## 2. Render에서 웹 서버(Web Service) 생성
1. Render 대시보드(New +) ➔ **Web Service** 클릭
2. 본인의 Github 레포지토리 연결
3. **Environment**: `Python 3`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `gunicorn server:app`
6. **Environment Variables**:
   - `SUPABASE_URL`: 본인의 Supabase URL
   - `SUPABASE_KEY`: 본인의 Supabase Anon Key

## 3. Render에서 수집 봇(Background Worker) 생성
1. Render 대시보드(New +) ➔ **Background Worker** 클릭
2. 위와 똑같이 Github 레포지토리 연결
3. **Environment**: `Python 3`
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `python scheduler.py`
6. **Environment Variables**:
   - `SUPABASE_URL`, `SUPABASE_KEY`
   - `OPENROUTER_API_KEY`: 본인의 AI 분석 API 키

> **참고:** Web Service와 Background Worker가 완벽히 독립되어 돌아가므로, 스케줄러가 터지거나 크롤링 에러가 나더라도 사용자의 웹페이지(Web Service)는 0.1초의 로딩 지연 없이 안전하게 유지보수됩니다.
