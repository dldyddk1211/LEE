"""
경로 설정 - 환경 자동 감지
  Mac  → 운영 서버 (production)  : /theone/srv/data
  Windows → 테스트 환경 (test)   : 프로젝트 내 data/
"""

import os
import platform

# =============================================
# 환경 감지
# =============================================
_system = platform.system()

if _system == 'Darwin':
    ENV = 'production'   # Mac = 운영 서버
elif _system == 'Windows':
    ENV = 'test'         # Windows = 테스트
else:
    ENV = 'production'   # Linux 서버도 운영으로 처리

IS_PRODUCTION = (ENV == 'production')
IS_TEST       = (ENV == 'test')

# =============================================
# 데이터 루트 경로
# =============================================
if IS_PRODUCTION:
    # Mac 서버: /theone/srv/data
    DATA_ROOT = '/theone/srv/data'
else:
    # Windows 테스트: 프로젝트 루트 아래 data/
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_ROOT = os.path.join(_project_root, 'data')

# =============================================
# 전체 폴더 구조 정의
# =============================================
PATHS = {
    # ---------- 고객 (customers) ----------
    'customers_raw':          os.path.join(DATA_ROOT, 'customers', 'raw'),
    'customers_processed':    os.path.join(DATA_ROOT, 'customers', 'processed'),
    'customers_exports':      os.path.join(DATA_ROOT, 'customers', 'exports'),

    # ---------- 주문 (orders) ----------
    'orders_raw':             os.path.join(DATA_ROOT, 'orders', 'raw'),
    'orders_processed':       os.path.join(DATA_ROOT, 'orders', 'processed'),
    'orders_invoices':        os.path.join(DATA_ROOT, 'orders', 'invoices'),

    # ---------- 제품·빅데이터 (products) ----------
    'products_metadata':      os.path.join(DATA_ROOT, 'products', 'metadata'),
    'products_analytics':     os.path.join(DATA_ROOT, 'products', 'analytics'),
    'products_images':        os.path.join(DATA_ROOT, 'products', 'images'),

    # ---------- 운영 자료 (operations) ----------
    'operations_hr':          os.path.join(DATA_ROOT, 'operations', 'hr'),
    'operations_finance':     os.path.join(DATA_ROOT, 'operations', 'finance'),
    'operations_legal':       os.path.join(DATA_ROOT, 'operations', 'legal'),
    'operations_projects':    os.path.join(DATA_ROOT, 'operations', 'projects'),

    # ---------- 백업 (backups) ----------
    'backups_daily':          os.path.join(DATA_ROOT, 'backups', 'daily'),
    'backups_weekly':         os.path.join(DATA_ROOT, 'backups', 'weekly'),
    'backups_monthly':        os.path.join(DATA_ROOT, 'backups', 'monthly'),

    # ---------- 시스템 ----------
    'logs':                   os.path.join(DATA_ROOT, 'logs'),
    'tmp':                    os.path.join(DATA_ROOT, 'tmp'),
    'vault':                  os.path.join(DATA_ROOT, 'vault'),

    # ---------- 포이즌 수집 결과 (products/analytics 하위) ----------
    'poizon_output':          os.path.join(DATA_ROOT, 'products', 'analytics'),
    'poizon_logs':            os.path.join(DATA_ROOT, 'logs'),
    'poizon_shots':           os.path.join(DATA_ROOT, 'tmp', 'shots'),
}


def get(key: str) -> str:
    """경로 반환. 없으면 DATA_ROOT 반환."""
    return PATHS.get(key, DATA_ROOT)


def ensure_dirs():
    """모든 데이터 폴더를 생성합니다 (없으면 자동 생성)."""
    for path in PATHS.values():
        os.makedirs(path, exist_ok=True)
    print(f"✅ [{ENV}] 데이터 폴더 준비 완료")
    print(f"   루트: {DATA_ROOT}")


def print_info():
    """현재 환경 및 경로 정보 출력."""
    print(f"\n{'='*50}")
    print(f"  환경  : {ENV.upper()}  ({'Mac 운영서버' if IS_PRODUCTION else 'Windows 테스트'})")
    print(f"  루트  : {DATA_ROOT}")
    print(f"{'='*50}")
    for key, path in PATHS.items():
        exists = '✅' if os.path.exists(path) else '❌'
        print(f"  {exists}  {key:<25} {path}")
    print(f"{'='*50}\n")


# 앱 시작 시 폴더 자동 생성
if __name__ != '__main__':
    ensure_dirs()


if __name__ == '__main__':
    print_info()
