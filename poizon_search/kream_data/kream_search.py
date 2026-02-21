import os
import sys
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 전역 변수
browser = None
context = None
page = None

# 중단 플래그
stop_flag = False

# 로그 콜백 함수
LOG_CALLBACK = None

def log(message, level='info'):
    """터미널 + GUI 로그 출력"""
    print(message)
    if LOG_CALLBACK:
        try:
            LOG_CALLBACK(message, level)
        except:
            pass

############################
# ===== KREAM CONFIG ===== #
############################

KREAM_BASE_URL = "https://kream.co.kr"
KREAM_SEARCH_URL = "https://kream.co.kr"
KREAM_LOGIN_URL = "https://kream.co.kr"
HEADLESS = False

# 크림 로그인 정보
KREAM_EMAIL = "yaglobal@naver.com"
KREAM_PASSWORD = "dyddk1309!"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_data")
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kream_cookies.json")

# 전역 브라우저 객체 (세션 유지용)
_playwright = None
_browser = None
_context = None
_page = None

############################


def wait_stable(page, ms=600):
    """페이지 안정화 대기"""
    try:
        page.wait_for_load_state("domcontentloaded")
    except:
        pass
    page.wait_for_timeout(ms)


def safe_screenshot(page, name: str):
    """스크린샷 저장"""
    shots_dir = "shots_kream"
    os.makedirs(shots_dir, exist_ok=True)
    path = os.path.join(shots_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.png")
    try:
        page.screenshot(path=path, full_page=True)
        log(f"📸 스크린샷 저장: {path}")
    except Exception as e:
        log(f"⚠️ 스크린샷 실패: {e}", 'error')


def get_browser():
    """브라우저 인스턴스 가져오기 (싱글톤)"""
    global _playwright, _browser, _context, _page
    
    if _browser is None or _page is None:
        if _playwright is None:
            _playwright = sync_playwright().start()
        
        _browser = _playwright.chromium.launch(headless=HEADLESS)
        _context = _browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        # 쿠키 로드
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'r') as f:
                    cookies = json.load(f)
                    _context.add_cookies(cookies)
                    log("  ✓ 쿠키 로드 완료", 'success')
            except:
                pass
        
        _page = _context.new_page()
    
    return _page


def save_cookies():
    """쿠키 저장"""
    global _context
    if _context:
        try:
            cookies = _context.cookies()
            with open(COOKIE_FILE, 'w') as f:
                json.dump(cookies, f)
            log("✓ 쿠키 저장 완료", 'success')
        except Exception as e:
            log(f"⚠️ 쿠키 저장 실패: {e}", 'warning')


# ==========================================
# 크림 로그인 (기존 함수 유지)
# ==========================================

def login_kream():
    """크림 로그인 - 포이즌 방식 봇 감지 방지"""
    global browser, context, page
    
    try:
        print("🔐 크림 검색 준비 중...")
        
        if browser is None:
            playwright = sync_playwright().start()
            
            # ==========================================
            # ✅ 포이즌과 동일한 브라우저 설정
            # ==========================================
            browser = playwright.chromium.launch(
                headless=False,
                channel='chrome',  # 설치된 Chrome 사용 (안정적!)
                args=[
                    '--window-size=960,540',                      # 크기
                    '--window-position=960,0',                     # 오른쪽 위
                    '--disable-blink-features=AutomationControlled'  # 봇 감지 방지
                ]
            )
            
            # ✅ 포이즌 방식: viewport=None, no_viewport=True
            context = browser.new_context(
                viewport=None,          # 포이즌 방식
                no_viewport=True,       # 포이즌 방식
                locale='ko-KR',
                timezone_id='Asia/Seoul'
            )
            
            page = context.new_page()
            
            print("✅ 브라우저 열림 (오른쪽 위, Chrome)")
        
        # ==========================================
        # 크림 메인 페이지 접속
        # ==========================================
        print("📱 크림 메인 페이지로 이동...")
        page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
        
        # ✅ 포이즌 방식: wait_stable 사용
        wait_stable(page, 2000)  # 2초 대기
        
        # ==========================================
        # 자연스러운 페이지 탐색 (스크롤)
        # ==========================================
        print("🖱️  페이지 자연스럽게 탐색 중...")
        
        # 랜덤 스크롤 1
        scroll_y = random.randint(200, 400)
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        # 랜덤 스크롤 2
        scroll_y = random.randint(500, 700)
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        # 맨 위로
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        time.sleep(random.uniform(0.5, 1.0))
        
        print("✅ 크림 메인 페이지 로드 완료")
        
        # ==========================================
        # 로그인 상태 확인
        # ==========================================
        print("🔍 로그인 상태 확인...")
        try:
            page.wait_for_selector('a[href*="my"]', timeout=3000)
            print("✅ 이미 로그인되어 있음")
            return True
        except:
            print("⚠️ 로그인 필요")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("💡 브라우저에서 수동으로 로그인하세요")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return True
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    
# ==========================================
# 2. wait_stable() 함수 추가 (포이즌 방식)
# ==========================================
def wait_stable(page, ms=600):
    """페이지 안정화 대기 - 포이즌 방식"""
    try:
        page.wait_for_load_state("domcontentloaded")
    except:
        pass
    page.wait_for_timeout(ms)

# ==========================================
# 크림 전용 상품 검색 (URL 직접 이동 방식)
# ==========================================
def search_product(product_code):
    """크림에서 상품 검색 - URL 직접 이동 방식"""
    global page
    
    try:
        if page is None:
            return {'success': False, 'error': '브라우저 없음'}
        
        print(f"🔍 상품 검색: {product_code}")
        
        # ==========================================
        # ✅ URL 직접 이동 (검색창 찾기 불필요!)
        # ==========================================
        search_url = f"https://kream.co.kr/search?keyword={product_code}"
        print(f"  📍 검색 URL: {search_url}")
        
        # 자연스러운 대기
        time.sleep(random.uniform(0.3, 0.7))
        
        # 검색 페이지로 이동
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        print(f"  ✓ 검색 페이지 이동 완료")
        
        # 페이지 로딩 대기
        wait_stable(page, 2000)
        
        # ==========================================
        # 검색 결과 대기
        # ==========================================
        try:
            page.wait_for_selector('.search_result_item, .product_card, a[href*="/products/"]', timeout=10000)
            print(f"  ✓ 검색 결과 발견")
        except:
            return {'success': False, 'error': '검색 결과 없음'}
        
        # ==========================================
        # 첫 번째 결과 클릭
        # ==========================================
        try:
            print("  📦 첫 번째 결과 클릭...")
            
            first_product = page.locator('.search_result_item, .product_card, a[href*="/products/"]').first
            
            # 자연스럽게 hover 후 클릭
            first_product.hover()
            time.sleep(random.uniform(0.3, 0.7))
            first_product.click()
            
            wait_stable(page, 2000)
            
            # ==========================================
            # ✅ 상품 정보 추출
            # ==========================================
            data = page.evaluate("""
                () => {
                    // 모델번호 찾기
                    let model_number = '';
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('모델번호')) {
                            const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                            if (match) {
                                model_number = match[1];
                                break;
                            }
                        }
                    }
                    
                    // 상품명 찾기
                    let product_name = '';
                    const h1 = document.querySelector('h1');
                    if (h1) product_name = h1.textContent.trim();
                    
                    // 가격 찾기 (즉시 구매가)
                    let price = '';
                    const priceEl = document.querySelector('.price, .product_price, .amount');
                    if (priceEl) price = priceEl.textContent.trim();
                    
                    // 거래량 찾기
                    let sales = '';
                    const salesEl = document.querySelector('[class*="sale"], [class*="count"]');
                    if (salesEl) sales = salesEl.textContent.trim();
                    
                    return {
                        model_number: model_number,
                        product_name: product_name,
                        price: price,
                        sales: sales
                    };
                }
            """)
            
            if not data or not data.get('model_number'):
                data = {
                    'model_number': product_code, 
                    'product_name': 'N/A', 
                    'price': 'N/A',
                    'sales': 'N/A'
                }
            
            result = {
                'success': True,
                'model_number': data['model_number'],
                'product_name': data['product_name'],
                'price': data['price'],
                'sales': data.get('sales', 'N/A')
            }
            
            print(f"✅ 검색 완료: {result['model_number']}")
            return result
            
        except Exception as e:
            print(f"⚠️ 결과 클릭 실패: {e}")
            return {'success': False, 'error': str(e)}
            
    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        return {'success': False, 'error': str(e)}

