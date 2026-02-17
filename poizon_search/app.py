from flask import Flask, render_template, request, Response, send_file, jsonify, render_template_string
import json
import os
import threading
import queue
import openpyxl
import uuid

# 크림 검색 모듈 import
kream_search = None

# 여러 경로 시도
try:
    # 방법 1: kream_data 패키지에서 import
    from kream_data import kream_search
    print("✅ kream_search 모듈 로드 성공 (kream_data)")
except ImportError:
    try:
        # 방법 2: kream_data.kream_search 직접 import
        import kream_data.kream_search as kream_search
        print("✅ kream_search 모듈 로드 성공 (kream_data.kream_search)")
    except ImportError:
        try:
            # 방법 3: 현재 폴더에서 import
            import kream_search
            print("✅ kream_search 모듈 로드 성공 (현재 폴더)")
        except ImportError:
            try:
                # 방법 4: sys.path에 kream_data 추가 후 import
                import sys
                kream_data_path = os.path.join(os.path.dirname(__file__), 'kream_data')
                if os.path.exists(kream_data_path) and kream_data_path not in sys.path:
                    sys.path.insert(0, kream_data_path)
                import kream_search
                print("✅ kream_search 모듈 로드 성공 (sys.path 추가)")
            except ImportError:
                print("⚠️ 경고: kream_search 모듈을 찾을 수 없습니다.")
                print("   다음 위치에 kream_search.py 파일이 있는지 확인하세요:")
                print("   1. kream_data/kream_search.py")
                print("   2. kream_search.py (프로젝트 루트)")
                kream_search = None

app = Flask(__name__)

log_queue = queue.Queue()
result_data = {}
stop_flag = False  # 중단 플래그
current_browser = None  # 현재 실행 중인 브라우저

# 작업 상태 관리
is_working = False
work_start_time = None
work_type = None  # 'scraping' or 'comparison'
estimated_items = 0  # 예상 작업 수
current_items = 0  # 현재 처리된 수
stop_requested = False  # 중단 요청 플래그

def log_callback(message, level='info'):
    """poizon_search에서 호출하는 콜백"""
    global current_items
    
    if message.startswith("PROGRESS:"):
        parts = message.split(":")
        if len(parts) == 2:
            current, total = parts[1].split("/")
            current_items = int(current)  # 현재 진행 상황 업데이트
            log_queue.put({
                'type': 'progress',
                'current': int(current),
                'total': int(total)
            })
    elif message.startswith("PRODUCT_START:"):
        product_code = message.split(":", 1)[1]
        log_queue.put({
            'type': 'product_start',
            'product_code': product_code
        })
    elif message.startswith("PRODUCT_RESULT:"):
        print(f"[DEBUG] PRODUCT_RESULT 받음!")  # 터미널 출력
        try:
            json_str = message.split(":", 1)[1]
            print(f"[DEBUG] JSON 길이: {len(json_str)}")
            
            data = json.loads(json_str)
            print(f"[DEBUG] JSON 파싱 성공!")
            print(f"[DEBUG] product_code: {data.get('product_code')}")
            print(f"[DEBUG] products 개수: {len(data.get('products', []))}")
            
            log_queue.put({
                'type': 'product_result',
                'product_code': data['product_code'],
                'products': data['products']
            })
            print(f"[DEBUG] log_queue에 전송 완료!")
        except Exception as e:
            print(f"[DEBUG] PRODUCT_RESULT 처리 오류: {e}")
            import traceback
            traceback.print_exc()
    elif message.startswith("DATA:"):
        try:
            import json as json_module
            data_str = message[5:]
            item_data = json_module.loads(data_str)
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

def run_scraper(keyword, max_pages, skip_login=False):
    """백그라운드에서 스크래핑 실행"""
    global result_data, stop_flag, is_working, work_start_time, work_type, estimated_items, current_items
    
    # 작업 시작
    is_working = True
    import time
    work_start_time = time.time()
    work_type = 'scraping'
    estimated_items = max_pages  # 페이지 수
    current_items = 0
    stop_flag = False  # 시작 시 플래그 초기화
    
    try:
        from poizon_data.poizon_search import run_poizon_from_gui
        
        result = run_poizon_from_gui(
            keyword=keyword,
            max_pages=max_pages,
            callback=log_callback,
            skip_login=skip_login
        )
        
        if result.get('success'):
            log_queue.put({
                'type': 'complete',
                'total_items': result.get('total_items', 0),
                'pages': result.get('pages', 0),
                'file_path': result.get('file_path', '')
            })
            result_data['file_path'] = result.get('file_path', '')
        else:
            log_queue.put({
                'type': 'error',
                'message': result.get('error', '알 수 없는 오류')
            })
    except Exception as e:
        if not stop_flag:  # 중단이 아닌 실제 오류만 표시
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    finally:
        # 작업 완료
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0

