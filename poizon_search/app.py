# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# .env 파일 로딩 (있으면 환경변수로 적용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import os
try:
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
except Exception:
    pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 표준 라이브러리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import os
import sys
import json
import time
import uuid
import threading
import queue
import asyncio 
from datetime import datetime

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Flask 관련
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    Response,
    send_file,
    jsonify,
    stream_with_context
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# openpyxl 관련
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 전역 변수 선언 ✅ 여기!
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# POIZON
browser = None
page = None
context = None

# 무신사 ✅
musinsa_browser = None
musinsa_page = None
musinsa_context = None

# 크림 ✅
kream_browser = None
kream_page = None
kream_context = None

# 기타
log_queue = queue.Queue()


# kream_search 모듈 import
try:
    from kream_data import kream_search
    print("✅ kream_search 모듈 로드 성공")


except ImportError:
    try:
        import kream_data.kream_search as kream_search
        print("✅ kream_search 모듈 로드 성공 (직접 import)")
    except ImportError:
        import sys
        kream_data_path = os.path.join(os.path.dirname(__file__), 'kream_data')
        if os.path.exists(kream_data_path):
            sys.path.insert(0, kream_data_path)
            try:
                import kream_search
                print("✅ kream_search 모듈 로드 성공 (sys.path)")
            except ImportError:
                print("⚠️ kream_search 모듈을 찾을 수 없습니다")
                kream_search = None

try:
    from musinsa_data import musinsa_search
    print("✅ musinsa_search 모듈 로드 성공")
except ImportError:
    try:
        import musinsa_data.musinsa_search as musinsa_search
        print("✅ musinsa_search 모듈 로드 성공 (직접 import)")
    except ImportError:
        import sys
        musinsa_data_path = os.path.join(os.path.dirname(__file__), 'musinsa_data')
        if os.path.exists(musinsa_data_path):
            sys.path.insert(0, musinsa_data_path)
            try:
                import musinsa_search
                print("✅ musinsa_search 모듈 로드 성공 (sys.path)")
            except ImportError:
                print("⚠️ musinsa_search 모듈을 찾을 수 없습니다")
                musinsa_search = None

app = Flask(__name__)

app.secret_key = 'inventory_secret_key_2024!'  # 아무 문자열이나 가능


# ✅ 스케줄러 Blueprint 등록
try:
    from scheduler_data.scheduler_api import scheduler_bp, save_task_to_history
    app.register_blueprint(scheduler_bp)
    print("✅ 스케줄러 등록 성공")
except Exception as e:
    print(f"⚠️ 스케줄러 로드 실패: {e}")
    # 대비용 더미 함수
    def save_task_to_history(task_data):
        print("⚠️ 스케줄러 없이 실행 중")
        return None

# ✅ 재고관리 Blueprint 등록
try:
    from inventory_data.inventory_api import inventory_bp
    app.register_blueprint(inventory_bp)
    print("✅ 재고관리 등록 성공")
except Exception as e:
    print(f"⚠️ 재고관리 로드 실패: {e}")

# 캐시 비활성화
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.after_request
def add_no_cache_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# 전역 변수
log_queue = queue.Queue()
result_data = {}
stop_flag = False
current_browser = None
is_working = False
work_start_time = None
work_type = None
estimated_items = 0
current_items = 0
stop_requested = False

# ==========================================
# 콜백 함수
# ==========================================

def log_callback(message, level='info'):
    global current_items
    
    if message.startswith("PROGRESS:"):
        parts = message.split(":")
        if len(parts) >= 2:
            progress_part = parts[1]
            page_info = None
            total_pages = None
            
            if "|PAGE:" in progress_part:
                main_part, page_part = progress_part.split("|PAGE:")
                current, total = main_part.split("/")
                page_info, total_pages = page_part.split("/")
            else:
                current, total = progress_part.split("/")
            
            current_items = int(current)
            log_data = {
                'type': 'progress',
                'current': int(current),
                'total': int(total)
            }
            
            if page_info and total_pages:
                log_data['page'] = int(page_info)
                log_data['total_pages'] = int(total_pages)
            
            log_queue.put(log_data)

    elif message.startswith("TOTAL_COUNT:"):
        try:
            total = int(message.split(":")[1])
            log_queue.put({'type': 'progress', 'current': 0, 'total': total})
        except:
            pass

    elif message.startswith("PRODUCT_START:"):
        product_code = message.split(":", 1)[1]
        log_queue.put({
            'type': 'product_start',
            'product_code': product_code
        })

    elif message.startswith("PRODUCT_RESULT:"):
        try:
            json_str = message.split(":", 1)[1]
            data = json.loads(json_str)
            log_queue.put({
                'type': 'product_result',
                'product_code': data['product_code'],
                'products': data['products']
            })
        except Exception as e:
            print(f"PRODUCT_RESULT 처리 오류: {e}")

    elif message.startswith("DATA:"):
        try:
            item = json.loads(message.split(":", 1)[1])
            log_queue.put({'type': 'data', 'item': item})
        except Exception as e:
            print(f"DATA 처리 오류: {e}")

    else:
        log_queue.put({
            'type': 'log',
            'message': message,
            'level': level
        })

# ==========================================
# 백그라운드 작업
# ==========================================
def run_scraper(keyword, max_pages, skip_login=False):
    """백그라운드에서 스크래핑 실행"""
    global result_data, stop_flag, is_working, work_start_time, work_type, estimated_items, current_items
    
    is_working = True
    import time as time_module
    work_start_time = time_module.time()
    work_type = 'scraping'
    estimated_items = max_pages
    current_items = 0
    stop_flag = False
    
    try:
        from poizon_data.poizon_search import run_poizon_from_gui
        
        result = run_poizon_from_gui(
            keyword=keyword,
            max_pages=max_pages,
            callback=log_callback,
            skip_login=skip_login
        )
        
        if result.get('success'):
            # ✅ 스케줄러에 저장!
            try:
                end_time = time_module.time()
                duration_seconds = int(end_time - work_start_time)
                
                task_data = {
                    'keyword': keyword,
                    'mode': 'keyword',
                    'collected_count': result.get('total_items', 0),
                    'kream_count': 0,
                    'duration_seconds': duration_seconds,
                    'data': result.get('data', [])
                }
                
                task_id = save_task_to_history(task_data)
                if task_id:
                    print(f"💾 스케줄러 저장 완료: {task_id}")
                else:
                    print(f"⚠️ 스케줄러 저장 실패")
                
            except Exception as e:
                print(f"⚠️ 스케줄러 저장 오류: {e}")
                import traceback
                traceback.print_exc()
            
            # 기존 complete 메시지
            log_queue.put({
                'type': 'complete',
                'total_items': result.get('total_items', 0),
                'pages': result.get('pages', 0),
                'file_path': result.get('file_path', ''),
                'data': result.get('data', [])
            })
            result_data['file_path'] = result.get('file_path', '')
        else:
            log_queue.put({
                'type': 'error',
                'message': result.get('error', '알 수 없는 오류')
            })
    except Exception as e:
        if not stop_flag:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    finally:
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0

