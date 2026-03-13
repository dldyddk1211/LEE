"""
경로 설정 - 로컬 DB + NAS 백업 이중 경로 관리
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DB는 로컬에 저장, NAS는 백업 전용

Mac (운영):  로컬 ~/poizon_search_data/  →  백업 /Volumes/LEE/.../
Windows (테스트): 로컬 {프로젝트}/local_data/  →  백업 Z:/VOL1/LEE/.../
"""

import os
import json
import platform
import shutil
from datetime import datetime

# =============================================
# 프로젝트 루트 & 설정 파일
# =============================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(PROJECT_ROOT, 'config', 'settings.json')

# =============================================
# 환경 감지
# =============================================
_system = platform.system()

if _system == 'Darwin':
    ENV = 'production'
    DEFAULT_DATA_ROOT = os.path.expanduser('~/poizon_search_data')
    NAS_ROOT = '/Volumes/LEE/theone/srv/data/poizon_search'
elif _system == 'Windows':
    ENV = 'test'
    DEFAULT_DATA_ROOT = os.path.join(PROJECT_ROOT, 'local_data')
    NAS_ROOT = 'Z:/VOL1/LEE/theone/srv/data/poizon_search'
else:
    ENV = 'production'
    DEFAULT_DATA_ROOT = os.path.expanduser('~/poizon_search_data')
    NAS_ROOT = '/Volumes/LEE/theone/srv/data/poizon_search'

IS_PRODUCTION = (ENV == 'production')
IS_TEST       = (ENV == 'test')


