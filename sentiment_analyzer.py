import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime

# .env 파일 로드
load_dotenv()

class SentimentAnalyzer:
    """
    하이브리드 감성 분석 엔진:
    1. Daily LLM Tutor: OpenRouter를 통해 신조어 및 문맥 사전 업데이트
    2. Local Engine: 업데이트된 사전을 바탕으로 전체 글 고속 분석
    """
    def __init__(self, db_manager):
        self.db = db_manager
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self._init_default_lexicon() # 초기 기본 사전 삽입
        self.lexicon = self._load_lexicon()

    def _init_default_lexicon(self):
        """기본적인 감성 단어들을 DB에 미리 넣어둡니다 (API 실패 대비)."""
        default_words = {
            # ── 게임성 및 재미 ─ 긍정 ──────────────────────────────
            "갓겜": 0.9, "꿀잼": 0.8, "인생겜": 0.9, "대박": 0.8,
            "수작": 0.7, "명작": 0.8, "재밌다": 0.7, "시간순삭": 0.7,
            "몰입감": 0.6, "신선하다": 0.5, "찰지다": 0.6,
            "짜임새": 0.5, "자유도": 0.4,

            # ── 게임성 및 재미 ─ 부정 ──────────────────────────────
            "망겜": -0.9, "노잼": -0.7, "똥겜": -0.8, "쿠소겜": -0.8,
            "지루하다": -0.6, "억까": -0.6, "피로도": -0.7, "불쾌하다": -0.7,
            "뇌절": -0.5, "숙제": -0.5, "노가다": -0.6,
            "양산형": -0.5, "재탕": -0.5, "밸붕": -0.7,

            # ── 운영 및 BM ─ 긍정 ──────────────────────────────────
            "혜자": 0.8, "갓운영": 0.8, "사료": 0.6,
            "퍼준다": 0.7, "합리적": 0.5, "갓패치": 0.7,
            "무과금": 0.5,  # "과금"(-0.4) 오매칭 상쇄용 + 의미 자체도 긍정

            # ── 운영 및 BM ─ 부정 ──────────────────────────────────
            "창렬": -0.8, "돈독": -0.7, "불통": -0.7, "먹튀": -0.8,
            "과금유도": -0.7, "현질": -0.5, "P2W": -0.7, "확률주작": -0.8,
            "잠수함패치": -0.6, "없뎃": -0.6, "꼬접": -0.6,
            "과금": -0.4, "방치": -0.5,

            # ── 기술 및 시청각 ─ 긍정 ──────────────────────────────
            "눈호강": 0.7, "귀호강": 0.7, "최적화": 0.5,

            # ── 기술 및 시청각 ─ 부정 ──────────────────────────────
            "발적화": -0.8, "렉": -0.6, "튕김": -0.7,
            "버그": -0.7, "오류": -0.6, "점검": -0.3,

            # ── 가챠/드랍 불만 ──────────────────────────────────────
            "안뜨": -0.6, "안나옴": -0.6, "안나와": -0.6,
            "안떠": -0.6, "안줌": -0.5, "조각만": -0.6,
            "꽝": -0.7, "못뽑": -0.7, "안뽑힘": -0.6,

            # ── 밸런스 불만 ─────────────────────────────────────────
            "너프": -0.6, "하향": -0.5, "사기캐": -0.7, "개강": -0.6,
            "상향": 0.5,

            # ── 기타 긍정 ───────────────────────────────────────────
            "최고": 0.8, "지린다": 0.7, "미쳤다": 0.6,
            "기대": 0.5, "역대급": 0.6,

            # ── 기타 부정 ───────────────────────────────────────────
            "망함": -0.8, "나락": -0.8, "접는다": -0.9,
            "삭제": -0.7, "토나와": -0.8, "쓰레기": -0.9,
            "혐": -0.8, "별로": -0.4, "그닥": -0.3,
            "실망": -0.5, "병맛": -0.3,
        }
        
        data = []
        for word, score in default_words.items():
            data.append({"word": word, "score": score, "updated_at": datetime.now().isoformat()})
        try:
            self.db.client.table('lexicon').upsert(data, on_conflict='word').execute()
        except Exception as e:
            print(f"기본 사전 초기화 오류: {e}")

    def _load_lexicon(self):
        """DB에서 로컬 감성 사전을 불러옵니다."""
        try:
            response = self.db.client.table('lexicon').select('word, score').execute()
            if hasattr(response, 'data') and response.data:
                return {item['word']: item['score'] for item in response.data}
        except Exception as e:
            print(f"로컬 감성 사전 로드 오류: {e}")
        return {}

    def update_lexicon_with_llm(self, sample_titles):
        """
        OpenRouter AI를 통해 신조어 및 문맥별 감성 점수를 추출하여 사전을 업데이트합니다.
        """
        if not sample_titles:
            return

        titles_str = "\n".join(sample_titles)
        prompt = f"""
        당신은 한국 게임 커뮤니티(디시인사이드) 전문가입니다. 
        다음은 최근 '쿠키런 오븐스매시' 갤러리의 게시글 제목들입니다.
        이 제목들을 분석해서 요즘 유저들이 사용하는 '신조어'나 '핵심 키워드' 중 여론(긍정/부정)을 파악할 수 있는 단어들을 20개 정도 골라내주세요.
        각 단어에 대해 긍정은 양수(최대 1.0), 부정은 음수(최소 -1.0)로 점수를 매겨 JSON 형식으로만 응답하세요.
        
        [게시글 제목]
        {titles_str}
        
        주의: 순수하게 JSON 객체 하나만 {{"단어": 점수}} 형태로 반환하세요.
        """

        try:
            print("AI에게 최신 여론 및 신조어 학습 중 (OpenRouter)...")
            # OpenRouter 무료 모델 재시도
            response = self.client.chat.completions.create(
                model="meta-llama/llama-3.2-3b-instruct:free",
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.choices[0].message.content
            if "{" in content:
                content = content[content.find("{"):content.rfind("}")+1]
                
            new_lexicon = json.loads(content)
            
            data = []
            for word, score in new_lexicon.items():
                data.append({"word": word, "score": score, "updated_at": datetime.now().isoformat()})
            
            try:
                self.db.client.table('lexicon').upsert(data, on_conflict='word').execute()
            except Exception as e:
                print(f"LLM 신조어 DB 반영 오류: {e}")
            
            print(f"새로운 단어 {len(new_lexicon)}개가 사전에 반영되었습니다.")
            self.lexicon = self._load_lexicon()
            
        except Exception as e:
            print(f"LLM 사전 업데이트 오류: {e}")

    def analyze_locally(self, text):
        """로컬 사전을 사용하여 텍스트의 감성 스코어를 계산합니다.

        긴 키워드 우선 매칭: '무과금'이 매칭되면 내부의 '과금'은 건너뜁니다.
        """
        score = 0.0
        count = 0
        matched_positions = set()  # 이미 매칭된 문자 위치 추적

        # 긴 키워드부터 먼저 매칭 (길이 내림차순 정렬)
        sorted_lexicon = sorted(self.lexicon.items(), key=lambda x: len(x[0]), reverse=True)

        for word, s in sorted_lexicon:
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                positions = set(range(idx, idx + len(word)))
                # 이미 더 긴 키워드가 커버한 위치면 건너뜀
                if not positions & matched_positions:
                    score += s
                    count += 1
                    matched_positions |= positions
                start = idx + 1

        return score / count if count > 0 else 0.0

    def process_all_unbound_posts(self, force=False):
        """아직 분석되지 않은 게시글을 분석합니다."""
        try:
            query = self.db.client.table('posts').select('id, title')
            if not force:
                query = query.is_('analyzed_at', 'null')
            
            response = query.execute()
            if not hasattr(response, 'data') or not response.data:
                return 0
                
            updates = []
            for row in response.data:
                score = self.analyze_locally(row['title'])
                updates.append({
                    'id': row['id'], 
                    'sentiment_score': score, 
                    'analyzed_at': datetime.now().isoformat()
                })
            
            if updates:
                self.db.client.table('posts').upsert(updates).execute()
            
            return len(updates)
        except Exception as e:
            print(f"게시글 감성 분석 처리 중 오류: {e}")
            return 0