def run_comparison(products):
    """리스트 비교 작업"""
    global result_data, stop_flag, current_browser, is_working, work_start_time, work_type, estimated_items, current_items
    
    is_working = True
    import time as time_module
    work_start_time = time_module.time()
    work_type = 'comparison'
    estimated_items = len(products)
    current_items = 0
    stop_flag = False
    
    try:
        from poizon_data.poizon_search import run_excel_comparison
        
        result = run_excel_comparison(products, callback=log_callback)
        
        if result.get('success'):
            # ✅ 스케줄러에 저장!
            try:
                end_time = time_module.time()
                duration_seconds = int(end_time - work_start_time)
                
                task_data = {
                    'keyword': f'리스트비교_{len(products)}개',
                    'mode': 'compare',
                    'collected_count': result.get('total_items', 0),
                    'kream_count': 0,
                    'duration_seconds': duration_seconds,
                    'data': result.get('results', [])  # results 필드 사용
                }
                
                task_id = save_task_to_history(task_data)
                if task_id:
                    print(f"💾 스케줄러 저장 완료: {task_id}")
                else:
                    print(f"⚠️ 스케줄러 저장 실패")
                
            except Exception as e:
                print(f"⚠️ 스케줄러 저장 오류: {e}")
                import traceback
                traceback.print_exc()
            
            # 텔레그램 알림
            try:
                from utils.telegram import send_telegram_async
                elapsed_min = int((time_module.time() - work_start_time) // 60)
                elapsed_sec = int((time_module.time() - work_start_time) % 60)
                send_telegram_async(
                    f"✅ <b>리스트 비교 완료</b>\n"
                    f"• 상품 수: {result.get('total_items', 0)}개\n"
                    f"• 소요 시간: {elapsed_min}분 {elapsed_sec}초"
                )
            except Exception:
                pass

            # 기존 complete 메시지
            log_queue.put({
                'type': 'complete',
                'total_items': result.get('total_items', 0),
                'file_path': result.get('file_path', '')
            })
            result_data['file_path'] = result.get('file_path', '')
        else:
            log_queue.put({
                'type': 'error',
                'message': result.get('error', '알 수 없는 오류')
            })
    except Exception as e:
        if not stop_flag:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    finally:
        current_browser = None
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0
            

# ==========================================
# 무신사 검색 실행 함수
# ==========================================

def run_musinsa_search(keyword, max_items, search_mode='keyword'):
    """무신사 검색 실행 (스레드)"""
    global stop_flag, is_working, work_start_time, work_type, estimated_items, current_items
    
    print(f"\n{'='*60}")
    print(f"🟤 run_musinsa_search 시작")
    print(f"  keyword: {keyword}")
    print(f"  max_items: {max_items}")
    print(f"  max_items 타입: {type(max_items)}")
    print(f"{'='*60}\n")
    
    is_working = True
    import time as time_module
    work_start_time = time_module.time()
    work_type = 'musinsa'
    
    if max_items == 'max':
        estimated_items = 1000
    else:
        try:
            estimated_items = int(max_items)
        except:
            estimated_items = 10
    
    current_items = 0
    stop_flag = False
    
    try:
        result = musinsa_search.search_musinsa(   # ← keyword_detail → search_musinsa
            keyword=keyword,
            max_items=max_items,
            search_mode=search_mode,
            callback=log_callback
        )
                
        print(f"\n{'='*60}")
        print(f"✅ run_musinsa_search 완료")
        print(f"  성공: {result.get('success')}")
        print(f"  수집 개수: {result.get('total_items', 0)}")
        print(f"{'='*60}\n")
        
        if result.get('success'):
            try:
                end_time = time_module.time()
                duration_seconds = int(end_time - work_start_time)
                task_data = {
                    'keyword': f'무신사_{keyword}',
                    'mode': 'musinsa',
                    'collected_count': result.get('total_items', 0),
                    'kream_count': 0,
                    'duration_seconds': duration_seconds,
                    'data': result.get('results', [])
                }
                task_id = save_task_to_history(task_data)
                if task_id:
                    print(f"💾 스케줄러 저장 완료: {task_id}")
                else:
                    print(f"⚠️ 스케줄러 저장 실패")
            except Exception as e:
                print(f"⚠️ 스케줄러 저장 오류: {e}")
                import traceback
                traceback.print_exc()
            
            # 텔레그램 알림
            try:
                from utils.telegram import send_telegram_async
                elapsed_min = int((time_module.time() - work_start_time) // 60)
                elapsed_sec = int((time_module.time() - work_start_time) % 60)
                send_telegram_async(
                    f"✅ <b>무신사 검색 완료</b>\n"
                    f"• 키워드: {keyword}\n"
                    f"• 수집 수: {result.get('total_items', 0)}개\n"
                    f"• 소요 시간: {elapsed_min}분 {elapsed_sec}초"
                )
            except Exception:
                pass

            log_queue.put({
                'type': 'complete',
                'total_items': result.get('total_items', 0),
                'data': result.get('results', [])
            })
        else:
            log_queue.put({
                'type': 'error',
                'message': result.get('error', '알 수 없는 오류')
            })

    except Exception as e:
        print(f"\n❌ run_musinsa_search 오류: {e}")
        import traceback
        traceback.print_exc()
        if not stop_flag:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    finally:
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0


# ==========================================
# 무신사 → 크림 → 포이즌 통합 검색
# ==========================================

def run_full_search(keyword, max_items):
    """무신사 검색 후 자동으로 크림 → 포이즌 순서로 연속 검색"""
    global stop_flag, is_working, work_start_time, work_type, estimated_items, current_items

    import time as time_module
    from utils.telegram import send_telegram_async

    is_working = True
    work_start_time = time_module.time()
    stop_flag = False
    while not log_queue.empty():
        log_queue.get()

    total_start = time_module.time()
    musinsa_count = 0
    kream_count   = 0
    poizon_count  = 0
    product_codes = []

    # ────────────────────────────────────
    # 1단계: 무신사 검색
    # ────────────────────────────────────
    try:
        work_type = 'musinsa'
        estimated_items = int(max_items) if str(max_items).isdigit() else 100
        current_items = 0

        log_queue.put({'type': 'log', 'message': f'🟤 [1/3] 무신사 검색 시작: {keyword} ({max_items}개)'})
        result = musinsa_search.search_musinsa(keyword=keyword, max_items=max_items, callback=log_callback)

        if result.get('success'):
            items = result.get('results', [])
            musinsa_count = len(items)
            # 유효한 품번만 추출
            product_codes = [
                it.get('product_code', '').strip()
                for it in items
                if it.get('product_code', '').strip() not in ('', '-')
            ]
            elapsed = int(time_module.time() - total_start)
            send_telegram_async(
                f"✅ <b>[1/3] 무신사 검색 완료</b>\n"
                f"• 키워드: {keyword}\n"
                f"• 수집: {musinsa_count}개 (품번 {len(product_codes)}개)\n"
                f"• 경과: {elapsed//60}분 {elapsed%60}초\n"
                f"→ 크림 검색 시작..."
            )
            log_queue.put({'type': 'log', 'message': f'✅ 무신사 완료 {musinsa_count}개 → 크림 검색 시작'})
        else:
            err = result.get('error', '알 수 없는 오류')
            send_telegram_async(f"❌ <b>무신사 오류</b>\n{err}")
            log_queue.put({'type': 'error', 'message': f'무신사 오류: {err}'})
            return

    except Exception as e:
        send_telegram_async(f"❌ <b>무신사 오류</b>\n{e}")
        log_queue.put({'type': 'error', 'message': f'무신사 오류: {e}'})
        return

    if stop_flag or not product_codes:
        if not product_codes:
            send_telegram_async('⚠️ 품번이 없어 크림/포이즌 검색을 건너뜁니다')
        is_working = False
        return

    # ────────────────────────────────────
    # 2단계: 크림 검색
    # ────────────────────────────────────
    try:
        work_type = 'kream'
        estimated_items = len(product_codes)
        current_items = 0

        log_queue.put({'type': 'log', 'message': f'🛒 [2/3] 크림 검색 시작: {len(product_codes)}개 품번'})
        kream_result = kream_search.search_kream_products_batch(product_codes, callback=log_callback)

        if kream_result.get('success'):
            kream_data = kream_result.get('results', {})
            kream_count = len(kream_data)
            elapsed = int(time_module.time() - total_start)
            send_telegram_async(
                f"✅ <b>[2/3] 크림 검색 완료</b>\n"
                f"• 결과: {kream_count}개\n"
                f"• 경과: {elapsed//60}분 {elapsed%60}초\n"
                f"→ 포이즌 검색 시작..."
            )
            log_queue.put({'type': 'log', 'message': f'✅ 크림 완료 {kream_count}개 → 포이즌 검색 시작'})
        else:
            err = kream_result.get('error', '알 수 없는 오류')
            send_telegram_async(f"❌ <b>크림 오류</b>\n{err}\n→ 포이즌 검색은 계속 진행합니다")
            log_queue.put({'type': 'log', 'message': f'⚠️ 크림 오류: {err}'})

    except Exception as e:
        send_telegram_async(f"❌ <b>크림 오류</b>\n{e}\n→ 포이즌 검색은 계속 진행합니다")
        log_queue.put({'type': 'log', 'message': f'⚠️ 크림 오류: {e}'})

    if stop_flag:
        is_working = False
        return

    # ────────────────────────────────────
    # 3단계: 포이즌 검색
    # ────────────────────────────────────
    try:
        from poizon_data.poizon_search import search_single_product
        work_type = 'poizon'
        estimated_items = len(product_codes)
        current_items = 0

        log_queue.put({'type': 'log', 'message': f'🔴 [3/3] 포이즌 검색 시작: {len(product_codes)}개 품번'})
        poizon_data = {}

        for idx, code in enumerate(product_codes):
            if stop_flag:
                break
            current_items = idx + 1
            log_queue.put({'type': 'log', 'message': f'  포이즌 [{idx+1}/{len(product_codes)}] {code}'})
            try:
                pr = search_single_product(code)
                if pr:
                    poizon_data[code] = pr
                    poizon_count += 1
            except Exception as e:
                log_queue.put({'type': 'log', 'message': f'  ⚠️ 포이즌 {code} 오류: {e}'})

        elapsed = int(time_module.time() - total_start)
        send_telegram_async(
            f"✅ <b>[3/3] 포이즌 검색 완료</b>\n"
            f"• 결과: {poizon_count}개\n"
            f"• 경과: {elapsed//60}분 {elapsed%60}초"
        )
        log_queue.put({'type': 'log', 'message': f'✅ 포이즌 완료 {poizon_count}개'})

    except Exception as e:
        send_telegram_async(f"❌ <b>포이즌 오류</b>\n{e}")
        log_queue.put({'type': 'log', 'message': f'⚠️ 포이즌 오류: {e}'})

    # ────────────────────────────────────
    # 최종 요약
    # ────────────────────────────────────
    total_elapsed = int(time_module.time() - total_start)
    send_telegram_async(
        f"🎉 <b>전체 검색 완료</b>\n"
        f"• 키워드: {keyword}\n"
        f"• 무신사: {musinsa_count}개\n"
        f"• 크림: {kream_count}개\n"
        f"• 포이즌: {poizon_count}개\n"
        f"• 총 소요: {total_elapsed//60}분 {total_elapsed%60}초"
    )
    log_queue.put({
        'type': 'complete',
        'total_items': musinsa_count,
        'message': f'전체 완료 - 무신사 {musinsa_count} / 크림 {kream_count} / 포이즌 {poizon_count}'
    })

    is_working = False
    work_type = None
    estimated_items = 0
    current_items = 0


# ==========================================
# 라우트
# ==========================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_login')
def check_login():
    """POIZON 로그인"""
    print("\n" + "="*60)
    print("🔍 /check_login 호출")
    print("="*60)
    
    try:
        from poizon_data.poizon_search import perform_login
        print("✅ perform_login import 성공")
        
        result = perform_login()
        print(f"✅ perform_login 실행 완료: {result}")
        
        return jsonify({
            'logged_in': result.get('success', False),
            'message': result.get('message', '')
        })
        
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        return jsonify({
            'logged_in': False,
            'message': f'모듈을 찾을 수 없습니다: {str(e)}'
        }), 500
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'logged_in': False,
            'message': f'오류: {str(e)}'
        }), 500

