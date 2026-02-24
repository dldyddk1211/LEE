import os
import sys
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

############################
# ===== 전역 변수 ===== #
###########################

# 중단 플래그
stop_flag = False

# 로그 콜백 함수
LOG_CALLBACK = None

# ✅ 전역 브라우저 객체 (Thread-Local 제거!)
_playwright = None
_browser = None
_context = None
_page = None

############################
# ===== MUSINSA CONFIG ===== #
############################

MUSINSA_BASE_URL = "https://www.musinsa.com"
MUSINSA_MAIN_URL = "https://www.musinsa.com/main/musinsa/recommend?gf=A"
MUSINSA_SEARCH_URL = "https://www.musinsa.com/search/musinsa/goods"
MUSINSA_LOGIN_URL = "https://www.musinsa.com/auth/login"
HEADLESS = False

# 무신사 로그인 정보
MUSINSA_ID = "yaglobal"
MUSINSA_PASSWORD = "dyddk1309!"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_data")
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "musinsa_cookies.json")

############################
# ===== 유틸리티 함수 ===== #
############################

def log(message, level='info'):
    """터미널 + GUI 로그 출력"""
    print(message)
    if LOG_CALLBACK:
        try:
            LOG_CALLBACK(message, level)
        except:
            pass


def wait_stable(page, ms=600):
    """페이지 안정화 대기"""
    try:
        page.wait_for_load_state("domcontentloaded")
    except:
        pass
    page.wait_for_timeout(ms)


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


############################
# ===== 브라우저 관리 ===== #
############################

