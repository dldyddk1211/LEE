import os
import sys
import json
import random
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

############################
# ===== 전역 변수 ===== #
############################

# 중단 플래그
stop_flag = False

# 로그 콜백 함수
LOG_CALLBACK = None

# 전역 브라우저 객체
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
        
       
        # ✅ 쿠키 로드 (상세 로그 추가)
        if os.path.exists(COOKIE_FILE):
            try:
                print(f"\n🍪 쿠키 로드 시작...")
                print(f"  → 쿠키 파일: {COOKIE_FILE}")
                
                with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                
                print(f"  → 로드된 쿠키 개수: {len(cookies)}개")
                
                # ✅ 무신사 쿠키만 필터링
                musinsa_cookies = [c for c in cookies if 'musinsa.com' in c.get('domain', '')]
                print(f"  → 무신사 쿠키: {len(musinsa_cookies)}개")
                
                if len(musinsa_cookies) > 0:
                    # ✅ 쿠키 적용
                    _context.add_cookies(cookies)
                    print(f"  ✅ 쿠키 로드 완료")
                    
                    # ✅ 주요 쿠키 확인
                    cookie_names = [c.get('name', '') for c in musinsa_cookies]
                    print(f"  → 쿠키 목록: {', '.join(cookie_names[:5])}...")
                else:
                    print(f"  ⚠️ 무신사 쿠키가 없습니다!")
                    
            except Exception as e:
                print(f"  ⚠️ 쿠키 로드 실패: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"  ⚠️ 쿠키 파일 없음: {COOKIE_FILE}")
        
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
    """무신사 로그인 - 로그인 후 브라우저 닫기"""
    global _browser, _context, _page
    
    try:
        print("\n" + "="*60)
        print("🔐 무신사 로그인 시작")
        print("="*60)
        
        # 기존 브라우저가 있으면 종료
        if _browser is not None:
            try:
                print("  → 기존 브라우저 종료 중...")
                close_musinsa_browser()
                time.sleep(1)
            except:
                pass
        
        # 새 브라우저 시작
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
        print(f"   URL: {MUSINSA_MAIN_URL}")
        
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
            # 로그인 버튼 확인
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
                    
                    # ✅ 로그인 성공 후 잠시 대기 (쿠키 완전 생성 대기)
                    print("  → 쿠키 생성 대기 중...")
                    time.sleep(2)
                    
                    # ✅ 쿠키 저장
                    try:
                        cookies = _context.cookies()
                        
                        # ✅ 쿠키 내용 확인
                        print(f"  → 저장할 쿠키 개수: {len(cookies)}개")
                        
                        # ✅ 도메인 확인
                        musinsa_cookies = [c for c in cookies if 'musinsa.com' in c.get('domain', '')]
                        print(f"  → 무신사 쿠키: {len(musinsa_cookies)}개")
                        
                        if len(musinsa_cookies) == 0:
                            print("  ⚠️ 무신사 쿠키가 없습니다!")
                        
                        # ✅ 쿠키 저장
                        with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                            json.dump(cookies, f, ensure_ascii=False, indent=2)
                        
                        print(f"  ✅ 쿠키 저장 완료: {COOKIE_FILE}")
                        
                        # ✅ 저장된 파일 확인
                        if os.path.exists(COOKIE_FILE):
                            file_size = os.path.getsize(COOKIE_FILE)
                            print(f"  ✅ 쿠키 파일 크기: {file_size} bytes")
                        else:
                            print(f"  ❌ 쿠키 파일 저장 실패!")
                            
                    except Exception as e:
                        print(f"  ⚠️ 쿠키 저장 실패: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # ✅ 브라우저 닫기
                    print("\n🔒 로그인 완료! 브라우저 닫는 중...")
                    close_musinsa_browser()
                    
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print("💡 로그인 완료! 대기 상태로 전환합니다")
                    print("💡 검색 시작 버튼을 누르면 백그라운드로 검색합니다")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    
                    return {'success': True, 'message': '로그인 성공'}
                else:
                    print("\n❌ 자동 로그인 실패")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    print("💡 브라우저에서 수동으로 로그인해주세요")
                    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                    return {'success': True, 'message': '수동 로그인 필요'}
            else:
                print("  ✅ 이미 로그인되어 있음!")
                
                # ✅ 쿠키 저장
                try:
                    cookies = _context.cookies()
                    with open(COOKIE_FILE, 'w') as f:
                        json.dump(cookies, f)
                    print("  ✅ 쿠키 저장 완료")
                except Exception as e:
                    print(f"  ⚠️ 쿠키 저장 실패: {e}")
                
                # ✅ 브라우저 닫기
                print("\n🔒 로그인 확인 완료! 브라우저 닫는 중...")
                close_musinsa_browser()
                
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print("💡 로그인 완료! 대기 상태로 전환합니다")
                print("💡 검색 시작 버튼을 누르면 백그라운드로 검색합니다")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                return {'success': True, 'message': '로그인 완료'}
                
        except Exception as e:
            print(f"\n⚠️ 로그인 확인 오류: {e}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("💡 브라우저에서 수동으로 로그인해주세요")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
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
        
        # ===== 1. 이미지 URL =====
        try:
            print("🖼️  이미지 URL 추출 중...")
            
            # 메인 이미지 선택자
            img_selectors = [
                'div.Swiper__ImageBox-sc-j9bha0-2 img',  # 메인 이미지
                'img.Swiper__Img-sc-j9bha0-8',
                '.swiper-slide img[src*="image.msscdn.net"]'
            ]
            
            image_url = None
            
            for selector in img_selectors:
                try:
                    img = page.locator(selector).first
                    if img.count() > 0:
                        src = img.get_attribute('src')
                        if src and 'image.msscdn.net' in src:
                            image_url = src
                            print(f"  ✅ 이미지 URL: {src[:80]}...")
                            break
                except Exception as e:
                    print(f"  ⚠️ {selector} 시도 실패: {e}")
                    continue
            
            product_info['image_url'] = image_url
            
        except Exception as e:
            print(f"  ❌ 이미지 추출 오류: {e}")
            product_info['image_url'] = None
        
        # ===== 2. 품번 (상품코드) =====
        try:
            print("🔢 품번 추출 중...")
            
            # dd 태그에서 품번 추출
            code_selectors = [
                'dd.text-body_13px_reg',
                'dd[data-mds="Typography"]',
                'dd.text-gray-600'
            ]
            
            product_code = None
            
            for selector in code_selectors:
                try:
                    code_elements = page.locator(selector).all()
                    
                    for element in code_elements:
                        text = element.text_content().strip()
                        
                        # "FQ3739-506" 형식 찾기 (영문+숫자-숫자)
                        import re
                        if re.match(r'^[A-Z0-9]+-[A-Z0-9]+$', text):
                            product_code = text
                            print(f"  ✅ 품번: {product_code}")
                            break
                    
                    if product_code:
                        break
                        
                except Exception as e:
                    print(f"  ⚠️ {selector} 시도 실패: {e}")
                    continue
            
            product_info['product_code'] = product_code or '-'
            
        except Exception as e:
            print(f"  ❌ 품번 추출 오류: {e}")
            product_info['product_code'] = '-'
        
        # ===== 3. 제품명 =====
        try:
            print("📝 제품명 추출 중...")
            
            # img 태그의 alt 속성에서 제품명 추출
            name_selectors = [
                'img.Swiper__Img-sc-j9bha0-8[alt]',
                'div.Swiper__ImageBox-sc-j9bha0-2 img[alt]',
                '.swiper-slide img[alt]'
            ]
            
            product_name = None
            
            for selector in name_selectors:
                try:
                    img = page.locator(selector).first
                    if img.count() > 0:
                        alt = img.get_attribute('alt')
                        if alt and len(alt) > 0:
                            product_name = alt.strip()
                            print(f"  ✅ 제품명: {product_name[:50]}...")
                            break
                except Exception as e:
                    print(f"  ⚠️ {selector} 시도 실패: {e}")
                    continue
            
            product_info['name'] = product_name or '-'
            
        except Exception as e:
            print(f"  ❌ 제품명 추출 오류: {e}")
            product_info['name'] = '-'
        
        # ===== 4. 최대혜택가 =====
        try:
            print("💰 최대혜택가 추출 중...")
            
            # "61,720원" 텍스트 찾기
            price_selectors = [
                'span.text-title_18px_semi.text-red',
                'span.text-red[data-mds="Typography"]',
                'div.MaxBenefitPriceTitle__PointDetailTooltip-sc-8vaunm-1 span.text-red'
            ]
            
            price = None
            
            for selector in price_selectors:
                try:
                    price_elements = page.locator(selector).all()
                    
                    for element in price_elements:
                        text = element.text_content().strip()
                        
                        # "61,720원" 형식 찾기
                        if '원' in text and any(c.isdigit() for c in text):
                            # 숫자만 추출
                            import re
                            price_num = int(re.sub(r'[^0-9]', '', text))
                            
                            if price_num > 0:
                                price = price_num
                                print(f"  ✅ 최대혜택가: {price:,}원")
                                break
                    
                    if price:
                        break
                        
                except Exception as e:
                    print(f"  ⚠️ {selector} 시도 실패: {e}")
                    continue
            
            product_info['price'] = price
            
        except Exception as e:
            print(f"  ❌ 가격 추출 오류: {e}")
            product_info['price'] = None
        
        # ===== 5. 브랜드 (제품명에서 추출) =====
        try:
            # "나이키(NIKE) ACG 긴소매..." → "나이키"
            if product_info.get('name'):
                name = product_info['name']
                
                # "나이키(NIKE)" 형식에서 앞부분만 추출
                import re
                brand_match = re.match(r'^([^\(]+)', name)
                
                if brand_match:
                    brand = brand_match.group(1).strip()
                    product_info['brand'] = brand
                    print(f"  ✅ 브랜드: {brand}")
                else:
                    product_info['brand'] = '-'
            else:
                product_info['brand'] = '-'
                
        except Exception as e:
            print(f"  ⚠️ 브랜드 추출 오류: {e}")
            product_info['brand'] = '-'
        
        print("="*50)
        print("✅ 상품 정보 추출 완료")
        print("="*50)
        
        return product_info
        
    except Exception as e:
        print(f"\n❌ 상품 정보 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


############################
# ===== 키워드 검색 (상세 정보) ===== #
############################

def search_musinsa_keyword_detail(keyword, max_items=10, callback=None):
    """무신사 키워드 검색 + 상품 상세 정보 추출 (무한 스크롤)"""
    global LOG_CALLBACK, stop_flag, _page
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
        
        # 백그라운드 브라우저 시작
        log("🌐 백그라운드 브라우저 시작...", 'info')
        _page = get_browser()
        
        log("🌐 무신사 검색 시작...", 'info')
        log(f"   키워드: {keyword}", 'info')
        
        # 검색 페이지로 직접 이동
        search_url = f"{MUSINSA_SEARCH_URL}?q={keyword}"
        log(f"  → 검색 URL: {search_url}", 'info')
        
        _page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        wait_stable(_page, 3000)
        
        # 로그인 상태 확인
        log("  → 로그인 상태 확인 중...", 'info')
        
        try:
            login_button = _page.locator('a[href*="/auth/login"]').first
            
            if login_button.count() > 0 and login_button.is_visible():
                log("⚠️ 로그인 세션 만료!", 'error')
                close_musinsa_browser()
                
                return {
                    'success': False,
                    'error': '로그인 세션 만료. 무신사 모드를 다시 선택하여 로그인해주세요.',
                    'results': []
                }
            else:
                log("  ✅ 로그인 상태 확인", 'success')
                
        except Exception as e:
            log(f"  ⚠️ 로그인 확인 오류: {e}", 'warning')
        
        log("✅ 검색 페이지 로드 완료", 'success')
        
        # ✅ 검색 결과 총 개수 추출
        total_count = 0
        
        try:
            log("\n📊 검색 결과 개수 확인 중...", 'info')
            
            count_selectors = [
                'span.text-\\[13px\\]',
                'span[data-mds="Typography"]',
                'span.text-gray-600'
            ]
            
            for selector in count_selectors:
                try:
                    elements = _page.locator(selector).all()
                    
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
                        
                except Exception as e:
                    continue
            
            if total_count == 0:
                log("  ⚠️ 검색 결과 개수를 찾을 수 없음", 'warning')
            
        except Exception as e:
            log(f"  ⚠️ 검색 결과 개수 추출 실패: {e}", 'warning')
        
        # 실제 수집할 개수 결정
        if total_count > 0:
            target_count = min(max_items, total_count)
            log(f"  → 수집 목표: {target_count:,}개 (전체 {total_count:,}개 중)", 'info')
        else:
            target_count = max_items
            log(f"  → 수집 목표: {target_count}개", 'info')
        
        # ✅ 정렬 변경 (무신사 추천순 → 신상품(재입고)순)
        log("\n🔄 정렬 변경 시작...", 'info')
        
        try:
            log("  → '무신사 추천순' 버튼 찾는 중...", 'info')
            
            sort_button = None
            sort_selectors = [
                'span:has-text("무신사 추천순")',
                'button:has-text("무신사 추천순")',
            ]
            
            for selector in sort_selectors:
                try:
                    btn = _page.locator(selector).first
                    if btn.count() > 0:
                        sort_button = btn
                        log(f"  ✅ 정렬 버튼 발견", 'success')
                        break
                except:
                    continue
            
            if sort_button and sort_button.count() > 0:
                log("  → '무신사 추천순' 클릭...", 'info')
                sort_button.click()
                wait_stable(_page, 2000)
                
                log("  → '신상품(재입고)순' 옵션 찾는 중...", 'info')
                
                new_item_option = None
                new_item_selectors = [
                    'span:has-text("신상품(재입고)순")',
                    'li:has-text("신상품(재입고)순")',
                ]
                
                for selector in new_item_selectors:
                    try:
                        option = _page.locator(selector).first
                        if option.count() > 0 and option.is_visible():
                            new_item_option = option
                            log(f"  ✅ 옵션 발견", 'success')
                            break
                    except:
                        continue
                
                if new_item_option and new_item_option.count() > 0:
                    log("  → '신상품(재입고)순' 클릭...", 'info')
                    new_item_option.click()
                    wait_stable(_page, 3000)
                    
                    log("  ✅ 정렬 변경 완료!", 'success')
                else:
                    log("  ⚠️ '신상품(재입고)순' 옵션을 찾을 수 없음", 'warning')
            else:
                log("  ⚠️ '무신사 추천순' 버튼을 찾을 수 없음", 'warning')
                
        except Exception as e:
            log(f"  ⚠️ 정렬 변경 실패: {e}", 'warning')
        
        # ✅ 무한 스크롤로 상품 링크 수집
        log("\n🔄 무한 스크롤 시작...", 'info')
        
        product_links = []
        scroll_count = 0
        max_scrolls = 50
        no_new_items_count = 0
        
        while len(product_links) < target_count and scroll_count < max_scrolls:
            scroll_count += 1
            
            # 현재 페이지의 상품 링크 추출
            current_links = _page.evaluate("""
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
                log(f"  [{scroll_count}회 스크롤] 새 상품 없음 ({no_new_items_count}/3)", 'warning')
                
                if no_new_items_count >= 3:
                    log("  ⚠️ 더 이상 새로운 상품이 없습니다.", 'warning')
                    break
            
            if len(product_links) >= target_count:
                log(f"  ✅ 목표 개수 달성: {len(product_links):,}개", 'success')
                break
            
            # 페이지 끝까지 스크롤
            _page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            
            wait_time = random.uniform(1.5, 2.5)
            time.sleep(wait_time)
        
        # 실제 수집할 링크
        product_links = product_links[:target_count]
        
        log(f"\n📋 최종 수집 링크: {len(product_links)}개", 'success')
        log(f"🔍 상세 정보 수집 시작...\n", 'info')
        
        # ✅ 각 상품 상세 페이지 방문
        for idx, product_url in enumerate(product_links, 1):
            if stop_flag:
                log("\n⏹️ 사용자가 검색을 중단했습니다.", 'warning')
                break
            
            log(f"\n{'='*60}", 'info')
            log(f"[{idx}/{len(product_links)}] 상품 정보 수집", 'info')
            log(f"{'='*60}", 'info')
            
            if callback:
                callback(f"PROGRESS:{idx}/{len(product_links)}", 'progress')
            
            try:
                log(f"  → URL: {product_url}", 'info')
                _page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
                wait_stable(_page, 2000)
                
                product_info = extract_product_detail(_page)
                
                if product_info:
                    product_info['url'] = product_url
                    product_info['source'] = 'MUSINSA'
                    product_info['keyword'] = keyword
                    
                    results.append(product_info)
                    
                    if callback:
                        callback(f"DATA:{json.dumps(product_info, ensure_ascii=False)}", 'data')
                    
                    log(f"  ✅ 수집 완료: {product_info.get('name', 'N/A')[:50]}", 'success')
                
                if idx < len(product_links):
                    delay = random.uniform(1.5, 3.0)
                    log(f"  💤 {delay:.1f}초 대기...", 'info')
                    time.sleep(delay)
                
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