@app.route('/check_status')
def check_status():
    global is_working, work_start_time, work_type, estimated_items, current_items
    
    if not is_working:
        return jsonify({'working': False, 'message': '서버 사용 가능'})
    
    import time
    elapsed_seconds = int(time.time() - work_start_time) if work_start_time else 0
    remaining_minutes = 1
    
    if current_items > 0:
        avg_time = elapsed_seconds / current_items
        remaining = max(0, estimated_items - current_items)
        remaining_minutes = max(1, int(avg_time * remaining) // 60)
    
    work_type_kr = '수집' if work_type == 'scraping' else '비교'
    
    return jsonify({
        'working': True,
        'message': f'서버 작업 중 ({work_type_kr})',
        'work_type': work_type,
        'progress': f'{current_items}/{estimated_items}',
        'elapsed_minutes': elapsed_seconds // 60,
        'remaining_minutes': remaining_minutes
    })

@app.route('/start')
def start_search():
    mode = request.args.get('mode', 'poizon')
    keyword = request.args.get('keyword', '')
    skip_login = request.args.get('skip_login', 'false') == 'true'
    
    # ✅ 무신사 검색 모드 추가
    search_mode = request.args.get('search_mode', 'keyword')  # 'keyword' 또는 'ranking'

    # ✅ max_pages 처리 (POIZON용)
    max_pages_str = request.args.get('max_pages', '1')
    try:
        if max_pages_str and max_pages_str != 'NaN':
            max_pages = int(max_pages_str)
        else:
            max_pages = 1
    except ValueError:
        max_pages = 1

    # ✅ max_items 처리 (무신사용)
    max_items_str = request.args.get('max_items', 'max')
    if max_items_str == 'max':
        max_items = 'max'  # ✅ 문자열 그대로
    else:
        try:
            max_items = int(max_items_str)
        except ValueError:
            max_items = 'max'
    
    print(f"\n{'='*60}")
    print(f"📡 /start 라우트 호출:")
    print(f"  mode: {mode}")
    print(f"  keyword: {keyword}")
    print(f"  search_mode: {search_mode}")
    print(f"  max_pages: {max_pages}")
    print(f"  max_items: {max_items} (타입: {type(max_items)})")
    print(f"  skip_login: {skip_login}")
    print(f"{'='*60}\n")
    
    # mode 처리
    if mode == 'keyword':
        mode = 'poizon'
    
    # 큐 비우기
    while not log_queue.empty():
        log_queue.get()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 모드별 처리
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    if mode == 'poizon':
        # POIZON 검색 (max_pages 사용)
        print(f"🟣 POIZON 스레드 시작: keyword={keyword}, max_pages={max_pages}")
        thread = threading.Thread(target=run_scraper, args=(keyword, max_pages, skip_login))
        thread.daemon = True
        thread.start()
        
    elif mode == 'musinsa':
        # ✅ 무신사 검색 (브라우저는 musinsa_search 모듈 내부에서 관리)
        print(f"🟤 무신사 스레드 시작: keyword={keyword}, max_items={max_items}")
        thread = threading.Thread(target=run_musinsa_search, args=(keyword, max_items))
        thread.daemon = True
        thread.start()
    elif mode == 'kream':
        print("🛒 크림 모드 (준비 중)")
        log_queue.put({'type': 'error', 'message': '🛒 크림 검색 기능은 준비 중입니다'})
        
    else:
        # 기본: POIZON
        print(f"⚠️ 알 수 없는 모드 '{mode}' → POIZON으로 처리")
        thread = threading.Thread(target=run_scraper, args=(keyword, max_pages, skip_login))
        thread.daemon = True
        thread.start()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SSE 이벤트 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def generate():
        """SSE 이벤트 생성"""
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📡 SSE generate 시작")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            event_count = 0
            
            while True:
                try:
                    # ✅ 1초 타임아웃으로 큐에서 데이터 가져오기
                    data = log_queue.get(timeout=1)
                    event_count += 1
                    
                    print(f"📩 [{event_count}] SSE 이벤트: {data.get('type', 'unknown')}")
                    
                    # ✅ complete 이벤트일 때 mode 정보 추가
                    if data.get('type') == 'complete':
                        data['mode'] = mode
                        print(f"  ✅ complete 이벤트 (mode: {mode})")
                    
                    # ✅ JSON 직렬화
                    json_data = json.dumps(data, ensure_ascii=False)
                    yield f"data: {json_data}\n\n"
                    
                    # ✅ complete 또는 error면 종료
                    if data.get('type') in ['complete', 'error']:
                        print(f"  🔚 SSE 스트림 종료 (type: {data.get('type')})")
                        break
                        
                except queue.Empty:
                    # ✅ heartbeat
                    yield ": ping\n\n"
                    
        except GeneratorExit:
            print("⚠️ SSE 클라이언트 연결 종료 (GeneratorExit)")
            
        except Exception as e:
            print(f"❌ SSE generate 오류: {e}")
            import traceback
            traceback.print_exc()
            
            error_msg = {
                'type': 'error',
                'message': f'서버 오류: {str(e)}'
            }
            
            try:
                json_data = json.dumps(error_msg, ensure_ascii=False)
                yield f"data: {json_data}\n\n"
            except:
                yield f"data: {{'type':'error','message':'서버 오류'}}\n\n"
        
        finally:
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("📡 SSE generate 종료")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # ✅ Response 생성
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    
    return response

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '파일이 없습니다'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다'})
        
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
        
        products = []
        header_row = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        
        code_col_idx = 0
        for i, header in enumerate(header_row):
            if header and '상품' in str(header):
                code_col_idx = i
                break
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            
            product_code = str(row[code_col_idx]).strip() if len(row) > code_col_idx and row[code_col_idx] else ''
            product_name = str(row[code_col_idx + 1]).strip() if len(row) > code_col_idx + 1 and row[code_col_idx + 1] else ''
            original_price = row[code_col_idx + 2] if len(row) > code_col_idx + 2 else None
            sale_price = row[code_col_idx + 3] if len(row) > code_col_idx + 3 else None
            stock = row[code_col_idx + 4] if len(row) > code_col_idx + 4 else None
            
            import re
            def safe_int(val):
                if val is None or val == '':
                    return 0
                if isinstance(val, (int, float)):
                    return int(val)
                nums = re.sub(r'[^\d]', '', str(val).strip())
                return int(nums) if nums else 0
            
            if product_code or product_name:
                products.append({
                    'code': product_code,
                    'name': product_name,
                    'original_price': safe_int(original_price),
                    'sale_price': safe_int(sale_price),
                    'stock': safe_int(stock)
                })
        
        return jsonify({'success': True, 'count': len(products), 'products': products})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/compare_prices', methods=['POST'])
def compare_prices():
    products = request.json.get('products', [])
    
    while not log_queue.empty():
        log_queue.get()
    
    thread = threading.Thread(target=run_comparison, args=(products,))
    thread.daemon = True
    thread.start()
    
    def generate():
        while True:
            try:
                data = log_queue.get(timeout=1)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                if data.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<path:filename>')
def download(filename):
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'poizon_data', 'output_data', filename)
        
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/shutdown_kream_browser')
def shutdown_kream_browser():
    try:
        if kream_search:
            kream_search.close_kream_browser()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"⚠️ 크림 브라우저 종료 오류 (무시): {e}")
        return jsonify({'success': True}), 200