# ==========================================
# 상품 정보 추출 (개선 버전)
# ==========================================
def extract_product_info(page, product_code):
    """상품 상세 페이지에서 정보 추출
    
    Args:
        page: Playwright page 객체
        product_code (str): 검색한 상품번호
    
    Returns:
        dict: 추출된 상품 정보 (모델번호, 상품명, 가격, 판매량)
    """
    try:
        print(f"  🔍 상품 정보 추출 중...")
        
        # JavaScript로 한 번에 모든 정보 추출
        data = page.evaluate("""
            () => {
                // 모델번호 찾기
                let model_number = '';
                const elements = document.querySelectorAll('*');
                
                for (let el of elements) {
                    const text = el.textContent;
                    if (text && text.includes('모델번호')) {
                        // 패턴 매칭
                        const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                        if (match) {
                            model_number = match[1];
                            break;
                        }
                        
                        // 다음 형제 요소 확인
                        const parent = el.parentElement;
                        const siblings = Array.from(parent.children);
                        const index = siblings.indexOf(el);
                        if (index < siblings.length - 1) {
                            const nextText = siblings[index + 1].textContent.trim();
                            if (/^[A-Z0-9-]+$/i.test(nextText)) {
                                model_number = nextText;
                                break;
                            }
                        }
                    }
                }
                
                // dl/dt/dd 구조 확인
                if (!model_number) {
                    const dts = document.querySelectorAll('dt');
                    for (let dt of dts) {
                        if (dt.textContent.includes('모델번호')) {
                            const dd = dt.nextElementSibling;
                            if (dd && dd.tagName === 'DD') {
                                model_number = dd.textContent.trim();
                                break;
                            }
                        }
                    }
                }
                
                // 상품명 찾기
                let product_name = '';
                const h1 = document.querySelector('h1, .product_title, .product-title');
                if (h1) product_name = h1.textContent.trim();
                
                // 가격 찾기 (즉시 구매가)
                let avg_price = '';
                const priceSelectors = [
                    '.price',
                    '.product_price', 
                    '.amount',
                    '.buy_price',
                    '[class*="price"]'
                ];
                
                for (let selector of priceSelectors) {
                    const priceEl = document.querySelector(selector);
                    if (priceEl && priceEl.textContent.includes('원')) {
                        avg_price = priceEl.textContent.trim();
                        break;
                    }
                }
                
                // 거래량/판매량 찾기
                let sales = '';
                const salesSelectors = [
                    '[class*="sale"]',
                    '[class*="count"]',
                    '[class*="trade"]',
                    'dd:has-text("거래")',
                ];
                
                for (let selector of salesSelectors) {
                    const salesEl = document.querySelector(selector);
                    if (salesEl) {
                        const text = salesEl.textContent.trim();
                        // 숫자 추출
                        const match = text.match(/([0-9,]+)/);
                        if (match) {
                            sales = match[1];
                            break;
                        }
                    }
                }
                
                return {
                    model_number: model_number,
                    product_name: product_name,
                    avg_price: avg_price,
                    sales: sales
                };
            }
        """)
        
        # 모델번호가 없으면 원래 코드 사용
        if not data.get('model_number'):
            data['model_number'] = product_code
        
        # 결과 구성
        result = {
            'success': True,
            'model_number': data.get('model_number', product_code),
            'product_name': data.get('product_name', 'N/A'),
            'avg_price': data.get('avg_price', 'N/A'),
            'sales': data.get('sales', 'N/A')
        }
        
        print(f"  ✅ 추출 완료: {result['model_number']}")
        print(f"     상품명: {result['product_name'][:30]}...")
        print(f"     가격: {result['avg_price']}")
        print(f"     판매량: {result['sales']}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ 정보 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'model_number': product_code,
            'error': f'정보 추출 실패: {str(e)}'
        }
# ==========================================
# 브라우저 종료 (기존 함수 통합)
# ==========================================
def close_browser():
    """브라우저 종료"""
    global browser, context, page
    global _playwright, _browser, _context, _page
    
    # 팝업용 브라우저 종료
    try:
        if page:
            page.close()
            page = None
        if context:
            context.close()
            context = None
        if browser:
            browser.close()
            browser = None
    except Exception as e:
        print(f"⚠️ 팝업 브라우저 종료 오류: {e}")
    
    # 백그라운드용 브라우저 종료
    try:
        if _page:
            _page.close()
            _page = None
        if _context:
            _context.close()
            _context = None
        if _browser:
            _browser.close()
            _browser = None
        if _playwright:
            _playwright.stop()
            _playwright = None
    except Exception as e:
        print(f"⚠️ 백그라운드 브라우저 종료 오류: {e}")
    
    print("✅ 브라우저 종료")


# ==========================================
# 기존 함수들 (그대로 유지)
# ==========================================


