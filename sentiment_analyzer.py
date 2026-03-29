import os
import json
import time
import re
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd
from datetime import datetime, date
from itertools import groupby

# .env 파일 로드
load_dotenv()


class SentimentAnalyzer:
    """
    하이브리드 감성 분석 엔진:
    1. LLM 배치 분석: Gemini / OpenRouter를 통해 문맥 기반 감성 분석 (15개씩 배치)
    2. 로컬 사전 폴백: API 소진 시 개선된 사전 기반 고속 분석
    3. LLM 사전 업데이트: 신조어 추출 (기존 기능 유지)
    """

    # ── 프로바이더 설정 ──────────────────────────────────────────────
    PROVIDER_CHAIN = [
        {
            'name': 'gemini_flash_lite',
            'rpd': 1000, 'rpm': 15, 'batch_size': 15,
            'model': 'gemini-2.5-flash-lite',
            'type': 'gemini',
            'sleep': 4,
        },
        {
            'name': 'gemini_flash',
            'rpd': 250, 'rpm': 10, 'batch_size': 15,
            'model': 'gemini-2.5-flash',
            'type': 'gemini',
            'sleep': 6,
        },
        {
            'name': 'openrouter_llama',
            'rpd': 50, 'rpm': 10, 'batch_size': 10,
            'model': 'meta-llama/llama-3.2-3b-instruct:free',
            'type': 'openrouter',
            'sleep': 6,
        },
    ]

    def __init__(self, db_manager):
        self.db = db_manager

        # OpenRouter 클라이언트 (기존)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

        # Gemini 클라이언트
        self.gemini_client = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai as google_genai
                self.gemini_client = google_genai.Client(api_key=gemini_key)
                print(">> Gemini API 클라이언트 초기화 완료")
            except Exception as e:
                print(f">> Gemini 초기화 실패: {e}")

        # 테스트 모드: LLM 배치 1회만 호출
        self.test_mode = os.getenv("TEST_MODE", "").lower() == "true"
        if self.test_mode:
            print("[TEST_MODE] LLM 배치 1회 제한 적용")

        # 일일 API 사용량 추적 (날짜 변경 시 자동 리셋)
        self._api_usage = {}
        self._api_usage_date = date.today()

        self._init_default_lexicon()
        self.lexicon = self._load_lexicon()

    def _init_default_lexicon(self):
        """기본적인 감성 단어들을 DB에 미리 넣어둡니다 (API 실패 대비). 이미 데이터가 있으면 건너뜀."""
        try:
            resp = self.db.client.table('lexicon').select('word', count='exact').limit(1).execute()
            if resp.count and resp.count > 0:
                return
        except:
            pass

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
            "무과금": 0.5,

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

            # ── 복합 부정 표현 (부정어+긍정어 조합) ─────────────────
            "재미없다": -0.7, "재미없어": -0.6, "재미없네": -0.6,
            "재미없음": -0.6, "재미없는": -0.6,
            "기대안됨": -0.6, "기대가안됨": -0.6,
            "기대없다": -0.5, "기대없어": -0.5,
            "안재밌다": -0.7, "안재밌어": -0.6, "안재밌네": -0.6,
            "못즐기": -0.5, "못하겠다": -0.5,

            # ── 신규: 문맥 누락 보강 ───────────────────────────────
            "조잡": -0.7, "조잡하": -0.7, "조잡함": -0.7,
            "구림": -0.6, "구리다": -0.5, "구린": -0.5,
            "에바": -0.4, "글쎄": -0.2,

            # ── 공략/가이드 (커뮤니티 기여 = 긍정) ─────────────────
            "공략": 0.4, "가이드": 0.4, "팁": 0.3, "정리": 0.2,
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

    def update_lexicon_with_llm(self, sample_titles, gallery_name="게임"):
        """
        OpenRouter AI를 통해 신조어 및 문맥별 감성 점수를 추출하여 사전을 업데이트합니다.
        gallery_name: 갤러리 이름 (프롬프트에 동적 반영)
        """
        if not sample_titles:
            return False

        titles_str = "\n".join(sample_titles)
        prompt = f"""
        당신은 한국 게임 커뮤니티(디시인사이드) 전문가입니다.
        다음은 최근 '{gallery_name}' 갤러리의 게시글 제목들입니다.
        이 제목들을 분석해서 요즘 유저들이 사용하는 '신조어'나 '핵심 키워드' 중 여론(긍정/부정)을 파악할 수 있는 단어들을 20개 정도 골라내주세요.
        각 단어에 대해 긍정은 양수(최대 1.0), 부정은 음수(최소 -1.0)로 점수를 매겨 JSON 형식으로만 응답하세요.

        [중요 가이드라인]
        - 욕설(씨발, 개 등)은 감성 판단에 사용하지 마세요. 한국 커뮤니티에서 욕설은 강조 표현이지 부정/긍정 지표가 아닙니다.
        - "사기캐", "개강", "밸붕" 등 오버밸런스 관련 단어는 부정(-0.6 ~ -0.7)으로 분류하세요. 게임 밸런스 불만입니다.
        - "안뜨", "안나옴", "조각만", "못뽑" 등 가챠/드랍 불만은 부정(-0.5 ~ -0.7)입니다.
        - "갓겜", "꿀잼", "혜자" 등 게임성/운영 칭찬은 긍정(0.7 ~ 0.9)입니다.
        - "안 + 긍정어" 또는 "못 + 긍정어" 조합("안재밌다", "기대가 안됨", "못즐기겠다" 등)은 반드시 부정(-0.5 ~ -0.7)으로 분류하세요.
        - "재미없다", "재미없어", "기대없다" 등 '없다'가 붙는 부정 복합어도 부정(-0.5 ~ -0.7)으로 분류하세요.

        [게시글 제목]
        {titles_str}

        주의: 순수하게 JSON 객체 하나만 {{"단어": 점수}} 형태로 반환하세요.
        """

        old_lexicon = dict(self.lexicon)

        try:
            print("AI에게 최신 여론 및 신조어 학습 중 (OpenRouter)...")
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
                return False

            print(f"새로운 단어 {len(new_lexicon)}개가 사전에 반영되었습니다.")
            self.lexicon = self._load_lexicon()
            changed = (old_lexicon != self.lexicon)
            print(f">> lexicon 변경 여부: {changed}")
            return changed

        except Exception as e:
            print(f"LLM 사전 업데이트 오류: {e}")
            return False

    # ── 부정어 목록 (비판 동사 패턴 추가) ─────────────────────────
    NEGATION_WORDS = [
        "안되", "안됨", "안 되", "못되", "안하", "못하", "안해", "못해",
        "없다", "없어", "없네", "없음", "없는", "없고",
        "안 ", "못 ", "않", "안되네", "안되는", "안됩",
        # 비판 동사 → 앞 단어 점수 반전
        "욕하", "까는", "깐다", "비판",
    ]

    def analyze_locally(self, text):
        """로컬 사전을 사용하여 텍스트의 감성 스코어를 계산합니다.

        긴 키워드 우선 매칭: '무과금'이 매칭되면 내부의 '과금'은 건너뜁니다.
        부정어 window: 키워드 앞 6글자 또는 뒤 6글자 내에 부정어가 있으면 점수를 반전합니다.
        """
        score = 0.0
        count = 0
        matched_positions = set()

        sorted_lexicon = sorted(self.lexicon.items(), key=lambda x: len(x[0]), reverse=True)

        for word, s in sorted_lexicon:
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                positions = set(range(idx, idx + len(word)))
                if not positions & matched_positions:
                    word_end = idx + len(word)
                    preceding = text[max(0, idx - 6):idx]
                    following = text[word_end:word_end + 6]
                    is_negated = (
                        any(neg in preceding for neg in self.NEGATION_WORDS)
                        or any(neg in following for neg in self.NEGATION_WORDS)
                    )
                    actual_score = -s if is_negated else s
                    score += actual_score
                    count += 1
                    matched_positions |= positions
                start = idx + 1

        return score / count if count > 0 else 0.0

    # ── 멀티 프로바이더 LLM 배치 분석 ────────────────────────────

    def _reset_usage_if_new_day(self):
        """날짜가 바뀌면 API 사용량 리셋."""
        today = date.today()
        if today != self._api_usage_date:
            self._api_usage = {}
            self._api_usage_date = today

    def _get_usage(self, provider_name):
        """특정 프로바이더의 오늘 사용 횟수 반환."""
        self._reset_usage_if_new_day()
        return self._api_usage.get(provider_name, 0)

    def _increment_usage(self, provider_name):
        """프로바이더 사용 횟수 증가."""
        self._api_usage[provider_name] = self._api_usage.get(provider_name, 0) + 1

    def _get_available_provider(self):
        """일일 한도가 남은 최우선 프로바이더 반환. 없으면 None."""
        self._reset_usage_if_new_day()
        for provider in self.PROVIDER_CHAIN:
            # Gemini 클라이언트 없으면 건너뜀
            if provider['type'] == 'gemini' and not self.gemini_client:
                continue
            used = self._get_usage(provider['name'])
            if used < provider['rpd']:
                return provider
        return None

    def _build_sentiment_prompt(self, posts, gallery_name):
        """문맥 인식 감성 분석 프롬프트를 생성합니다."""
        lines = []
        for p in posts:
            lines.append(f"(id:{p['id']}) {p['title']}")
        posts_str = "\n".join(lines)

        return f"""당신은 한국 게임 커뮤니티(디시인사이드) 감성 분석 전문가입니다.
다음은 '{gallery_name}' 갤러리의 게시글 제목들입니다.

[핵심 규칙]
1. 감성 점수는 이 갤러리의 게임({gallery_name})에 대한 감성만 측정합니다.
2. 다른 게임을 비하하면서 자기 게임을 칭찬하는 패턴은 긍정입니다.
   예: "쿠오스하니까 브롤 노잼" → 쿠오스 긍정(+0.5~0.7)
3. "욕하다", "까다", "비판" 등 비판 동사가 붙으면 부정입니다.
   예: "최적화 욕하노" → 부정(-0.6)
4. 사전에 없는 단어도 문맥으로 판단하세요.
   예: "조잡하다" → 부정(-0.7)
5. 욕설은 감성 지표가 아닙니다.
6. 줄임말: 쿠오스=쿠키런 오븐 스매시, 쿠킹덤=쿠키런 킹덤
7. 복합 감성: "그래픽 좋은데 최적화 구림" → 전체적으로 판단 (부정 -0.3)
8. 공략/가이드/팁 게시글은 커뮤니티 기여이므로 긍정(+0.3~0.5)입니다.
   예: "[오븐공략] 뉴비용 가이드" → 긍정(+0.4)
   예: "초보 팁 정리" → 긍정(+0.3)

[점수 범위]
-1.0(매우 부정) ~ 0.0(중립) ~ 1.0(매우 긍정)

[게시글 목록]
{posts_str}

[응답 형식] 반드시 JSON만 출력하세요. 설명이나 마크다운 없이 순수 JSON만:
{{{{"id숫자": {{"score": 0.0, "target": "분석대상"}}, ...}}}}"""

    def _parse_llm_response(self, content):
        """LLM 응답에서 JSON을 안전하게 파싱합니다."""
        if not content:
            return {}

        # 마크다운 코드블럭 제거
        content = re.sub(r'```(?:json)?\s*', '', content)
        content = re.sub(r'```\s*$', '', content)
        content = content.strip()

        # JSON 추출
        if "{" in content:
            content = content[content.find("{"):content.rfind("}") + 1]
        else:
            return {}

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 쉼표 누락 등 경미한 포맷 오류 보정 시도
            try:
                content = re.sub(r'}\s*{', '}, {', content)
                content = re.sub(r'"\s*\n\s*"', '",\n"', content)
                parsed = json.loads(content)
            except json.JSONDecodeError:
                return {}

        results = {}
        for key, val in parsed.items():
            # id 키에서 숫자만 추출
            id_str = re.sub(r'[^0-9]', '', str(key))
            if not id_str:
                continue
            post_id = int(id_str)

            if isinstance(val, dict) and 'score' in val:
                score = float(val['score'])
            elif isinstance(val, (int, float)):
                score = float(val)
            else:
                continue

            # 점수 범위 클램핑
            score = max(-1.0, min(1.0, score))
            results[post_id] = score

        return results

    def _call_llm_batch(self, provider, posts, gallery_name):
        """프로바이더별 API 호출. Gemini SDK / OpenRouter 분기."""
        prompt = self._build_sentiment_prompt(posts, gallery_name)

        try:
            if provider['type'] == 'gemini':
                response = self.gemini_client.models.generate_content(
                    model=provider['model'],
                    contents=prompt,
                )
                content = response.text
            else:
                # OpenRouter (기존 OpenAI 호환 클라이언트)
                response = self.client.chat.completions.create(
                    model=provider['model'],
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.choices[0].message.content

            self._increment_usage(provider['name'])
            results = self._parse_llm_response(content)

            matched = len(results)
            total = len(posts)
            print(f"   [{provider['name']}] {matched}/{total}개 분석 완료 "
                  f"(일일: {self._get_usage(provider['name'])}/{provider['rpd']})")

            return results

        except Exception as e:
            error_msg = str(e)
            print(f"   [{provider['name']}] API 오류: {error_msg}")

            # 429 (Rate Limit) → 해당 프로바이더 일일 한도 소진 처리
            if '429' in error_msg or 'rate' in error_msg.lower():
                self._api_usage[provider['name']] = provider['rpd']
                print(f"   [{provider['name']}] Rate limit 도달 → 다음 프로바이더로 전환")

            return {}

    def analyze_batch_with_llm(self, posts, gallery_name):
        """
        LLM 배치 분석 + 로컬 사전 폴백.
        posts: [{'id': int, 'title': str}, ...]
        returns: {post_id: score, ...}
        """
        results = {}
        batch_count = 0
        max_batches = 1 if self.test_mode else None

        # 현재 프로바이더의 batch_size로 청크 분할
        i = 0
        while i < len(posts):
            if max_batches is not None and batch_count >= max_batches:
                if self.test_mode:
                    print(f"   [TEST_MODE] LLM 배치 {max_batches}회 제한 도달, 나머지는 로컬 분석")
                break

            provider = self._get_available_provider()
            if not provider:
                print("   >> 모든 LLM 프로바이더 소진 → 로컬 사전 폴백")
                break

            batch_size = provider['batch_size']
            chunk = posts[i:i + batch_size]

            batch_results = self._call_llm_batch(provider, chunk, gallery_name)
            if batch_results:
                results.update(batch_results)
                batch_count += 1
            else:
                # 실패한 배치는 카운트하지 않고, 같은 청크를 다음 프로바이더로 재시도
                continue

            i += batch_size

            # RPM 제한 대응: 호출 간 sleep
            if i < len(posts):
                time.sleep(provider['sleep'])

        # LLM 미처리분 → 로컬 사전 분석
        local_fallback_count = 0
        for post in posts:
            if post['id'] not in results:
                results[post['id']] = self.analyze_locally(post['title'])
                local_fallback_count += 1

        if local_fallback_count > 0:
            print(f"   >> 로컬 사전 폴백: {local_fallback_count}개")

        return results

    # ── 메인 처리 ────────────────────────────────────────────────

    def process_all_unbound_posts(self, force=False):
        """게시글 감성 분석. LLM 배치 분석 → RPC 벌크 업데이트."""
        from config import TARGET_GALLERIES

        FETCH_SIZE = 1000
        RPC_BATCH = 500
        total_count = 0
        offset = 0

        try:
            while True:
                query = self.db.client.table('posts').select('id, title, gallery_id')
                if not force:
                    query = query.is_('analyzed_at', 'null')

                response = query.order('id').range(offset, offset + FETCH_SIZE - 1).execute()
                if not hasattr(response, 'data') or not response.data:
                    break

                # gallery_id별 그룹핑 → LLM 배치 분석
                sorted_posts = sorted(response.data, key=lambda x: x['gallery_id'])
                ids = []
                scores = []

                for gallery_id, group_iter in groupby(sorted_posts, key=lambda x: x['gallery_id']):
                    group = list(group_iter)
                    gallery_info = next((g for g in TARGET_GALLERIES if g['id'] == gallery_id), None)
                    gallery_name = gallery_info['name'] if gallery_info else gallery_id

                    print(f">> [{gallery_name}] {len(group)}개 게시글 분석 시작")
                    batch_results = self.analyze_batch_with_llm(group, gallery_name)

                    for post in group:
                        score = batch_results.get(post['id'], self.analyze_locally(post['title']))
                        ids.append(post['id'])
                        scores.append(score)

                # RPC로 벌크 업데이트 (500개씩)
                for i in range(0, len(ids), RPC_BATCH):
                    batch_ids = ids[i:i + RPC_BATCH]
                    batch_scores = scores[i:i + RPC_BATCH]
                    try:
                        self.db.client.rpc('bulk_update_sentiment', {
                            'ids': batch_ids,
                            'scores': batch_scores
                        }).execute()
                    except Exception as rpc_err:
                        print(f">> RPC 실패, 개별 업데이트 폴백: {rpc_err}")
                        self._fallback_individual_update(batch_ids, batch_scores)

                batch_count = len(response.data)
                total_count += batch_count
                offset += batch_count
                print(f">> 배치 완료: {batch_count}개 처리 (누적: {total_count}개)", flush=True)

                if batch_count < FETCH_SIZE:
                    break

            return total_count
        except Exception as e:
            print(f"게시글 감성 분석 처리 중 오류: {e}")
            return total_count

    def _fallback_individual_update(self, ids, scores):
        """RPC 실패 시 개별 update + 쿨다운 폴백."""
        now = datetime.now().isoformat()
        for i, (pid, score) in enumerate(zip(ids, scores)):
            try:
                self.db.client.table('posts').update({
                    'sentiment_score': score,
                    'analyzed_at': now
                }).eq('id', pid).execute()
            except Exception:
                time.sleep(5)
                try:
                    self.db.client.table('posts').update({
                        'sentiment_score': score,
                        'analyzed_at': now
                    }).eq('id', pid).execute()
                except:
                    pass
            if (i + 1) % 200 == 0:
                print(f"   폴백: {i + 1}/{len(ids)} 처리중...", flush=True)
                time.sleep(5)
