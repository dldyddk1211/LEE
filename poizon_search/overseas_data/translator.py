"""
translator.py
googletrans 비공식 라이브러리를 이용한 일본어 → 한국어 번역
"""

import logging
import time

logger = logging.getLogger(__name__)

# 번역기 초기화
try:
    from googletrans import Translator
    _translator = Translator()
    TRANSLATE_AVAILABLE = True
    logger.info("✅ googletrans 초기화 성공")
except Exception:
    TRANSLATE_AVAILABLE = False
    _translator = None
    logger.warning("⚠️ googletrans 초기화 실패 — 커스텀 단어장만 사용")

# 번역 캐시
_cache = {}

CUSTOM_DICT = {
    "ナイキ": "나이키", "アディダス": "아디다스", "アシックス": "아식스",
    "ニューバランス": "뉴발란스", "プーマ": "푸마", "ミズノ": "미즈노",
    "アンダーアーマー": "언더아머", "コンバース": "컨버스", "ヴァンズ": "반스",
    "リーボック": "리복", "DUARIG": "듀아리그",
    "スニーカー": "스니커즈", "ランニングシューズ": "러닝화",
    "トレーニングシューズ": "트레이닝화", "ジョギングシューズ": "조깅화",
    "サッカースパイク": "축구화", "フットサルシューズ": "풋살화",
    "バスケットボールシューズ": "농구화", "ウォーキングシューズ": "워킹화",
    "シャツ": "셔츠", "パンツ": "팬츠", "ジャケット": "자켓",
    "ウェア": "웨어", "ソックス": "양말", "キャップ": "캡",
    "メンズ": "남성", "レディース": "여성", "キッズ": "키즈",
    "ユニセックス": "유니섹스", "部活": "클럽활동",
}


def apply_custom_dict(text: str) -> str:
    for ja, ko in CUSTOM_DICT.items():
        text = text.replace(ja, ko)
    return text


def translate_ja_ko(text: str, retries: int = 3) -> str:
    if not text or not text.strip():
        return text
    if text in _cache:
        return _cache[text]

    pre_translated = apply_custom_dict(text)

    if not TRANSLATE_AVAILABLE:
        _cache[text] = pre_translated
        return pre_translated

    for attempt in range(retries):
        try:
            result = _translator.translate(pre_translated, src="ja", dest="ko")
            translated = result.text.strip()
            _cache[text] = translated
            return translated
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
            else:
                logger.debug(f"번역 실패 (원문 반환): {e}")
                return text
    return text


def translate_brand(brand: str) -> str:
    if not brand:
        return brand
    if brand.isascii():
        return brand
    return translate_ja_ko(brand)
