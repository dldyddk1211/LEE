import os
import sys
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

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
KREAM_SEARCH_URL = "https://kream.co.kr/search"
KREAM_LOGIN_URL = "https://kream.co.kr/login"
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


def login_kream():
    """크림 로그인"""
    try:
        log("\n🔐 크림 로그인 시작", 'info')
        
        page = get_browser()
        
        # 로그인 페이지로 이동
        page.goto(KREAM_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        wait_stable(page, 2000)
        
        # 이미 로그인되어 있는지 확인
        try:
            # 로그인 상태 체크 (예: 마이페이지 요소가 있는지)
            page.wait_for_selector('a[href="/my"]', timeout=3000)
            log("  ✓ 이미 로그인되어 있습니다", 'success')
            return True
        except:
            pass
        
        # 로그인 진행
        log(f"  → 이메일: {KREAM_EMAIL}")
        
        # 이메일 입력
        try:
            email_input = page.wait_for_selector('input[type="email"], input[name="email"]', timeout=5000)
            email_input.fill(KREAM_EMAIL)
            wait_stable(page, 500)
        except Exception as e:
            log(f"  ❌ 이메일 입력란을 찾을 수 없습니다: {e}", 'error')
            safe_screenshot(page, "login_email_error")
            return False
        
        # 비밀번호 입력
        try:
            password_input = page.wait_for_selector('input[type="password"], input[name="password"]', timeout=5000)
            password_input.fill(KREAM_PASSWORD)
            wait_stable(page, 500)
        except Exception as e:
            log(f"  ❌ 비밀번호 입력란을 찾을 수 없습니다: {e}", 'error')
            safe_screenshot(page, "login_password_error")
            return False
        
        # 로그인 버튼 클릭
        try:
            login_btn = page.wait_for_selector('button[type="submit"], .login_btn_box button', timeout=5000)
            login_btn.click()
            wait_stable(page, 3000)
        except Exception as e:
            log(f"  ❌ 로그인 버튼을 찾을 수 없습니다: {e}", 'error')
            safe_screenshot(page, "login_button_error")
            return False
        
        # 로그인 성공 확인
        try:
            page.wait_for_selector('a[href="/my"]', timeout=5000)
            log("  ✅ 로그인 성공!", 'success')
            
            # 쿠키 저장
            save_cookies()
            
            return True
        except:
            log("  ❌ 로그인 실패", 'error')
            safe_screenshot(page, "login_failed")
            return False
        
    except Exception as e:
        log(f"❌ 로그인 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return False


def search_kream_product_detail(product_code):
    """
    크림에서 상품 검색하고 모델번호 추출
    
    1. 상품 검색
    2. 첫 번째 결과 클릭
    3. 상품 상세 페이지에서 모델번호 확인
    
    Args:
        product_code: 상품번호 (예: "CJ9219-001")
    
    Returns:
        dict: {'success': True/False, 'model_number': '...', 'product_id': '...', 'error': '...'}
    """
    try:
        log(f"\n🔍 크림 검색: {product_code}", 'info')
        
        page = get_browser()
        
        # 검색 URL로 이동
        search_url = f"{KREAM_SEARCH_URL}?keyword={product_code}&tab=products&footer=home"
        log(f"  → URL: {search_url}")
        
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        wait_stable(page, 2000)
        
        # 검색 결과 대기
        try:
            # 첫 번째 상품 카드 찾기
            first_product = page.wait_for_selector('.search_result_item, .product_card, .item_inner', timeout=10000)
            log(f"  ✓ 검색 결과 발견")
            
            # 첫 번째 상품 클릭
            first_product.click()
            wait_stable(page, 2000)
            
        except Exception as e:
            log(f"  ⚠️ 검색 결과 없음: {e}", 'warning')
            safe_screenshot(page, f"search_no_result_{product_code}")
            return {'success': False, 'error': '검색 결과 없음'}
        
        # 상품 상세 페이지에서 정보 추출
        try:
            # URL에서 product_id 추출 (예: https://kream.co.kr/products/20820)
            current_url = page.url
            product_id = current_url.split('/products/')[-1].split('?')[0] if '/products/' in current_url else None
            
            log(f"  → 상품 페이지: {current_url}")
            if product_id:
                log(f"  → Product ID: {product_id}")
            
            # 모델번호 추출 (여러 선택자 시도)
            model_number = None
            
            # 방법 1: JavaScript로 페이지 내용 읽기
            try:
                model_number = page.evaluate("""
                    () => {
                        // 모델번호를 포함하는 요소 찾기
                        const elements = document.querySelectorAll('*');
                        for (let el of elements) {
                            const text = el.textContent;
                            if (text && text.includes('모델번호')) {
                                // 다음 요소 또는 같은 요소에서 모델번호 추출
                                const parent = el.parentElement;
                                const siblings = Array.from(parent.children);
                                const index = siblings.indexOf(el);
                                
                                // 다음 형제 요소 확인
                                if (index < siblings.length - 1) {
                                    return siblings[index + 1].textContent.trim();
                                }
                                
                                // 같은 요소 내에서 추출
                                const match = text.match(/모델번호[:\\s]+([A-Z0-9-]+)/i);
                                if (match) return match[1];
                            }
                        }
                        
                        // dl/dt/dd 구조에서 찾기
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
            except Exception as e:
                log(f"  ⚠️ JavaScript 추출 실패: {e}", 'warning')
            
            if not model_number:
                # 방법 2: 선택자로 직접 찾기
                selectors = [
                    'dd.product_info',
                    '.model_number',
                    '.product-code',
                    'dd:has-text("모델번호")',
                ]
                
                for selector in selectors:
                    try:
                        el = page.query_selector(selector)
                        if el:
                            model_number = el.text_content().strip()
                            if model_number:
                                break
                    except:
                        continue
            
            # 모델번호와 검색 상품번호 비교
            if model_number:
                log(f"  ✅ 모델번호 발견: {model_number}", 'success')
                
                # 대소문자 구분 없이 비교
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


def close_browser():
    """브라우저 종료"""
    global _playwright, _browser, _context, _page
    
    if _page:
        try:
            _page.close()
        except:
            pass
        _page = None
    
    if _context:
        try:
            _context.close()
        except:
            pass
        _context = None
    
    if _browser:
        try:
            _browser.close()
        except:
            pass
        _browser = None
    
    if _playwright:
        try:
            _playwright.stop()
        except:
            pass
        _playwright = None
    
    log("✓ 크림 브라우저 종료", 'info')


def search_kream_product(product_code, page, callback=None):
    """
    크림에서 상품 검색
    
    Args:
        product_code: 상품번호 (예: "DZ5485-410")
        page: Playwright page 객체
        callback: 로그 콜백 함수
    
    Returns:
        list: 검색 결과 리스트 [{'name': ..., 'price': ..., 'image_url': ..., 'link': ...}, ...]
    """
    global LOG_CALLBACK
    LOG_CALLBACK = callback
    
    try:
        log(f"\n🔍 크림 검색: {product_code}", 'info')
        
        # 검색 페이지 이동
        search_url = f"{KREAM_SEARCH_URL}?keyword={product_code}"
        log(f"  → URL: {search_url}")
        
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        wait_stable(page, 2000)
        
        # 검색 결과 대기
        try:
            # 상품 카드 선택자 (크림 구조에 맞게 조정 필요)
            page.wait_for_selector(".product_card, .item_inner, .product-item", timeout=10000)
            log(f"  ✓ 검색 결과 로드됨")
        except:
            log(f"  ⚠️ 검색 결과 없음", 'warning')
            return []
        
        # JavaScript로 데이터 추출
        results = page.evaluate("""
            () => {
                const products = [];
                
                // 크림의 상품 카드 선택 (실제 HTML 구조에 맞게 조정 필요)
                const cards = document.querySelectorAll('.product_card, .item_inner, .product-item');
                
                cards.forEach((card, index) => {
                    if (index >= 10) return; // 최대 10개
                    
                    try {
                        // 상품명
                        const nameEl = card.querySelector('.product_name, .name, h3, .title');
                        const name = nameEl ? nameEl.textContent.trim() : '';
                        
                        // 가격
                        const priceEl = card.querySelector('.price, .amount, .product_price');
                        let price = '';
                        if (priceEl) {
                            price = priceEl.textContent.trim();
                        }
                        
                        // 이미지
                        const imgEl = card.querySelector('img');
                        const image_url = imgEl ? (imgEl.src || imgEl.dataset.src || '') : '';
                        
                        // 링크
                        const linkEl = card.querySelector('a');
                        let link = '';
                        if (linkEl) {
                            link = linkEl.href || '';
                            if (link && !link.startsWith('http')) {
                                link = 'https://kream.co.kr' + link;
                            }
                        }
                        
                        // 추가 정보
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
        
        # 결과 로그 출력
        for idx, product in enumerate(results, 1):
            log(f"    {idx}. {product.get('name', 'N/A')[:50]} - {product.get('price', 'N/A')}")
        
        return results
        
    except Exception as e:
        log(f"  ❌ 크림 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return []


def search_kream_products_batch(product_codes, callback=None):
    """
    여러 상품을 크림에서 일괄 검색
    
    Args:
        product_codes: 상품번호 리스트 ['ABC123', 'DEF456', ...]
        callback: 로그 콜백 함수
    
    Returns:
        dict: {product_code: [검색결과], ...}
    """
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
            # 브라우저 실행
            log("🌐 브라우저 시작...", 'info')
            browser = p.chromium.launch(headless=HEADLESS)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            
            # 쿠키 로드 (있으면)
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            # 각 상품 검색
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                # 진행률 전송
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                # 검색 시작 알림
                if callback:
                    callback(f"PRODUCT_START:{product_code}", 'info')
                
                # 검색 실행
                product_results = search_kream_product(product_code, page, callback)
                results[product_code] = product_results
                
                # 결과 전송
                if callback:
                    result_data = {
                        'product_code': product_code,
                        'products': product_results
                    }
                    callback(f"PRODUCT_RESULT:{json.dumps(result_data, ensure_ascii=False)}", 'data')
                
                # 다음 검색 전 대기 (크림 차단 방지)
                if idx < total:
                    delay = random.uniform(1.5, 3.0)
                    log(f"  💤 {delay:.1f}초 대기...", 'info')
                    time.sleep(delay)
            
            # 쿠키 저장
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


def search_kream_sourcing(product_codes, callback=None):
    """
    크림 소싱 검색 - app.py의 /kream_sourcing 라우트에서 호출
    
    Args:
        product_codes: 상품번호 리스트 ['ABC123', 'DEF456', ...]
        callback: 로그 콜백 함수
    
    Returns:
        dict: {
            'success': True/False,
            'results': {product_code: [검색결과], ...},
            'total_searched': 검색된 상품 수
        }
    """
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
            # 브라우저 실행
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
            
            # 쿠키 로드 (있으면)
            if os.path.exists(COOKIE_FILE):
                try:
                    with open(COOKIE_FILE, 'r') as f:
                        cookies = json.load(f)
                        context.add_cookies(cookies)
                        log("  ✓ 쿠키 로드 완료", 'success')
                except:
                    pass
            
            page = context.new_page()
            
            # 각 상품 검색
            for idx, product_code in enumerate(product_codes, 1):
                if stop_flag:
                    log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                    break
                
                # 진행률 전송
                if callback:
                    callback(f"PROGRESS:{idx}/{total}", 'progress')
                
                log(f"\n[{idx}/{total}] 상품: {product_code}", 'info')
                
                try:
                    # 검색 실행
                    search_results = search_kream_product(product_code, page, callback)
                    
                    if search_results:
                        results[product_code] = search_results
                        searched_count += 1
                        log(f"  ✅ {len(search_results)}개 결과 발견", 'success')
                    else:
                        results[product_code] = []
                        log(f"  ⚠️ 검색 결과 없음", 'warning')
                    
                    # 검색 간격 (서버 부하 방지)
                    if idx < total:
                        delay = random.uniform(1.0, 2.0)
                        time.sleep(delay)
                
                except Exception as e:
                    log(f"  ❌ 오류: {e}", 'error')
                    results[product_code] = []
            
            # 브라우저 종료
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


if __name__ == "__main__":
    print("=" * 60)
    print("🛒 KREAM 검색 엔진")
    print("=" * 60)
    print("\n이 파일은 app.py를 통해 실행됩니다.")
    print("\n직접 테스트하려면:")
    print("  python kream_search.py test")
    print("=" * 60)
    
    # 테스트 실행 여부 확인
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_kream_search()