@app.route('/shutdown_browser')
def shutdown_browser():
    try:
        from poizon_data.poizon_search import close_browser_session
        close_browser_session()
        return jsonify({'success': True, 'message': 'POIZON 브라우저 종료 완료'}), 200
    except Exception as e:
        print(f"⚠️ POIZON 브라우저 종료 중 오류 (무시): {e}")
        return jsonify({'success': True, 'message': '이미 종료됨 또는 오류 무시'}), 200

@app.route('/stop', methods=['POST'])
def stop():
    global stop_flag, current_browser
    
    stop_flag = True
    
    try:
        from poizon_data import poizon_search
        poizon_search.stop_flag = True
    except:
        pass
    
    if current_browser:
        try:
            current_browser.close()
        except:
            pass
        current_browser = None
    
    return jsonify({'success': True})

# ==========================================
# 크림 검색
# ==========================================

@app.route('/kream_popup')
def kream_popup():
    """크림 검색 팝업 (자동 시작 지원)"""
    session_id = request.args.get('session_id', None)
    
    if session_id and hasattr(app, 'kream_search_sessions'):
        if session_id in app.kream_search_sessions:
            product_codes = app.kream_search_sessions[session_id]['product_codes']
            return render_template('kream_popup.html', 
                                   auto_start=True, 
                                   product_codes=product_codes)
    
    return render_template('kream_popup.html')

