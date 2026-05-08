import os
import time
import re
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from db_manager import DBManager
from config import TARGET_GALLERIES
import pandas as pd

load_dotenv()

KST = timezone(timedelta(hours=9))


class Summarizer:
    """AI 여론 요약 생성기: gemini-2.5-flash 전용"""

    MODEL = 'gemini-2.5-flash'
    PERIODS = [1, 7]

    def __init__(self):
        self.db = DBManager()
        self.gemini_client = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai as google_genai
                self.gemini_client = google_genai.Client(api_key=gemini_key)
                print(">> Summarizer: Gemini 클라이언트 초기화 완료")
            except Exception as e:
                print(f">> Summarizer: Gemini 초기화 실패: {e}")
        else:
            print(">> Summarizer: GEMINI_API_KEY가 설정되지 않았습니다.")

    def _fetch_summary_data(self, gallery_id, days):
        """요약용 데이터를 수집합니다."""
        target_date = (datetime.now(KST) - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()

        FETCH_SIZE = 1000
        all_data = []
        offset = 0
        while True:
            response = self.db.client.table('posts') \
                .select('title, sentiment_score, views, recommend, comment_count') \
                .eq('gallery_id', gallery_id) \
                .gte('date_standard', target_date) \
                .order('date_standard', desc=True) \
                .range(offset, offset + FETCH_SIZE - 1) \
                .execute()
            if hasattr(response, 'data') and response.data:
                all_data.extend(response.data)
                if len(response.data) < FETCH_SIZE:
                    break
                offset += FETCH_SIZE
            else:
                break

        if not all_data:
            return None

        df = pd.DataFrame(all_data)
        df['engagement_score'] = df['views'] + df['recommend'] + df['comment_count']

        total = len(df)
        pos_df = df[df['sentiment_score'] > 0.1].sort_values('engagement_score', ascending=False)
        neg_df = df[df['sentiment_score'] < -0.1].sort_values('engagement_score', ascending=False)

        trend = self._fetch_trend(gallery_id, days)

        return {
            'total_count': total,
            'pos_count': len(pos_df),
            'neg_count': len(neg_df),
            'neu_count': total - len(pos_df) - len(neg_df),
            'avg_score': round(df['sentiment_score'].mean(), 4),
            'pos_posts': pos_df.head(10).to_dict('records'),
            'neg_posts': neg_df.head(10).to_dict('records'),
            'trend': trend,
        }

    def _fetch_trend(self, gallery_id, days):
        """일별 통계를 조회합니다."""
        end_date = datetime.now(KST).date()
        start_date = end_date - timedelta(days=days - 1)
        try:
            response = self.db.client.table('daily_stats') \
                .select('stat_date, total_count, pos_count, neg_count, avg_score') \
                .eq('gallery_id', gallery_id) \
                .gte('stat_date', start_date.isoformat()) \
                .order('stat_date') \
                .execute()
            return response.data or []
        except Exception:
            return []

    def _build_summary_prompt(self, gallery_name, period, data):
        """한국어 요약 프롬프트를 생성합니다."""
        pos_pct = round(data['pos_count'] / data['total_count'] * 100, 1) if data['total_count'] else 0
        neg_pct = round(data['neg_count'] / data['total_count'] * 100, 1) if data['total_count'] else 0

        pos_lines = []
        for p in data['pos_posts']:
            pos_lines.append(f"- \"{p['title']}\" (감성: +{p['sentiment_score']}, 공감: {p['engagement_score']})")
        neg_lines = []
        for p in data['neg_posts']:
            neg_lines.append(f"- \"{p['title']}\" (감성: {p['sentiment_score']}, 공감: {p['engagement_score']})")

        trend_lines = []
        for t in data['trend']:
            if t['total_count'] > 0:
                t_pos_pct = round(t['pos_count'] / t['total_count'] * 100, 1)
                t_neg_pct = round(t['neg_count'] / t['total_count'] * 100, 1)
                trend_lines.append(f"- {t['stat_date']}: 총 {t['total_count']}건, 긍정 {t_pos_pct}%, 부정 {t_neg_pct}%, 평균 {t['avg_score']}")

        return f"""당신은 한국 게임 커뮤니티(디시인사이드) 여론 분석 전문가입니다.
다음은 '{gallery_name}' 갤러리의 최근 {period}일간 커뮤니티 여론 데이터입니다.

[전체 통계]
- 총 게시글: {data['total_count']}개
- 긍정 비율: {pos_pct}% ({data['pos_count']}건)
- 부정 비율: {neg_pct}% ({data['neg_count']}건)
- 평균 감성 점수: {data['avg_score']}

[긍정 대표글 (공감순 Top 10)]
{chr(10).join(pos_lines) if pos_lines else '- (없음)'}

[부정 대표글 (공감순 Top 10)]
{chr(10).join(neg_lines) if neg_lines else '- (없음)'}

[일별 추이]
{chr(10).join(trend_lines) if trend_lines else '- (데이터 없음)'}

위 데이터를 바탕으로 한국어 3~5문장의 여론 요약을 작성하세요.

[작성 규칙]
1. 전반적인 커뮤니티 분위기(긍정적/부정적/혼재)를 먼저 언급하세요.
2. 긍정 여론의 주요 화제를 구체적으로 설명하세요.
3. 부정 여론의 주요 화제를 구체적으로 설명하세요.
4. 기간 내 눈에 띄는 추세 변화가 있다면 언급하세요.
5. 자연스러운 한국어로 작성하되, 마크다운이나 특수 서식 없이 순수 텍스트로만 응답하세요."""

    def _save_summary(self, gallery_id, period, summary_text):
        """요약을 summaries 테이블에 저장합니다."""
        today = datetime.now(KST).strftime('%Y-%m-%d')
        try:
            self.db.client.table('summaries') \
                .delete() \
                .eq('gallery_id', gallery_id) \
                .eq('period', period) \
                .eq('summary_date', today) \
                .execute()
        except Exception:
            pass

        self.db.client.table('summaries').insert({
            'gallery_id': gallery_id,
            'period': period,
            'summary_text': summary_text,
            'model_used': self.MODEL,
            'summary_date': today,
            'generated_at': datetime.now(KST).isoformat()
        }).execute()

    def _generate_summary(self, gallery_name, gallery_id, period):
        """단일 갤러리+기간 조합의 요약을 생성합니다."""
        data = self._fetch_summary_data(gallery_id, period)
        if not data or data['total_count'] < 5:
            print(f"   [{gallery_name}/{period}일] 데이터 부족 ({data['total_count'] if data else 0}건), 스킵")
            return False

        prompt = self._build_summary_prompt(gallery_name, period, data)

        try:
            response = self.gemini_client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
            )
            summary_text = response.text.strip()
            summary_text = re.sub(r'```\w*\s*', '', summary_text).strip()
            summary_text = re.sub(r'\*\*|##|__', '', summary_text).strip()

            if len(summary_text) > 1000:
                summary_text = summary_text[:1000]

            self._save_summary(gallery_id, period, summary_text)
            print(f"   [{gallery_name}/{period}일] 요약 생성 완료 ({len(summary_text)}자)")
            return True

        except Exception as e:
            print(f"   [{gallery_name}/{period}일] Gemini API 오류: {e}")
            return False

    def generate_all_summaries(self):
        """모든 갤러리의 1일/7일 요약을 생성합니다."""
        if not self.gemini_client:
            print(">> Gemini 클라이언트 없음, 요약 생성 불가")
            return

        print(f"\n{'='*50}")
        print(f">> AI 여론 요약 생성 시작 ({datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST)")
        print(f"{'='*50}")

        success = 0
        total = 0
        for gallery in TARGET_GALLERIES:
            print(f"\n>> [{gallery['name']}] 요약 생성 중...")
            for period in self.PERIODS:
                total += 1
                if self._generate_summary(gallery['name'], gallery['id'], period):
                    success += 1
                time.sleep(4)

        print(f"\n>> 요약 생성 완료: {success}/{total}건 성공")


if __name__ == "__main__":
    Summarizer().generate_all_summaries()
