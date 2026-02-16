"""
네이버 쇼핑 검색 - Selenium + undetected-chromedriver 버전
Playwright보다 네이버 차단 우회에 강력함
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import random
import json
import os
import shutil

# 쿠키 파일 경로
NAVER_COOKIE_FILE = os.path.join(os.path.dirname(__file__), 'naver_cookies_selenium.json')

def create_stealth_driver(headless=False):
    """
    네이버 차단 우회가 가능한 Chrome 드라이버 생성
    """
    options = uc.ChromeOptions()
    
    # 기본 설정
    if headless:
        options.add_argument('--headless=new')
    
    options.add_argument('--start-maximized')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    # undetected-chromedriver로 드라이버 생성
    # driver_executable_path를 None으로 하면 자동으로 Chrome 버전에 맞는 드라이버 다운로드
    try:
        print("   Chrome 버전 확인 중...")
        driver = uc.Chrome(options=options, use_subprocess=False, driver_executable_path=None)
        print("   ✅ 드라이버 생성 성공!")
    except Exception as e:
        print(f"   ⚠️ 첫 시도 실패, 재시도 중...")
        # 캐시 삭제 후 재시도
        import shutil
        cache_dir = os.path.join(os.path.expanduser('~'), '.undetected_chromedriver')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            print(f"   🗑️ 캐시 삭제: {cache_dir}")
        
        driver = uc.Chrome(options=options, use_subprocess=False)
        print("   ✅ 드라이버 생성 성공!")
    
    return driver


def save_cookies(driver, filepath):
    """쿠키 저장"""
    cookies = driver.get_cookies()
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ 쿠키 저장: {filepath}")


def load_cookies(driver, filepath):
    """쿠키 로드"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        for cookie in cookies:
            if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                cookie['sameSite'] = 'None'
            driver.add_cookie(cookie)
        print(f"✅ 쿠키 로드: {filepath}")
        return True
    return False


def naver_login(driver, user_id='dldyddk1211', user_pw='dhkdl4213!'):
    """
    네이버 로그인 (메인 페이지에서 직접)
    """
    print("\n" + "="*60)
    print("🔐 네이버 로그인 시작")
    print("="*60)
    
    # 네이버 메인 접속
    driver.get("https://www.naver.com/")
    time.sleep(random.uniform(2, 4))
    
    # 로그인 버튼 찾기
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
                print(f"✓ 로그인 버튼 발견: {selector}")
                break
            except:
                continue
        
        if not login_btn:
            print("✅ 이미 로그인되어 있습니다!")
            return True
        
        # 로그인 버튼 클릭
        print("🖱️ 로그인 버튼 클릭...")
        login_btn.click()
        time.sleep(random.uniform(2, 3))
        
        # 아이디 입력
        print("📝 아이디 입력...")
        id_input = driver.find_element(By.ID, 'id')
        id_input.clear()
        for char in user_id:
            id_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.2))
        time.sleep(random.uniform(0.8, 1.5))
        
        # 비밀번호 입력
        print("🔑 비밀번호 입력...")
        pw_input = driver.find_element(By.ID, 'pw')
        pw_input.clear()
        for char in user_pw:
            pw_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.2))
        time.sleep(random.uniform(0.8, 1.5))
        
        # 로그인 버튼 클릭
        print("🚀 로그인 실행...")
        login_submit = driver.find_element(By.CSS_SELECTOR, '.btn_login')
        login_submit.click()
        
        # 로그인 완료 대기
        time.sleep(random.uniform(5, 8))
        
        # 로그인 확인
        if "nidlogin.login" not in driver.current_url:
            print("✅ 네이버 로그인 성공!")
            save_cookies(driver, NAVER_COOKIE_FILE)
            print("="*60)
            return True
        else:
            print("❌ 로그인 실패")
            return False
            
    except Exception as e:
        print(f"❌ 로그인 오류: {e}")
        return False