@app.route('/check_status')
def check_status():
    """현재 작업 상태 확인"""
    global is_working, work_start_time, work_type, estimated_items, current_items
    
    if not is_working:
        return jsonify({
            'working': False,
            'message': '서버 사용 가능'
        })
    
    # 작업 시작 후 경과 시간 (초)
    import time
    elapsed_seconds = int(time.time() - work_start_time) if work_start_time else 0
    
    # 평균 처리 속도 계산 (초/건)
    avg_time_per_item = 0
    remaining_minutes = 0
    
    if current_items > 0:
        avg_time_per_item = elapsed_seconds / current_items
        remaining_items = max(0, estimated_items - current_items)
        remaining_seconds = int(avg_time_per_item * remaining_items)
        remaining_minutes = max(1, remaining_seconds // 60)  # 최소 1분
    else:
        # 아직 처리된 항목이 없으면 추정치
        if work_type == 'scraping':
            remaining_minutes = max(1, estimated_items // 5)  # 페이지당 ~12초 가정
        else:  # comparison
            remaining_minutes = max(1, estimated_items // 3)  # 건당 ~20초 가정
    
    work_type_kr = '수집' if work_type == 'scraping' else '비교'
    
    return jsonify({
        'working': True,
        'message': f'서버 작업 중 ({work_type_kr})',
        'work_type': work_type,
        'progress': f'{current_items}/{estimated_items}',
        'elapsed_minutes': elapsed_seconds // 60,
        'remaining_minutes': remaining_minutes
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check_login')
def check_login():
    """실제 브라우저로 로그인 수행"""
    try:
        from poizon_data.poizon_search import perform_login
        
        result = perform_login()
        
        return jsonify({
            'logged_in': result.get('success', False),
            'message': result.get('message', '')
        })
    except Exception as e:
        return jsonify({
            'logged_in': False,
            'message': str(e)
        }), 500

@app.route('/start')
def start():
    keyword = request.args.get('keyword', '나이키')
    max_pages = int(request.args.get('max_pages', 20))
    skip_login = request.args.get('skip_login', 'false').lower() == 'true'
    
    while not log_queue.empty():
        log_queue.get()
    
    thread = threading.Thread(target=run_scraper, args=(keyword, max_pages, skip_login))
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

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    """엑셀 파일 업로드 및 파싱"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '파일이 없습니다'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다'})
        
        # 엑셀 파일 읽기 (수식이 아닌 표시 값 가져오기)
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
        
        products = []
        print(f"📋 엑셀 파일 파싱 시작...")
        
        # 헤더 확인 (디버깅용)
        header_row = list(next(ws.iter_rows(min_row=1, max_row=1, values_only=True)))
        print(f"  📋 헤더: {header_row}")
        
        # 상품번호가 어느 컬럼에 있는지 찾기
        code_col_idx = 0
        for i, header in enumerate(header_row):
            if header and '상품' in str(header):
                code_col_idx = i
                print(f"  ✅ '상품번호' 컬럼 위치: {code_col_idx}번째")
                break
        
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            if not any(row):  # 빈 행 스킵
                continue
            
            # 디버깅: 처음 3개 행만 전체 출력
            if idx <= 4:
                print(f"\n  Row {idx}: {row}")
            
            # 상품번호 컬럼 기준으로 읽기
            product_code = str(row[code_col_idx]).strip() if len(row) > code_col_idx and row[code_col_idx] else ''
            product_name = str(row[code_col_idx + 1]).strip() if len(row) > code_col_idx + 1 and row[code_col_idx + 1] else ''
            original_price_val = row[code_col_idx + 2] if len(row) > code_col_idx + 2 else None
            sale_price_val = row[code_col_idx + 3] if len(row) > code_col_idx + 3 else None
            stock_val = row[code_col_idx + 4] if len(row) > code_col_idx + 4 else None
            
            if idx <= 4:
                print(f"    상품번호: {product_code}")
                print(f"    제품명: {product_name}")
                print(f"    정가: {original_price_val} (type: {type(original_price_val).__name__})")
                print(f"    할인가: {sale_price_val} (type: {type(sale_price_val).__name__})")
                print(f"    수량: {stock_val}")
            
            # 숫자 추출
            import re
            
            def safe_int(val):
                if val is None or val == '':
                    return 0
                if isinstance(val, (int, float)):
                    return int(val)
                val_str = str(val).strip()
                if not val_str:
                    return 0
                nums = re.sub(r'[^\d]', '', val_str)
                return int(nums) if nums else 0
            
            original_price_num = safe_int(original_price_val)
            sale_price_num = safe_int(sale_price_val)
            stock_num = safe_int(stock_val)
            
            if idx <= 4:
                print(f"    → 파싱 결과: 정가={original_price_num}, 할인가={sale_price_num}, 재고={stock_num}")
            
            if product_code or product_name:
                products.append({
                    'code': product_code,
                    'name': product_name,
                    'original_price': original_price_num,
                    'sale_price': sale_price_num,
                    'stock': stock_num
                })
        
        return jsonify({
            'success': True,
            'count': len(products),
            'products': products
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def run_comparison(products):
    """백그라운드에서 가격 비교 실행"""
    global result_data, stop_flag, current_browser, is_working, work_start_time, work_type, estimated_items, current_items
    
    # 작업 시작
    is_working = True
    import time
    work_start_time = time.time()
    work_type = 'comparison'
    estimated_items = len(products)  # 상품 수
    current_items = 0
    stop_flag = False  # 시작 시 플래그 초기화
    
    try:
        from poizon_data.poizon_search import run_excel_comparison
        
        # 브라우저 참조 저장을 위해 수정된 버전 필요
        result = run_excel_comparison(products, callback=log_callback)
        
        if result.get('success'):
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
        if not stop_flag:  # 중단이 아닌 실제 오류만 표시
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    finally:
        current_browser = None  # 작업 완료 후 참조 제거
        # 작업 완료
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0

@app.route('/compare_prices', methods=['POST'])
def compare_prices():
    """엑셀 리스트와 포이즌 가격 비교"""
    products = request.json.get('products', [])
    
    # 큐 초기화
    while not log_queue.empty():
        log_queue.get()
    
    # 백그라운드 스레드 시작
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
    """엑셀 파일 다운로드"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), 'poizon_data', 'output_data', filename)
        
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=filename
            )
        else:
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/shutdown_browser')
def shutdown_browser():
    """5분 타임아웃 시 브라우저 종료"""
    try:
        from poizon_data.poizon_search import close_browser_session
        close_browser_session()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop():
    """작업 중단"""
    global stop_flag, current_browser
    
    stop_flag = True
    
    # poizon_search.py의 stop_flag도 설정
    try:
        from poizon_data import poizon_search
        poizon_search.stop_flag = True
        log_queue.put({
            'type': 'log',
            'message': '⏹️ 중단 요청 전송 완료',
            'level': 'warning'
        })
    except Exception as e:
        log_queue.put({
            'type': 'log',
            'message': f'⚠️ 중단 요청 중 오류: {e}',
            'level': 'error'
        })
    
    # 브라우저 강제 종료 시도
    if current_browser:
        try:
            current_browser.close()
            log_queue.put({
                'type': 'log',
                'message': '✅ 브라우저 종료 완료',
                'level': 'info'
            })
        except:
            pass
        current_browser = None
    
    return jsonify({'success': True})


# ==========================================
# ✨ 구매처 검색 - 팝업 버전 (NEW!)
# ==========================================

@app.route('/start_sourcing', methods=['POST'])
def start_sourcing():
    """구매처 검색 시작 - 팝업 창 열기"""
    product_codes = request.json.get('product_codes', [])
    
    if not product_codes:
        return jsonify({'success': False, 'error': '상품번호가 없습니다'})
    
    # 세션 ID 생성
    session_id = str(uuid.uuid4())
    
    # 세션 데이터 저장
    if not hasattr(app, 'sourcing_sessions'):
        app.sourcing_sessions = {}
    
    app.sourcing_sessions[session_id] = {
        'product_codes': product_codes,
        'status': 'pending'
    }
    
    return jsonify({
        'success': True,
        'session_id': session_id,
        'popup_url': f'/sourcing_results/{session_id}'
    })


@app.route('/sourcing_results/<session_id>')
def sourcing_results(session_id):
    """구매처 검색 결과 팝업 페이지"""
    if not hasattr(app, 'sourcing_sessions') or session_id not in app.sourcing_sessions:
        return "세션을 찾을 수 없습니다", 404
    
    # templates 폴더의 HTML 파일 시도
    html_path = os.path.join(os.path.dirname(__file__), 'templates', 'sourcing_results.html')
    
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        # session_id를 JavaScript에 전달
        html = html.replace('"/start_sourcing_stream"', f'"/start_sourcing_stream/{session_id}"')
        return html
    else:
        # 인라인 HTML 사용
        return render_template_string(SOURCING_RESULTS_HTML, session_id=session_id)


@app.route('/start_sourcing_stream/<session_id>')
def start_sourcing_stream(session_id):
    """구매처 검색 SSE 스트림"""
    if not hasattr(app, 'sourcing_sessions') or session_id not in app.sourcing_sessions:
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': '세션을 찾을 수 없습니다'}, ensure_ascii=False)}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    product_codes = app.sourcing_sessions[session_id]['product_codes']
    
    def generate():
        # 큐 초기화
        while not log_queue.empty():
            log_queue.get()
        
        # 백그라운드 스레드 시작
        thread = threading.Thread(target=run_sourcing_background_stream, args=(product_codes, session_id))
        thread.daemon = True
        thread.start()
        
        # SSE 스트림
        while True:
            try:
                msg = log_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                
                if msg.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

def run_sourcing_background_stream(product_codes, session_id):
    """백그라운드에서 구매처 검색 실행 (스트림 버전)"""
    global is_working, work_start_time, work_type, estimated_items, current_items, stop_flag
    
    print(f"\n{'='*60}")
    print(f"DEBUG: run_sourcing_background_stream 시작!")
    print(f"DEBUG: product_codes 개수 = {len(product_codes)}")
    print(f"DEBUG: session_id = {session_id}")
    print(f"{'='*60}\n")
    
    is_working = True
    import time
    work_start_time = time.time()
    work_type = 'sourcing'
    estimated_items = len(product_codes)
    current_items = 0
    stop_flag = False
    
    try:
        print("DEBUG: sourcing_search 모듈 import 시도...")
        from poizon_data.sourcing_search import run_sourcing_for_products
        print("DEBUG: import 성공!")
        
        print("DEBUG: run_sourcing_for_products 호출 시작...")
        result = run_sourcing_for_products(product_codes, callback=log_callback)
        print(f"DEBUG: 함수 완료! result = {result}")
        
        if result.get('success'):
            log_queue.put({
                'type': 'complete',
                'total_searched': result.get('total_searched', 0),
                'message': '구매처 검색 완료'
            })
        else:
            log_queue.put({
                'type': 'error',
                'message': result.get('error', '알 수 없는 오류')
            })
    
    except Exception as e:
        print(f"DEBUG: 예외 발생! {e}")
        import traceback
        traceback.print_exc()
        
        if not stop_flag:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
    
    finally:
        print("DEBUG: finally 블록 실행")
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0
        
        # 세션 정리
        if hasattr(app, 'sourcing_sessions') and session_id in app.sourcing_sessions:
            app.sourcing_sessions[session_id]['status'] = 'completed'
        
        print("DEBUG: run_sourcing_background_stream 종료\n")

@app.route('/stop_sourcing', methods=['POST'])
def stop_sourcing():
    """구매처 검색 중단"""
    global stop_requested
    stop_requested = True
    return jsonify({'success': True, 'message': '중단 요청되었습니다'})


# ==========================================
# 팝업 HTML 템플릿 (templates 폴더 없을 때 사용)
# ==========================================
SOURCING_RESULTS_HTML = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>구매처 검색 결과</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 { font-size: 32px; margin-bottom: 10px; }
        .status {
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 3px solid #667eea;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
        }
        .status-searching { background: #ffc107; color: #000; }
        .status-complete { background: #28a745; color: white; }
        .status-error { background: #dc3545; color: white; }
        .progress-container {
            padding: 20px 30px;
            background: #fff;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            position: relative;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }
        .results-container { padding: 30px; }
        .product-card {
            background: white;
            border: 2px solid #e9ecef;
            border-radius: 15px;
            margin-bottom: 20px;
            overflow: hidden;
            transition: all 0.3s ease;
            animation: slideIn 0.5s ease;
        }
        .product-card:hover {
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transform: translateY(-5px);
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .product-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .product-code { font-size: 20px; font-weight: bold; }
        .product-status {
            padding: 5px 15px;
            border-radius: 15px;
            background: rgba(255,255,255,0.2);
            font-size: 14px;
        }
        .product-items { padding: 20px; }
        .item-row {
            display: grid;
            grid-template-columns: 80px 150px 1fr 120px 100px 150px;
            gap: 15px;
            padding: 15px;
            border-bottom: 1px solid #e9ecef;
            align-items: center;
        }
        .item-row:last-child { border-bottom: none; }
        .item-row:hover { background: #f8f9fa; }
        .item-image {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 8px;
            border: 2px solid #e9ecef;
        }
        .item-mall { font-weight: bold; color: #667eea; }
        .item-name { color: #333; line-height: 1.4; }
        .item-price { font-size: 18px; font-weight: bold; color: #dc3545; }
        .item-shipping { color: #28a745; font-size: 14px; }
        .item-link {
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-size: 14px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .item-link:hover {
            background: #764ba2;
            transform: scale(1.05);
        }
        .no-results {
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-size: 16px;
        }
        .loading-spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        .log-container {
            padding: 20px 30px;
            background: #f8f9fa;
            max-height: 200px;
            overflow-y: auto;
            border-top: 3px solid #667eea;
        }
        .log-item {
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 5px;
            font-size: 13px;
            font-family: 'Courier New', monospace;
        }
        .log-info { background: #d1ecf1; color: #0c5460; }
        .log-success { background: #d4edda; color: #155724; }
        .log-warning { background: #fff3cd; color: #856404; }
        .log-error { background: #f8d7da; color: #721c24; }
        .footer {
            padding: 20px 30px;
            text-align: center;
            background: #f8f9fa;
            color: #6c757d;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛒 구매처 검색 결과</h1>
            <p>네이버 쇼핑 실시간 검색</p>
        </div>

        <div class="status">
            <div class="status-item">
                <span>상태:</span>
                <span class="status-badge status-searching" id="statusBadge">
                    <span class="loading-spinner"></span> 검색 중...
                </span>
            </div>
            <div class="status-item">
                <span>진행:</span>
                <strong id="progressText">0/0</strong>
            </div>
            <div class="status-item">
                <span>검색 시작:</span>
                <strong id="startTime">-</strong>
            </div>
        </div>

        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill" style="width: 0%">0%</div>
            </div>
        </div>

        <div class="results-container" id="resultsContainer">
            <div class="no-results">
                <p>🔍 검색을 시작합니다...</p>
            </div>
        </div>

        <div class="log-container" id="logContainer">
            <div class="log-item log-info">시스템 준비 완료</div>
        </div>

        <div class="footer">
            © 2026 POIZON 구매처 검색 시스템
        </div>
    </div>

    <script>
        const eventSource = new EventSource('/start_sourcing_stream/{{ session_id }}');
        const resultsContainer = document.getElementById('resultsContainer');
        const logContainer = document.getElementById('logContainer');
        const statusBadge = document.getElementById('statusBadge');
        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');
        const startTime = document.getElementById('startTime');

        startTime.textContent = new Date().toLocaleTimeString('ko-KR');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.type === 'log') {
                addLog(data.message, data.level || 'info');
            }
            else if (data.type === 'progress') {
                updateProgress(data.current, data.total);
            }
            else if (data.type === 'product_start') {
                addProductCard(data.product_code);
            }
            else if (data.type === 'product_result') {
                updateProductCard(data.product_code, data.products);
            }
            else if (data.type === 'complete') {
                completeSearch();
            }
            else if (data.type === 'error') {
                showError(data.message);
            }
        };

        function addLog(message, level) {
            const logItem = document.createElement('div');
            logItem.className = `log-item log-${level}`;
            logItem.textContent = `[${new Date().toLocaleTimeString('ko-KR')}] ${message}`;
            logContainer.appendChild(logItem);
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function updateProgress(current, total) {
            const percentage = Math.round((current / total) * 100);
            progressText.textContent = `${current}/${total}`;
            progressFill.style.width = `${percentage}%`;
            progressFill.textContent = `${percentage}%`;
        }

        function addProductCard(productCode) {
            if (resultsContainer.querySelector('.no-results')) {
                resultsContainer.innerHTML = '';
            }

            const card = document.createElement('div');
            card.className = 'product-card';
            card.id = `product-${productCode}`;
            card.innerHTML = `
                <div class="product-header">
                    <span class="product-code">${productCode}</span>
                    <span class="product-status">
                        <span class="loading-spinner"></span> 검색 중...
                    </span>
                </div>
                <div class="product-items">
                    <div class="no-results">
                        <p>🔍 상품 정보를 검색하고 있습니다...</p>
                    </div>
                </div>
            `;
            resultsContainer.appendChild(card);
        }

        function updateProductCard(productCode, products) {
            const card = document.getElementById(`product-${productCode}`);
            if (!card) return;

            const header = card.querySelector('.product-header');
            const itemsContainer = card.querySelector('.product-items');

            if (products && products.length > 0) {
                header.querySelector('.product-status').innerHTML = `✅ ${products.length}개 발견`;
                
                itemsContainer.innerHTML = products.map(product => `
                    <div class="item-row">
                        <img src="${product.image_url || ''}" 
                             alt="상품 이미지" 
                             class="item-image"
                             onerror="this.style.display='none'">
                        <div class="item-mall">${product.mall || '알 수 없음'}</div>
                        <div class="item-name">${product.name || '상품명 없음'}</div>
                        <div class="item-price">${product.price || '-'}원</div>
                        <div class="item-shipping">${product.shipping || '무료배송'}</div>
                        <a href="${product.link}" target="_blank" class="item-link">
                            상세보기 →
                        </a>
                    </div>
                `).join('');
            } else {
                header.querySelector('.product-status').innerHTML = '❌ 결과 없음';
                itemsContainer.innerHTML = `
                    <div class="no-results">
                        <p>😢 검색 결과가 없습니다</p>
                    </div>
                `;
            }
        }

        function completeSearch() {
            statusBadge.className = 'status-badge status-complete';
            statusBadge.innerHTML = '✅ 검색 완료';
            addLog('모든 상품 검색이 완료되었습니다!', 'success');
            eventSource.close();
        }

        function showError(message) {
            statusBadge.className = 'status-badge status-error';
            statusBadge.innerHTML = '❌ 오류 발생';
            addLog(`오류: ${message}`, 'error');
            eventSource.close();
        }

        eventSource.onerror = function() {
            if (statusBadge.className.includes('status-searching')) {
                showError('서버 연결이 끊어졌습니다');
            }
        };
    </script>
</body>
</html> test 26-02-17
'''


# ==========================================
# 크림(KREAM) 검색 HTML 템플릿
# ==========================================

# 크림 팝업 HTML (수집 데이터 표시)
KREAM_POPUP_HTML = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>크림(KREAM) 검색</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 30px;
            max-width: 1600px;
            margin: 0 auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
        }
        .header h1 {
            font-size: 2em;
            color: #333;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 1.1em;
        }
        .controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 15px 20px;
            background: #f8f9fa;
            border-radius: 12px;
        }
        .controls .count {
            font-size: 1.1em;
            font-weight: 600;
            color: #333;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.3);
        }
        .table-container {
            max-height: 700px;
            overflow: auto;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            background: white;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            min-width: 1200px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }
        th {
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .product-img {
            width: 60px;
            height: 60px;
            object-fit: contain;
            border-radius: 6px;
            background: #f8f9fa;
            padding: 3px;
        }
        .kream-btn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.3s;
        }
        .kream-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 3px 12px rgba(245, 87, 108, 0.35);
        }
        .status {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        .status-pending {
            background: #fff3cd;
            color: #856404;
        }
        .status-searching {
            background: #d1ecf1;
            color: #0c5460;
        }
        .status-done {
            background: #d4edda;
            color: #155724;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛒 크림(KREAM) 검색</h1>
            <p>포이즌에서 수집한 상품을 크림에서 검색합니다</p>
        </div>

        <div class="controls">
            <div class="count">
                총 <strong id="totalCount">0</strong>개 상품
            </div>
            <button class="btn btn-primary" onclick="startKreamSearch()">
                🔍 크림 검색 시작
            </button>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th style="width: 50px;">#</th>
                        <th style="width: 80px;">이미지</th>
                        <th style="width: 100px;">크림</th>
                        <th style="width: 150px;">상품번호</th>
                        <th>제품명</th>
                        <th style="width: 120px;">평균거래가</th>
                        <th style="width: 120px;">중국노출가</th>
                        <th style="width: 100px;">판매량</th>
                        <th style="width: 100px;">상태</th>
                    </tr>
                </thead>
                <tbody id="productTableBody">
                    <tr>
                        <td colspan="9" style="text-align: center; padding: 40px; color: #999;">
                            데이터를 불러오는 중...
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let collectedData = [];

        // sessionStorage에서 데이터 읽기
        window.addEventListener('load', function() {
            const dataStr = sessionStorage.getItem('kreamSearchData');
            if (dataStr) {
                try {
                    collectedData = JSON.parse(dataStr);
                    displayProducts(collectedData);
                } catch (e) {
                    console.error('데이터 파싱 오류:', e);
                }
            }
        });

        function displayProducts(data) {
            const tbody = document.getElementById('productTableBody');
            const totalCount = document.getElementById('totalCount');
            
            totalCount.textContent = data.length;
            
            if (data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; padding: 40px; color: #999;">
                            표시할 상품이 없습니다
                        </td>
                    </tr>
                `;
                return;
            }
            
            tbody.innerHTML = data.map((item, index) => `
                <tr id="row-${index}">
                    <td>${index + 1}</td>
                    <td>
                        ${item.이미지URL ? 
                            `<img src="${item.이미지URL}" class="product-img" onerror="this.style.display='none'">` : 
                            '-'}
                    </td>
                    <td>
                        <button class="kream-btn" onclick="searchKream('${item.상품번호}', ${index})" id="btn-${index}">
                            🔍 검색
                        </button>
                    </td>
                    <td>${item.상품번호 || '-'}</td>
                    <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;" title="${item.제품명 || '-'}">
                        ${item.제품명 || '-'}
                    </td>
                    <td>${item.최근30일평균거래가 || '-'}</td>
                    <td>${item.중국노출 || '-'}</td>
                    <td>${item.중국시장최근30일판매량 ? item.중국시장최근30일판매량.toLocaleString() + '개' : '0개'}</td>
                    <td>
                        <span class="status status-pending" id="status-${index}">대기</span>
                    </td>
                </tr>
            `).join('');
        }

        async function startKreamSearch() {
            if (collectedData.length === 0) {
                alert('검색할 상품이 없습니다.');
                return;
            }
            
            const btn = event.target;
            btn.disabled = true;
            btn.textContent = '검색 중...';
            
            // 크림 로그인 확인
            try {
                const loginRes = await fetch('/kream_login', {
                    method: 'POST'
                });
                const loginData = await loginRes.json();
                
                if (!loginData.success) {
                    alert('크림 로그인 실패: ' + loginData.error);
                    btn.disabled = false;
                    btn.textContent = '🔍 크림 검색 시작';
                    return;
                }
                
                // 순차적으로 검색
                for (let i = 0; i < collectedData.length; i++) {
                    const item = collectedData[i];
                    const productCode = item.상품번호;
                    
                    if (!productCode || productCode === '-') continue;
                    
                    await searchKream(productCode, i);
                    
                    // 0.5초 대기 (크림 차단 방지)
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
                
                btn.disabled = false;
                btn.textContent = '✅ 검색 완료';
                
            } catch (error) {
                alert('오류 발생: ' + error.message);
                btn.disabled = false;
                btn.textContent = '🔍 크림 검색 시작';
            }
        }

        async function searchKream(productCode, index) {
            const statusEl = document.getElementById(`status-${index}`);
            const btnEl = document.getElementById(`btn-${index}`);
            
            if (!productCode || productCode === '-') {
                statusEl.className = 'status';
                statusEl.style.background = '#e0e0e0';
                statusEl.style.color = '#666';
                statusEl.textContent = '스킵';
                return;
            }
            
            statusEl.className = 'status status-searching';
            statusEl.textContent = '검색중';
            btnEl.disabled = true;
            
            try {
                const response = await fetch('/search_kream_product', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ product_code: productCode })
                });
                
                const result = await response.json();
                
                if (result.success && result.model_number) {
                    statusEl.className = 'status status-done';
                    statusEl.textContent = '완료';
                    statusEl.title = `모델번호: ${result.model_number}`;
                    
                    // 행에 결과 추가
                    const row = document.getElementById(`row-${index}`);
                    const newCell = row.insertCell();
                    newCell.innerHTML = `<strong>${result.model_number}</strong>`;
                    newCell.style.color = '#667eea';
                    
                } else {
                    statusEl.className = 'status';
                    statusEl.style.background = '#f8d7da';
                    statusEl.style.color = '#721c24';
                    statusEl.textContent = '실패';
                    statusEl.title = result.error || '검색 결과 없음';
                }
                
            } catch (error) {
                console.error('검색 오류:', error);
                statusEl.className = 'status';
                statusEl.style.background = '#f8d7da';
                statusEl.style.color = '#721c24';
                statusEl.textContent = '오류';
            } finally {
                btnEl.disabled = false;
            }
        }
    </script>
</body>
</html>
'''

# 크림 검색 결과 팝업 HTML
KREAM_RESULTS_HTML = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>크림(KREAM) 검색 결과</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 30px;
            max-width: 1400px;
            margin: 0 auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #667eea;
        }
        .header h1 {
            font-size: 2em;
            color: #333;
            margin-bottom: 10px;
        }
        .header p {
            color: #666;
            font-size: 1.1em;
        }
        .status {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .status-badge {
            padding: 10px 20px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
        }
        .status-searching { background: #ffc107; color: #333; }
        .status-complete { background: #28a745; color: white; }
        .status-error { background: #dc3545; color: white; }
        .progress-container {
            margin-bottom: 20px;
        }
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: 700;
            font-size: 14px;
        }
        .product-card {
            background: #f8f9fa;
            border: 2px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }
        .product-card:hover {
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.2);
        }
        .product-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #ddd;
        }
        .product-code {
            font-size: 1.3em;
            font-weight: 700;
            color: #333;
        }
        .product-status {
            font-size: 14px;
            color: #666;
        }
        .product-items {
            display: grid;
            gap: 12px;
        }
        .item-row {
            display: grid;
            grid-template-columns: 80px 120px 1fr 150px 150px 120px;
            gap: 15px;
            align-items: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            transition: all 0.2s;
        }
        .item-row:hover {
            border-color: #667eea;
            box-shadow: 0 2px 8px rgba(102,126,234,0.15);
        }
        .item-image {
            width: 70px;
            height: 70px;
            object-fit: contain;
            border-radius: 6px;
            background: #f8f9fa;
            padding: 5px;
        }
        .item-brand {
            font-size: 12px;
            color: #999;
            font-weight: 600;
        }
        .item-name {
            font-size: 14px;
            font-weight: 600;
            color: #333;
            line-height: 1.4;
        }
        .item-price {
            font-size: 18px;
            font-weight: 700;
            color: #667eea;
        }
        .item-size {
            font-size: 13px;
            color: #666;
        }
        .item-link {
            background: #667eea;
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            text-align: center;
            transition: all 0.2s;
        }
        .item-link:hover {
            background: #5568d3;
            transform: scale(1.05);
        }
        .no-results {
            text-align: center;
            padding: 40px;
            color: #999;
        }
        .log-container {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 12px;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 20px;
        }
        .log-item {
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 5px;
            font-size: 13px;
            font-family: 'Courier New', monospace;
        }
        .log-info { background: #d1ecf1; color: #0c5460; }
        .log-success { background: #d4edda; color: #155724; }
        .log-warning { background: #fff3cd; color: #856404; }
        .log-error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛒 크림(KREAM) 검색 결과</h1>
            <p>실시간 검색 진행 중</p>
        </div>

        <div class="status">
            <div>
                <span class="status-badge status-searching" id="statusBadge">
                    검색 중...
                </span>
            </div>
            <div>
                <strong>진행:</strong> <span id="progressText">0/0</span>
            </div>
        </div>

        <div class="progress-container">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill" style="width: 0%">0%</div>
            </div>
        </div>

        <div id="resultsContainer">
            <div class="no-results">
                <p>🔍 검색을 시작합니다...</p>
            </div>
        </div>

        <div class="log-container" id="logContainer">
            <div class="log-item log-info">시스템 준비 완료</div>
        </div>
    </div>

    <script>
        const eventSource = new EventSource('/kream_search_stream/{{ session_id }}');
        const resultsContainer = document.getElementById('resultsContainer');
        const logContainer = document.getElementById('logContainer');
        const statusBadge = document.getElementById('statusBadge');
        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.type === 'log') {
                addLog(data.message, data.level || 'info');
            }
            else if (data.type === 'progress') {
                updateProgress(data.current, data.total);
            }
            else if (data.type === 'product_start') {
                addProductCard(data.product_code);
            }
            else if (data.type === 'product_result') {
                updateProductCard(data.product_code, data.products);
            }
            else if (data.type === 'complete') {
                completeSearch();
            }
            else if (data.type === 'error') {
                showError(data.message);
            }
        };

        function addLog(message, level) {
            const logItem = document.createElement('div');
            logItem.className = `log-item log-${level}`;
            logItem.textContent = `[${new Date().toLocaleTimeString('ko-KR')}] ${message}`;
            logContainer.appendChild(logItem);
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        function updateProgress(current, total) {
            const percentage = Math.round((current / total) * 100);
            progressText.textContent = `${current}/${total}`;
            progressFill.style.width = `${percentage}%`;
            progressFill.textContent = `${percentage}%`;
        }

        function addProductCard(productCode) {
            if (resultsContainer.querySelector('.no-results')) {
                resultsContainer.innerHTML = '';
            }

            const card = document.createElement('div');
            card.className = 'product-card';
            card.id = `product-${productCode}`;
            card.innerHTML = `
                <div class="product-header">
                    <span class="product-code">${productCode}</span>
                    <span class="product-status">검색 중...</span>
                </div>
                <div class="product-items">
                    <div class="no-results">
                        <p>🔍 상품 정보를 검색하고 있습니다...</p>
                    </div>
                </div>
            `;
            resultsContainer.appendChild(card);
        }

        function updateProductCard(productCode, products) {
            const card = document.getElementById(`product-${productCode}`);
            if (!card) return;

            const header = card.querySelector('.product-header');
            const itemsContainer = card.querySelector('.product-items');

            if (products && products.length > 0) {
                header.querySelector('.product-status').innerHTML = `✅ ${products.length}개 발견`;
                
                itemsContainer.innerHTML = products.map(product => `
                    <div class="item-row">
                        <img src="${product.image_url || ''}" 
                             alt="상품 이미지" 
                             class="item-image"
                             onerror="this.style.display='none'">
                        <div>
                            <div class="item-brand">${product.brand || 'KREAM'}</div>
                            <div class="item-size">${product.size || '-'}</div>
                        </div>
                        <div class="item-name">${product.name || '상품명 없음'}</div>
                        <div class="item-price">${product.price || '-'}</div>
                        <div style="font-size:12px;color:#999;">${product.source || 'KREAM'}</div>
                        <a href="${product.link}" target="_blank" class="item-link">
                            상세보기 →
                        </a>
                    </div>
                `).join('');
            } else {
                header.querySelector('.product-status').innerHTML = '❌ 결과 없음';
                itemsContainer.innerHTML = `
                    <div class="no-results">
                        <p>😢 검색 결과가 없습니다</p>
                    </div>
                `;
            }
        }

        function completeSearch() {
            statusBadge.className = 'status-badge status-complete';
            statusBadge.innerHTML = '✅ 검색 완료';
            addLog('모든 상품 검색이 완료되었습니다!', 'success');
            eventSource.close();
        }

        function showError(message) {
            statusBadge.className = 'status-badge status-error';
            statusBadge.innerHTML = '❌ 오류 발생';
            addLog(`오류: ${message}`, 'error');
            eventSource.close();
        }

        eventSource.onerror = function() {
            if (statusBadge.className.includes('status-searching')) {
                showError('서버 연결이 끊어졌습니다');
            }
        };
    </script>
</body>
</html>
'''


# ==========================================
# 크림(KREAM) 검색 엔드포인트
# ==========================================

# 크림 검색 세션 관리
kream_sessions = {}

@app.route('/kream_popup')
def kream_popup():
    """크림 검색 팝업 페이지 - 수집 데이터 표시"""
    return render_template_string(KREAM_POPUP_HTML)


@app.route('/kream_login', methods=['POST'])
def kream_login():
    """크림 로그인"""
    try:
        if kream_search is None:
            return jsonify({'success': False, 'error': 'kream_search 모듈이 없습니다'})
        
        result = kream_search.login_kream()
        
        return jsonify({
            'success': result,
            'message': '로그인 성공' if result else '로그인 실패'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/search_kream_product', methods=['POST'])
def search_kream_product():
    """크림 상품 검색 (모델번호 추출)"""
    try:
        if kream_search is None:
            return jsonify({'success': False, 'error': 'kream_search 모듈이 없습니다'})
        
        data = request.json
        product_code = data.get('product_code', '')
        
        if not product_code:
            return jsonify({'success': False, 'error': '상품 코드가 없습니다'})
        
        # 크림 검색 실행
        result = kream_search.search_kream_product_detail(product_code)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/start_kream_search', methods=['POST'])
def start_kream_search():
    """크림 검색 시작 (기존 방식 - 사용 안 함)"""
    try:
        if kream_search is None:
            return jsonify({
                'success': False, 
                'error': 'kream_search 모듈이 로드되지 않았습니다.\nkream_data/kream_search.py 파일을 확인하세요.'
            }), 500
        
        data = request.json
        product_codes = data.get('product_codes', [])
        
        if not product_codes:
            return jsonify({'success': False, 'error': '상품 코드가 없습니다'})
        
        # 세션 ID 생성
        session_id = str(uuid.uuid4())
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'popup_url': f'/kream_results/{session_id}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/kream_results/<session_id>')
def kream_results(session_id):
    """크림 검색 결과 팝업 페이지"""
    return render_template_string(KREAM_RESULTS_HTML, session_id=session_id)


@app.route('/kream_search_stream/<session_id>')
def kream_search_stream(session_id):
    """크림 검색 실시간 스트림"""
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


@app.route('/stop_kream_search', methods=['POST'])
def stop_kream_search():
    """크림 검색 중단"""
    global stop_flag
    stop_flag = True
    
    # kream_search 모듈이 있으면 중단 플래그 설정
    if kream_search is not None:
        kream_search.stop_flag = True
    
    return jsonify({'success': True, 'message': '검색이 중단되었습니다'})


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 POIZON 데이터 수집기 서버 시작")
    print("=" * 50)
    print("📱 로컬 접속: http://127.0.0.1:3000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=3000)