# =============================================
# 설정 파일 로드/저장
# =============================================
def _load_settings():
    """settings.json 로드 (없으면 기본값)"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(settings):
    """settings.json 저장"""
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_data_root():
    """현재 데이터 루트 경로 반환 (settings.json 우선)"""
    settings = _load_settings()
    custom = settings.get('data_root', '').strip()
    if custom:
        return custom
    return DEFAULT_DATA_ROOT


def set_data_root(new_root):
    """데이터 루트 경로 변경 후 settings.json에 저장"""
    settings = _load_settings()
    settings['data_root'] = new_root.strip()
    _save_settings(settings)
    # 전역 변수 갱신
    _rebuild_paths()


# =============================================
# 데이터 루트 (동적)
# =============================================
DATA_ROOT = get_data_root()


# =============================================
# 폴더 구조 정의
# =============================================
def _build_paths(root):
    """데이터 루트 기반으로 전체 경로 딕셔너리 생성"""
    return {
        # ---------- DB ----------
        'db':                     os.path.join(root, 'db'),
        'invoices_db':            os.path.join(root, 'db', 'invoices.db'),
        'inventory_db':           os.path.join(root, 'db', 'inventory.db'),
        'bigdata_db':             os.path.join(root, 'db', 'bigdata.db'),

        # ---------- 고객·주문 데이터 ----------
        'customers_json':         os.path.join(root, 'db', 'customers.json'),
        'task_history_json':      os.path.join(root, 'db', 'task_history.json'),
        'invoices_pdf':           os.path.join(root, 'outputs', 'invoices'),

        # ---------- 출력 (엑셀 등) ----------
        'outputs':                os.path.join(root, 'outputs'),
        'outputs_excel':          os.path.join(root, 'outputs', 'excel'),
        'bigdata_backups':        os.path.join(root, 'outputs', 'bigdata_backups'),

        # ---------- 로그 ----------
        'logs':                   os.path.join(root, 'logs'),
    }


PATHS = _build_paths(DATA_ROOT)


def _rebuild_paths():
    """DATA_ROOT가 변경될 때 전역 변수 갱신"""
    global DATA_ROOT, PATHS
    DATA_ROOT = get_data_root()
    PATHS.clear()
    PATHS.update(_build_paths(DATA_ROOT))


# =============================================
# 유틸리티
# =============================================
def get(key: str) -> str:
    """경로 반환. 없으면 DATA_ROOT 반환."""
    return PATHS.get(key, DATA_ROOT)


def ensure_dirs():
    """모든 데이터 폴더를 생성합니다 (없으면 자동 생성)."""
    dirs_to_create = set()
    for path in PATHS.values():
        # .db, .json 등 파일 경로는 부모 디렉토리만 생성
        if os.path.splitext(path)[1]:
            dirs_to_create.add(os.path.dirname(path))
        else:
            dirs_to_create.add(path)

    for d in dirs_to_create:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass  # 드라이브 미연결 시 무시

    print(f"[OK] [{ENV}] data dirs ready")
    print(f"     root: {DATA_ROOT}")


def is_drive_connected():
    """로컬 데이터 폴더가 존재하는지 확인"""
    return os.path.isdir(DATA_ROOT)


def is_nas_connected():
    """NAS 공유 드라이브가 연결되어 있는지 확인"""
    return os.path.isdir(NAS_ROOT)


# =============================================
# NAS 백업
# =============================================
_NAS_PATHS = _build_paths(NAS_ROOT)

# 백업 대상 파일 키
_BACKUP_FILES = ['invoices_db', 'inventory_db', 'bigdata_db', 'customers_json', 'task_history_json']


def backup_to_nas():
    """로컬 DB를 NAS에 백업. 결과 dict 반환."""
    if not is_nas_connected():
        return {'success': False, 'error': 'NAS가 연결되어 있지 않습니다', 'files': []}

    nas_db_dir = _NAS_PATHS['db']
    os.makedirs(nas_db_dir, exist_ok=True)

    # 날짜별 백업 폴더
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = os.path.join(NAS_ROOT, 'backups', 'daily', timestamp)
    os.makedirs(backup_dir, exist_ok=True)

    copied = []
    errors = []
    for key in _BACKUP_FILES:
        src = PATHS.get(key, '')
        if not src or not os.path.exists(src):
            continue
        filename = os.path.basename(src)
        try:
            # 1) 날짜별 백업 폴더에 복사
            shutil.copy2(src, os.path.join(backup_dir, filename))
            # 2) NAS db/ 폴더에 최신 복사본 덮어쓰기
            shutil.copy2(src, os.path.join(nas_db_dir, filename))
            size = os.path.getsize(src)
            copied.append({'file': filename, 'size': size})
        except Exception as e:
            errors.append({'file': filename, 'error': str(e)})

    # 마지막 백업 시간 저장
    settings = _load_settings()
    settings['last_backup_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _save_settings(settings)

    return {
        'success': len(errors) == 0,
        'timestamp': timestamp,
        'files': copied,
        'errors': errors,
        'backup_dir': backup_dir
    }


def get_backup_status():
    """백업 상태 정보 반환"""
    settings = _load_settings()
    local_files = []
    for key in _BACKUP_FILES:
        fpath = PATHS.get(key, '')
        if fpath and os.path.exists(fpath):
            stat = os.stat(fpath)
            local_files.append({
                'key': key,
                'file': os.path.basename(fpath),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
    return {
        'nas_connected': is_nas_connected(),
        'nas_root': NAS_ROOT,
        'last_backup_time': settings.get('last_backup_time', ''),
        'local_files': local_files,
    }


def migrate_from_nas():
    """NAS → 로컬로 DB 초기 마이그레이션 (로컬 파일이 없을 때만)"""
    if not is_nas_connected():
        return
    migrated = []
    for key in _BACKUP_FILES:
        local_path = PATHS.get(key, '')
        nas_path = _NAS_PATHS.get(key, '')
        if not local_path or not nas_path:
            continue
        # 로컬에 없고 NAS에 있으면 복사
        if not os.path.exists(local_path) and os.path.exists(nas_path) and os.path.getsize(nas_path) > 0:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            try:
                shutil.copy2(nas_path, local_path)
                migrated.append(os.path.basename(local_path))
            except Exception as e:
                print(f"  ⚠️ 마이그레이션 실패 ({os.path.basename(nas_path)}): {e}")
    if migrated:
        print(f"  [OK] NAS -> local migration: {', '.join(migrated)}")


def get_settings():
    """전체 설정 반환 (API용)"""
    settings = _load_settings()
    return {
        'env': ENV,
        'system': _system,
        'default_data_root': DEFAULT_DATA_ROOT,
        'data_root': DATA_ROOT,
        'nas_root': NAS_ROOT,
        'nas_connected': is_nas_connected(),
        'custom_data_root': settings.get('data_root', ''),
        'drive_connected': is_drive_connected(),
        'last_backup_time': settings.get('last_backup_time', ''),
    }


def print_info():
    """현재 환경 및 경로 정보 출력."""
    connected = 'Connected' if is_drive_connected() else 'Not connected'
    nas_status = 'Connected' if is_nas_connected() else 'Not connected'
    print(f"\n{'='*50}")
    print(f"  ENV    : {ENV.upper()}  ({'Mac' if IS_PRODUCTION else 'Windows'})")
    print(f"  Local  : {connected}  {DATA_ROOT}")
    print(f"  NAS    : {nas_status}  {NAS_ROOT}")
    print(f"{'='*50}")
    for key, path in PATHS.items():
        exists = '[O]' if os.path.exists(path) else '[X]'
        print(f"  {exists}  {key:<25} {path}")
    print(f"{'='*50}\n")


# =============================================
# 앱 시작 시 폴더 자동 생성 + NAS 마이그레이션
# =============================================
if __name__ != '__main__':
    ensure_dirs()
    migrate_from_nas()

if __name__ == '__main__':
    print_info()
