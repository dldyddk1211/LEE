"""
xebio_search.py
Xebio 사이트 상품 스크래핑 (Playwright 기반)
— jp_sourcing 프로젝트에서 포팅
"""

import asyncio
import json
import os
import re
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from overseas_data.translator import translate_ja_ko, translate_brand
from overseas_data.site_config import get_site, get_category, build_url

logger = logging.getLogger(__name__)

# ── 전역 상태 ────────────────────────────────
_app_status = None
_browser = None
_playwright = None

# 스크래핑 딜레이 (초)
SCRAPE_DELAY = 1.5

# 출력 경로 (overseas_data/output/)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def set_app_status(status_dict):
    global _app_status
    _app_status = status_dict


def _check_flag(flag: str) -> bool:
    if _app_status is None:
        return False
    if flag == "pause":
        return _app_status.get("paused", False)
    if flag == "stop":
        return _app_status.get("stop_requested", False)
    return False


async def force_close_browser():
    global _browser, _playwright
    try:
        if _browser:
            await _browser.close()
            _browser = None
            logger.info("🔄 브라우저 강제 종료 완료")
        if _playwright:
            await _playwright.stop()
            _playwright = None
    except Exception as e:
        logger.debug(f"브라우저 종료 오류 (무시): {e}")


# ── 페이지 지정 파싱 ─────────────────────────
def _parse_pages(pages_str: str) -> list:
    if not pages_str or not pages_str.strip():
        return []
    pages_str = pages_str.strip()
    result = set()
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start, end = int(bounds[0].strip()), int(bounds[1].strip())
                for p in range(start, end + 1):
                    if p >= 1:
                        result.add(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if p >= 1:
                    result.add(p)
            except ValueError:
                continue
    return sorted(result)


# =============================================
# 메인 스크래핑 함수
# =============================================

async def scrape_xebio(status_callback=None,
                       site_id="xebio", category_id="sale",
                       keyword="", pages="", brand_code=""):
    """
    지정 사이트/카테고리에서 상품 수집

    Args:
        status_callback : 진행상황 문자열을 실시간으로 전달할 콜백 함수
        site_id         : 사이트 ID (예: "xebio")
        category_id     : 카테고리 ID (예: "sale", "running")
        keyword         : 검색 키워드 (비어있으면 전체)
        pages           : 페이지 지정 (예: "2-10", "2,3,5", "2", 비우면 전체)

    Returns:
        list: 수집된 상품 딕셔너리 리스트
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    products = []

    def log(msg):
        logger.info(msg)
        if status_callback:
            status_callback(msg)

    async with async_playwright() as p:
        global _browser, _playwright
        _playwright = p
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--window-size=1280,900"]
        )
        _browser = browser
        context = await browser.new_context(
            locale="ja-JP",
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            # ── 사이트/카테고리 URL 결정 ─────────────────
            site_info = get_site(site_id)
            cat_info = get_category(site_id, category_id)
            CATEGORY_URL = build_url(site_id, category_id, brand_code)
            site_name = site_info["name"] if site_info else "Xebio"
            cat_name = cat_info["name"] if cat_info else "세일"
            base_url = site_info["base_url"] if site_info else "https://www.supersports.com/ja-jp/xebio"
            domain = site_info["domain"] if site_info else "https://www.supersports.com"

            target_pages = _parse_pages(pages)

            if not CATEGORY_URL:
                CATEGORY_URL = "https://www.supersports.com/ja-jp/xebio/products/?discount=sale"

            kw_label = f" [{keyword}]" if keyword else ""

            # ── STEP 1: 메인 접속 ──────────────────
            log("━" * 45)
            log(f"🚀 [STEP 1/5] {site_name} 메인 페이지 접속 중...")
            log(f"   🌐 접속 URL: {base_url}")
            await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            log("   ✅ 메인 페이지 접속 완료!")

            # ── STEP 2: 카테고리 이동 ────────
            log("━" * 45)
            log(f"🏷️  [STEP 2/5] {cat_name} 페이지로 이동 중...")
            await page.goto(CATEGORY_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            log(f"   ✅ {cat_name} 페이지 이동 완료!")
            log(f"   🔗 현재 URL: {page.url}")

            # ── STEP 3: 키워드 검색 ────────
            if keyword:
                log("━" * 45)
                log(f"🔍 [STEP 3/5] 키워드 검색: {keyword}")

                search_selectors = [
                    'input[placeholder*="絞り込む"]',
                    'input[placeholder*="さらに"]',
                    'input.middle[type="search"]',
                    'input[type="search"]',
                ]
                search_input = None
                for sel in search_selectors:
                    try:
                        el = page.locator(sel).first
                        if await el.is_visible(timeout=3000):
                            search_input = el
                            log(f"   ✅ 검색창 발견: {sel}")
                            break
                    except Exception:
                        continue

                if search_input:
                    await search_input.click()
                    await asyncio.sleep(0.5)
                    await search_input.fill(keyword)
                    await asyncio.sleep(0.5)
                    await search_input.press("Enter")
                    log(f"   ⌨️ '{keyword}' 입력 후 검색 실행")
                    await asyncio.sleep(3)
                    for sel in [".product-tile", ".product-item", "[class*='product-card']"]:
                        try:
                            await page.wait_for_selector(sel, timeout=8000)
                            break
                        except Exception:
                            continue
                    log(f"   ✅ 검색 완료! URL: {page.url}")
                else:
                    log("   ⚠️ 검색창을 찾지 못함 — 키워드 없이 진행합니다")
            else:
                log("━" * 45)
                log(f"🔍 [STEP 3/5] 키워드 없음 — 전체 상품 수집")

            # ── STEP 4: 수집 준비 ────────
            log("━" * 45)
            log(f"🛍️  [STEP 4/5] {site_name} › {cat_name}{kw_label} 상품 수집 준비 중...")
            if target_pages:
                log(f"   📄 지정 페이지: {pages}")
            else:
                log("   📋 전체 상품을 수집합니다")
            log(f"   ✅ 준비 완료! 현재 URL: {page.url}")

            # ── STEP 5: 페이지 순회 ──────────────────
            log("━" * 45)
            log(f"📦 [STEP 5/5] 상품 수집 시작!{kw_label}")
            total = await _get_total_count(page)
            if total:
                log(f"   📊 총 수집 대상: 약 {total:,}개 상품")

            current_page = 1
            prev_product_links = set()
            max_target_page = max(target_pages) if target_pages else None

            while True:
                # 리셋 체크
                if status_callback and _check_flag("stop"):
                    log("🔄 리셋 요청 — 수집을 중단합니다")
                    return []

                # 일시정지 체크
                if status_callback and _check_flag("pause"):
                    log("⏸️ 일시정지 중... (재개 버튼을 누르면 계속됩니다)")
                    while _check_flag("pause"):
                        await asyncio.sleep(1)
                        if _check_flag("stop"):
                            return []
                    log("▶️ 수집 재개!")

                if current_page == 1:
                    log(f"   📄 [{current_page}페이지] 상품 파싱 중...")
                    log(f"   🔗 {page.url}")
                else:
                    log(f"   📄 [{current_page}페이지] 다음 페이지로 이동 중...")
                    moved = await _go_next_page(page, domain)
                    if not moved:
                        log("   ✅ 마지막 페이지 도달! (다음 버튼 없음)")
                        break
                    for sel in [".product-tile", ".product-item", "[class*='product-card']"]:
                        try:
                            await page.wait_for_selector(sel, timeout=5000)
                            break
                        except Exception:
                            continue
                    await asyncio.sleep(3)

                # 페이지 지정 모드: 해당 페이지 아니면 건너뛰기
                if target_pages and current_page not in target_pages:
                    log(f"   ⏭️ [{current_page}페이지] 건너뜀 (지정 페이지 아님)")
                    if max_target_page and current_page >= max_target_page:
                        log(f"   🛑 지정 페이지 수집 완료!")
                        break
                    current_page += 1
                    await asyncio.sleep(0.5)
                    continue

                log(f"   ✅ 실제 URL: {page.url}")

                page_products = await _parse_product_list(page, domain)
                log(f"   📦 이 페이지에서 수집: {len(page_products)}개")

                if not page_products:
                    log("   ✅ 마지막 페이지 도달! (상품 없음)")
                    break

                curr_links = set(p.get("link", "") for p in page_products)
                if curr_links and curr_links == prev_product_links:
                    log(f"   ⚠️ 이전 페이지와 동일한 상품 — 마지막 페이지로 판단")
                    break
                prev_product_links = curr_links

                products.extend(page_products)
                pct = int(len(products) / total * 100) if total else 0
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                log(f"   [{bar}] {pct}% — {len(page_products)}개 수집 / 누적: {len(products):,}개")

                if max_target_page and current_page >= max_target_page:
                    log(f"   🛑 지정 페이지 수집 완료!")
                    break

                current_page += 1
                await asyncio.sleep(SCRAPE_DELAY)

            # ── 상세 페이지 수집 ──────────────────
            log("━" * 45)
            log(f"🔎 [STEP 6] 상품 상세 페이지 수집 시작!")
            log(f"   📋 총 {len(products):,}개 상품 상세 페이지 방문 예정")
            log(f"   ⏱️  예상 소요 시간: 약 {len(products) * 2 // 60}분")

            for i, product in enumerate(products, 1):
                if status_callback and _check_flag("stop"):
                    log("🔄 리셋 요청 — 상세 수집 중단")
                    return []
                while status_callback and _check_flag("pause"):
                    log("⏸️ 일시정지 중...")
                    await asyncio.sleep(1)
                    if _check_flag("stop"):
                        return []
                    log("▶️ 재개!")

                link = product.get("link", "")
                if not link:
                    continue

                pct = int(i / len(products) * 100)
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                if i % 10 == 1 or i == len(products):
                    log(f"   [{bar}] {pct}% — {i:,}/{len(products):,} 상세 수집 중...")

                try:
                    if not link.startswith("http"):
                        link = domain + link
                    if i <= 3:
                        log(f"   🔗 상세 URL 확인: {link}")
                    detail = await _scrape_detail_page(page, link, domain)
                    product.update(detail)
                except Exception as e:
                    log(f"   ⚠️ 상세 오류 ({link[:60]}): {e}")

                if status_callback and _check_flag("stop"):
                    log("🔄 리셋 — 상세 수집 즉시 중단")
                    return []

                await asyncio.sleep(SCRAPE_DELAY)

            log("   ✅ 상세 페이지 수집 완료!")

        except PlaywrightTimeout as e:
            log(f"⏰ 타임아웃: {e}")
        except Exception as e:
            log(f"❌ 오류 발생: {e}")
            logger.exception(e)
        finally:
            await browser.close()
            _browser = None
            _playwright = None

    if products:
        for p in products:
            p["site_id"] = site_id
            p["category_id"] = category_id

        save_products(products)

        log("━" * 45)
        log(f"🎉 전체 수집 완료!")
        log(f"   📦 총 수집: {len(products):,}개 상품 (목록 + 상세)")
        log(f"   💾 결과 저장 완료")
        log("━" * 45)

    return products


# =============================================
# 사이트 조작 함수
# =============================================

async def _get_total_count(page):
    for sel in [".product-count", "[class*='count']", "[class*='total']", ".search-results"]:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                text = await el.inner_text()
                numbers = re.findall(r'[\d,]+', text)
                if numbers:
                    return int(numbers[0].replace(",", ""))
        except Exception:
            continue
    return 0


async def _parse_product_list(page, domain):
    products = []
    card_selectors = [
        ".product-tile", ".product-item", ".product-list__item",
        "[class*='product-card']", "li.product", ".item-box",
    ]
    items = None
    for sel in card_selectors:
        cnt = await page.locator(sel).count()
        if cnt > 0:
            items = page.locator(sel)
            logger.info(f"선택자 매칭: {sel} ({cnt}개)")
            break

    if items is None:
        logger.warning("상품 카드 선택자 미매칭")
        return []

    for i in range(await items.count()):
        try:
            product = await _extract_product_info(items.nth(i), domain)
            if product:
                products.append(product)
        except Exception as e:
            logger.debug(f"상품 {i} 파싱 오류: {e}")

    return products


async def _extract_product_info(item, domain):
    try:
        # 브랜드
        brand = ""
        for sel in ["b[class*='caption']", "b.caption", "[class*='caption']"]:
            el = item.locator(sel).first
            if await el.count() > 0:
                txt = (await el.inner_text()).strip()
                if txt:
                    brand = txt
                    break

        # 상품명
        name = ""
        for sel in ["b[class*='title']", "b.title", "[class*='title']", "h2", "h3"]:
            el = item.locator(sel).first
            if await el.count() > 0:
                txt = (await el.inner_text()).strip()
                if txt:
                    name = txt
                    break

        # 가격 (엔화)
        price_jpy = 0
        for sel in ["strong[class*='sale']", "strong.sale", "[class*='sale'] strong", ".price", "strong"]:
            el = item.locator(sel).first
            if await el.count() > 0:
                txt = await el.inner_text()
                numbers = re.findall(r'[\d,]+', txt)
                if numbers:
                    val = int(numbers[0].replace(",", ""))
                    if val > 100:
                        price_jpy = val
                        break

        # 링크
        link = ""
        a_tag = item.locator("a").first
        if await a_tag.count() > 0:
            href = await a_tag.get_attribute("href") or ""
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = domain + href
            elif href:
                link = domain + "/" + href

        # 이미지
        img_url = ""
        for sel in ["img", "[class*='image'] img"]:
            img = item.locator(sel).first
            if await img.count() > 0:
                src = (await img.get_attribute("src") or
                       await img.get_attribute("data-src") or "")
                if src and "placeholder" not in src:
                    img_url = src if src.startswith("http") else (
                        "https:" + src if src.startswith("//") else domain + src
                    )
                break

        if not name and not link:
            return None

        name_ko = translate_ja_ko(name)
        brand_ko = translate_brand(brand)

        return {
            "name": name,
            "name_ko": name_ko,
            "brand": brand,
            "brand_ko": brand_ko,
            "product_code": "",
            "price_jpy": price_jpy,
            "link": link,
            "img_url": img_url,
            "scraped_at": datetime.now().isoformat(),
            "selected": True,
        }

    except Exception as e:
        logger.debug(f"extract 오류: {e}")
        return None


async def _scrape_detail_page(page, url: str, domain: str) -> dict:
    detail = {
        "description": "",
        "sizes": [],
        "detail_images": [],
        "original_price": 0,
        "discount_rate": 0,
        "in_stock": False,
    }

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(1)

        # 품번 (メーカー品番)
        try:
            spec_titles = page.locator("span[class*='title']")
            cnt = await spec_titles.count()
            for i in range(cnt):
                txt = (await spec_titles.nth(i).inner_text()).strip()
                if "品番" in txt or "メーカー" in txt:
                    parent = spec_titles.nth(i).locator("xpath=..")
                    desc = parent.locator("span[class*='description']").first
                    if await desc.count() > 0:
                        code = (await desc.inner_text()).strip()
                        if code:
                            detail["product_code"] = code
                            break
            if not detail.get("product_code"):
                descs = page.locator("span[class*='description']")
                dcnt = await descs.count()
                for i in range(dcnt):
                    val = (await descs.nth(i).inner_text()).strip()
                    if re.match(r'^[A-Z]{1,4}[\d]', val):
                        detail["product_code"] = val
                        break
        except Exception as e:
            logger.debug(f"품번 추출 오류: {e}")

        # 상세 설명
        for sel in ["[class*='description']", ".product-description", ".item-description", "#description"]:
            el = page.locator(sel).first
            if await el.count() > 0:
                txt = (await el.inner_text()).strip()
                if txt and len(txt) > 10:
                    detail["description"] = txt[:500]
                    break

        # 사이즈 + 재고
        size_selectors = [
            "[class*='size'] button", "[class*='size'] li",
            "[class*='size-item']", "[class*='sizeList'] li",
            "button[class*='size']",
        ]
        for sel in size_selectors:
            items = page.locator(sel)
            cnt = await items.count()
            if cnt > 0:
                sizes = []
                for i in range(cnt):
                    item = items.nth(i)
                    size_text = (await item.inner_text()).strip()
                    size_text = re.sub(r'[^\d.]', '', size_text)
                    cls = await item.get_attribute("class") or ""
                    disabled = await item.get_attribute("disabled")
                    in_stock = (
                        "sold" not in cls.lower() and
                        "disable" not in cls.lower() and
                        "unavailable" not in cls.lower() and
                        disabled is None
                    )
                    if size_text:
                        sizes.append({"size": size_text, "in_stock": in_stock})
                if sizes:
                    detail["sizes"] = sizes
                    detail["in_stock"] = any(s["in_stock"] for s in sizes)
                    break

        if not detail["sizes"]:
            for sel in [".sold-out", "[class*='soldout']", "[class*='outOfStock']"]:
                el = page.locator(sel).first
                if await el.count() > 0:
                    detail["in_stock"] = False
                    break
            else:
                detail["in_stock"] = True

        # 정가 vs 세일가
        for sel in ["[class*='original']", "[class*='regular']", "[class*='before']"]:
            el = page.locator(sel).first
            if await el.count() > 0:
                txt = await el.inner_text()
                nums = re.findall(r'[\d,]+', txt)
                if nums:
                    val = int(nums[0].replace(",", ""))
                    if val > 100:
                        detail["original_price"] = val
                        break

        # 상세 이미지
        for sel in ["[class*='thumbnail'] img", "[class*='gallery'] img",
                     "[class*='swiper'] img", "[class*='images'] img"]:
            imgs = page.locator(sel)
            cnt = await imgs.count()
            if cnt > 1:
                urls = []
                for i in range(min(cnt, 8)):
                    src = (await imgs.nth(i).get_attribute("src") or
                           await imgs.nth(i).get_attribute("data-src") or "")
                    if src and "placeholder" not in src:
                        src = src if src.startswith("http") else (
                            "https:" + src if src.startswith("//") else src)
                        urls.append(src)
                if urls:
                    detail["detail_images"] = urls
                    break

    except Exception as e:
        logger.debug(f"상세 수집 오류: {e}")

    # 스펙 전체 수집
    try:
        specs = {}
        titles = page.locator("span[class*='title']")
        cnt = await titles.count()
        for i in range(cnt):
            title_txt = (await titles.nth(i).inner_text()).strip()
            if not title_txt:
                continue
            parent = titles.nth(i).locator("xpath=..")
            desc_el = parent.locator("span[class*='description']").first
            if await desc_el.count() > 0:
                desc_txt = (await desc_el.inner_text()).strip()
                if desc_txt:
                    specs[title_txt] = desc_txt
        if specs:
            detail["specs"] = specs
            if "ブランド" in specs and not detail.get("brand"):
                detail["brand"] = specs["ブランド"]
            if not detail.get("product_code"):
                for key in ["メーカー品番", "品番", "商品コード"]:
                    if key in specs and specs[key]:
                        detail["product_code"] = specs[key]
                        break
    except Exception as e:
        logger.debug(f"스펙 수집 오류: {e}")

    # 상세 설명 번역
    if detail.get("description"):
        try:
            detail["description_ko"] = translate_ja_ko(detail["description"])
        except Exception:
            detail["description_ko"] = detail["description"]
    else:
        detail["description_ko"] = ""

    return detail


async def _go_next_page(page, domain):
    old_url = page.url

    for sel in [
        "a[aria-label='次へ']", "a.pagination__next",
        ".pagination__item--next a", "a:has-text('次へ')",
        "a:has-text('次のページ')", "a:has-text('>')",
        "[class*='next']:not([class*='disabled']) a",
        "nav[class*='pagination'] a:last-child",
        "[class*='pager'] a:last-child",
    ]:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                cls = await btn.get_attribute("class") or ""
                disabled = await btn.get_attribute("disabled")
                if "disabled" not in cls and disabled is None:
                    href = await btn.get_attribute("href") or ""
                    logger.info(f"다음 페이지 버튼 발견: {sel} / href={href[:80]}")

                    if href and href.startswith("http"):
                        await page.goto(href, wait_until="domcontentloaded", timeout=30000)
                    elif href and href.startswith("/"):
                        await page.goto(f"{domain}{href}",
                                        wait_until="domcontentloaded", timeout=30000)
                    else:
                        await btn.click()
                        try:
                            await page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            pass

                    await asyncio.sleep(3)
                    return True
        except Exception as e:
            logger.debug(f"다음 페이지 선택자 오류 ({sel}): {e}")
            continue
    return False


# =============================================
# 저장 / 불러오기
# =============================================

def save_products(products: list) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(OUTPUT_DIR, f"products_{ts}.json")

    for p in [path, os.path.join(OUTPUT_DIR, "latest.json")]:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
    return path


def load_latest_products() -> list:
    path = os.path.join(OUTPUT_DIR, "latest.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