def search_kream_product_detail(product_code):
    """크림에서 상품 검색 - background_kream_search 로직 적용"""
    try:
        log(f"\n🔍 크림 검색: {product_code}", 'info')
        
        page = get_browser()
        
        # 랜덤 딜레이
        delay = random.uniform(1.0, 2.0)
        time.sleep(delay)
        log(f"  💤 {delay:.1f}초 대기", 'info')
        
        # 검색 URL
        search_url = f"https://kream.co.kr/search?keyword={product_code}"
        log(f"  → URL: {search_url}")
        
        # 페이지 이동
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        log(f"  ✅ 검색 페이지 이동 완료", 'success')
        
        # 검색 결과 확인
        try:
            log("  → 검색 결과 대기 중...", 'info')
            page.wait_for_selector('.product_card, a[href*="/products/"]', timeout=10000)
            log("  ✅ 검색 결과 발견!", 'success')
        except Exception as e:
            log(f"  ❌ 검색 결과 없음: {e}", 'error')
            safe_screenshot(page, f"no_result_{product_code}")
            return {'success': False, 'error': '검색 결과 없음'}
        
        # 첫 번째 상품 클릭
        try:
            log("  → 첫 번째 상품 클릭...", 'info')
            first_product = page.locator('a.product_card[href*="/products/"]').first
            
            if first_product.count() == 0:
                log(f"  ❌ 상품 카드 없음", 'error')
                return {'success': False, 'error': '상품 카드 없음'}
            
            first_product.hover()
            time.sleep(random.uniform(0.3, 0.7))
            first_product.click()
            time.sleep(2)
            
            current_url = page.url
            product_id = current_url.split('/products/')[-1].split('?')[0] if '/products/' in current_url else None
            
            log(f"  ✅ 상품 페이지 이동: {current_url}", 'success')
            if product_id:
                log(f"  → Product ID: {product_id}", 'info')
            
        except Exception as e:
            log(f"  ❌ 상품 클릭 실패: {e}", 'error')
            safe_screenshot(page, f"click_fail_{product_code}")
            return {'success': False, 'error': '상품 클릭 실패'}
        
        # 모델번호 확인
        try:
            log(f"  → 모델번호 확인 중...", 'info')
            
            model_info = page.evaluate("""
                () => {
                    let model_numbers = [];
                    let full_text = '';
                    
                    const pTags = document.querySelectorAll('p.text-lookup');
                    
                    for (let p of pTags) {
                        const text = p.textContent.trim();
                        if (text.includes('모델번호')) {
                            full_text = text;
                            const pattern = /[A-Z0-9]{2,10}-[0-9]{3}|[A-Z0-9]{6,}/g;
                            const matches = text.match(pattern);
                            
                            if (matches) {
                                model_numbers = [...new Set(matches)];
                            }
                            break;
                        }
                    }
                    
                    if (model_numbers.length === 0) {
                        const allElements = document.querySelectorAll('*');
                        
                        for (let el of allElements) {
                            const text = el.textContent;
                            if (text && text.includes('모델번호') && text.length < 200) {
                                full_text = text.trim();
                                const pattern = /[A-Z0-9]{2,10}-[0-9]{3}|[A-Z0-9]{6,}/g;
                                const matches = text.match(pattern);
                                
                                if (matches) {
                                    model_numbers = [...new Set(matches)];
                                    break;
                                }
                            }
                        }
                    }
                    
                    return {
                        found: model_numbers.length > 0,
                        model_numbers: model_numbers,
                        full_text: full_text
                    };
                }
            """)
            
            model_found = model_info.get('found', False)
            model_numbers = model_info.get('model_numbers', [])
            model_text = model_info.get('full_text', '')
            
            is_match = False
            matched_model = None
            
            if model_found and model_numbers:
                for model in model_numbers:
                    if product_code.upper() == model.upper():
                        is_match = True
                        matched_model = model
                        log(f"  ✅ 모델번호 일치: {model}", 'success')
                        break
            
            if not is_match and model_text:
                if product_code.upper() in model_text.upper():
                    is_match = True
                    matched_model = product_code
                    log(f"  ✅ 모델번호 포함 일치!", 'success')
            
            if not is_match:
                log(f"  ❌ 모델번호 불일치", 'warning')
                log(f"     찾는 번호: {product_code}", 'warning')
                log(f"     페이지 번호: {', '.join(model_numbers) if model_numbers else '없음'}", 'warning')
                safe_screenshot(page, f"mismatch_{product_code}")
                
                return {
                    'success': False,
                    'model_number': ', '.join(model_numbers) if model_numbers else None,
                    'product_id': product_id,
                    'url': current_url,
                    'error': '모델번호 불일치'
                }
            
        except Exception as e:
            log(f"  ❌ 모델번호 확인 실패: {e}", 'error')
            safe_screenshot(page, f"model_error_{product_code}")
            return {'success': False, 'error': '모델번호 확인 실패'}
        
        # 거래 정보 추출
        try:
            log(f"  → 거래 정보 추출 중...", 'info')
            
            trade_info = page.evaluate("""
                () => {
                    let prices = [];
                    let trade_dates = [];
                    
                    const allElements = document.querySelectorAll('*');
                    
                    for (let el of allElements) {
                        const text = el.textContent.trim();
                        const priceMatch = text.match(/^([0-9,]+)원$/);
                        
                        if (priceMatch && prices.length < 5) {
                            const priceText = priceMatch[1].replace(/,/g, '');
                            const price = parseInt(priceText);
                            
                            if (price >= 10000 && price <= 1000000000) {
                                prices.push(price);
                            }
                        }
                    }
                    
                    for (let el of allElements) {
                        const text = el.textContent.trim();
                        
                        if (text.match(/^\\d{2}\\/\\d{2}\\/\\d{2}$|^\\d+일 전$|^방금 전$|^오늘$|^어제$/)) {
                            if (trade_dates.length === 0) {
                                trade_dates.push(text);
                                break;
                            }
                        }
                    }
                    
                    let avg_price = 0;
                    if (prices.length > 0) {
                        const sum = prices.reduce((a, b) => a + b, 0);
                        avg_price = Math.round(sum / prices.length);
                    }
                    
                    return {
                        prices: prices.slice(0, 5),
                        count: Math.min(prices.length, 5),
                        avg_price: avg_price,
                        first_trade_date: trade_dates.length > 0 ? trade_dates[0] : ''
                    };
                }
            """)
            
            prices = trade_info.get('prices', [])
            count = trade_info.get('count', 0)
            avg_price = trade_info.get('avg_price', 0)
            first_trade_date = trade_info.get('first_trade_date', 'N/A')
            
            average_price = f"{avg_price:,}원" if avg_price > 0 else "N/A"
            sales_count = first_trade_date if first_trade_date else "N/A"
            
            if count > 0:
                log(f"  ✅ 거래 정보 추출 완료!", 'success')
                log(f"     💰 평균가: {average_price}", 'success')
                log(f"     📦 최근 거래: {sales_count}", 'success')
                safe_screenshot(page, f"success_{product_code}")
                
                return {
                    'success': True,
                    'model_number': matched_model,
                    'product_id': product_id,
                    'url': current_url,
                    'average_price': average_price,
                    'sales_count': sales_count
                }
            else:
                log(f"  ⚠️ 거래 정보 없음", 'warning')
                safe_screenshot(page, f"no_trade_{product_code}")
                
                return {
                    'success': False,
                    'model_number': matched_model,
                    'product_id': product_id,
                    'url': current_url,
                    'error': '거래 정보 없음'
                }
            
        except Exception as e:
            log(f"  ❌ 거래 정보 추출 실패: {e}", 'error')
            safe_screenshot(page, f"trade_error_{product_code}")
            return {'success': False, 'error': '거래 정보 추출 실패'}
        
    except Exception as e:
        log(f"❌ 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return {'success': False, 'error': str(e)}



def search_kream_product(product_code, page, callback=None):
    """크림에서 상품 검색 (기존 함수 유지)"""
    global LOG_CALLBACK
    LOG_CALLBACK = callback
    
    try:
        log(f"\n🔍 크림 검색: {product_code}", 'info')
        
        search_url = f"{KREAM_SEARCH_URL}?keyword={product_code}"
        log(f"  → URL: {search_url}")
        
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        wait_stable(page, 2000)
        
        try:
            page.wait_for_selector(".product_card, .item_inner, .product-item", timeout=10000)
            log(f"  ✓ 검색 결과 로드됨")
        except:
            log(f"  ⚠️ 검색 결과 없음", 'warning')
            return []
        
        results = page.evaluate("""
            () => {
                const products = [];
                const cards = document.querySelectorAll('.product_card, .item_inner, .product-item');
                
                cards.forEach((card, index) => {
                    if (index >= 10) return;
                    
                    try {
                        const nameEl = card.querySelector('.product_name, .name, h3, .title');
                        const name = nameEl ? nameEl.textContent.trim() : '';
                        
                        const priceEl = card.querySelector('.price, .amount, .product_price');
                        let price = '';
                        if (priceEl) {
                            price = priceEl.textContent.trim();
                        }
                        
                        const imgEl = card.querySelector('img');
                        const image_url = imgEl ? (imgEl.src || imgEl.dataset.src || '') : '';
                        
                        const linkEl = card.querySelector('a');
                        let link = '';
                        if (linkEl) {
                            link = linkEl.href || '';
                            if (link && !link.startsWith('http')) {
                                link = 'https://kream.co.kr' + link;
                            }
                        }
                        
                        const sizeEl = card.querySelector('.size, .product_size');
                        const size = sizeEl ? sizeEl.textContent.trim() : '';
                        
                        const brandEl = card.querySelector('.brand, .product_brand');
                        const brand = brandEl ? brandEl.textContent.trim() : '';
                        
                        if (name) {
                            products.push({
                                name: name,
                                price: price,
                                image_url: image_url,
                                link: link,
                                size: size,
                                brand: brand,
                                source: 'KREAM'
                            });
                        }
                    } catch (e) {
                        console.error('상품 파싱 오류:', e);
                    }
                });
                
                return products;
            }
        """)
        
        log(f"  ✅ {len(results)}개 상품 발견", 'success')
        
        for idx, product in enumerate(results, 1):
            log(f"    {idx}. {product.get('name', 'N/A')[:50]} - {product.get('price', 'N/A')}")
        
        return results
        
    except Exception as e:
        log(f"  ❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return []


def search_kream_products_batch(product_codes, callback=None):
    """여러 상품을 크림에서 일괄 검색 (기존 함수 유지)"""
    global LOG_CALLBACK, stop_flag
    LOG_CALLBACK = callback
    stop_flag = False
    
    log("\n" + "=" * 60, 'info')
    log("🛒 크림(KREAM) 일괄 검색 시작", 'info')
    log("=" * 60, 'info')
    
    total = len(product_codes)
    log(f"📊 총 {total}개 상품 검색 예정\n", 'info')
    
    results = {}
    
    try:
        with sync_playwright() as p:
            log("🌐 브라우저 시작...", 'info')
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                if callback:
                    callback(f"PRODUCT_START:{product_code}", 'info')
                
                product_results = search_kream_product(product_code, page, callback)
                results[product_code] = product_results
                
                if callback:
                    result_data = {
                        'product_code': product_code,
                        'products': product_results
                    }
                    callback(f"PRODUCT_RESULT:{json.dumps(result_data, ensure_ascii=False)}", 'data')
                
                if idx < total:
                    delay = random.uniform(2.0, 4.0)
                    log(f"  💤 {delay:.1f}초 대기...", 'info')
                    time.sleep(delay)
            
            try:
                cookies = context.cookies()
                with open(COOKIE_FILE, 'w') as f:
                    json.dump(cookies, f)
                log("\n✓ 쿠키 저장 완료", 'success')
            except:
                pass
            
            browser.close()
        
        log("\n" + "=" * 60, 'success')
        log(f"✅ 크림 검색 완료! 총 {len(results)}개 상품", 'success')
        log("=" * 60, 'success')
        
        return {
            'success': True,
            'results': results,
            'total_searched': len(results)
        }
        
    except Exception as e:
        log(f"\n❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'results': results
        }


def search_kream_sourcing(product_codes, callback=None):
    """크림 소싱 검색 (기존 함수 유지)"""
    global LOG_CALLBACK, stop_flag
    LOG_CALLBACK = callback
    stop_flag = False
    
    log("\n" + "=" * 60, 'info')
    log("🛒 크림(KREAM) 소싱 검색 시작", 'info')
    log("=" * 60, 'info')
    
    total = len(product_codes)
    log(f"📊 총 {total}개 상품 검색 예정\n", 'info')
    
    results = {}
    searched_count = 0
    
    try:
        with sync_playwright() as p:
            log("🌐 브라우저 시작...", 'info')
            browser = p.chromium.launch(
                headless=HEADLESS,
                channel='chrome',
                args=['--start-maximized', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                viewport=None,
                no_viewport=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                try:
                    search_results = search_kream_product(product_code, page, callback)
                    
                    if search_results:
                        results[product_code] = search_results
                        searched_count += 1
                        log(f"  ✅ {len(search_results)}개 결과 발견", 'success')
                    else:
                        results[product_code] = []
                        log(f"  ⚠️ 검색 결과 없음", 'warning')
                    
                    if idx < total:
                        delay = random.uniform(2.0, 4.0)
                        time.sleep(delay)
                
                except Exception as e:
                    log(f"  ❌ 오류: {e}", 'error')
                    results[product_code] = []
            
            browser.close()
        
        log("\n" + "=" * 60, 'success')
        log(f"✅ 크림 검색 완료! 총 {searched_count}개 상품", 'success')
        log("=" * 60, 'success')
        
        return {
            'success': True,
            'results': results,
            'total_searched': searched_count
        }
        
    except Exception as e:
        log(f"\n❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'results': results,
            'total_searched': searched_count
        }


def test_kream_search():
    """테스트 함수"""
    print("\n" + "=" * 60)
    print("🧪 크림 검색 테스트")
    print("=" * 60)
    
    test_codes = [
        "DZ5485-410",  # 나이키 덩크
        "GY5167",      # 아디다스
    ]
    
    result = search_kream_products_batch(test_codes)
    
    print("\n📊 테스트 결과:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    print("=" * 60)
    print("🛒 KREAM 검색 엔진")
    print("=" * 60)
    print("\n이 파일은 app.py를 통해 실행됩니다.")
    print("\n직접 테스트하려면:")
    print("  python kream_search.py test")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_kream_search()


# 수정된 background_kream_search() 함수
# kream_search.py 파일의 해당 함수를 이것으로 교체하세요

# 기존 background_kream_search() 함수에 4단계만 추가
# kream_data/kream_search.py 파일에서 background_kream_search() 함수를 이것으로 교체

import os
import sys
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 전역 변수
browser = None
context = None
page = None

# 중단 플래그
stop_flag = False

# 로그 콜백 함수
LOG_CALLBACK = None

def log(message, level='info'):
    """터미널 + GUI 로그 출력"""
    print(message)
    if LOG_CALLBACK:
        try:
            LOG_CALLBACK(message, level)
        except:
            pass

############################
# ===== KREAM CONFIG ===== #
############################

KREAM_BASE_URL = "https://kream.co.kr"
KREAM_SEARCH_URL = "https://kream.co.kr"
KREAM_LOGIN_URL = "https://kream.co.kr"
HEADLESS = False

# 크림 로그인 정보
KREAM_EMAIL = "yaglobal@naver.com"
KREAM_PASSWORD = "dyddk1309!"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_data")
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kream_cookies.json")

# 전역 브라우저 객체 (세션 유지용)
_playwright = None
_browser = None
_context = None
_page = None

############################


def wait_stable(page, ms=600):
    """페이지 안정화 대기"""
    try:
        page.wait_for_load_state("domcontentloaded")
    except:
        pass
    page.wait_for_timeout(ms)


def safe_screenshot(page, name: str):
    """스크린샷 저장"""
    shots_dir = "shots_kream"
    os.makedirs(shots_dir, exist_ok=True)
    path = os.path.join(shots_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.png")
    try:
        page.screenshot(path=path, full_page=True)
        log(f"📸 스크린샷 저장: {path}")
    except Exception as e:
        log(f"⚠️ 스크린샷 실패: {e}", 'error')


def get_browser():
    """브라우저 인스턴스 가져오기 (싱글톤) - 봇 차단 우회"""
    global _playwright, _browser, _context, _page
    
    if _browser is None or _page is None:
        if _playwright is None:
            _playwright = sync_playwright().start()
        
        # ✅ 봇 감지 방지 설정!
        _browser = _playwright.chromium.launch(
            headless=HEADLESS,
            channel='chrome',  # 실제 Chrome 사용
            args=[
                '--disable-blink-features=AutomationControlled',  # 자동화 감지 방지
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # ✅ User-Agent 및 헤더 설정
        _context = _browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Referer': 'https://kream.co.kr/',
                'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"'
            }
        )
        
        # 쿠키 로드
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'r') as f:
                    cookies = json.load(f)
                    _context.add_cookies(cookies)
                    log("  ✓ 쿠키 로드 완료", 'success')
            except:
                pass
        
        _page = _context.new_page()
        
        # ✅ JavaScript 탐지 우회
        _page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en']
            });
        """)
    
    return _page

def save_cookies():
    """쿠키 저장"""
    global _context
    if _context:
        try:
            cookies = _context.cookies()
            with open(COOKIE_FILE, 'w') as f:
                json.dump(cookies, f)
            log("✓ 쿠키 저장 완료", 'success')
        except Exception as e:
            log(f"⚠️ 쿠키 저장 실패: {e}", 'warning')


# ==========================================
# 크림 로그인 (기존 함수 유지)
# ==========================================

def login_kream():
    """크림 로그인 - 포이즌 방식 봇 감지 방지"""
    global browser, context, page
    
    try:
        print("🔐 크림 검색 준비 중...")
        
        if browser is None:
            playwright = sync_playwright().start()
            
            # ==========================================
            # ✅ 포이즌과 동일한 브라우저 설정
            # ==========================================
            browser = playwright.chromium.launch(
                headless=False,
                channel='chrome',  # 설치된 Chrome 사용 (안정적!)
                args=[
                    '--window-size=960,540',                      # 크기
                    '--window-position=960,0',                     # 오른쪽 위
                    '--disable-blink-features=AutomationControlled'  # 봇 감지 방지
                ]
            )
            
            # ✅ 포이즌 방식: viewport=None, no_viewport=True
            context = browser.new_context(
                viewport=None,          # 포이즌 방식
                no_viewport=True,       # 포이즌 방식
                locale='ko-KR',
                timezone_id='Asia/Seoul'
            )
            
            page = context.new_page()
            
            print("✅ 브라우저 열림 (오른쪽 위, Chrome)")
        
        # ==========================================
        # 크림 메인 페이지 접속
        # ==========================================
        print("📱 크림 메인 페이지로 이동...")
        page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
        
        # ✅ 포이즌 방식: wait_stable 사용
        wait_stable(page, 2000)  # 2초 대기
        
        # ==========================================
        # 자연스러운 페이지 탐색 (스크롤)
        # ==========================================
        print("🖱️  페이지 자연스럽게 탐색 중...")
        
        # 랜덤 스크롤 1
        scroll_y = random.randint(200, 400)
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        # 랜덤 스크롤 2
        scroll_y = random.randint(500, 700)
        page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        # 맨 위로
        page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        time.sleep(random.uniform(0.5, 1.0))
        
        print("✅ 크림 메인 페이지 로드 완료")
        
        # ==========================================
        # 로그인 상태 확인
        # ==========================================
        print("🔍 로그인 상태 확인...")
        try:
            page.wait_for_selector('a[href*="my"]', timeout=3000)
            print("✅ 이미 로그인되어 있음")
            return True
        except:
            print("⚠️ 로그인 필요")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("💡 브라우저에서 수동으로 로그인하세요")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            return True
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    
# ==========================================
# 2. wait_stable() 함수 추가 (포이즌 방식)
# ==========================================
def wait_stable(page, ms=600):
    """페이지 안정화 대기 - 포이즌 방식"""
    try:
        page.wait_for_load_state("domcontentloaded")
    except:
        pass
    page.wait_for_timeout(ms)

# ==========================================
# 크림 전용 상품 검색 (URL 직접 이동 방식)
# ==========================================
def search_product(product_code):
    """크림에서 상품 검색 - URL 직접 이동 방식"""
    global page
    
    try:
        if page is None:
            return {'success': False, 'error': '브라우저 없음'}
        
        print(f"🔍 상품 검색: {product_code}")
        
        # ==========================================
        # ✅ URL 직접 이동 (검색창 찾기 불필요!)
        # ==========================================
        search_url = f"https://kream.co.kr/search?keyword={product_code}"
        print(f"  📍 검색 URL: {search_url}")
        
        # 자연스러운 대기
        time.sleep(random.uniform(0.3, 0.7))
        
        # 검색 페이지로 이동
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        print(f"  ✓ 검색 페이지 이동 완료")
        
        # 페이지 로딩 대기
        wait_stable(page, 2000)
        
        # ==========================================
        # 검색 결과 대기
        # ==========================================
        try:
            page.wait_for_selector('.search_result_item, .product_card, a[href*="/products/"]', timeout=10000)
            print(f"  ✓ 검색 결과 발견")
        except:
            return {'success': False, 'error': '검색 결과 없음'}
        
        # ==========================================
        # 첫 번째 결과 클릭
        # ==========================================
        try:
            print("  📦 첫 번째 결과 클릭...")
            
            first_product = page.locator('.search_result_item, .product_card, a[href*="/products/"]').first
            
            # 자연스럽게 hover 후 클릭
            first_product.hover()
            time.sleep(random.uniform(0.3, 0.7))
            first_product.click()
            
            wait_stable(page, 2000)
            
            # ==========================================
            # ✅ 상품 정보 추출
            # ==========================================
            data = page.evaluate("""
                () => {
                    // 모델번호 찾기
                    let model_number = '';
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('모델번호')) {
                            const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                            if (match) {
                                model_number = match[1];
                                break;
                            }
                        }
                    }
                    
                    // 상품명 찾기
                    let product_name = '';
                    const h1 = document.querySelector('h1');
                    if (h1) product_name = h1.textContent.trim();
                    
                    // 가격 찾기 (즉시 구매가)
                    let price = '';
                    const priceEl = document.querySelector('.price, .product_price, .amount');
                    if (priceEl) price = priceEl.textContent.trim();
                    
                    // 거래량 찾기
                    let sales = '';
                    const salesEl = document.querySelector('[class*="sale"], [class*="count"]');
                    if (salesEl) sales = salesEl.textContent.trim();
                    
                    return {
                        model_number: model_number,
                        product_name: product_name,
                        price: price,
                        sales: sales
                    };
                }
            """)
            
            if not data or not data.get('model_number'):
                data = {
                    'model_number': product_code, 
                    'product_name': 'N/A', 
                    'price': 'N/A',
                    'sales': 'N/A'
                }
            
            result = {
                'success': True,
                'model_number': data['model_number'],
                'product_name': data['product_name'],
                'price': data['price'],
                'sales': data.get('sales', 'N/A')
            }
            
            print(f"✅ 검색 완료: {result['model_number']}")
            return result
            
        except Exception as e:
            print(f"⚠️ 결과 클릭 실패: {e}")
            return {'success': False, 'error': str(e)}
            
    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        return {'success': False, 'error': str(e)}

# ==========================================
# 상품 정보 추출 (개선 버전)
# ==========================================
def extract_product_info(page, product_code):
    """상품 상세 페이지에서 정보 추출
    
    Args:
        page: Playwright page 객체
        product_code (str): 검색한 상품번호
    
    Returns:
        dict: 추출된 상품 정보 (모델번호, 상품명, 가격, 판매량)
    """
    try:
        print(f"  🔍 상품 정보 추출 중...")
        
        # JavaScript로 한 번에 모든 정보 추출
        data = page.evaluate("""
            () => {
                // 모델번호 찾기
                let model_number = '';
                const elements = document.querySelectorAll('*');
                
                for (let el of elements) {
                    const text = el.textContent;
                    if (text && text.includes('모델번호')) {
                        // 패턴 매칭
                        const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                        if (match) {
                            model_number = match[1];
                            break;
                        }
                        
                        // 다음 형제 요소 확인
                        const parent = el.parentElement;
                        const siblings = Array.from(parent.children);
                        const index = siblings.indexOf(el);
                        if (index < siblings.length - 1) {
                            const nextText = siblings[index + 1].textContent.trim();
                            if (/^[A-Z0-9-]+$/i.test(nextText)) {
                                model_number = nextText;
                                break;
                            }
                        }
                    }
                }
                
                // dl/dt/dd 구조 확인
                if (!model_number) {
                    const dts = document.querySelectorAll('dt');
                    for (let dt of dts) {
                        if (dt.textContent.includes('모델번호')) {
                            const dd = dt.nextElementSibling;
                            if (dd && dd.tagName === 'DD') {
                                model_number = dd.textContent.trim();
                                break;
                            }
                        }
                    }
                }
                
                // 상품명 찾기
                let product_name = '';
                const h1 = document.querySelector('h1, .product_title, .product-title');
                if (h1) product_name = h1.textContent.trim();
                
                // 가격 찾기 (즉시 구매가)
                let avg_price = '';
                const priceSelectors = [
                    '.price',
                    '.product_price', 
                    '.amount',
                    '.buy_price',
                    '[class*="price"]'
                ];
                
                for (let selector of priceSelectors) {
                    const priceEl = document.querySelector(selector);
                    if (priceEl && priceEl.textContent.includes('원')) {
                        avg_price = priceEl.textContent.trim();
                        break;
                    }
                }
                
                // 거래량/판매량 찾기
                let sales = '';
                const salesSelectors = [
                    '[class*="sale"]',
                    '[class*="count"]',
                    '[class*="trade"]',
                    'dd:has-text("거래")',
                ];
                
                for (let selector of salesSelectors) {
                    const salesEl = document.querySelector(selector);
                    if (salesEl) {
                        const text = salesEl.textContent.trim();
                        // 숫자 추출
                        const match = text.match(/([0-9,]+)/);
                        if (match) {
                            sales = match[1];
                            break;
                        }
                    }
                }
                
                return {
                    model_number: model_number,
                    product_name: product_name,
                    avg_price: avg_price,
                    sales: sales
                };
            }
        """)
        
        # 모델번호가 없으면 원래 코드 사용
        if not data.get('model_number'):
            data['model_number'] = product_code
        
        # 결과 구성
        result = {
            'success': True,
            'model_number': data.get('model_number', product_code),
            'product_name': data.get('product_name', 'N/A'),
            'avg_price': data.get('avg_price', 'N/A'),
            'sales': data.get('sales', 'N/A')
        }
        
        print(f"  ✅ 추출 완료: {result['model_number']}")
        print(f"     상품명: {result['product_name'][:30]}...")
        print(f"     가격: {result['avg_price']}")
        print(f"     판매량: {result['sales']}")
        
        return result
        
    except Exception as e:
        print(f"  ❌ 정보 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'model_number': product_code,
            'error': f'정보 추출 실패: {str(e)}'
        }
# ==========================================
# 브라우저 종료 (기존 함수 통합)
# ==========================================
def close_browser():
    """브라우저 종료"""
    global browser, context, page
    global _playwright, _browser, _context, _page
    
    # 팝업용 브라우저 종료
    try:
        if page:
            page.close()
            page = None
        if context:
            context.close()
            context = None
        if browser:
            browser.close()
            browser = None
    except Exception as e:
        print(f"⚠️ 팝업 브라우저 종료 오류: {e}")
    
    # 백그라운드용 브라우저 종료
    try:
        if _page:
            _page.close()
            _page = None
        if _context:
            _context.close()
            _context = None
        if _browser:
            _browser.close()
            _browser = None
        if _playwright:
            _playwright.stop()
            _playwright = None
    except Exception as e:
        print(f"⚠️ 백그라운드 브라우저 종료 오류: {e}")
    
    print("✅ 브라우저 종료")


# ==========================================
# 기존 함수들 (그대로 유지)
# ==========================================

def search_kream_products_batch(product_codes, callback=None):
    """여러 상품을 크림에서 일괄 검색 (기존 함수 유지)"""
    global LOG_CALLBACK, stop_flag
    LOG_CALLBACK = callback
    stop_flag = False
    
    log("\n" + "=" * 60, 'info')
    log("🛒 크림(KREAM) 일괄 검색 시작", 'info')
    log("=" * 60, 'info')
    
    total = len(product_codes)
    log(f"📊 총 {total}개 상품 검색 예정\n", 'info')
    
    results = {}
    
    try:
        with sync_playwright() as p:
            log("🌐 브라우저 시작...", 'info')
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                if callback:
                    callback(f"PRODUCT_START:{product_code}", 'info')
                
                product_results = search_kream_product(product_code, page, callback)
                results[product_code] = product_results
                
                if callback:
                    result_data = {
                        'product_code': product_code,
                        'products': product_results
                    }
                    callback(f"PRODUCT_RESULT:{json.dumps(result_data, ensure_ascii=False)}", 'data')
                
                if idx < total:
                    delay = random.uniform(2.0, 4.0)
                    log(f"  💤 {delay:.1f}초 대기...", 'info')
                    time.sleep(delay)
            
            try:
                cookies = context.cookies()
                with open(COOKIE_FILE, 'w') as f:
                    json.dump(cookies, f)
                log("\n✓ 쿠키 저장 완료", 'success')
            except:
                pass
            
            browser.close()
        
        log("\n" + "=" * 60, 'success')
        log(f"✅ 크림 검색 완료! 총 {len(results)}개 상품", 'success')
        log("=" * 60, 'success')
        
        return {
            'success': True,
            'results': results,
            'total_searched': len(results)
        }
        
    except Exception as e:
        log(f"\n❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'results': results
        }


def search_kream_sourcing(product_codes, callback=None):
    """크림 소싱 검색 (기존 함수 유지)"""
    global LOG_CALLBACK, stop_flag
    LOG_CALLBACK = callback
    stop_flag = False
    
    log("\n" + "=" * 60, 'info')
    log("🛒 크림(KREAM) 소싱 검색 시작", 'info')
    log("=" * 60, 'info')
    
    total = len(product_codes)
    log(f"📊 총 {total}개 상품 검색 예정\n", 'info')
    
    results = {}
    searched_count = 0
    
    try:
        with sync_playwright() as p:
            log("🌐 브라우저 시작...", 'info')
            browser = p.chromium.launch(
                headless=HEADLESS,
                channel='chrome',
                args=['--start-maximized', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                viewport=None,
                no_viewport=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                try:
                    search_results = search_kream_product(product_code, page, callback)
                    
                    if search_results:
                        results[product_code] = search_results
                        searched_count += 1
                        log(f"  ✅ {len(search_results)}개 결과 발견", 'success')
                    else:
                        results[product_code] = []
                        log(f"  ⚠️ 검색 결과 없음", 'warning')
                    
                    if idx < total:
                        delay = random.uniform(2.0, 4.0)
                        time.sleep(delay)
                
                except Exception as e:
                    log(f"  ❌ 오류: {e}", 'error')
                    results[product_code] = []
            
            browser.close()
        
        log("\n" + "=" * 60, 'success')
        log(f"✅ 크림 검색 완료! 총 {searched_count}개 상품", 'success')
        log("=" * 60, 'success')
        
        return {
            'success': True,
            'results': results,
            'total_searched': searched_count
        }
        
    except Exception as e:
        log(f"\n❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'error': str(e),
            'results': results,
            'total_searched': searched_count
        }


def test_kream_search():
    """테스트 함수"""
    print("\n" + "=" * 60)
    print("🧪 크림 검색 테스트")
    print("=" * 60)
    
    test_codes = [
        "DZ5485-410",  # 나이키 덩크
        "GY5167",      # 아디다스
    ]
    
    result = search_kream_products_batch(test_codes)
    
    print("\n📊 테스트 결과:")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    print("=" * 60)
    print("🛒 KREAM 검색 엔진")
    print("=" * 60)
    print("\n이 파일은 app.py를 통해 실행됩니다.")
    print("\n직접 테스트하려면:")
    print("  python kream_search.py test")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_kream_search()



# ==========================================
# 백그라운드 검색 함수 (app.py에서 호출)
# 이 함수 1개만 kream_search.py 파일 맨 끝에 추가하세요
# ==========================================

"""
크림(KREAM) 검색 모듈
- 백그라운드 다중 상품 검색
- 모델번호 확인
- 거래 정보 추출
- 자동 브라우저 종료
"""

import os
import json
import random
import time
from playwright.sync_api import sync_playwright

# 전역 변수
browser = None
context = None
page = None
stop_flag = False

# 크림 로그인 정보
KREAM_EMAIL = "yaglobal@naver.com"
KREAM_PASSWORD = "dyddk1309!"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kream_cookies.json")


def background_kream_search(task_id, product_codes, progress_queue):
    """백그라운드 크림 검색 - 여러 상품 반복 검색"""
    global stop_flag, browser, context, page
    
    try:
        print(f"\n{'='*60}")
        print(f"🚀 백그라운드 검색 시작 (Task: {task_id})")
        print(f"📦 검색할 상품: {len(product_codes)}개")
        print(f"{'='*60}\n")
        
        stop_flag = False
        
        if not product_codes:
            error_msg = "검색할 상품이 없습니다"
            print(f"❌ {error_msg}")
            progress_queue.put({'event': 'error', 'data': {'error': error_msg}})
            return
        
        # ==========================================
        # 준비: 기존 브라우저 종료
        # ==========================================
        print("\n🎯 [준비] 기존 브라우저 확인 및 종료")
        progress_queue.put({'event': 'message', 'data': {'message': '[준비] 기존 브라우저 종료 중...'}})
        
        if browser is not None:
            try:
                print("  → 기존 브라우저 종료 중...")
                browser.close()
                print("  ✅ 기존 브라우저 종료 완료")
            except Exception as e:
                print(f"  ⚠️ 브라우저 종료 실패: {e}")
        
        browser = None
        context = None
        page = None
        
        # ==========================================
        # 1단계: 브라우저 실행
        # ==========================================
        print("\n🎯 [1단계] 새 브라우저 열기")
        progress_queue.put({'event': 'message', 'data': {'message': '[1단계] 브라우저 실행 중...'}})
        
        playwright = sync_playwright().start()
        
        browser = playwright.chromium.launch(
            headless=False,
            channel='chrome',
            args=[
                '--window-size=960,540',
                '--window-position=960,0',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        context = browser.new_context(
            viewport=None,
            no_viewport=True,
            locale='ko-KR',
            timezone_id='Asia/Seoul'
        )
        
        # 쿠키 로드
        if os.path.exists(COOKIE_FILE):
            try:
                with open(COOKIE_FILE, 'r') as f:
                    cookies = json.load(f)
                    context.add_cookies(cookies)
                print("  ✅ 쿠키 로드 완료")
            except:
                print("  ⚠️ 쿠키 로드 실패")
        
        page = context.new_page()
        print("  ✅ 새 브라우저 열림")
        
        page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        print("  ✅ [1단계 완료] 메인 페이지 로드 성공!")
        progress_queue.put({'event': 'message', 'data': {'message': '[1단계 완료] ✅'}})
        
        # ==========================================
        # 자동 로그인
        # ==========================================
        print("\n🔐 [자동 로그인] 로그인 시도")
        progress_queue.put({'event': 'message', 'data': {'message': '[로그인] 상태 확인 중...'}})
        
        try:
            login_link = page.locator('a[href="/login"]').first
            
            if login_link.count() > 0 and login_link.is_visible():
                print("  ⚠️ 로그인이 필요합니다")
                print("  🔐 자동 로그인 시도 중...")
                
                page.goto('https://kream.co.kr/login', wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                
                email_input = page.locator('input[type="email"], input[name="email"]').first
                if email_input.count() > 0:
                    email_input.fill(KREAM_EMAIL)
                    time.sleep(0.5)
                
                password_input = page.locator('input[type="password"]').first
                if password_input.count() > 0:
                    password_input.fill(KREAM_PASSWORD)
                    time.sleep(0.5)
                
                login_button = page.locator('button:has-text("로그인")').first
                if login_button.count() > 0:
                    login_button.click()
                    time.sleep(3)
                
                page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                
                login_link_after = page.locator('a[href="/login"]').first
                
                if login_link_after.count() == 0 or not login_link_after.is_visible():
                    print("  ✅ 자동 로그인 성공!")
                    
                    try:
                        cookies = context.cookies()
                        with open(COOKIE_FILE, 'w') as f:
                            json.dump(cookies, f)
                        print("  ✅ 쿠키 저장 완료")
                    except Exception as e:
                        print(f"  ⚠️ 쿠키 저장 실패: {e}")
                    
                    progress_queue.put({'event': 'message', 'data': {'message': '[로그인] ✅ 완료'}})
                else:
                    print("  ❌ 자동 로그인 실패")
                    progress_queue.put({'event': 'message', 'data': {'message': '[로그인] ⚠️ 실패'}})
                    
            else:
                print("  ✅ 이미 로그인되어 있음!")
                progress_queue.put({'event': 'message', 'data': {'message': '[로그인] ✅ 완료'}})
                
        except Exception as e:
            print(f"  ❌ 자동 로그인 오류: {e}")
            print("  → 로그인 없이 계속 진행합니다...")
            progress_queue.put({'event': 'message', 'data': {'message': '[로그인] ⚠️ 실패'}})
        
        # ==========================================
        # 상품 반복 검색
        # ==========================================
        print(f"\n{'='*60}")
        print(f"🔁 상품 반복 검색 시작: {len(product_codes)}개")
        print(f"{'='*60}\n")
        
        success_count = 0
        fail_count = 0
        
        for index, product_code in enumerate(product_codes):
            if stop_flag:
                print(f"\n🛑 검색 중단됨 (진행: {index}/{len(product_codes)})")
                progress_queue.put({
                    'event': 'complete',
                    'data': {
                        'message': f'🛑 중단됨 - {success_count}개 성공, {fail_count}개 실패',
                        'total': len(product_codes),
                        'success': success_count,
                        'fail': fail_count
                    }
                })
                
                # 중단 시 브라우저 종료
                print("\n🔒 크림 브라우저 종료 중...")
                time.sleep(1)
                close_browser_safe()
                break
            
            print(f"\n{'='*60}")
            print(f"🔍 [{index + 1}/{len(product_codes)}] 상품 검색: {product_code}")
            print(f"{'='*60}\n")
            
            progress_queue.put({
                'event': 'progress',
                'data': {
                    'current': index + 1,
                    'total': len(product_codes),
                    'product_code': product_code,
                    'index': index
                }
            })
            
            try:
                # 검색 페이지로 이동
                print(f"  → 검색 URL로 이동...")
                search_url = f"https://kream.co.kr/search?keyword={product_code}"
                
                time.sleep(random.uniform(1.0, 2.0))
                page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                
                print(f"  ✅ 검색 페이지 이동 완료")
                
                # 검색 결과 확인
                try:
                    print("  → 검색 결과 대기 중...")
                    page.wait_for_selector('.product_card, a[href*="/products/"]', timeout=10000)
                    print("  ✅ 검색 결과 발견!")
                except Exception as e:
                    print(f"  ❌ 검색 결과 없음: {e}")
                    fail_count += 1
                    
                    progress_queue.put({
                        'event': 'result',
                        'data': {
                            'index': index,
                            'result': {
                                'success': False,
                                'error': '검색 결과 없음',
                                'kream_data': None
                            }
                        }
                    })
                    continue
                
                # 첫 번째 상품 클릭
                try:
                    print("  → 첫 번째 상품 클릭...")
                    first_product_link = page.locator('a.product_card[href*="/products/"]').first
                    
                    if first_product_link.count() == 0:
                        print(f"  ❌ 상품 카드 없음")
                        fail_count += 1
                        
                        progress_queue.put({
                            'event': 'result',
                            'data': {
                                'index': index,
                                'result': {
                                    'success': False,
                                    'error': '상품 카드 없음',
                                    'kream_data': None
                                }
                            }
                        })
                        continue
                    
                    first_product_link.hover()
                    time.sleep(random.uniform(0.3, 0.7))
                    first_product_link.click()
                    time.sleep(2)
                    
                    product_url = page.url
                    print(f"  ✅ 상품 페이지 이동: {product_url}")
                    
                except Exception as e:
                    print(f"  ❌ 상품 클릭 실패: {e}")
                    fail_count += 1
                    
                    progress_queue.put({
                        'event': 'result',
                        'data': {
                            'index': index,
                            'result': {
                                'success': False,
                                'error': '상품 클릭 실패',
                                'kream_data': None
                            }
                        }
                    })
                    continue
                
                # 모델번호 확인
                print(f"  → 모델번호 확인 중...")
                
                try:
                    model_info = page.evaluate("""
                        () => {
                            let model_numbers = [];
                            let full_text = '';
                            
                            const pTags = document.querySelectorAll('p.text-lookup');
                            
                            for (let p of pTags) {
                                const text = p.textContent.trim();
                                if (text.includes('모델번호')) {
                                    full_text = text;
                                    const pattern = /[A-Z0-9]{2,10}-[0-9]{3}|[A-Z0-9]{6,}/g;
                                    const matches = text.match(pattern);
                                    
                                    if (matches) {
                                        model_numbers = [...new Set(matches)];
                                    }
                                    break;
                                }
                            }
                            
                            if (model_numbers.length === 0) {
                                const allElements = document.querySelectorAll('*');
                                
                                for (let el of allElements) {
                                    const text = el.textContent;
                                    if (text && text.includes('모델번호') && text.length < 200) {
                                        full_text = text.trim();
                                        const pattern = /[A-Z0-9]{2,10}-[0-9]{3}|[A-Z0-9]{6,}/g;
                                        const matches = text.match(pattern);
                                        
                                        if (matches) {
                                            model_numbers = [...new Set(matches)];
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            return {
                                found: model_numbers.length > 0,
                                model_numbers: model_numbers,
                                full_text: full_text
                            };
                        }
                    """)
                    
                    model_found = model_info.get('found', False)
                    model_numbers = model_info.get('model_numbers', [])
                    model_text = model_info.get('full_text', '')
                    
                    is_match = False
                    
                    if model_found and model_numbers:
                        for model in model_numbers:
                            if product_code.upper() == model.upper():
                                is_match = True
                                print(f"  ✅ 모델번호 일치!")
                                break
                    
                    if not is_match and model_text:
                        if product_code.upper() in model_text.upper():
                            is_match = True
                            print(f"  ✅ 모델번호 포함 일치!")
                    
                    # 모델번호 불일치 시 바로 다음으로
                    if not is_match:
                        print(f"  ❌ 모델번호 불일치! 다음 상품으로 이동...")
                        print(f"     찾는 번호: {product_code}")
                        print(f"     페이지 번호: {', '.join(model_numbers) if model_numbers else '없음'}")
                        
                        fail_count += 1
                        
                        progress_queue.put({
                            'event': 'result',
                            'data': {
                                'index': index,
                                'result': {
                                    'success': False,
                                    'error': '모델번호 불일치',
                                    'kream_data': None
                                }
                            }
                        })
                        continue
                    
                except Exception as e:
                    print(f"  ⚠️ 모델번호 확인 실패: {e}")
                    fail_count += 1
                    
                    progress_queue.put({
                        'event': 'result',
                        'data': {
                            'index': index,
                            'result': {
                                'success': False,
                                'error': '모델번호 확인 실패',
                                'kream_data': None
                            }
                        }
                    })
                    continue
                
                # 거래 정보 추출 (모델번호 일치할 때만)
                print(f"  → 거래 정보 추출 중...")
                
                try:
                    trade_info = page.evaluate("""
                        () => {
                            let prices = [];
                            let trade_dates = [];
                            
                            const allElements = document.querySelectorAll('*');
                            
                            for (let el of allElements) {
                                const text = el.textContent.trim();
                                const priceMatch = text.match(/^([0-9,]+)원$/);
                                
                                if (priceMatch && prices.length < 5) {
                                    const priceText = priceMatch[1].replace(/,/g, '');
                                    const price = parseInt(priceText);
                                    
                                    if (price >= 10000 && price <= 1000000000) {
                                        prices.push(price);
                                    }
                                }
                            }
                            
                            for (let el of allElements) {
                                const text = el.textContent.trim();
                                
                                if (text.match(/^\\d{2}\\/\\d{2}\\/\\d{2}$|^\\d+일 전$|^방금 전$|^오늘$|^어제$/)) {
                                    if (trade_dates.length === 0) {
                                        trade_dates.push(text);
                                        break;
                                    }
                                }
                            }
                            
                            let avg_price = 0;
                            if (prices.length > 0) {
                                const sum = prices.reduce((a, b) => a + b, 0);
                                avg_price = Math.round(sum / prices.length);
                            }
                            
                            return {
                                prices: prices.slice(0, 5),
                                count: Math.min(prices.length, 5),
                                avg_price: avg_price,
                                first_trade_date: trade_dates.length > 0 ? trade_dates[0] : ''
                            };
                        }
                    """)
                    
                    prices = trade_info.get('prices', [])
                    count = trade_info.get('count', 0)
                    avg_price = trade_info.get('avg_price', 0)
                    first_trade_date = trade_info.get('first_trade_date', 'N/A')
                    
                    kream_avg_price = f"{avg_price:,}원" if avg_price > 0 else "N/A"
                    kream_sales = first_trade_date if first_trade_date else "N/A"
                    
                    if count > 0:
                        print(f"  ✅ 거래 정보 추출 완료!")
                        print(f"     💰 크림 평균가: {kream_avg_price}")
                        print(f"     📦 크림 판매량: {kream_sales}")
                        
                        success_count += 1
                        
                        progress_queue.put({
                            'event': 'result',
                            'data': {
                                'index': index,
                                'result': {
                                    'success': True,
                                    'kream_data': {
                                        'avg_price': kream_avg_price,
                                        'sales': kream_sales
                                    }
                                }
                            }
                        })
                    else:
                        print(f"  ⚠️ 거래가 없음")
                        fail_count += 1
                        
                        progress_queue.put({
                            'event': 'result',
                            'data': {
                                'index': index,
                                'result': {
                                    'success': False,
                                    'error': '거래가 없음',
                                    'kream_data': None
                                }
                            }
                        })
                    
                except Exception as e:
                    print(f"  ❌ 거래 정보 추출 실패: {e}")
                    fail_count += 1
                    
                    progress_queue.put({
                        'event': 'result',
                        'data': {
                            'index': index,
                            'result': {
                                'success': False,
                                'error': '거래 정보 추출 실패',
                                'kream_data': None
                            }
                        }
                    })
                
            except Exception as e:
                print(f"  ❌ 오류 발생: {e}")
                fail_count += 1
                
                progress_queue.put({
                    'event': 'result',
                    'data': {
                        'index': index,
                        'result': {
                            'success': False,
                            'error': str(e),
                            'kream_data': None
                        }
                    }
                })
        
        # ==========================================
        # 전체 검색 완료
        # ==========================================
        print(f"\n{'='*60}")
        print(f"🎉 전체 검색 완료!")
        print(f"   ✅ 성공: {success_count}개")
        print(f"   ❌ 실패: {fail_count}개")
        print(f"   📊 전체: {len(product_codes)}개")
        print(f"{'='*60}\n")
        
        progress_queue.put({
            'event': 'complete',
            'data': {
                'message': f'✅ 전체 검색 완료 - {success_count}개 성공, {fail_count}개 실패',
                'total': len(product_codes),
                'success': success_count,
                'fail': fail_count
            }
        })
        
        # 브라우저 자동 종료
        print("\n🔒 크림 브라우저 자동 종료 중...")
        time.sleep(2)  # 결과 확인 대기
        close_browser_safe()
    
    except Exception as e:
        error_msg = f"오류 발생: {str(e)}"
        print(f"\n❌ {error_msg}")
        import traceback
        traceback.print_exc()
        progress_queue.put({'event': 'error', 'data': {'error': error_msg}})
    
    finally:
        print("\n🔚 검색 프로세스 종료")
        # finally에서도 브라우저 종료 보장
        if browser:
            close_browser_safe()


def close_browser_safe():
    """브라우저 안전하게 종료"""
    global browser, context, page
    
    print("\n🔒 브라우저 종료 중...")
    
    closed_count = 0
    
    try:
        if page:
            page.close()
            print("  ✓ 페이지 종료")
            closed_count += 1
    except Exception as e:
        print(f"  ⚠️ 페이지 종료 실패: {e}")
    
    try:
        if context:
            context.close()
            print("  ✓ 컨텍스트 종료")
            closed_count += 1
    except Exception as e:
        print(f"  ⚠️ 컨텍스트 종료 실패: {e}")
    
    try:
        if browser:
            browser.close()
            print("  ✓ 브라우저 종료")
            closed_count += 1
    except Exception as e:
        print(f"  ⚠️ 브라우저 종료 실패: {e}")
    
    browser = None
    context = None
    page = None
    
    if closed_count > 0:
        print(f"✅ 브라우저 완전 종료 ({closed_count}개 객체)")
    else:
        print("ℹ️  브라우저가 이미 종료되어 있음")


def stop_search():
    """검색 중단"""
    global stop_flag
    stop_flag = True
    print("🛑 검색 중단 플래그 설정됨")