import os
import json
import sqlite3
import threading
import time
from datetime import datetime

# ==========================================
# 설정
# ==========================================

# credentials.json 파일 경로 (inventory_data 폴더 기준)
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'office-stock-manager-488609-4dec3f68ef0c.json')

# 구글 시트 ID (URL에서 복사)
# https://docs.google.com/spreadsheets/d/  ★이부분★  /edit
SPREADSHEET_ID = '1iYJgdyajNLzvKzzv2XrerUqTWNnhXNuS8a8vYMdpzjU'

# 시트 이름 (하단 탭 이름)
SHEET_NAME = '재고' #← 실제 탭 이름으로 변경하세요

# DB 파일 경로
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inventory.db')

# 동기화 주기 (초) - 8시간
SYNC_INTERVAL = 28800  # 8 * 60 * 60

# ==========================================
# 컬럼 매핑
# 구글 시트 컬럼 순서에 맞게 설정
# ==========================================

# 시트 컬럼 순서:
# 순번 / 일자 / 판매일자 / 브랜드 / 상품명 / 품번 / 사이즈 / 수량 / 상태 /
# 판매사이트 / 판매금액 / 최저가 / 입금금액 / 원가 / 마진 / 마진률 /
# 입금확인 / 구매자 / 결제내역 / 비고 / 구매사이트링크

COLUMN_MAP = {
    'seq':           0,   # 순번
    'date':          1,   # 일자
    'sale_date':     2,   # 판매일자
    'brand':         3,   # 브랜드
    'name':          4,   # 상품명
    'product_code':  5,   # 품번
    'size':          6,   # 사이즈
    'quantity':      7,   # 수량
    'status':        8,   # 상태
    'sale_site':     9,   # 판매사이트
    'sale_price':    10,  # 판매금액
    'min_price':     11,  # 최저가
    'deposit_price': 12,  # 입금금액
    'cost_price':    13,  # 원가
    'margin':        14,  # 마진
    'margin_rate':   15,  # 마진률
    'deposit_check': 16,  # 입금확인
    'buyer':         17,  # 구매자
    'payment':       18,  # 결제내역
    'notes':         19,  # 비고
    'purchase_link': 20,  # 구매사이트링크
}

# ==========================================
# DB 초기화 (판매 테이블)
# ==========================================

def init_sales_db():
    """판매 데이터 테이블 생성"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq TEXT,
            date TEXT,
            sale_date TEXT,
            brand TEXT,
            name TEXT,
            product_code TEXT,
            size TEXT,
            quantity INTEGER DEFAULT 0,
            status TEXT,
            sale_site TEXT,
            sale_price INTEGER DEFAULT 0,
            min_price INTEGER DEFAULT 0,
            deposit_price INTEGER DEFAULT 0,
            cost_price INTEGER DEFAULT 0,
            margin INTEGER DEFAULT 0,
            margin_rate TEXT,
            deposit_check TEXT,
            buyer TEXT,
            payment TEXT,
            notes TEXT,
            purchase_link TEXT,
            synced_at TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ 판매 DB 테이블 초기화 완료")

# ==========================================
# 숫자 변환 유틸
# ==========================================

def safe_int(val):
    """안전하게 정수 변환"""
    if val is None or val == '':
        return 0
    try:
        # 쉼표, 원, % 등 제거
        cleaned = str(val).replace(',', '').replace('원', '').replace('%', '').replace(' ', '')
        return int(float(cleaned))
    except:
        return 0

def safe_str(val):
    """안전하게 문자열 변환"""
    if val is None:
        return ''
    return str(val).strip()

# ==========================================
# 구글 시트 데이터 가져오기
# ==========================================

def fetch_sheet_data():
    """구글 시트에서 데이터 가져오기"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # 권한 설정
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]

        creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
        client = gspread.authorize(creds)

        # 시트 열기
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(SHEET_NAME)

        # 전체 데이터 가져오기
        all_rows = worksheet.get_all_values()

        if not all_rows:
            print("⚠️ 시트가 비어있습니다")
            return []

        # 첫 번째 행은 헤더 → 2번째 행부터 데이터
        data_rows = all_rows[1:]

        print(f"✅ 시트에서 {len(data_rows)}행 데이터 가져옴")
        return data_rows

    except ImportError:
        print("❌ gspread 모듈이 없습니다. 아래 명령어로 설치하세요:")
        print("   pip install gspread google-auth")
        return []
    except Exception as e:
        print(f"❌ 시트 데이터 가져오기 실패: {e}")
        return []

# ==========================================
# DB에 데이터 저장
# ==========================================