@app.route('/kream_login', methods=['POST'])
def kream_login():
    try:
        if kream_search is None:
            return jsonify({'success': False, 'error': 'kream_search 모듈이 없습니다'})
        
        result = kream_search.login_kream()
        return jsonify({'success': result, 'message': '로그인 성공' if result else '로그인 실패'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/search_kream_product', methods=['POST'])
def search_kream_product():
    try:
        if kream_search is None:
            return jsonify({'success': False, 'error': 'kream_search 모듈이 없습니다'})
        
        product_code = request.json.get('product_code', '')
        if not product_code:
            return jsonify({'success': False, 'error': '상품 코드가 없습니다'})
        
        result = kream_search.search_kream_product_detail(product_code)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/start_kream_search', methods=['POST'])
def start_kream_search():
    """크림 검색 시작 - 인라인 방식"""
    try:
        if kream_search is None:
            return jsonify({
                'success': False, 
                'error': 'kream_search 모듈이 로드되지 않았습니다.'
            }), 500
        
        data = request.json
        product_codes = data.get('product_codes', [])
        
        if not product_codes:
            return jsonify({'success': False, 'error': '상품 코드가 없습니다'})
        
        task_id = str(uuid.uuid4())
        
        if not hasattr(app, 'kream_tasks'):
            app.kream_tasks = {}
        
        app.kream_tasks[task_id] = {
            'product_codes': product_codes,
            'status': 'pending'
        }
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'total_products': len(product_codes)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    

@app.route('/kream_search_progress/<task_id>')
def kream_search_progress(task_id):
    """크림 검색 진행 상황 SSE"""
    
    if not hasattr(app, 'kream_tasks') or task_id not in app.kream_tasks:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    task = app.kream_tasks[task_id]
    product_codes = task['product_codes']
    
    progress_queue = queue.Queue()
    
    def run_background():
        try:
            kream_search.background_kream_search(task_id, product_codes, progress_queue)
        except Exception as e:
            print(f"❌ 백그라운드 검색 오류: {e}")
            import traceback
            traceback.print_exc()
            progress_queue.put({'event': 'error', 'data': {'error': str(e)}})
    
    thread = threading.Thread(target=run_background)
    thread.daemon = True
    thread.start()
    
    def generate():
        try:
            while True:
                try:
                    msg = progress_queue.get(timeout=30)
                    
                    event_type = msg.get('event', 'message')
                    event_data = msg.get('data', {})
                    
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    
                    if event_type in ['complete', 'error']:
                        if task_id in app.kream_tasks:
                            del app.kream_tasks[task_id]
                        break
                    
                except queue.Empty:
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"
                    
        except Exception as e:
            print(f"❌ SSE 스트림 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )

@app.route('/export_kream_to_excel', methods=['POST'])
def export_kream_to_excel():
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        
        data = request.json.get('data', [])
        if not data:
            return jsonify({'success': False, 'error': '데이터가 없습니다'})
        
        wb = Workbook()
        ws = wb.active
        ws.title = "크림 검색 결과"
        
        header_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_align = Alignment(horizontal="center", vertical="center")
        
        headers = ['순번', '상품번호', '제품명', '평균거래가', '중국노출가', 
                   '중국판매량', '현업자판매량', '크림평균가', '크림판매량', '비교']
        
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
        
        for row_idx, item in enumerate(data, start=2):
            ws.cell(row=row_idx, column=1, value=str(item.get('순번', '')))
            ws.cell(row=row_idx, column=2, value=str(item.get('상품번호', '')))
            ws.cell(row=row_idx, column=3, value=str(item.get('제품명', '')))
            ws.cell(row=row_idx, column=4, value=str(item.get('평균거래가', '')))
            ws.cell(row=row_idx, column=5, value=str(item.get('중국노출가', '')))
            ws.cell(row=row_idx, column=6, value=str(item.get('중국판매량', '')))
            ws.cell(row=row_idx, column=7, value=str(item.get('현업자판매량', '')))
            ws.cell(row=row_idx, column=8, value=str(item.get('크림평균가', '')))
            ws.cell(row=row_idx, column=9, value=str(item.get('크림판매량', '')))
            ws.cell(row=row_idx, column=10, value=str(item.get('비교', '')))
        
        column_widths = [8, 15, 40, 15, 15, 12, 15, 15, 12, 12]
        for idx, width in enumerate(column_widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kream_search_{timestamp}.xlsx'
        
        output_dir = os.path.join(os.path.dirname(__file__), 'kream_data', 'output_data')
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        wb.save(filepath)
        wb.close()
        
        return jsonify({'success': True, 'filename': filename, 'count': len(data)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download_kream/<filename>')
def download_kream(filename):
    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '잘못된 파일명입니다'}), 400
        
        file_path = os.path.join(os.path.dirname(__file__), 'kream_data', 'output_data', filename)
        
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# 구매처 검색
# ==========================================

@app.route('/start_sourcing', methods=['POST'])
def start_sourcing():
    """크림 검색 시작"""
    product_codes = request.json.get('product_codes', [])
    
    if not product_codes:
        return jsonify({'success': False, 'error': '상품번호가 없습니다'})
    
    session_id = str(uuid.uuid4())
    
    if not hasattr(app, 'kream_search_sessions'):
        app.kream_search_sessions = {}
    
    app.kream_search_sessions[session_id] = {
        'product_codes': product_codes,
        'status': 'pending'
    }
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'popup_url': f'/kream_popup?session_id={session_id}'
    })


@app.route('/shutdown_musinsa_browser')
def shutdown_musinsa_browser():
    try:
        if musinsa_search:
            musinsa_search.close_musinsa_browser()
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"⚠️ 무신사 브라우저 종료 오류 (무시): {e}")
        return jsonify({'success': True}), 200


# ✅ 무신사 로그인 라우트 추가
@app.route('/check_musinsa_login')
def check_musinsa_login():
    """무신사 로그인"""
    print("\n" + "="*60)
    print("🔍 /check_musinsa_login 호출")
    print("="*60)
    
    try:
        if musinsa_search is None:
            return jsonify({
                'logged_in': False,
                'message': 'musinsa_search 모듈을 찾을 수 없습니다'
            }), 500
        
        result = musinsa_search.login_musinsa()
        print(f"✅ login_musinsa 실행 완료: {result}")
        
        return jsonify({
            'logged_in': result.get('success', False),
            'message': result.get('message', '')
        })
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'logged_in': False,
            'message': f'오류: {str(e)}'
        }), 500
    
