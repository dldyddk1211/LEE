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
# 상품 검색 (신규 - 백그라운드용)
# ==========================================
def search_product(product_code):
    """크림에서 상품 검색 - 포이즌 방식 타이핑"""
    global page
    
    try:
        if page is None:
            return {'success': False, 'error': '브라우저 없음'}
        
        print(f"🔍 상품 검색: {product_code}")
        
        # ==========================================
        # ✅ 포이즌 방식: 검색창 찾기
        # ==========================================
        search_input = None
        for selector in ['input[type="search"]', 'input[placeholder*="검색"]']:
            try:
                search_input = page.locator(selector).first
                if search_input.count() > 0:
                    break
            except:
                continue
        
        if not search_input:
            return {'success': False, 'error': '검색창 없음'}
        
        # ==========================================
        # ✅ 포이즌 방식: 검색창 클릭 후 클리어
        # ==========================================
        try:
            search_input.click()
            page.keyboard.press("Control+A")
            page.keyboard.press("Delete")
            wait_stable(page, 100)
        except:
            pass
        
        # ==========================================
        # ✅ 포이즌 방식: type() 사용 (delay 30ms)
        # ==========================================
        search_input.type(product_code, delay=30)
        wait_stable(page, 200)
        
        # Enter로 검색
        page.keyboard.press("Enter")
        print(f"  ✓ 검색 실행")
        
        # ✅ 포이즌 방식: 충분한 대기
        wait_stable(page, 2000)  # 2초
        
        # ==========================================
        # 검색 결과 대기
        # ==========================================
        try:
            page.wait_for_selector('.search_result_item, .product_card, a[href*="/products/"]', timeout=10000)
        except:
            return {'success': False, 'error': '검색 결과 없음'}
        
        # ==========================================
        # 첫 번째 결과 클릭
        # ==========================================
        try:
            print("  📦 첫 번째 결과 클릭...")
            
            first_product = page.locator('.search_result_item, .product_card, a[href*="/products/"]').first
            
            # hover 후 클릭
            first_product.hover()
            time.sleep(random.uniform(0.3, 0.7))
            first_product.click()
            
            wait_stable(page, 2000)
            
            # ==========================================
            # ✅ 포이즌 방식: evaluate()로 정보 추출
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
                    
                    // 가격 찾기
                    let price = '';
                    const priceEl = document.querySelector('.price, .product_price, span:has-text("원")');
                    if (priceEl) price = priceEl.textContent.trim();
                    
                    return {
                        model_number: model_number,
                        product_name: product_name,
                        price: price
                    };
                }
            """)
            
            if not data or not data.get('model_number'):
                data = {'model_number': product_code, 'product_name': 'N/A', 'price': 'N/A'}
            
            result = {
                'success': True,
                'model_number': data['model_number'],
                'product_name': data['product_name'],
                'price': data['price']
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
# 상품 정보 추출 (신규)
# ==========================================
def extract_product_info(page, product_code):
    """상품 상세 페이지에서 정보 추출
    
    Args:
        page: Playwright page 객체
        product_code (str): 검색한 상품번호
    
    Returns:
        dict: 추출된 상품 정보
    """
    try:
        # 모델번호 추출
        model_number = None
        try:
            # JavaScript로 모델번호 찾기
            model_number = page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('모델번호')) {
                            const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                            if (match) return match[1];
                            
                            // 다음 요소 확인
                            const parent = el.parentElement;
                            const siblings = Array.from(parent.children);
                            const index = siblings.indexOf(el);
                            if (index < siblings.length - 1) {
                                return siblings[index + 1].textContent.trim();
                            }
                        }
                    }
                    
                    // dl/dt/dd 구조
                    const dts = document.querySelectorAll('dt');
                    for (let dt of dts) {
                        if (dt.textContent.includes('모델번호')) {
                            const dd = dt.nextElementSibling;
                            if (dd && dd.tagName === 'DD') {
                                return dd.textContent.trim();
                            }
                        }
                    }
                    return null;
                }
            """)
        except:
            model_number = product_code
        
        if not model_number:
            model_number = product_code
        
        # 상품명 추출
        product_name = 'N/A'
        try:
            product_name = page.locator('.product_title, .product-title, h1').first.inner_text()
        except:
            pass
        
        # 가격 추출
        price = 'N/A'
        try:
            price = page.locator('.price, .product_price, span:has-text("원")').first.inner_text()
        except:
            pass
        
        return {
            'success': True,
            'model_number': model_number,
            'product_name': product_name,
            'price': price
        }
        
    except Exception as e:
        print(f"❌ 정보 추출 오류: {e}")
        return {
            'success': False,
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
    """크림에서 상품 검색하고 모델번호 추출 (기존 함수 유지)"""
    try:
        log(f"\n🔍 크림 검색: {product_code}", 'info')
        
        page = get_browser()
        
        search_url = f"{KREAM_SEARCH_URL}?keyword={product_code}&tab=products&footer=home"
        log(f"  → URL: {search_url}")
        
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        wait_stable(page, 2000)
        
        try:
            first_product = page.wait_for_selector('.search_result_item, .product_card, .item_inner', timeout=10000)
            log(f"  ✓ 검색 결과 발견")
            first_product.click()
            wait_stable(page, 2000)
            
        except Exception as e:
            log(f"  ⚠️ 검색 결과 없음: {e}", 'warning')
            safe_screenshot(page, f"search_no_result_{product_code}")
            return {'success': False, 'error': '검색 결과 없음'}
        
        try:
            current_url = page.url
            product_id = current_url.split('/products/')[-1].split('?')[0] if '/products/' in current_url else None
            
            log(f"  → 상품 페이지: {current_url}")
            if product_id:
                log(f"  → Product ID: {product_id}")
            
            # 모델번호 추출
            model_number = page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');
                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('모델번호')) {
                            const parent = el.parentElement;
                            const siblings = Array.from(parent.children);
                            const index = siblings.indexOf(el);
                            
                            if (index < siblings.length - 1) {
                                return siblings[index + 1].textContent.trim();
                            }
                            
                            const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                            if (match) return match[1];
                        }
                    }
                    
                    const dts = document.querySelectorAll('dt');
                    for (let dt of dts) {
                        if (dt.textContent.includes('모델번호')) {
                            const dd = dt.nextElementSibling;
                            if (dd && dd.tagName === 'DD') {
                                return dd.textContent.trim();
                            }
                        }
                    }
                    return null;
                }
            """)
            
            if model_number:
                log(f"  ✅ 모델번호 발견: {model_number}", 'success')
                
                if model_number.upper() == product_code.upper():
                    log(f"  ✅ 모델번호 일치!", 'success')
                    safe_screenshot(page, f"match_{product_code}")
                    
                    return {
                        'success': True,
                        'model_number': model_number,
                        'product_id': product_id,
                        'url': current_url
                    }
                else:
                    log(f"  ⚠️ 모델번호 불일치: {model_number} != {product_code}", 'warning')
                    safe_screenshot(page, f"mismatch_{product_code}")
                    
                    return {
                        'success': False,
                        'model_number': model_number,
                        'product_id': product_id,
                        'url': current_url,
                        'error': f'모델번호 불일치 ({model_number})'
                    }
            else:
                log(f"  ❌ 모델번호를 찾을 수 없습니다", 'error')
                safe_screenshot(page, f"no_model_{product_code}")
                
                return {
                    'success': False,
                    'product_id': product_id,
                    'url': current_url,
                    'error': '모델번호 없음'
                }
                
        except Exception as e:
            log(f"  ❌ 상품 정보 추출 실패: {e}", 'error')
            safe_screenshot(page, f"extract_error_{product_code}")
            import traceback
            traceback.print_exc()
            
            return {'success': False, 'error': str(e)}
        
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


# ==========================================
# 백그라운드 검색 함수 (app.py에서 호출)
# ==========================================
def background_kream_search(task_id, product_codes, progress_queue):
    """백그라운드 크림 검색 - 브라우저 재사용 또는 새로 열기"""
    global stop_flag, browser, context, page
    
    try:
        print(f"\n{'='*60}")
        print(f"🚀 백그라운드 검색 시작 (Task: {task_id})")
        print(f"📦 검색할 상품: {len(product_codes)}개")
        print(f"{'='*60}\n")
        
        stop_flag = False
        
        # ==========================================
        # 1단계: 메인 페이지 열기 (또는 재사용)
        # ==========================================
        print("🎯 [1단계] 크림 브라우저 확인")
        progress_queue.put({
            'event': 'message',
            'data': {'message': '[1단계] 브라우저 확인 중...'}
        })
        
        # 브라우저가 이미 열려있는지 확인
        browser_exists = False
        if browser is not None and page is not None:
            try:
                # 페이지가 살아있는지 테스트
                page.url
                browser_exists = True
                print("  ✅ 기존 브라우저 재사용")
            except:
                # 브라우저가 죽어있으면 None으로 초기화
                print("  ⚠️ 기존 브라우저 종료됨, 새로 열기")
                browser = None
                context = None
                page = None
        
        # 브라우저가 없으면 새로 열기
        if browser is None:
            print("  📱 새 브라우저 열기...")
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
            
            page = context.new_page()
            print("  ✅ 브라우저 열림 (오른쪽 위)")
            
            # 메인 페이지 접속
            print("  📱 크림 메인 페이지로 이동...")
            page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)
            
            print("  ✅ [1단계 완료] 메인 페이지 로드 성공!")
        else:
            # 기존 브라우저 재사용
            print("  🔄 기존 브라우저 재사용")
            
            # 현재 URL 확인
            current_url = page.url
            print(f"  → 현재 URL: {current_url[:50]}...")
            
            # 크림 메인이 아니면 이동
            if 'kream.co.kr' not in current_url or 'search' in current_url:
                print("  📱 크림 메인 페이지로 이동...")
                page.goto('https://kream.co.kr/', wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
            
            print("  ✅ [1단계 완료] 브라우저 준비됨!")
        
        progress_queue.put({
            'event': 'message',
            'data': {'message': '[1단계 완료] 브라우저 준비 ✅'}
        })
        
        # ==========================================
        # 2단계: 검색 버튼 찾기
        # ==========================================
        print("\n🎯 [2단계] 검색 버튼(돋보기) 찾기")
        progress_queue.put({
            'event': 'message',
            'data': {'message': '[2단계] 검색 버튼 찾기 중...'}
        })
        
        # 실제 크림 버튼 선택자
        button_selectors = [
            'button.btn_search.header-search-button',
            'button.btn_search',
            'button.header-search-button',
            'button[data-v-32ec60ef]',
            'button:has(svg)',
        ]
        
        search_button = None
        found_btn_selector = None
        
        for selector in button_selectors:
            try:
                temp = page.locator(selector).first
                if temp.count() > 0 and temp.is_visible():
                    search_button = temp
                    found_btn_selector = selector
                    print(f"  ✅ 검색 버튼 발견! (선택자: {selector})")
                    break
            except:
                continue
        
        if not search_button:
            error_msg = "검색 버튼을 찾을 수 없습니다"
            print(f"  ❌ {error_msg}")
            
            # 스크린샷
            try:
                page.screenshot(path=f"error_no_button_{int(time.time())}.png")
                print(f"  📸 스크린샷 저장됨")
            except:
                pass
            
            progress_queue.put({
                'event': 'error',
                'data': {'error': error_msg}
            })
            return
        
        print("  ✅ [2단계 완료] 검색 버튼 찾기 성공!")
        
        progress_queue.put({
            'event': 'message',
            'data': {'message': f'[2단계 완료] 검색 버튼 찾기 성공 ✅'}
        })
        
        # ==========================================
        # 3단계: 검색 버튼 클릭
        # ==========================================
        print("\n🎯 [3단계] 검색 버튼 클릭")
        progress_queue.put({
            'event': 'message',
            'data': {'message': '[3단계] 검색 버튼 클릭 중...'}
        })
        
        # 버튼 클릭
        print("  🖱️  검색 버튼 클릭...")
        search_button.click()
        
        # 클릭 후 대기
        time.sleep(0.8)
        
        print("  ✅ [3단계 완료] 검색 버튼 클릭 성공!")
        
        progress_queue.put({
            'event': 'message',
            'data': {'message': '[3단계 완료] 검색 버튼 클릭 성공 ✅'}
        })
        
        # ==========================================
        # ⏹️ 여기서 멈춤!
        # ==========================================
        print("\n" + "="*60)
        print("⏹️  3단계까지 완료! 여기서 멈춥니다.")
        print("="*60)
        print("💡 브라우저 확인:")
        print("   ✅ 돋보기 버튼을 클릭했습니다")
        print("   ✅ 검색창이 나타났나요?")
        print(f"   ✅ 버튼 선택자: {found_btn_selector}")
        if browser_exists:
            print("   🔄 기존 브라우저를 재사용했습니다")
        else:
            print("   🆕 새 브라우저를 열었습니다")
        print("="*60 + "\n")
        
        progress_queue.put({
            'event': 'complete',
            'data': {
                'message': '✅ 3단계까지 완료 - 검색 버튼 클릭됨!',
                'button_selector': found_btn_selector,
                'browser_reused': browser_exists,
                'total_processed': 0
            }
        })
        
        return
        
    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        
        progress_queue.put({
            'event': 'error',
            'data': {'error': str(e)}
        })

# ==========================================
# 추가: close_browser_safe() 함수
# ==========================================
def close_browser_safe():
    """브라우저 안전하게 종료"""
    global browser, context, page
    
    try:
        if page:
            page.close()
            print("  ✓ 페이지 종료")
    except:
        pass
    
    try:
        if context:
            context.close()
            print("  ✓ 컨텍스트 종료")
    except:
        pass
    
    try:
        if browser:
            browser.close()
            print("  ✓ 브라우저 종료")
    except:
        pass
    
    # 전역 변수 초기화
    browser = None
    context = None
    page = None
    
    print("✅ 브라우저 완전 종료")


def stop_search():
    """검색 중단"""
    global stop_flag
    stop_flag = True
    print("🛑 검색 중단 플래그 설정됨")