def save_to_db(rows):
    """가져온 데이터를 DB에 저장"""
    if not rows:
        return 0

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # 기존 데이터 삭제 후 새로 저장 (전체 동기화)
    cursor.execute('DELETE FROM sales')

    synced_at = datetime.now().isoformat()
    count = 0

    for row in rows:
        # 빈 행 스킵
        if not any(row):
            continue

        def get_col(key):
            idx = COLUMN_MAP.get(key, -1)
            if idx < 0 or idx >= len(row):
                return ''
            return row[idx]

        try:
            cursor.execute('''
                INSERT INTO sales (
                    seq, date, sale_date, brand, name, product_code,
                    size, quantity, status, sale_site, sale_price,
                    min_price, deposit_price, cost_price, margin,
                    margin_rate, deposit_check, buyer, payment,
                    notes, purchase_link, synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                safe_str(get_col('seq')),
                safe_str(get_col('date')),
                safe_str(get_col('sale_date')),
                safe_str(get_col('brand')),
                safe_str(get_col('name')),
                safe_str(get_col('product_code')),
                safe_str(get_col('size')),
                safe_int(get_col('quantity')),
                safe_str(get_col('status')),
                safe_str(get_col('sale_site')),
                safe_int(get_col('sale_price')),
                safe_int(get_col('min_price')),
                safe_int(get_col('deposit_price')),
                safe_int(get_col('cost_price')),
                safe_int(get_col('margin')),
                safe_str(get_col('margin_rate')),
                safe_str(get_col('deposit_check')),
                safe_str(get_col('buyer')),
                safe_str(get_col('payment')),
                safe_str(get_col('notes')),
                safe_str(get_col('purchase_link')),
                synced_at
            ))
            count += 1
        except Exception as e:
            print(f"⚠️ 행 저장 오류: {e}")
            continue

    conn.commit()
    conn.close()

    print(f"✅ DB 저장 완료: {count}건")
    return count

# ==========================================
# 동기화 실행
# ==========================================

def sync_once():
    """한 번 동기화"""
    print(f"\n🔄 구글 시트 동기화 시작... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    rows = fetch_sheet_data()
    if rows:
        count = save_to_db(rows)
        print(f"✅ 동기화 완료: {count}건")
        return count
    return 0

_sync_lock = threading.Lock()
_syncing = False

def sync_if_needed():
    """마지막 동기화로부터 8시간이 지난 경우에만 동기화"""
    global _syncing
    with _sync_lock:
        if _syncing:
            print("⏭️ 동기화 이미 진행 중 - 스킵")
            return
        last = get_last_synced()
        if last:
            from datetime import timedelta
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = datetime.now() - last_dt
                if elapsed.total_seconds() < SYNC_INTERVAL:
                    remaining_h = int((SYNC_INTERVAL - elapsed.total_seconds()) // 3600)
                    remaining_m = int((SYNC_INTERVAL - elapsed.total_seconds()) % 3600 // 60)
                    print(f"⏭️ 동기화 스킵 (다음 동기화까지 {remaining_h}시간 {remaining_m}분 남음)")
                    return
            except Exception:
                pass
        _syncing = True

    try:
        sync_once()
    except Exception as e:
        print(f"❌ 동기화 오류: {e}")
    finally:
        with _sync_lock:
            _syncing = False

def sync_loop():
    """주기적 동기화 루프 (백그라운드 스레드) - 8시간마다"""
    while True:
        print(f"⏰ 다음 동기화까지 {SYNC_INTERVAL//3600}시간 대기...")
        time.sleep(SYNC_INTERVAL)
        try:
            sync_once()
        except Exception as e:
            print(f"❌ 동기화 오류: {e}")

def start_sync_background():
    """백그라운드에서 자동 동기화 시작"""
    init_sales_db()

    # 서버 시작 시 - 8시간이 지났을 때만 동기화
    threading.Thread(target=sync_if_needed, daemon=True).start()

    # 8시간마다 주기적 동기화 (첫 실행은 8시간 후)
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
    print(f"✅ 자동 동기화 설정 완료 (매 {SYNC_INTERVAL//3600}시간마다)")

# ==========================================
# 데이터 조회 함수 (API에서 사용)
# ==========================================

def get_sales_data(keyword=None, brand=None, status=None):
    """판매 데이터 조회"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = 'SELECT * FROM sales WHERE 1=1'
    params = []

    if keyword:
        query += ' AND (name LIKE ? OR product_code LIKE ? OR buyer LIKE ?)'
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])

    if brand:
        query += ' AND brand = ?'
        params.append(brand)

    if status:
        query += ' AND status = ?'
        params.append(status)

    query += ' ORDER BY seq ASC'

    cursor.execute(query, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return rows

def get_last_synced():
    """마지막 동기화 시간 조회"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT synced_at FROM sales ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except:
        return None


# ==========================================
# 직접 실행 시 테스트
# ==========================================
if __name__ == '__main__':
    print("🧪 구글 시트 동기화 테스트")
    init_sales_db()
    count = sync_once()
    print(f"\n결과: {count}건 동기화됨")