# ✅ POIZON 로그인 라우트 추가
@app.route('/check_poizon_login')
def check_poizon_login():
    """POIZON 로그인"""
    print("\n" + "="*60)
    print("🔍 /check_poizon_login 호출")
    print("="*60)
    
    try:
        from poizon_data.poizon_search import perform_login
        print("✅ perform_login import 성공")
        
        result = perform_login()
        print(f"✅ perform_login 실행 완료: {result}")
        
        return jsonify({
            'logged_in': result.get('success', False),
            'message': result.get('message', '')
        })
        
    except ImportError as e:
        print(f"❌ ImportError: {e}")
        return jsonify({
            'logged_in': False,
            'message': f'모듈을 찾을 수 없습니다: {str(e)}'
        }), 500
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'logged_in': False,
            'message': f'오류: {str(e)}'
        }), 500


# ==========================================
# 무신사→포이즌 검색 API
# ==========================================

@app.route('/start_poizon_search', methods=['POST'])
def start_poizon_search():
    """무신사 상품번호로 포이즌 검색 시작"""
    try:
        data = request.json
        product_codes = data.get('product_codes', [])
        
        if not product_codes:
            return jsonify({'success': False, 'error': '상품번호가 없습니다'}), 400
        
        task_id = str(uuid.uuid4())
        
        if not hasattr(app, 'poizon_tasks'):
            app.poizon_tasks = {}
        
        app.poizon_tasks[task_id] = {
            'product_codes': product_codes,
            'status': 'pending',
            'queue': queue.Queue()
        }
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'total_products': len(product_codes)
        })
        
    except Exception as e:
        print(f"❌ start_poizon_search 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/poizon_search_progress/<task_id>')
def poizon_search_progress(task_id):
    """포이즌 검색 진행 상황 SSE"""
    
    if not hasattr(app, 'poizon_tasks') or task_id not in app.poizon_tasks:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    task = app.poizon_tasks[task_id]
    product_codes = task['product_codes']
    progress_queue = task['queue']
    
    def run_background():
        try:
            from poizon_data import poizon_search
            poizon_search.search_multiple_products(product_codes, progress_queue)
        except Exception as e:
            print(f"❌ 백그라운드 검색 오류: {e}")
            import traceback
            traceback.print_exc()
            progress_queue.put({'event': 'error', 'data': {'error': str(e)}})
    
    thread = threading.Thread(target=run_background)
    thread.daemon = True
    thread.start()
    
    def generate():
        try:
            while True:
                try:
                    msg = progress_queue.get(timeout=30)
                    
                    event_type = msg.get('event', 'message')
                    event_data = msg.get('data', {})
                    
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    
                    if event_type in ['complete', 'error']:
                        if task_id in app.poizon_tasks:
                            del app.poizon_tasks[task_id]
                        break
                    
                except queue.Empty:
                    yield f"event: ping\ndata: {json.dumps({'status': 'alive'})}\n\n"
                    
        except Exception as e:
            print(f"❌ SSE 스트림 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )

@app.route('/download_excel', methods=['POST'])
def download_excel():
    """현재 테이블 그대로 엑셀 저장"""
    try:
        data = request.json
        mode = data.get('mode', 'poizon')
        keyword = data.get('keyword', '검색결과')
        collected_data = data.get('data', [])
        
        if not collected_data:
            return jsonify({'success': False, 'error': '데이터가 없습니다'})
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        mode_names = {
            'poizon': 'POIZON',
            'musinsa': '무신사',
            'compare': '리스트비교',
            'kream': '크림'
        }
        mode_name = mode_names.get(mode, 'DATA')
        
        safe_keyword = keyword.replace('/', '_').replace('\\', '_')[:30]
        filename = f"{mode_name}_{safe_keyword}_{timestamp}.xlsx"
        
        output_dir = os.path.join(os.getcwd(), 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "수집결과"
        
        if mode == 'compare':
            headers = [
                '#', '이미지', '상품번호', '제품명', '정가', '할인가', '재고',
                '크림평균가', '크림비교', '크림판매량',
                '중국노출가', '포이즌비교', '중국판매량', '현업자판매량'
            ]
        elif mode == 'poizon':
            headers = [
                '#', '이미지', '상품번호', '제품명', '평균거래가',
                '중국노출가', '중국판매량', '현업자판매량',
                '크림평균가', '크림비교'
            ]
        elif mode == 'musinsa':
            headers = [
                '#', '이미지', '상품번호', '제품명', '최대혜택가',
                '크림평균가', '크림비교', '크림판매량',
                '포이즌노출가', '포이즌비교', '중국판매량', '현업자판매량'
            ]
        else:
            headers = [
                '#', '이미지', '상품번호', '제품명', '평균거래가',
                '중국노출가', '판매량'
            ]
        
        ws.append(headers)
        
        header_fill = PatternFill(start_color="667eea", end_color="667eea", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=11)
        header_alignment = Alignment(horizontal="center", vertical="center")
        
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_num)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
        
        for idx, item in enumerate(collected_data, 1):
            if mode == 'compare':
                row = [
                    idx,
                    item.get('포이즌이미지URL', item.get('크림이미지URL', item.get('이미지URL', '-'))),
                    item.get('엑셀_상품번호', item.get('상품번호', '-')),
                    item.get('제품명', '-'),
                    item.get('엑셀_정가', '-'),
                    item.get('엑셀_할인가', '-'),
                    item.get('엑셀_재고', '-'),
                    item.get('크림평균가', '-'),
                    item.get('크림비교', '-'),
                    item.get('크림판매량', '-'),
                    item.get('포이즌노출가', item.get('중국노출', '-')),
                    item.get('포이즌비교', '-'),
                    item.get('포이즌중국판매량', 0),
                    item.get('포이즌현업자판매량', 0)
                ]
            elif mode == 'poizon':
                row = [
                    idx,
                    item.get('이미지URL', item.get('image_url', '-')),
                    item.get('상품번호', '-'),
                    item.get('제품명', '-'),
                    item.get('최근30일평균거래가', '-'),
                    item.get('중국노출', '-'),
                    item.get('중국시장최근30일판매량', 0),
                    item.get('현지판매자최근30일판매량', 0),
                    item.get('크림평균가', '-'),
                    item.get('크림비교', '-')
                ]
            elif mode == 'musinsa':
                row = [
                    idx,
                    item.get('이미지URL', item.get('image_url', '-')),
                    item.get('product_code', '-'),
                    item.get('name', '-'),
                    item.get('price', '-'),
                    item.get('크림평균가', '-'),
                    item.get('크림비교', '-'),
                    item.get('크림판매량', '-'),
                    item.get('포이즌노출가', '-'),
                    item.get('포이즌비교', '-'),
                    item.get('포이즌중국판매량', 0),
                    item.get('포이즌현업자판매량', 0)
                ]
            else:
                row = [
                    idx,
                    item.get('이미지URL', item.get('image_url', '-')),
                    item.get('상품번호', '-'),
                    item.get('제품명', '-'),
                    item.get('최근30일평균거래가', '-'),
                    item.get('중국노출', '-'),
                    item.get('중국시장최근30일판매량', 0)
                ]
            
            ws.append(row)
        
        column_widths = {
            '#': 8, '이미지': 50, '상품번호': 20, '제품명': 30,
            '정가': 15, '할인가': 15, '재고': 10,
            '평균거래가': 15, '최대혜택가': 15,
            '중국노출가': 15, '포이즌노출가': 15,
            '크림평균가': 15, '크림비교': 15, '포이즌비교': 15,
            '중국판매량': 15, '현업자판매량': 15, '크림판매량': 15, '판매량': 15
        }
        
        for col_num, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_num)
            width = column_widths.get(header, 15)
            ws.column_dimensions[col_letter].width = width
        
        image_col = headers.index('이미지') + 1 if '이미지' in headers else None
        
        if image_col:
            for row_num in range(2, len(collected_data) + 2):
                cell = ws.cell(row=row_num, column=image_col)
                url_value = cell.value
                
                if url_value and url_value != '-' and isinstance(url_value, str) and url_value.startswith('http'):
                    cell.hyperlink = url_value
                    cell.value = '🔗 이미지'
                    cell.font = Font(color="0563C1", underline="single")
        
        wb.save(filepath)

        if os.path.exists(filepath):
            print(f"✅ 파일 저장 성공: {filepath}")
        else:
            print(f"❌ 파일 저장 실패: {filepath}")
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': filepath,
            'count': len(collected_data)
        })
        
    except Exception as e:
        print(f"엑셀 다운로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/<filename>')
def download_file(filename):
    """파일 다운로드"""
    try:
        filepath = os.path.join(os.getcwd(), 'outputs', filename)
        
        if not os.path.exists(filepath):
            print(f"❌ 파일 없음: {filepath}")
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
        
        print(f"✅ 파일 전송: {filepath}")
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ 다운로드 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/search_wholesale_product', methods=['POST'])
def search_wholesale_product():
    """도매 오더폼 - 포이즌에서 단건 상품 검색 (이미지 + 품명)"""
    try:
        code = request.json.get('code', '').strip()
        if not code:
            return jsonify({'success': False, 'error': '품번 없음'})
        from poizon_data import poizon_search as ps
        result = ps.search_single_product(code)
        if result:
            return jsonify({'success': True, 'img_url': result.get('img_url', ''), 'name': result.get('name', '')})
        return jsonify({'success': False, 'error': '검색 결과 없음 (포이즌 쿠키 확인 필요)'})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/proxy_image')
def proxy_image():
    """외부 이미지 프록시 (CORS 우회용)"""
    import requests as req
    url = request.args.get('url', '')
    if not url:
        return '', 404
    try:
        r = req.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        return Response(r.content, content_type=r.headers.get('Content-Type', 'image/jpeg'))
    except Exception:
        return '', 404


# ✅ 서식 Blueprint 등록 (forms_data/forms_api.py)
try:
    import sys
    _forms_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'forms_data')
    if _forms_data_path not in sys.path:
        sys.path.insert(0, _forms_data_path)
    from forms_api import forms_bp
    app.register_blueprint(forms_bp)
    print("✅ 서식/양식 등록 성공")