def get_browser():
    """브라우저 인스턴스 가져오기 (싱글톤)"""
    global _playwright, _browser, _context, _page
    
    if _browser is None or _page is None:
        if _playwright is None:
            _playwright = sync_playwright().start()
        
        _browser = _playwright.chromium.launch(
            headless=HEADLESS,
            channel='chrome',
            args=[
                '--window-size=960,540',
                '--window-position=960,0',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        _context = _browser.new_context(
            viewport=None,
            no_viewport=True,
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        )
        
        # 쿠키 로드
        if os.path.exists(COOKIE_FILE):
            try:
                print(f"\n🍪 쿠키 로드 시작...")
                with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                musinsa_cookies = [c for c in cookies if 'musinsa.com' in c.get('domain', '')]
                
                if len(musinsa_cookies) > 0:
                    _context.add_cookies(cookies)
                    print(f"  ✅ 쿠키 로드 완료")
                    
            except Exception as e:
                print(f"  ⚠️ 쿠키 로드 실패: {e}")
        
        _page = _context.new_page()
        
        # JavaScript 탐지 우회
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


def close_musinsa_browser():
    """무신사 브라우저 완전 종료"""
    global _playwright, _browser, _context, _page
    
    print("🔄 무신사 브라우저 종료 시작...")
    
    if _page:
        try:
            _page.close()
            print("  ✓ 페이지 종료")
        except Exception as e:
            print(f"  ⚠️ 페이지 종료 오류: {e}")
        _page = None
    
    if _context:
        try:
            _context.close()
            print("  ✓ 컨텍스트 종료")
        except Exception as e:
            print(f"  ⚠️ 컨텍스트 종료 오류: {e}")
        _context = None
    
    if _browser:
        try:
            _browser.close()
            print("  ✓ 브라우저 종료")
        except Exception as e:
            print(f"  ⚠️ 브라우저 종료 오류: {e}")
        _browser = None
    
    if _playwright:
        try:
            _playwright.stop()
            print("  ✓ Playwright 종료")
        except Exception as e:
            print(f"  ⚠️ Playwright 종료 오류: {e}")
        _playwright = None
    
    print("✅ 무신사 브라우저 완전 종료 완료")
    time.sleep(0.2)


############################
# ===== 로그인 함수 ===== #
############################

def login_musinsa():
    """무신사 로그인 - 쿠키 체크 후 필요시에만 브라우저 열기"""
    global _playwright, _browser, _context, _page  # ✅ global 선언 추가
    
    # ✅ 쿠키 파일 체크
    if os.path.exists(COOKIE_FILE):
        file_size = os.path.getsize(COOKIE_FILE)
        
        if file_size > 10:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            musinsa_cookies = [c for c in cookies if 'musinsa.com' in c.get('domain', '')]
            
            if len(musinsa_cookies) > 0:
                print("♻️ 이미 로그인되어 있습니다 (쿠키 유효)")
                return {
                    'success': True,
                    'message': '✅ 이미 로그인되어 있습니다 (쿠키 사용)'
                }
    
    try:
        print("\n" + "="*60)
        print("🔐 무신사 로그인 시작")
        print("="*60)
        
        # ✅ 기존 브라우저가 있으면 종료
        if _browser is not None:
            close_musinsa_browser()
            time.sleep(1)
        
        # ✅ 새 브라우저 시작
        print("\n🌐 브라우저 시작 중...")
        
        _playwright = sync_playwright().start()
        
        _browser = _playwright.chromium.launch(
            headless=False,
            channel='chrome',
            args=[
                '--window-size=960,540',
                '--window-position=960,0',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        _context = _browser.new_context(
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
                    _context.add_cookies(cookies)
                print("  ✅ 쿠키 로드 완료")
            except:
                print("  ⚠️ 쿠키 로드 실패")
        
        _page = _context.new_page()
        
        print("✅ 브라우저 열림 (오른쪽 위, Chrome)")
        
        # 무신사 메인 페이지 이동
        print(f"\n📱 무신사 메인 페이지로 이동...")
        
        _page.goto(MUSINSA_MAIN_URL, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        print("✅ 메인 페이지 로드 완료")
        
        # 자연스러운 스크롤
        print("\n🖱️  페이지 자연스럽게 탐색 중...")
        
        scroll_y = random.randint(200, 400)
        _page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        scroll_y = random.randint(500, 700)
        _page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
        time.sleep(random.uniform(1.0, 2.0))
        
        _page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        time.sleep(random.uniform(0.5, 1.0))
        
        # 로그인 상태 확인
        print("\n🔍 로그인 상태 확인 중...")
        
        try:
            login_button = _page.locator('a[href*="/auth/login"]').first
            
            if login_button.count() > 0 and login_button.is_visible():
                print("  ⚠️ 로그인이 필요합니다")
                print("\n🔐 자동 로그인 시도 중...")
                
                # 로그인 페이지로 이동
                _page.goto(MUSINSA_LOGIN_URL, wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                
                print("  → 로그인 페이지 이동 완료")
                
                # 아이디 입력
                try:
                    id_input = _page.locator('input.login-v2-input__input[title="통합계정 또는 이메일"]').first
                    
                    if id_input.count() == 0:
                        id_input = _page.locator('input[placeholder*="통합계정"], input[placeholder*="이메일"]').first
                    
                    if id_input.count() == 0:
                        id_input = _page.locator('input[name="id"], input#id').first
                    
                    if id_input.count() > 0:
                        print(f"  → 아이디 입력: {MUSINSA_ID}")
                        id_input.click()
                        time.sleep(0.3)
                        id_input.fill(MUSINSA_ID)
                        time.sleep(0.5)
                    else:
                        print("  ⚠️ 아이디 입력란을 찾을 수 없음")
                except Exception as e:
                    print(f"  ⚠️ 아이디 입력 실패: {e}")
                
                # 비밀번호 입력
                try:
                    pw_input = _page.locator('input.login-v2-input__input[type="password"]').first
                    
                    if pw_input.count() == 0:
                        pw_input = _page.locator('input[placeholder*="비밀번호"]').first
                    
                    if pw_input.count() == 0:
                        pw_input = _page.locator('input[name="pw"], input[type="password"]').first
                    
                    if pw_input.count() > 0:
                        print(f"  → 비밀번호 입력")
                        pw_input.click()
                        time.sleep(0.3)
                        pw_input.fill(MUSINSA_PASSWORD)
                        time.sleep(0.5)
                    else:
                        print("  ⚠️ 비밀번호 입력란을 찾을 수 없음")
                except Exception as e:
                    print(f"  ⚠️ 비밀번호 입력 실패: {e}")
                
                # 로그인 버튼 클릭
                try:
                    login_submit = _page.locator('button.login-v2-button__button').first
                    
                    if login_submit.count() == 0:
                        login_submit = _page.locator('button:has-text("로그인")').first
                    
                    if login_submit.count() == 0:
                        login_submit = _page.locator('button[type="submit"], button.login-btn').first
                    
                    if login_submit.count() > 0:
                        print("  → 로그인 버튼 클릭")
                        login_submit.click()
                        time.sleep(3)
                    else:
                        print("  ⚠️ 로그인 버튼을 찾을 수 없음")
                except Exception as e:
                    print(f"  ⚠️ 로그인 버튼 클릭 실패: {e}")
                
                # 로그인 성공 확인
                _page.goto(MUSINSA_MAIN_URL, wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                
                login_check = _page.locator('a[href*="/auth/login"]').first
                
                if login_check.count() == 0 or not login_check.is_visible():
                    print("\n✅ 자동 로그인 성공!")
                    
                    # 쿠키 저장
                    cookies = _context.cookies()
                    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(cookies, f, ensure_ascii=False, indent=2)
                    
                    print(f"  ✅ 쿠키 저장 완료: {COOKIE_FILE}")
                    
                    # 브라우저 닫기
                    print("\n🔒 로그인 완료! 브라우저 닫는 중...")
                    close_musinsa_browser()
                    
                    return {'success': True, 'message': '로그인 성공'}
                else:
                    print("\n❌ 자동 로그인 실패")
                    return {'success': True, 'message': '수동 로그인 필요'}
            else:
                print("  ✅ 이미 로그인되어 있음!")
                
                # 쿠키 저장
                cookies = _context.cookies()
                with open(COOKIE_FILE, 'w') as f:
                    json.dump(cookies, f)
                
                # 브라우저 닫기
                print("\n🔒 로그인 확인 완료! 브라우저 닫는 중...")
                close_musinsa_browser()
                
                return {'success': True, 'message': '로그인 완료'}
                
        except Exception as e:
            print(f"\n⚠️ 로그인 확인 오류: {e}")
            return {'success': True, 'message': '수동 로그인 필요'}
            
    except Exception as e:
        print(f"\n❌ 로그인 오류: {e}")
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e)}
    

############################
# ===== 상품 상세 정보 추출 ===== #
############################
def extract_product_detail(page):
    """무신사 상품 상세 정보 추출"""
    try:
        product_info = {}
        
        print("\n" + "="*50)
        print("📦 상품 정보 추출 시작")
        print("="*50)
        
        # ✅ 페이지가 완전히 로드될 때까지 대기
        time.sleep(5.0)
                
        # ===== 이미지 URL 추출 ===== ✅ 수정
        try:
            log("🖼️ 이미지 URL 추출 중...", 'info')
            
            image_url = None
            
            # ✅ 1순위: 상세 페이지 제일 첫 이미지 (Thumbnail 0)
            try:
                first_img = page.locator('img[alt="Thumbnail 0"]').first
                if first_img.count() > 0:
                    src = first_img.get_attribute('src')
                    if src and 'image.msscdn.net' in src:
                        image_url = src
                        log(f"  ✅ 이미지 (1순위 - Thumbnail 0): {src[:80]}...", 'info')
            except Exception as e:
                log(f"  ⚠️ 1순위 실패: {e}", 'warning')
            
            # ✅ 2순위: Swiper 대표 이미지
            if not image_url:
                try:
                    swiper_img = page.locator('div.Swiper__ImageBox-sc-j9bha0-2 img').first
                    if swiper_img.count() > 0:
                        src = swiper_img.get_attribute('src')
                        if src and 'image.msscdn.net' in src:
                            image_url = src
                            log(f"  ✅ 이미지 (2순위 - Swiper): {src[:80]}...", 'info')
                except Exception as e:
                    log(f"  ⚠️ 2순위 실패: {e}", 'warning')
            
            # ✅ 3순위: 일반 상품 이미지 (alt에 상품명 포함)
            if not image_url:
                try:
                    # alt 속성에 상품번호나 상품명이 포함된 이미지
                    product_imgs = page.locator('img[alt*="/"]').all()  # "FQ3739-506" 같은 패턴
                    
                    for img in product_imgs[:5]:  # 상위 5개만 확인
                        try:
                            src = img.get_attribute('src')
                            alt = img.get_attribute('alt')
                            
                            if src and 'image.msscdn.net' in src:
                                # 배너 이미지 제외 (banner, logo, icon 등)
                                if alt and not any(word in alt.lower() for word in ['banner', 'logo', 'icon', 'ad']):
                                    image_url = src
                                    log(f"  ✅ 이미지 (3순위 - alt): {src[:80]}...", 'info')
                                    break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 3순위 실패: {e}", 'warning')
            
            # ✅ 최종: 아무 이미지나 (image.msscdn.net)
            if not image_url:
                try:
                    all_imgs = page.locator('img[src*="image.msscdn.net"]').all()
                    
                    for img in all_imgs[:10]:  # 상위 10개만
                        try:
                            src = img.get_attribute('src')
                            
                            # 썸네일이 아닌 큰 이미지 우선
                            if src and ('_big.jpg' in src or '_500.jpg' in src):
                                image_url = src
                                log(f"  ✅ 이미지 (최종): {src[:80]}...", 'info')
                                break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 최종 시도 실패: {e}", 'warning')
            
            # ✅ 이미지 URL 정제
            if image_url:
                # ?w= 쿼리스트링 제거
                if '?w=' in image_url:
                    image_url = image_url.split('?w=')[0]
                
                # /thumbnails/ 경로 정리
                if '/thumbnails/images/' in image_url:
                    image_url = image_url.replace('/thumbnails/images/', '/images/')
                elif '/thumbnails/' in image_url:
                    image_url = image_url.replace('/thumbnails/', '/images/')
                
                product_info['image_url'] = image_url
                log(f"  ✅ 최종 이미지 URL: {image_url[:80]}...", 'success')
            else:
                product_info['image_url'] = ''
                log("  ⚠️ 이미지를 찾을 수 없습니다", 'warning')
                
        except Exception as e:
            log(f"  ❌ 이미지 추출 오류: {e}", 'error')
            product_info['image_url'] = ''
            
           
        # ===== 제품명 추출 ===== ✅ 수정
        try:
            log("📝 제품명 추출 중...", 'info')
            
            product_name = None
            
            # ✅ 1순위: span.GoodsName-sc-1tpr922-1 (상품명 전용 클래스)
            try:
                name_elem = page.locator('span.GoodsName-sc-1tpr922-1').first
                if name_elem.count() > 0 and name_elem.is_visible(timeout=3000):
                    product_name = name_elem.text_content()
                    if product_name:
                        product_info['name'] = product_name.strip()
                        log(f"  ✅ 제품명 (1순위 - GoodsName): {product_info['name'][:80]}...", 'info')
            except Exception as e:
                log(f"  ⚠️ 1순위 실패: {e}", 'warning')
            
            # ✅ 2순위: span[class*="GoodsName"] (클래스 부분 매칭)
            if not product_name:
                try:
                    name_elem = page.locator('span[class*="GoodsName"]').first
                    if name_elem.count() > 0:
                        product_name = name_elem.text_content()
                        if product_name:
                            product_info['name'] = product_name.strip()
                            log(f"  ✅ 제품명 (2순위 - GoodsName*): {product_info['name'][:80]}...", 'info')
                except Exception as e:
                    log(f"  ⚠️ 2순위 실패: {e}", 'warning')
            
            # ✅ 3순위: text-title_18px_med 중에서 긴 텍스트 (50자 이상)
            if not product_name:
                try:
                    name_elems = page.locator('span.text-title_18px_med').all()
                    
                    for elem in name_elems:
                        try:
                            text = elem.text_content()
                            
                            # 50자 이상인 것만 (상품명은 보통 길다)
                            if text and len(text) >= 50:
                                product_name = text
                                product_info['name'] = product_name.strip()
                                log(f"  ✅ 제품명 (3순위 - 긴 텍스트): {product_info['name'][:80]}...", 'info')
                                break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 3순위 실패: {e}", 'warning')
            
            # ✅ 4순위: 품번 패턴이 포함된 span
            if not product_name:
                try:
                    spans = page.locator('span[data-mds="Typography"]').all()
                    
                    for span in spans:
                        try:
                            text = span.text_content()
                            
                            # 품번 패턴 포함 (예: "FQ3739-506")
                            import re
                            if text and re.search(r'[A-Z]{2,3}\d{4,5}-\d{2,3}', text):
                                product_name = text
                                product_info['name'] = product_name.strip()
                                log(f"  ✅ 제품명 (4순위 - 품번 포함): {product_info['name'][:80]}...", 'info')
                                break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 4순위 실패: {e}", 'warning')
            
            # ✅ 최종: 못 찾으면 '-'
            if not product_name:
                product_info['name'] = '-'
                log("  ⚠️ 제품명을 찾을 수 없습니다", 'warning')
                
        except Exception as e:
            log(f"  ⚠️ 제품명 추출 실패: {e}", 'warning')
            product_info['name'] = '-'

        # ===== 가격 추출 ===== ✅ 수정
        try:
            log("💰 최대혜택가 추출 중...", 'info')
            
            price = None
            
            # ✅ 1순위: span.text-title_18px_semi.text-red (최대혜택가)
            try:
                price_elem = page.locator('span.text-title_18px_semi.text-red').first
                if price_elem.count() > 0 and price_elem.is_visible(timeout=3000):
                    price_text = price_elem.text_content()
                    if price_text and '원' in price_text:
                        # 숫자만 추출
                        import re
                        numbers = re.findall(r'\d+', price_text.replace(',', ''))
                        if numbers:
                            price = int(''.join(numbers))
                            product_info['price'] = price
                            log(f"  ✅ 최대혜택가 (1순위): {price:,}원", 'info')
            except Exception as e:
                log(f"  ⚠️ 1순위 실패: {e}", 'warning')
            
            # ✅ 2순위: "최대혜택가" 라벨 앞의 가격
            if not price:
                try:
                    # JavaScript로 "최대혜택가" 앞에 있는 가격 찾기
                    price = page.evaluate("""
                        () => {
                            const allText = document.body.innerText;
                            
                            // "61,720원 최대혜택가" 패턴 찾기
                            const pricePattern = /([0-9]{1,3}(?:,?[0-9]{3})*)\s*원\s*최대혜택가/;
                            const match = allText.match(pricePattern);
                            
                            if (match && match[1]) {
                                const priceStr = match[1].replace(/,/g, '');
                                return parseInt(priceStr);
                            }
                            
                            return null;
                        }
                    """)
                    
                    if price and price > 0:
                        product_info['price'] = price
                        log(f"  ✅ 최대혜택가 (2순위 - JS): {price:,}원", 'info')
                except Exception as e:
                    log(f"  ⚠️ 2순위 실패: {e}", 'warning')
            
            # ✅ 3순위: span.text-red 중에서 "원" 포함
            if not price:
                try:
                    red_spans = page.locator('span.text-red').all()
                    
                    for span in red_spans:
                        try:
                            text = span.text_content()
                            
                            if text and '원' in text:
                                # 숫자 추출
                                import re
                                numbers = re.findall(r'\d+', text.replace(',', ''))
                                
                                if numbers:
                                    test_price = int(''.join(numbers))
                                    
                                    # 10,000원 ~ 10,000,000원 사이인지 확인
                                    if 10000 <= test_price <= 10000000:
                                        price = test_price
                                        product_info['price'] = price
                                        log(f"  ✅ 최대혜택가 (3순위 - text-red): {price:,}원", 'info')
                                        break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 3순위 실패: {e}", 'warning')
            
            # ✅ 4순위: 모든 span에서 "원" 포함된 가격
            if not price:
                try:
                    all_spans = page.locator('span').all()
                    
                    for span in all_spans[:100]:  # 상위 100개만
                        try:
                            text = span.text_content()
                            
                            if text and '원' in text and len(text) < 20:
                                # 숫자 추출
                                import re
                                numbers = re.findall(r'\d+', text.replace(',', ''))
                                
                                if numbers:
                                    test_price = int(''.join(numbers))
                                    
                                    # 10,000원 ~ 10,000,000원 사이
                                    if 10000 <= test_price <= 10000000:
                                        price = test_price
                                        product_info['price'] = price
                                        log(f"  ✅ 최대혜택가 (4순위 - 전체): {price:,}원", 'info')
                                        break
                        except:
                            continue
                except Exception as e:
                    log(f"  ⚠️ 4순위 실패: {e}", 'warning')
            
            # ✅ 최종: 못 찾으면 0
            if not price:
                product_info['price'] = 0
                log("  ⚠️ 가격을 찾을 수 없습니다", 'warning')
                
        except Exception as e:
            log(f"  ⚠️ 가격 추출 실패: {e}", 'warning')
            product_info['price'] = 0
                
        
        # ===== 품번 추출 ===== 
        try:
            log("🔢 품번 추출 중...", 'info')
            
            # JavaScript로 품번 추출 (라벨 기반만)
            product_code = page.evaluate("""
                () => {
                    const allText = document.body.innerText;
                    
                    // ✅ 1순위: '품번:' 또는 '모델번호:' 라벨 다음 텍스트 (엄격)
                    const codeRegex1 = /(품번|모델번호|상품코드)\\s*[:\\s]+([A-Z0-9][A-Z0-9-]+)/i;
                    const match1 = allText.match(codeRegex1);
                    
                    if (match1 && match1[2]) {
                        const code = match1[2].trim();
                        // 최소 5자 이상, 하이픈 포함
                        if (code.length >= 5 && code.includes('-')) {
                            return code;
                        }
                    }
                    
                    // ✅ 2순위: '품번:' 라벨 다음 텍스트 (완화)
                    const codeRegex2 = /(품번|모델번호|상품코드)\\s*[:\\s]+([A-Z0-9-]+)/i;
                    const match2 = allText.match(codeRegex2);
                    
                    if (match2 && match2[2]) {
                        const code = match2[2].trim();
                        // 하이픈 있고 5자 이상
                        if (code.includes('-') && code.length >= 5) {
                            return code;
                        }
                    }
                    
                    // ✅ 3순위: 숫자나 특수문자 앞까지만 추출
                    const codeRegex3 = /(품번|모델번호|상품코드)\\s*[:\\s]+([A-Z0-9-]+?)(?=\\s|$|[^A-Z0-9-])/i;
                    const match3 = allText.match(codeRegex3);
                    
                    if (match3 && match3[2]) {
                        const code = match3[2].trim();
                        if (code.length >= 5) {
                            return code;
                        }
                    }
                    
                    return null;
                }
            """)
            
            if product_code:
                product_info['product_code'] = product_code
                log(f"  ✅ 품번: {product_code}", 'info')
            else:
                product_info['product_code'] = '-'
                log("  ⚠️ 품번을 찾을 수 없습니다", 'warning')
                
        except Exception as e:
            log(f"  ⚠️ 품번 추출 실패: {e}", 'warning')
            product_info['product_code'] = '-'
        
        # ===== 브랜드 추출 ===== ✅ 수정
        try:
            log("🏷️ 브랜드 추출 중...", 'info')
            
            # 방법 1: URL에서 브랜드 추출
            current_url = page.url
            if '/brands/' in current_url:
                brand = current_url.split('/brands/')[1].split('/')[0]
                product_info['brand'] = brand
                log(f"  ✅ 브랜드 (URL): {brand}", 'info')
            else:
                # 방법 2: a 태그에서 추출
                brand_elem = page.locator('a[href*="/brands/"]').first
                if brand_elem.count() > 0:
                    brand = brand_elem.text_content()
                    product_info['brand'] = brand.strip() if brand else '-'
                    log(f"  ✅ 브랜드: {product_info['brand']}", 'info')
                else:
                    product_info['brand'] = '-'
                    
        except Exception as e:
            log(f"  ⚠️ 브랜드 추출 실패: {e}", 'warning')
            product_info['brand'] = '-'
        
        print("="*50)
        print("✅ 상품 정보 추출 완료")
        print("="*50)
        
        # ✅ 추출한 데이터 출력
        print(f"📊 추출된 데이터:")
        print(f"  이미지: {product_info.get('image_url', '')[:50]}...")
        print(f"  품번: {product_info.get('product_code', '-')}")
        print(f"  제품명: {product_info.get('name', '-')[:50]}...")
        print(f"  가격: {product_info.get('price', 0):,}원")
        print(f"  브랜드: {product_info.get('brand', '-')}")
        
        return product_info
        
    except Exception as e:
        log(f"❌ 상품 정보 추출 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return None
    


############################
# ===== 키워드 검색 (상세 정보) ===== #
############################

def search_musinsa_keyword_detail(keyword, max_items=10, callback=None):
    """무신사 키워드 검색 + 상품 상세 정보 추출 (무한 스크롤)"""
    global LOG_CALLBACK, stop_flag
    LOG_CALLBACK = callback
    stop_flag = False
    
    log("\n" + "=" * 60, 'info')
    log("🟤 무신사 키워드 검색 (무한 스크롤)", 'info')
    log("=" * 60, 'info')
    
    log(f"📊 검색 키워드: {keyword}", 'info')
    log(f"📦 수집 목표: {max_items}개\n", 'info')
    
    results = []
    
    try:
        # 쿠키 파일 확인
        if not os.path.exists(COOKIE_FILE):
            log("❌ 쿠키 파일 없음. 먼저 로그인이 필요합니다.", 'error')
            return {
                'success': False,
                'error': '로그인이 필요합니다',
                'results': []
            }
        
        # ✅ Thread-Local 브라우저 가져오기
        log("🌐 백그라운드 브라우저 시작...", 'info')
        page = get_browser()
        
        log("🌐 무신사 검색 시작...", 'info')
        
        # 검색 페이지로 직접 이동
        search_url = f"{MUSINSA_SEARCH_URL}?q={keyword}"
        log(f"  → 검색 URL: {search_url}", 'info')
        
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        wait_stable(page, 1500)
        
        # 로그인 상태 확인
        log("  → 로그인 상태 확인 중...", 'info')
        
        try:
            login_button = page.locator('a[href*="/auth/login"]').first
            
            if login_button.count() > 0 and login_button.is_visible():
                log("⚠️ 로그인 세션 만료!", 'error')
                close_musinsa_browser()
                
                return {
                    'success': False,
                    'error': '로그인 세션 만료',
                    'results': []
                }
            else:
                log("  ✅ 로그인 상태 확인", 'success')
                
        except Exception as e:
            log(f"  ⚠️ 로그인 확인 오류: {e}", 'warning')
        
        log("✅ 검색 페이지 로드 완료", 'success')
        
        # 검색 결과 총 개수 추출
        total_count = 0
        
        try:
            log("\n📊 검색 결과 개수 확인 중...", 'info')
            
            count_selectors = [
                'span.text-\\[13px\\]',
                'span[data-mds="Typography"]',
            ]
            
            for selector in count_selectors:
                try:
                    elements = page.locator(selector).all()
                    
                    for element in elements:
                        text = element.text_content()
                        
                        if '개' in text and any(c.isdigit() for c in text):
                            log(f"  → 발견된 텍스트: {text}", 'info')
                            
                            import re
                            numbers = re.findall(r'\d+', text.replace(',', ''))
                            
                            if numbers:
                                total_count = int(numbers[0])
                                log(f"  ✅ 총 검색 결과: {total_count:,}개", 'success')
                                break
                    
                    if total_count > 0:
                        break
                except:
                    continue
        except:
            pass
        
        # 실제 수집할 개수 결정
        target_count = min(max_items, total_count) if total_count > 0 else max_items
        log(f"  → 수집 목표: {target_count}개", 'info')
        
        # 정렬 변경
        log("\n🔄 정렬 변경 시작...", 'info')
        
        try:
            sort_button = page.locator('span:has-text("무신사 추천순")').first
            
            if sort_button.count() > 0:
                sort_button.click()
                wait_stable(page, 1500)
                
                new_item_option = page.locator('span:has-text("신상품(재입고)순")').first
                
                if new_item_option.count() > 0:
                    new_item_option.click()
                    wait_stable(page, 1500)
                    log("  ✅ 정렬 변경 완료!", 'success')
        except:
            log("  ⚠️ 정렬 변경 실패", 'warning')
        
        # 무한 스크롤로 상품 링크 수집
        log("\n🔄 무한 스크롤 시작...", 'info')
        
        product_links = []
        scroll_count = 0
        max_scrolls = 50
        no_new_items_count = 0
        
        while len(product_links) < target_count and scroll_count < max_scrolls:
            scroll_count += 1
            
            # 현재 페이지의 상품 링크 추출
            current_links = page.evaluate("""
                () => {
                    const links = [];
                    const productCards = document.querySelectorAll('a[href*="/products/"]');
                    
                    productCards.forEach(card => {
                        if (card.href && !links.includes(card.href)) {
                            links.push(card.href);
                        }
                    });
                    
                    return links;
                }
            """)
            
            # 새로운 링크만 추가
            new_links = [link for link in current_links if link not in product_links]
            
            if new_links:
                product_links.extend(new_links)
                no_new_items_count = 0
                log(f"  [{scroll_count}회 스크롤] 수집: {len(product_links):,}/{target_count:,}개", 'info')
            else:
                no_new_items_count += 1
                
                if no_new_items_count >= 3:
                    log("  ⚠️ 더 이상 새로운 상품이 없습니다.", 'warning')
                    break
            
            if len(product_links) >= target_count:
                log(f"  ✅ 목표 개수 달성: {len(product_links):,}개", 'success')
                break
            
            # 페이지 끝까지 스크롤
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(random.uniform(3.0, 4.0))
        
        # 실제 수집할 링크
        product_links = product_links[:target_count]
        
        log(f"\n📋 최종 수집 링크: {len(product_links)}개", 'success')
        log(f"🔍 상세 정보 수집 시작...\n", 'info')
        
        # 각 상품 상세 페이지 방문
        for idx, product_url in enumerate(product_links, 1):
            if stop_flag:
                log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                break
            
            log(f"[{idx}/{len(product_links)}] 상품 정보 수집", 'info')
            
            if callback:
                callback(f"PROGRESS:{idx}/{len(product_links)}", 'progress')
            
            try:
                page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
                wait_stable(page, 3000)
                
                product_info = extract_product_detail(page)
                
                if product_info:
                    product_info['url'] = product_url
                    product_info['source'] = 'MUSINSA'
                    product_info['keyword'] = keyword
                    
                    results.append(product_info)
                    
                    if callback:
                        callback(f"DATA:{json.dumps(product_info, ensure_ascii=False)}", 'data')
                    
                    log(f"  ✅ 수집 완료: {product_info.get('name', 'N/A')[:50]}", 'success')
                
                if idx < len(product_links):
                    time.sleep(random.uniform(2.0, 3.0))
                
            except Exception as e:
                log(f"  ❌ 상품 정보 수집 실패: {e}", 'error')
                continue
        
        # 검색 완료 후 브라우저 닫기
        log("\n🔒 검색 완료! 브라우저 닫는 중...", 'info')
        close_musinsa_browser()
        
        log("\n" + "=" * 60, 'success')
        log(f"✅ 무신사 검색 완료! 총 {len(results)}개 상품", 'success')
        log("=" * 60, 'success')
        
        return {
            'success': True,
            'keyword': keyword,
            'total_items': len(results),
            'results': results
        }
        
    except Exception as e:
        log(f"\n❌ 무신사 검색 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        
        close_musinsa_browser()
        
        return {
            'success': False,
            'error': str(e),
            'results': results
        }

def stop_search():
    """검색 중단"""
    global stop_flag
    stop_flag = True
    print("🛑 검색 중단 플래그 설정됨")


############################
# ===== 테스트 ===== #
############################

def test_musinsa_search():
    """테스트 함수"""
    print("\n" + "=" * 60)
    print("🧪 무신사 검색 테스트")
    print("=" * 60)
    
    # 로그인
    login_result = login_musinsa()
    
    if login_result.get('success'):
        # 상세 정보 검색 테스트
        result = search_musinsa_keyword_detail("나이키", max_items=3)
        
        print("\n📊 테스트 결과:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    # 브라우저 종료
    input("\n엔터를 누르면 브라우저가 종료됩니다...")
    close_musinsa_browser()


if __name__ == "__main__":
    print("=" * 60)
    print("🟤 MUSINSA 검색 엔진")
    print("=" * 60)
    print("\n이 파일은 app.py를 통해 실행됩니다.")
    print("\n직접 테스트하려면:")
    print("  python musinsa_search.py test")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_musinsa_search()