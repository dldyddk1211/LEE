"""
site_config.py
사이트 / 카테고리 설정 — 크롤링 대상 관리
"""

from urllib.parse import urlencode

SITES = {
    "xebio": {
        "name": "제비오 (Xebio)",
        "domain": "https://www.supersports.com",
        "base_url": "https://www.supersports.com/ja-jp/xebio",
        "categories": {
            "sale": {
                "name": "세일",
                "name_ja": "セール",
                "params": {"discount": "sale"},
            },
            "running": {
                "name": "런닝",
                "name_ja": "ランニング",
                "params": {"category": "running"},
            },
            "soccer-futsal": {
                "name": "축구/풋살",
                "name_ja": "サッカー・フットサル",
                "params": {"category": "soccer-futsal"},
            },
            "basketball": {
                "name": "농구",
                "name_ja": "バスケットボール",
                "params": {"category": "basketball"},
            },
            "tennis": {
                "name": "테니스",
                "name_ja": "テニス",
                "params": {"category": "tennis"},
            },
            "golf": {
                "name": "골프",
                "name_ja": "ゴルフ",
                "params": {"category": "golf"},
            },
            "training": {
                "name": "트레이닝",
                "name_ja": "トレーニング",
                "params": {"category": "training"},
            },
        },
    },
}


def get_site(site_id: str) -> dict:
    return SITES.get(site_id)


def get_category(site_id: str, cat_id: str) -> dict:
    site = SITES.get(site_id)
    if not site:
        return None
    return site["categories"].get(cat_id)


def build_url(site_id: str, cat_id: str) -> str:
    site = SITES.get(site_id)
    if not site:
        return ""
    cat = site["categories"].get(cat_id)
    if not cat:
        return ""
    return f"{site['base_url']}/products/?{urlencode(cat['params'])}"
