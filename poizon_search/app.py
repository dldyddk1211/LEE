from flask import (
    Flask,
    render_template,
    request,
    Response,
    send_file,
    jsonify,
    render_template_string,
    stream_with_context
)
import json
import os
import threading
import queue
import openpyxl
import uuid
import time
from datetime import datetime
import uuid
import queue
import threading
from flask import stream_with_context

# 전역 변수
kream_search_tasks = {}
kream_search = None
musinsa_search = None  # ✅ 전역 변수 추가


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
            data_str = message[5:]
            item_data = json.loads(data_str)
            log_queue.put({
                'type': 'data',
                'item': item_data
            })
        except:
            pass
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

def run_musinsa_search(keyword, max_items):
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
    
    # ✅ max_items 처리
    if max_items == 'max':
        estimated_items = 1000  # 임시 추정값
    else:
        try:
            estimated_items = int(max_items)
        except:
            estimated_items = 10
    
    current_items = 0
    stop_flag = False
    
    try:
        # ✅ max_items를 그대로 전달 (문자열 'max' 또는 숫자)
        result = musinsa_search.search_musinsa_keyword_detail(
            keyword=keyword,
            max_items=max_items,  # ✅ 'max' 또는 숫자 그대로 전달
            callback=log_callback
        )
        
        print(f"\n{'='*60}")
        print(f"✅ run_musinsa_search 완료")
        print(f"  성공: {result.get('success')}")
        print(f"  수집 개수: {result.get('total_items', 0)}")
        print(f"{'='*60}\n")
        
        if result.get('success'):
            # ✅ 스케줄러에 저장
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
            
            # 검색 완료 메시지
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
    print(f"  max_pages: {max_pages}")
    print(f"  max_items: {max_items} (타입: {type(max_items)})")
    print(f"{'='*60}\n")
    
    # mode 처리
    if mode == 'keyword':
        mode = 'poizon'
    
    # 큐 비우기
    while not log_queue.empty():
        log_queue.get()
    
    # 모드별 처리
    if mode == 'poizon':
        # POIZON 검색 (max_pages 사용)
        thread = threading.Thread(target=run_scraper, args=(keyword, max_pages, skip_login))
        thread.daemon = True
        thread.start()
        
    elif mode == 'musinsa':
        # ✅ 무신사 검색 (max_items 사용)
        thread = threading.Thread(target=run_musinsa_search, args=(keyword, max_items))
        thread.daemon = True
        thread.start()
        
    elif mode == 'kream':
        log_queue.put({'type': 'error', 'message': '🛒 크림 검색 기능은 준비 중입니다'})
        
    else:
        # 기본: POIZON
        thread = threading.Thread(target=run_scraper, args=(keyword, max_pages, skip_login))
        thread.daemon = True
        thread.start()
    
    def generate():
        while True:
            try:
                data = log_queue.get(timeout=1)
                
                # ✅ complete 이벤트일 때 mode 정보 추가!
                if data.get('type') == 'complete':
                    data['mode'] = mode  # ⬅️ 이 줄 추가!
                
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                
                if data.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        
    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
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
        return jsonify({'success': True}), 200  # ⬅️ 핵심!

@app.route('/shutdown_browser')
def shutdown_browser():
    try:
        from poizon_data.poizon_search import close_browser_session
        close_browser_session()
        return jsonify({'success': True, 'message': 'POIZON 브라우저 종료 완료'}), 200
    except Exception as e:
        print(f"⚠️ POIZON 브라우저 종료 중 오류 (무시): {e}")
        return jsonify({'success': True, 'message': '이미 종료됨 또는 오류 무시'}), 200  # ✅ 200 반환!

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
    
    # 세션 ID가 있으면 자동 검색
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
        
        # Task ID 생성
        task_id = str(uuid.uuid4())
        
        # 글로벌 딕셔너리에 작업 등록
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
    



# /stop_kream_search 함수 바로 아래에 추가:
@app.route('/kream_search_progress/<task_id>')
def kream_search_progress(task_id):
    """크림 검색 진행 상황 SSE"""
    
    if not hasattr(app, 'kream_tasks') or task_id not in app.kream_tasks:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    task = app.kream_tasks[task_id]
    product_codes = task['product_codes']
    
    # ✅ 진행 상황 큐 생성
    progress_queue = queue.Queue()
    
    # ✅ 백그라운드 스레드 시작
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
    
    # ✅ SSE 스트림
    def generate():
        try:
            while True:
                try:
                    # 큐에서 메시지 가져오기 (30초 타임아웃)
                    msg = progress_queue.get(timeout=30)
                    
                    event_type = msg.get('event', 'message')
                    event_data = msg.get('data', {})
                    
                    # SSE 형식으로 전송
                    yield f"event: {event_type}\ndata: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                    
                    # 완료 또는 에러 시 종료
                    if event_type in ['complete', 'error']:
                        # Task 삭제
                        if task_id in app.kream_tasks:
                            del app.kream_tasks[task_id]
                        break
                    
                except queue.Empty:
                    # 타임아웃 시 핑 전송
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
        return jsonify({'success': True}), 200  # ⬅️ 핵심!


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
        
        # Task ID 생성
        task_id = str(uuid.uuid4())
        
        # 글로벌 딕셔너리에 작업 등록
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
    
    # 백그라운드 스레드 시작
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
    
    # SSE 스트림
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



# 구글 시트 자동 동기화 시작
try:
    from inventory_data.sheets_sync import sync_once, start_sync_background
    start_sync_background()
    print("✅ 구글 시트 자동 동기화 시작")
except Exception as e:
    print(f"⚠️ 시트 동기화 시작 실패: {e}")

# ==========================================
# 서버 시작
# ==========================================

if __name__ == '__main__':
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=3001,
        use_reloader=False  # ← 이게 핵심! 재시작 시 포트 충돌 방지
    )