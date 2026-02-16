import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import openpyxl
from openpyxl.drawing.image import Image as XLImage
import requests
from io import BytesIO

############################
# ===== USER CONFIG ===== #
############################

MODE = "TEST"
SEARCH_KEYWORD = "나이키"
HEADLESS = False
POIZON_ID = "sionejj@naver.com"
POIZON_PW = "wnaoddl1!"
LOGIN_URL = "https://seller.poizon.com/"
GOODS_SEARCH_URL = "https://seller.poizon.com/main/goods/search"
LOG_DIR = "logs"
SHOT_DIR = "shots"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_MAX_PAGES = 2

############################


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"runlog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    f = open(log_path, "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, f)
    sys.stderr = sys.stdout
    print("=== RUN START ===")
    print("LOG PATH:", log_path)
    print("MODE:", MODE)
    print("SEARCH_KEYWORD:", SEARCH_KEYWORD)
    return log_path


def safe_screenshot(page, name: str):
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.png")
    try:
        page.screenshot(path=path, full_page=True)
        print("📸 screenshot saved:", path)
    except Exception as e:
        print("⚠️ screenshot failed:", e)


def wait_for_inputs(page):
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    try:
        page.wait_for_function("document.querySelectorAll('input').length > 0", timeout=6000)
    except Exception:
        pass


def fill_first(page, selectors, value, step_name="fill"):
    last_err = None
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=2000)  # 3000 → 2000
            page.fill(sel, value)
            print(f"✅ {step_name} OK:", sel)
            return sel
        except Exception as e:
            last_err = e
    raise last_err


def click_first(page, selectors, step_name="click"):
    last_err = None
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=2000)  # 3000 → 2000
            page.click(sel)
            print(f"✅ {step_name} OK:", sel)
            return sel
        except Exception as e:
            last_err = e
    raise last_err


def wait_stable(page, ms=600):
    """기본 대기 - networkidle 생략"""
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(ms)


def set_language_korean(page):
    print("\n[1-1] 언어 한국어로 변경")
    try:
        current_lang = page.locator("text=English").first
        if current_lang.count() == 0:
            print("  ✅ 이미 한국어")
            return
        page.click("text=English", timeout=5000)
        page.wait_for_timeout(500)  # 원래 속도로 복구
        page.click("text=한국어", timeout=5000)
        page.wait_for_timeout(800)  # 원래 속도로 복구
        print("  ✅ 한국어 변경 완료")
    except Exception as e:
        print(f"  ⚠️ 언어 변경 실패: {e}")


def try_sort_descending(page):
    print("\n[4-1] 중국 시장 최근 30일 판매량 내림차순 정렬")
    
    try:
        sales_th = page.locator("th").nth(12)
        icon = sales_th.locator("span.anticon")
        
        if icon.count() > 0:
            icon.last.click()
            page.wait_for_timeout(600)  # 변경 없음
            
            page.locator("text=내림차순").first.click()
            page.wait_for_timeout(400)  # 변경 없음
            page.locator("button:has-text('확인')").first.click()
            page.wait_for_timeout(1000)  # 1500 → 1000
            print("  ✅ 내림차순 정렬 완료")
            return True
    except Exception as e:
        print(f"  ⚠️ 정렬 실패: {e}")
    
    return False


def download_image(url):
    """이미지 다운로드"""
    try:
        response = requests.get(url, timeout=5)  # 10 → 5
        if response.status_code == 200:
            return BytesIO(response.content)
    except Exception:
        pass
    return None


def scrape_current_page(page):
    """현재 페이지 데이터 수집"""
    rows_data = []
    try:
        page.wait_for_selector(".ant-table-tbody tr:not(.ant-table-measure-row)", timeout=8000)
        rows = page.locator(".ant-table-tbody tr:not(.ant-table-measure-row)")
        count = rows.count()
        print(f"  → 현재 페이지 행 수: {count}")

        for i in range(count):
            try:
                row = rows.nth(i)
                cells = row.locator("td")
                
                # 이미지 URL - 빠른 추출 (타임아웃 없음)
                img_url = ""
                try:
                    # td[1]에서 img 찾기 (가장 일반적)
                    imgs = cells.nth(1).locator("img")
                    if imgs.count() > 0:
                        img_url = imgs.first.get_attribute("src")
                except Exception:
                    pass
                
                # td[1]에 없으면 row 전체에서 찾기
                if not img_url:
                    try:
                        imgs = row.locator("img")
                        if imgs.count() > 0:
                            img_url = imgs.first.get_attribute("src")
                    except Exception:
                        pass

                # td[2]: 상품번호 + 제품명 + SPU_ID
                item_info = cells.nth(2).inner_text()
                lines = [l.strip() for l in item_info.split("\n") if l.strip()]
                
                style_id = ""
                item_name = ""
                spu_id = ""
                
                for line in lines:
                    if "상품번호:" in line or "상품번호" in line:
                        style_id = line.replace("상품번호:", "").replace("상품번호", "").strip()
                    elif "SPU_ID" in line or "SPU_ID：" in line:
                        spu_id = line.replace("SPU_ID：", "").replace("SPU_ID:", "").replace("SPU_ID", "").strip()
                    elif not style_id and not spu_id:
                        if not item_name:
                            item_name = line
                
                if not item_name and len(lines) >= 2:
                    item_name = lines[1]

                brand_category = cells.nth(3).inner_text().replace("\n", " / ")
                status = cells.nth(4).inner_text()
                avg_price = cells.nth(5).inner_text()
                cn_exposure = cells.nth(6).inner_text()
                cn_sales = cells.nth(7).inner_text()
                local_sales = cells.nth(8).inner_text()

                rows_data.append({
                    "이미지URL": img_url,
                    "상품번호": style_id,
                    "제품명": item_name,
                    "SPU_ID": spu_id,
                    "상태": status,
                    "최근30일평균거래가": avg_price,
                    "중국노출": cn_exposure,
                    "중국시장최근30일판매량": cn_sales,
                    "현지판매자최근30일판매량": local_sales,
                })
                
                print(f"    [{i+1}/{count}] ✓ {style_id} | {item_name[:30]}... | 판매량:{cn_sales}")

            except Exception as e:
                print(f"    [{i+1}/{count}] ✗ 파싱 실패: {e}")
                continue

    except Exception as e:
        print(f"⚠️ scrape_current_page 오류: {e}")

    return rows_data


