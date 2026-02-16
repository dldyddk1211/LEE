"""
네이버 쇼핑 구매처 검색 - 최종 완성판
1. 백화점/홈쇼핑 필터
2. 낮은가격순 정렬
3. 해외직구 제외 (실제 HTML 기반)
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random
import os
import shutil

LOG_CALLBACK = None

def create_stealth_driver(headless=False):
    """Chrome 드라이버 생성"""
    options = uc.ChromeOptions()
    
    if headless:
        options.add_argument('--headless=new')
    
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = uc.Chrome(options=options, use_subprocess=False, driver_executable_path=None)
        return driver
    except Exception as e:
        cache_dir = os.path.join(os.path.expanduser('~'), '.undetected_chromedriver')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        driver = uc.Chrome(options=options, use_subprocess=False)
        return driver


def perform_naver_login(driver, callback=None):
    """네이버 로그인"""
    def log(msg, level='info'):
        print(msg)
        if callback:
            try:
                callback(msg, level)
            except:
                pass
    
    log("\n" + "="*60)
    log("🔐 네이버 로그인 확인")
    log("="*60)
    
    driver.get("https://www.naver.com/")
    time.sleep(random.uniform(2, 4))
    
    try:
        login_selectors = [
            (By.CSS_SELECTOR, 'a.MyView-module__link_login___HpHMW'),
            (By.CSS_SELECTOR, 'a[href*="nidlogin.login"]'),
            (By.XPATH, '//a[contains(text(), "로그인")]')
        ]
        
        login_btn = None
        for by, selector in login_selectors:
            try:
                login_btn = driver.find_element(by, selector)
                log("   로그인 필요")
                break
            except:
                continue
        
        if not login_btn:
            log("✅ 이미 로그인되어 있습니다!")
            log("="*60)
            return True
        
        log("🖱️ 로그인 버튼 클릭...")
        login_btn.click()
        time.sleep(random.uniform(2, 3))
        
        log("📝 아이디 입력...")
        id_input = driver.find_element(By.ID, 'id')
        for char in 'dldyddk1211':
            id_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.2))
        
        log("🔑 비밀번호 입력...")
        pw_input = driver.find_element(By.ID, 'pw')
        for char in 'dhkdl4213!':
            pw_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.2))
        
        log("🚀 로그인 실행...")
        login_submit = driver.find_element(By.CSS_SELECTOR, '.btn_login')
        login_submit.click()
        time.sleep(random.uniform(5, 8))
        
        current_url = driver.current_url
        if "nidlogin.login" in current_url or "confirm" in current_url:
            log("\n⚠️ 2차 인증(영수증 등) 필요")
            log("💡 브라우저에서 직접 인증을 완료해주세요")
            
            for i in range(10):
                log(f"⏱️ 인증 대기 중... ({i*30}초 경과)")
                time.sleep(30)
                
                current_url = driver.current_url
                if "nidlogin" not in current_url and "confirm" not in current_url:
                    log("✅ 인증 완료 감지!")
                    break
            
            driver.get("https://www.naver.com/")
            time.sleep(3)
        
        log("✅ 네이버 로그인 성공!")
        log("="*60)
        return True
        
    except Exception as e:
        log(f"❌ 로그인 오류: {e}", 'error')
        import traceback
        traceback.print_exc()
        return False


def apply_naver_shopping_filters(driver, product_code, callback=None):
    """
    네이버 쇼핑 필터 적용
    1. 백화점/홈쇼핑 클릭
    2. 낮은가격순 정렬
    3. 해외직구 제외 (실제 HTML 기반)
    """
    def log(msg, level='info'):
        print(msg)
        if callback:
            try:
                callback(msg, level)
            except:
                pass
    
    try:
        # === STEP 1: 백화점/홈쇼핑 필터 ===
        log(f"\n  📍 STEP 1: 백화점/홈쇼핑 필터 적용...")
        
        try:
            filter_selectors = [
                '//button[contains(text(), "판매처")]',
                '//div[contains(text(), "판매처")]',
            ]
            
            filter_clicked = False
            for selector in filter_selectors:
                try:
                    elem = driver.find_element(By.XPATH, selector)
                    elem.click()
                    log(f"     ✓ 판매처 필터 버튼 클릭")
                    time.sleep(random.uniform(1, 2))
                    filter_clicked = True
                    break
                except:
                    continue
            
            if filter_clicked:
                dept_selectors = [
                    '//label[contains(text(), "백화점")]',
                    '//span[contains(text(), "백화점")]',
                ]
                
                for selector in dept_selectors:
                    try:
                        elem = driver.find_element(By.XPATH, selector)
                        elem.click()
                        log(f"     ✓ 백화점/홈쇼핑 선택")
                        time.sleep(random.uniform(0.5, 1))
                        break
                    except:
                        continue
                
                apply_selectors = [
                    '//button[contains(text(), "적용")]',
                ]
                
                for selector in apply_selectors:
                    try:
                        elem = driver.find_element(By.XPATH, selector)
                        elem.click()
                        log(f"     ✓ 필터 적용")
                        time.sleep(random.uniform(2, 3))
                        break
                    except:
                        continue
                
                log(f"  ✅ STEP 1 완료: 백화점/홈쇼핑 필터 적용")
            else:
                log(f"  ⚠️ STEP 1 건너뛰기: 판매처 필터 버튼 못 찾음")
        
        except Exception as e:
            log(f"  ⚠️ STEP 1 건너뛰기: {e}")
        
        # === STEP 2: 낮은가격순 정렬 ===
        log(f"\n  📍 STEP 2: 낮은가격순 정렬...")
        
        try:
            # 직접 URL로 정렬 적용 (가장 확실함)
            current_url = driver.current_url
            
            if 'sort=' not in current_url:
                # sort 파라미터 추가
                if '?' in current_url:
                    new_url = current_url + '&sort=price_asc'
                else:
                    new_url = current_url + '?sort=price_asc'
                
                log(f"     → URL에 정렬 파라미터 추가")
                driver.get(new_url)
                time.sleep(random.uniform(2, 3))
                log(f"  ✅ STEP 2 완료: 낮은가격순 정렬 (URL)")
            else:
                log(f"  ✅ STEP 2 완료: 이미 정렬됨")
        
        except Exception as e:
            log(f"  ⚠️ STEP 2 건너뛰기: {e}")
        
        # === STEP 3: 해외직구 제외 (실제 HTML 기반) ===
        log(f"\n  📍 STEP 3: 해외직구 제외...")
        
        try:
            # 실제 HTML 속성 사용
            overseas_selectors = [
                # data-shp-contents-id 사용
                (By.CSS_SELECTOR, 'a[data-shp-contents-id="해외직구제외"]'),
                # class 사용
                (By.CSS_SELECTOR, 'a.subFilter_select__LwxTx'),
                # XPath (텍스트)
                (By.XPATH, '//a[contains(text(), "해외직구제외")]'),
            ]
            
            for by, selector in overseas_selectors:
                try:
                    elem = driver.find_element(by, selector)
                    
                    # 이미 선택되어 있는지 확인
                    class_attr = elem.get_attribute('class')
                    
                    # 선택 안 되어 있으면 클릭
                    if 'selected' not in class_attr.lower():
                        elem.click()
                        log(f"     ✓ 해외직구 제외 클릭")
                        time.sleep(random.uniform(2, 3))
                    else:
                        log(f"     ✓ 해외직구 이미 제외됨")
                    
                    log(f"  ✅ STEP 3 완료: 해외직구 제외")
                    break
                    
                except Exception as e:
                    continue
            else:
                # 모든 셀렉터 실패 시 URL로 시도
                log(f"     ⚠️ 버튼 못 찾음, URL로 시도...")
                current_url = driver.current_url
                
                if 'nv_filter' not in current_url:
                    if '?' in current_url:
                        new_url = current_url + '&nv_filter=exagency:해외직구제외'
                    else:
                        new_url = current_url + '?nv_filter=exagency:해외직구제외'
                    
                    driver.get(new_url)
                    time.sleep(random.uniform(2, 3))
                    log(f"  ✅ STEP 3 완료: 해외직구 제외 (URL)")
                else:
                    log(f"  ✅ STEP 3 완료: 이미 제외됨")
        
        except Exception as e:
            log(f"  ⚠️ STEP 3 건너뛰기: {e}")
        
        log(f"\n  🎉 모든 필터 적용 완료!")
        return True
        
    except Exception as e:
        log(f"  ❌ 필터 적용 오류: {e}", 'error')
        return False


def parse_naver_shopping_page(driver, product_code, callback=None):
    """네이버 쇼핑 1페이지 파싱"""
    def log(msg, level='info'):
        print(msg)
        if callback:
            try:
                callback(msg, level)
            except:
                pass
    
    products = []
    
    try:
        log(f"\n  📊 상품 리스트 파싱 시작...")
        time.sleep(3)
        
        product_selectors = [
            'div.product_item__MDtDF',
            'div.product_item',
            'li.product_item',
            'div.basicList_item__0T9JD',
        ]
        
        product_list = None
        for selector in product_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if len(elements) > 0:
                    log(f"     ✓ 상품 카드 발견: {selector} ({len(elements)}개)")
                    product_list = elements
                    break
            except:
                continue
        
        if not product_list:
            log(f"  ⚠️ 상품 리스트를 찾을 수 없음")
            return []
        
        total = len(product_list)
        log(f"  📦 총 {total}개 상품 파싱...")
        
        for i, item in enumerate(product_list, 1):
            try:
                # 이미지 URL
                image_url = ""
                try:
                    img = item.find_element(By.CSS_SELECTOR, 'img')
                    image_url = img.get_attribute('src')
                    if not image_url:
                        image_url = img.get_attribute('data-src')
                except:
                    pass
                
                # 판매처
                mall_name = ""
                mall_img = ""
                
                mall_selectors = [
                    'div.product_mall__REoUI',
                    'a.product_mall',
                    'span.product_mall',
                ]
                
                for sel in mall_selectors:
                    try:
                        mall_elem = item.find_element(By.CSS_SELECTOR, sel)
                        mall_name = mall_elem.text.strip()
                        if mall_name:
                            break
                    except:
                        continue
                
                try:
                    mall_logo = item.find_element(By.CSS_SELECTOR, 'img[alt*="판매처"], img[class*="mall"]')
                    mall_img = mall_logo.get_attribute('src')
                except:
                    pass
                
                # 상품명
                product_name = ""
                name_selectors = [
                    'div.product_title__Mmw2K',
                    'a.product_link__TrAac',
                    'div.product_title',
                ]
                
                for sel in name_selectors:
                    try:
                        name_elem = item.find_element(By.CSS_SELECTOR, sel)
                        product_name = name_elem.text.strip()
                        if product_name:
                            break
                    except:
                        continue
                
                # 상품 URL
                product_url = ""
                url_selectors = [
                    'a.product_link__TrAac',
                    'a[href*="shopping.naver.com"]',
                ]
                
                for sel in url_selectors:
                    try:
                        link_elem = item.find_element(By.CSS_SELECTOR, sel)
                        href = link_elem.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                product_url = f"https://shopping.naver.com{href}"
                            else:
                                product_url = href
                            break
                    except:
                        continue
                
                # 가격
                price = ""
                price_selectors = [
                    'span.price_num__S2p_v strong',
                    'strong.price_num',
                    'span.price_num strong',
                ]
                
                for sel in price_selectors:
                    try:
                        price_elem = item.find_element(By.CSS_SELECTOR, sel)
                        price = price_elem.text.strip()
                        if price:
                            break
                    except:
                        continue
                
                # 배송비
                shipping = "무료배송"
                try:
                    delivery_elem = item.find_element(By.CSS_SELECTOR, 'span[class*="delivery"], div[class*="delivery"]')
                    shipping_text = delivery_elem.text.strip()
                    if shipping_text:
                        shipping = shipping_text
                except:
                    pass
                
                if product_name or price:
                    product_data = {
                        'image_url': image_url,
                        'mall': mall_name if mall_name else '판매처 정보 없음',
                        'mall_img': mall_img,
                        'name': product_name,
                        'link': product_url,
                        'price': price,
                        'shipping': shipping
                    }
                    
                    products.append(product_data)
                    
                    mall_display = mall_name[:15] if mall_name else "(로고)"
                    name_display = product_name[:30] if len(product_name) > 30 else product_name
                    log(f"     [{i}] {mall_display} | {name_display}... | {price}원")
            
            except Exception as e:
                log(f"     [{i}] 파싱 오류: {e}")
                continue
        
        log(f"  ✅ 파싱 완료: {len(products)}개 상품")
        
    except Exception as e:
        log(f"  ❌ 파싱 오류: {e}", 'error')
        import traceback
        log(traceback.format_exc())
    
    return products


def search_naver_shopping(driver, product_code, callback=None):
    """네이버 쇼핑 검색 (필터 적용 + 파싱)"""
    def log(msg, level='info'):
        print(msg)
        if callback:
            try:
                callback(msg, level)
            except:
                pass
    
    result = {
        'success': False,
        'product_code': product_code,
        'products': [],
        'error': None
    }
    
    try:
        log(f"\n{'='*60}")
        log(f"🔍 상품 검색: {product_code}")
        log(f"{'='*60}")
        
        search_url = f"https://search.shopping.naver.com/search/all?query={product_code}"
        log(f"  🔗 검색 URL: {search_url[:80]}...")
        
        driver.get(search_url)
        time.sleep(random.uniform(3, 5))
        
        current_url = driver.current_url
        log(f"  📍 현재 URL: {current_url[:80]}...")
        
        page_source = driver.page_source
        if "접속이 일시적으로 제한" in page_source or "오류가 발생" in page_source:
            log("\n❌ 네이버 쇼핑 접속 제한!")
            log("💡 브라우저에서 직접 조작해주세요")
            
            for i in range(10):
                time.sleep(30)
                driver.refresh()
                time.sleep(2)
                
                new_content = driver.page_source
                if "접속이 일시적으로 제한" not in new_content and "오류가 발생" not in new_content:
                    log(f"\n✅ 차단 해제 확인!")
                    break
                else:
                    log(f"⏱️ 남은 시간: {(10-i-1)*30}초...")
            else:
                result['error'] = '네이버 쇼핑 접속 제한'
                return result
        
        # 필터 적용
        apply_naver_shopping_filters(driver, product_code, callback)
        
        # 상품 파싱
        products = parse_naver_shopping_page(driver, product_code, callback)
        
        result['success'] = True
        result['products'] = products
        result['total'] = len(products)
        
        log(f"\n✅ 검색 완료: {len(products)}개 상품")
        
        return result
        
    except Exception as e:
        log(f"❌ 검색 오류: {e}", 'error')
        import traceback
        log(traceback.format_exc())
        result['error'] = str(e)
        return result


def run_sourcing_for_products(product_codes, callback=None):
    """여러 상품 구매처 검색 - 스트림 지원"""
    global LOG_CALLBACK
    LOG_CALLBACK = callback
    
    def log(msg, level='info'):
        print(msg)
        if callback:
            try:
                callback(msg, level)
            except:
                pass
    
    log(f"\n🚀 구매처 검색 시작")
    log(f"📦 총 {len(product_codes)}개 상품")
    
    collected_results = []
    driver = None
    
    try:
        log("\n🌐 Chrome 드라이버 시작...")
        driver = create_stealth_driver(headless=False)
        log("✅ 드라이버 생성 완료")
        
        if not perform_naver_login(driver, callback):
            log("❌ 로그인 실패")
            return {
                'success': False,
                'error': '로그인 실패',
                'results': collected_results
            }
        
        log("\n✅ 로그인 완료, 검색 시작\n")
        
        for idx, code in enumerate(product_codes, 1):
            log(f"\n{'='*60}")
            log(f"[{idx}/{len(product_codes)}] {code}")
            log(f"{'='*60}")
            
            # ⬇️⬇️⬇️ 여기에 추가! ⬇️⬇️⬇️
            if callback:
                callback(f"PROGRESS:{idx}/{len(product_codes)}", 'progress')
                callback(f"PRODUCT_START:{code}", 'info')
            # ⬆️⬆️⬆️ 여기까지 추가! ⬆️⬆️⬆️
            
            # 중단 체크 (기존 코드)
            import sys
            if hasattr(sys.modules['__main__'], 'stop_requested'):
                if sys.modules['__main__'].stop_requested:
                    log("\n⏹️ 사용자가 검색을 중단했습니다")
                    break
            
            # 검색 실행 (기존 코드)
            result = search_naver_shopping(driver, code, callback)
            collected_results.append(result)
            
            # ⬇️⬇️⬇️ 여기는 이미 있음 (OK) ⬇️⬇️⬇️
            if callback:
                import json
                callback(f"PRODUCT_RESULT:{json.dumps({
                    'product_code': code,
                    'products': result.get('products', [])
                }, ensure_ascii=False)}", 'info')
            # ⬆️⬆️⬆️ 여기까지 OK ⬆️⬆️⬆️
            
            # 다음 상품 대기 (기존 코드)
            if idx < len(product_codes):
                wait_time = random.uniform(10, 20)
                log(f"\n⏱️ 다음 상품까지 대기: {wait_time:.1f}초")
                time.sleep(wait_time)
                
                    
        log("\n✅ 모든 검색 완료!")
        
        # 엑셀 저장
        try:
            from poizon_data.poizon_search import save_sourcing_results_to_excel
            filepath = save_sourcing_results_to_excel(collected_results, "정상 종료")
            log(f"💾 데이터 저장: {filepath}")
        except Exception as e:
            log(f"⚠️ 데이터 저장 실패: {e}")
        
        return {
            'success': True,
            'total_searched': len(collected_results),
            'results': collected_results
        }
        
    except KeyboardInterrupt:
        log("\n⚠️ Ctrl+C로 중단됨")
        try:
            from poizon_data.poizon_search import save_sourcing_results_to_excel
            save_sourcing_results_to_excel(collected_results, "Ctrl+C 중단")
        except:
            pass
        return {'success': False, 'error': '사용자 중단', 'results': collected_results}
        
    except Exception as e:
        log(f"\n❌ 오류 발생: {e}", 'error')
        import traceback
        traceback.print_exc()
        try:
            from poizon_data.poizon_search import save_sourcing_results_to_excel
            save_sourcing_results_to_excel(collected_results, f"오류: {e}")
        except:
            pass
        return {'success': False, 'error': str(e), 'results': collected_results}
        
    finally:
        if driver:
            log("\n🔒 브라우저 종료 중...")
            try:
                driver.quit()
            except:
                pass
        
        if collected_results:
            log(f"\n📊 총 {len(collected_results)}개 상품 검색 완료")


if __name__ == "__main__":
    test_codes = ['AR3565-600']
    result = run_sourcing_for_products(test_codes)
    print(f"\n최종 결과: {result}")