except Exception as e:
    print(f"⚠️ 서식/양식 로드 실패: {e}")

# 구글 시트 자동 동기화 시작
try:
    from inventory_data.sheets_sync import sync_once, start_sync_background
    start_sync_background()
    print("✅ 구글 시트 자동 동기화 시작")
except Exception as e:
    print(f"⚠️ 시트 동기화 시작 실패: {e}")

# 텔레그램 명령어 폴링 시작
try:
    from utils.telegram import register_handler, start_polling, send_telegram_async
    import time as _time

    def _cmd_status(_):
        if is_working:
            elapsed = int(_time.time() - (work_start_time or _time.time()))
            m, s = elapsed // 60, elapsed % 60
            wt = {'scraping': '포이즌 검색', 'comparison': '리스트 비교', 'musinsa': '무신사 검색'}.get(work_type, work_type)
            return (f'🔄 <b>작업 중</b>: {wt}\n'
                    f'• 진행: {current_items} / {estimated_items}개\n'
                    f'• 경과: {m}분 {s}초')
        return '✅ 현재 대기 중 (작업 없음)'

    def _cmd_stop(_):
        global stop_flag
        if not is_working:
            return '⚠️ 현재 실행 중인 작업이 없습니다'
        stop_flag = True
        return '🛑 중지 신호를 보냈습니다'

    def _cmd_musinsa(args):
        global stop_flag
        if is_working:
            return '⚠️ 이미 작업 중입니다. /stop 으로 먼저 중지하세요'
        if not args:
            return '사용법: /musinsa [키워드] [개수]\n예) /musinsa 나이키 100\n\n무신사 → 크림 → 포이즌 순서로 자동 검색합니다'
        keyword = args[0]
        max_items = int(args[1]) if len(args) > 1 and args[1].isdigit() else 100
        t = threading.Thread(target=run_full_search, args=(keyword, max_items), daemon=True)
        t.start()
        return (f'🔍 <b>통합 검색 시작</b>\n'
                f'• 키워드: {keyword}\n'
                f'• 최대: {max_items}개\n'
                f'• 순서: 무신사 → 크림 → 포이즌\n'
                f'각 단계 완료 시 알림을 보내드립니다')

    def _cmd_ranking(args):
        if is_working:
            return '⚠️ 이미 작업 중입니다. /stop 으로 먼저 중지하세요'
        max_items = int(args[0]) if args and args[0].isdigit() else 100
        t = threading.Thread(target=run_musinsa_search, args=('', max_items, 'ranking'), daemon=True)
        t.start()
        return (f'📊 <b>무신사 랭킹 검색 시작</b>\n'
                f'• 최대: {max_items}개\n'
                f'• 완료 시 알림을 보내드립니다')

    def _cmd_sync(_):
        def _do():
            from inventory_data.sheets_sync import sync_once
            count = sync_once()
            send_telegram_async(f'✅ 구글 시트 동기화 완료: {count}건')
        threading.Thread(target=_do, daemon=True).start()
        return '🔄 구글 시트 동기화를 시작합니다...'

    def _cmd_deploy(args):
        """GitHub에서 최신 코드 pull 후 서버 재시작. /deploy force 시 강제 덮어쓰기"""
        import subprocess
        force = len(args) > 0 and args[0].lower() == 'force'

        def _do():
            try:
                repo_dir = os.path.dirname(os.path.abspath(__file__))

                if force:
                    # 강제: 로컬 변경사항 무시하고 원격 최신으로 덮어쓰기
                    cmds = [
                        ['git', 'fetch', 'origin'],
                        ['git', 'reset', '--hard', 'origin/main'],
                        ['git', 'clean', '-fd'],
                    ]
                    outputs = []
                    for cmd in cmds:
                        r = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=60)
                        outputs.append((r.stdout + r.stderr).strip())
                    output = '\n'.join(o for o in outputs if o)
                    send_telegram_async(f'⚠️ <b>강제 업데이트 완료</b>\n<code>{output}</code>\n\n🔄 서버 재시작 중...')
                else:
                    # 일반 pull
                    result = subprocess.run(
                        ['git', 'pull', 'origin', 'main'],
                        cwd=repo_dir, capture_output=True, text=True, timeout=60
                    )
                    output = result.stdout.strip() or result.stderr.strip()
                    if result.returncode != 0:
                        send_telegram_async(
                            f'❌ pull 실패:\n<code>{output}</code>\n\n'
                            f'강제 업데이트: /deploy force'
                        )
                        return
                    send_telegram_async(f'📦 <b>Git Pull 완료</b>\n<code>{output}</code>\n\n🔄 서버 재시작 중...')

                _time.sleep(2)
                os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                send_telegram_async(f'❌ 배포 실패: {e}')

        threading.Thread(target=_do, daemon=True).start()
        mode = '⚠️ 강제 업데이트' if force else '🚀 일반 업데이트'
        return f'{mode} 시작... GitHub에서 최신 코드를 받아옵니다.'

    def _cmd_help(_):
        return ('📋 <b>사용 가능한 명령어</b>\n\n'
                '/status — 현재 작업 상태 확인\n'
                '/stop — 진행 중인 작업 중지\n'
                '/musinsa [키워드] [개수]\n'
                '  → 무신사 → 크림 → 포이즌 순서로 자동 검색\n'
                '  예) /musinsa 나이키 100\n'
                '/ranking [개수]\n'
                '  → 무신사 랭킹 TOP N 수집\n'
                '  예) /ranking 100\n'
                '/sync — 구글 시트 강제 동기화\n'
                '/deploy — GitHub 최신 코드 받아서 서버 재시작\n'
                '/deploy force — 충돌 무시하고 강제 업데이트\n'
                '/help — 도움말')

    register_handler('/status',  _cmd_status)
    register_handler('/stop',    _cmd_stop)
    register_handler('/musinsa', _cmd_musinsa)
    register_handler('/ranking', _cmd_ranking)
    register_handler('/sync',    _cmd_sync)
    register_handler('/deploy',  _cmd_deploy)
    register_handler('/help',    _cmd_help)
    register_handler('/start',   _cmd_help)

    start_polling()
    print('✅ 텔레그램 명령어 폴링 시작')
except Exception as e:
    print(f'⚠️ 텔레그램 폴링 시작 실패: {e}')

# ==========================================
# 서버 시작
# ==========================================

if __name__ == '__main__':
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=3001,
        use_reloader=False  # ← 재시작 시 포트 충돌 방지
    )