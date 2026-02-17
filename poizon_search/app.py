from flask import Flask, render_template, request, Response, send_file, jsonify, render_template_string
import json
import os
import threading
import queue
import openpyxl
import uuid

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
</html>
'''


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 POIZON 데이터 수집기 서버 시작")
    print("=" * 50)
    print("📱 로컬 접속: http://127.0.0.1:3000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=3000)