def search_naver_shopping(driver, product_code):
    """
    네이버 쇼핑 검색
    """
    print(f"\n{'='*60}")
    print(f"🔍 상품 검색: {product_code}")
    print(f"{'='*60}")
    
    try:
        # STEP 1: 네이버 메인 이동
        print("📍 STEP 1: 네이버 메인 이동...")
        driver.get("https://www.naver.com/")
        time.sleep(random.uniform(2, 4))
        print("✅ STEP 1 완료")
        
        # STEP 2: 검색창 찾기
        print("\n📍 STEP 2: 메인 검색창 찾기...")
        search_input = driver.find_element(By.ID, 'query')
        print("✅ STEP 2 완료: 검색창 발견")
        
        # STEP 3: 검색어 입력
        print(f"\n📍 STEP 3: 검색어 입력 ('{product_code}')...")
        search_input.clear()
        time.sleep(random.uniform(0.3, 0.5))
        
        for i, char in enumerate(product_code, 1):
            search_input.send_keys(char)
            time.sleep(random.uniform(0.1, 0.2))
            if i % 3 == 0:
                print(f"   → 입력 중: {product_code[:i]}")
        
        time.sleep(random.uniform(0.5, 1))
        print("✅ STEP 3 완료: 검색어 입력 완료")
        
        # STEP 4: 검색 실행
        print("\n📍 STEP 4: 검색 실행 (Enter)...")
        search_input.send_keys(Keys.RETURN)
        time.sleep(random.uniform(3, 5))
        print(f"   현재 URL: {driver.current_url[:60]}...")
        print("✅ STEP 4 완료")
        
        # STEP 5: 쇼핑탭 클릭
        print("\n📍 STEP 5: 쇼핑탭 클릭...")
        try:
            shopping_tab = driver.find_element(By.XPATH, '//a[contains(text(), "쇼핑")]')
            shopping_tab.click()
            time.sleep(random.uniform(3, 5))
            
            if "search.shopping.naver.com" in driver.current_url:
                print("✅ STEP 5 완료: 쇼핑탭 이동 성공!")
            else:
                print("⚠️ 쇼핑 페이지로 이동 안 됨, 직접 URL로...")
                driver.get(f"https://search.shopping.naver.com/search/all?query={product_code}")
                time.sleep(random.uniform(3, 5))
                print("✅ STEP 5 완료: 직접 URL 이동!")
        except:
            print("⚠️ 쇼핑탭 못 찾음, 직접 URL로...")
            driver.get(f"https://search.shopping.naver.com/search/all?query={product_code}")
            time.sleep(random.uniform(3, 5))
            print("✅ STEP 5 완료: 직접 URL 이동!")
        
        # 접속 제한 확인
        page_source = driver.page_source
        if "접속이 일시적으로 제한" in page_source or "오류가 발생" in page_source:
            print("\n" + "="*60)
            print("❌ 네이버 쇼핑 접속 제한 감지!")
            print("="*60)
            print("🚨 브라우저 창을 확인하고 직접 조작해주세요!")
            print("💡 차단이 풀릴 때까지 브라우저 창을 유지합니다")
            input("\n✋ 차단이 풀리면 Enter를 눌러주세요...")
            driver.refresh()
            time.sleep(3)
        
        print("\n🎉 검색 완료!")
        return True
        
    except Exception as e:
        print(f"❌ 검색 오류: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 함수"""
    print("="*60)
    print("🚀 네이버 쇼핑 검색 (Selenium Stealth)")
    print("="*60)
    
    # 드라이버 생성
    print("\n🌐 Chrome 드라이버 시작...")
    
    try:
        driver = create_stealth_driver(headless=False)
        print("✅ 드라이버 생성 완료!")
        
        # 드라이버 테스트
        print("\n📍 네이버 접속 테스트...")
        driver.get("https://www.naver.com/")
        print(f"✅ 현재 URL: {driver.current_url}")
        
        # 10초 대기 (브라우저 확인용)
        print("\n⏱️  10초 대기 (브라우저를 확인하세요)...")
        time.sleep(10)
        
        print("\n계속 진행할까요?")
        input("Enter를 누르면 로그인을 시작합니다...")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnter를 눌러 종료...")
        return
    
    try:
        # 로그인
        if not naver_login(driver):
            print("❌ 로그인 실패로 종료")
            input("\nEnter를 눌러 종료...")
            return
        
        print("\n✅ 로그인 완료, 검색 시작\n")
        
        # 테스트 검색
        test_codes = ['AR3565-600', 'HF9460-010']
        
        for i, code in enumerate(test_codes, 1):
            print(f"\n[{i}/{len(test_codes)}] {code}")
            
            if search_naver_shopping(driver, code):
                print(f"✅ {code} 검색 완료")
            else:
                print(f"❌ {code} 검색 실패")
            
            # 다음 상품 전 대기
            if i < len(test_codes):
                wait_time = random.uniform(10, 20)
                print(f"\n⏱️ 다음 상품까지 대기: {wait_time:.1f}초")
                time.sleep(wait_time)
        
        print("\n" + "="*60)
        print("✅ 모든 검색 완료!")
        print("="*60)
        
        input("\n✋ Enter를 누르면 브라우저가 종료됩니다...")
        
    finally:
        try:
            driver.quit()
        except:
            pass  # 종료 오류 무시


if __name__ == "__main__":
    main()