def save_to_excel(all_data, keyword):
    filename = f"poizon_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = os.path.join(OUTPUT_DIR, filename)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "검색결과"
    
    headers = ["이미지", "상품번호", "제품명", "SPU_ID", "상태", 
               "최근30일평균거래가", "중국노출", "중국시장최근30일판매량", "현지판매자최근30일판매량"]
    ws.append(headers)

    ws.row_dimensions[1].height = 20

    row_num = 2
    for data in all_data:
        ws.append([
            "",
            data.get("상품번호", ""),
            data.get("제품명", ""),
            data.get("SPU_ID", ""),
            data.get("상태", ""),
            data.get("최근30일평균거래가", ""),
            data.get("중국노출", ""),
            data.get("중국시장최근30일판매량", ""),
            data.get("현지판매자최근30일판매량", ""),
        ])

        # 이미지 다운로드 & 삽입
        img_url = data.get("이미지URL", "")
        if img_url:
            try:
                img_data = download_image(img_url)
                if img_data:
                    img = XLImage(img_data)
                    img.width = 60
                    img.height = 60
                    ws.add_image(img, f'A{row_num}')
                    ws.row_dimensions[row_num].height = 50
            except Exception:
                pass

        row_num += 1

    # 컬럼 너비
    ws.column_dimensions['A'].width = 10
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 18
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 22
    ws.column_dimensions['I'].width = 25

    wb.save(filepath)
    print(f"💾 엑셀 저장 완료: {filepath} ({len(all_data)}행)")
    return filepath


def run():
    setup_logging()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context()
        page = context.new_page()

        try:
            print("\n[1] 접속:", LOGIN_URL)
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            wait_stable(page, 500)  # 200 → 500으로 증가

            set_language_korean(page)

            print("\n[2] 로그인")
            wait_for_inputs(page)
            page.locator("input").nth(0).fill(POIZON_ID)
            page.locator("input").nth(1).fill(POIZON_PW)

            try:
                click_first(page, ["button:has-text('로그인')"], "로그인")
            except Exception:
                page.locator("input").nth(1).press("Enter")

            wait_stable(page, 400)  # 600 → 400

            print("\n[3] 상품 검색 페이지 이동")
            page.goto(GOODS_SEARCH_URL, wait_until="domcontentloaded")
            wait_stable(page, 1000)

            print("\n[4] 키워드 입력:", SEARCH_KEYWORD)
            wait_for_inputs(page)
            fill_first(page, ["input[placeholder*='상품명']"], SEARCH_KEYWORD, "키워드")

            try:
                click_first(page, ["button:has-text('검색 및 입찰')"], "검색")
            except Exception:
                page.keyboard.press("Enter")

            wait_stable(page, 1600)  # 2000 → 1600
            try_sort_descending(page)

            max_pages = TEST_MAX_PAGES if MODE == "TEST" else 9999
            print(f"\n[5] 수집 시작 (최대 {max_pages}페이지)")
            all_data = []
            page_num = 1

            while page_num <= max_pages:
                print(f"\n  📄 페이지 {page_num} 수집 중...")
                page_data = scrape_current_page(page)
                all_data.extend(page_data)
                print(f"  ✅ 페이지 {page_num} 완료: {len(page_data)}개 수집 (누계: {len(all_data)}개)")

                if page_num >= max_pages:
                    print(f"\n  ⏹ 최대 페이지({max_pages}) 도달")
                    break

                try:
                    next_btn = page.locator("li.ant-pagination-next:not(.ant-pagination-disabled) button")
                    if next_btn.count() == 0 or not next_btn.first.is_enabled():
                        print("\n  ⏹ 마지막 페이지")
                        break

                    next_btn.first.click()
                    wait_stable(page, 1200)  # 1200 유지
                    page_num += 1
                except Exception as e:
                    print(f"\n  ⏹ 다음 페이지 오류: {e}")
                    break

            print(f"\n[6] 총 {len(all_data)}개 수집 완료")
            save_to_excel(all_data, SEARCH_KEYWORD)
            safe_screenshot(page, "done")
            print("\n=== 완료 ===")

        except Exception as e:
            print(f"⛔ Error: {e}")
            safe_screenshot(page, "error")
        finally:
            page.wait_for_timeout(1000)
            browser.close()


if __name__ == "__main__":
    run()