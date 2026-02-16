from flask import Flask, render_template, request, Response, send_file, jsonify
import json
import os
import threading
import queue
import openpyxl
import uuid
from datetime import datetime
import zipfile
import io
import time

app = Flask(__name__)

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

HISTORY_DIR = 'search_history'
os.makedirs(HISTORY_DIR, exist_ok=True)

def log_callback(message, level='info'):
    global current_items
    
    if message.startswith("PROGRESS:"):
        parts = message.split(":")
        if len(parts) == 2:
            current, total = parts[1].split("/")
            current_items = int(current)
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
        try:
            data = json.loads(message.split(":", 1)[1])
            log_queue.put({
                'type': 'product_result',
                'product_code': data['product_code'],
                'products': data['products']
            })
        except Exception as e:
            print(f"PRODUCT_RESULT 파싱 오류: {e}")
    else:
        log_queue.put({
            'type': 'log',
            'message': message,
            'level': level
        })

def run_poizon_from_gui(keyword, max_pages, search_type):
    global is_working, work_start_time, work_type, estimated_items, current_items, stop_requested
    
    is_working = True
    work_start_time = time.time()
    work_type = 'scraping'
    estimated_items = max_pages * 10
    current_items = 0
    stop_requested = False
    
    try:
        # ✅ 정확한 함수 이름 사용
        from poizon_data.poizon_search import run
        
        def progress_callback(msg, level='info'):
            log_callback(msg, level)
        
        # run() 함수 호출
        result = run(
            keyword=keyword,
            max_pages=max_pages,
            callback=progress_callback,
            skip_login=False
        )
        
        global result_data
        result_data = result
        
        log_queue.put({
            'type': 'complete',
            'data': result,              # ← 전체 데이터 추가!
            'total_items': len(result),
            'pages': max_pages,
            'message': f'수집 완료: {len(result)}개 항목'
        })
        
        return result
        
    except Exception as e:
        if not stop_requested:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
        import traceback
        traceback.print_exc()
        return []
    finally:
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0

def run_excel_comparison(excel_data):
    global is_working, work_start_time, work_type, estimated_items, current_items, stop_requested
    
    is_working = True
    work_start_time = time.time()
    work_type = 'comparison'
    estimated_items = len(excel_data)
    current_items = 0
    stop_requested = False
    
    try:
        # ✅ 엑셀 비교 함수 찾기
        from poizon_data.poizon_search import compare_prices_with_poizon
        
        def progress_callback(msg, level='info'):
            log_callback(msg, level)
        
        result = compare_prices_with_poizon(
            excel_data=excel_data,
            callback=progress_callback
        )
        
        global result_data
        result_data = result
        
        log_queue.put({
            'type': 'complete',
            'data': result,
            'message': f'비교 완료: {len(result)}개 항목'
        })
        
        return result
        
    except ImportError:
        # 함수가 없으면 run() 사용
        print("⚠️ compare_prices_with_poizon 없음, run() 사용")
        try:
            from poizon_data.poizon_search import run
            
            def progress_callback(msg, level='info'):
                log_callback(msg, level)
            
            # 엑셀 데이터를 순차적으로 검색
            results = []
            for idx, item in enumerate(excel_data):
                keyword = item.get('상품번호') or item.get('code')
                if keyword:
                    result = run(
                        keyword=keyword,
                        max_pages=1,
                        callback=progress_callback,
                        skip_login=True
                    )
                    results.extend(result)
            
            return results
            
        except Exception as e:
            raise e
        
    except Exception as e:
        if not stop_requested:
            log_queue.put({
                'type': 'error',
                'message': str(e)
            })
        import traceback
        traceback.print_exc()
        return []
    finally:
        is_working = False
        work_start_time = None
        work_type = None
        estimated_items = 0
        current_items = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history_page():
    """기록 팝업 페이지"""
    return render_template('history_popup.html')

@app.route('/check_login', methods=['GET'])
def check_login():
    cookie_file = 'poizon_cookies.json'
    
    if os.path.exists(cookie_file):
        print(f"✅ 쿠키 파일 발견: {cookie_file}")
        message = 'POIZON 쿠키 파일이 존재합니다. 접속 준비 완료!'
    else:
        print(f"⚠️ 쿠키 파일 없음: {cookie_file}")
        message = '쿠키 파일이 없지만 검색 시 자동 로그인을 시도합니다'
    
    return jsonify({
        'logged_in': True,
        'message': message
    })

@app.route('/check_status', methods=['GET'])
def check_status():
    global is_working, work_start_time, work_type, estimated_items, current_items
    
    if not is_working:
        return jsonify({
            'working': False,
            'message': '작업 중이 아닙니다'
        })
    
    elapsed = int(time.time() - work_start_time) if work_start_time else 0
    elapsed_minutes = elapsed // 60
    
    if estimated_items > 0:
        progress_percent = int((current_items / estimated_items) * 100)
        progress = f"{current_items}/{estimated_items} ({progress_percent}%)"
        
        if current_items > 0:
            avg_time = elapsed / current_items
            remaining = int(avg_time * (estimated_items - current_items) / 60)
        else:
            remaining = 0
    else:
        progress = "처리 중..."
        remaining = 0
    
    return jsonify({
        'working': True,
        'work_type': work_type,
        'progress': progress,
        'elapsed_minutes': elapsed_minutes,
        'remaining_minutes': remaining,
        'current_items': current_items,
        'estimated_items': estimated_items
    })

@app.route('/start')
def start():
    keyword = request.args.get('keyword', '')
    max_pages = int(request.args.get('maxPages', 1))
    search_type = request.args.get('searchType', 'keyword')
    
    def generate():
        while not log_queue.empty():
            log_queue.get()
        
        thread = threading.Thread(
            target=run_poizon_from_gui,
            args=(keyword, max_pages, search_type)
        )
        thread.daemon = True
        thread.start()
        
        while True:
            try:
                msg = log_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                
                if msg.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '파일이 없습니다'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다'}), 400
    
    try:
        wb = openpyxl.load_workbook(file)
        sheet = wb.active
        
        data = []
        headers = None
        
        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), 1):
            if row_idx == 1:
                headers = row
                continue
            
            if not any(row):
                continue
            
            row_dict = {}
            for col_idx, value in enumerate(row):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    row_dict[header] = value
            
            data.append(row_dict)
        
        return jsonify({
            'success': True,
            'data': data,
            'count': len(data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'엑셀 파일 읽기 실패: {str(e)}'
        }), 500

@app.route('/compare_prices', methods=['POST'])
def compare_prices():
    data = request.json
    excel_data = data.get('excelData', [])
    
    if not excel_data:
        return jsonify({'success': False, 'error': '데이터가 없습니다'}), 400
    
    def generate():
        while not log_queue.empty():
            log_queue.get()
        
        thread = threading.Thread(
            target=run_excel_comparison,
            args=(excel_data,)
        )
        thread.daemon = True
        thread.start()
        
        while True:
            try:
                msg = log_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                
                if msg.get('type') in ['complete', 'error']:
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<path:filename>')
def download_file(filename):
    try:
        filepath = os.path.join('output_data', filename)
        
        if not os.path.exists(filepath):
            return jsonify({'error': '파일을 찾을 수 없습니다'}), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/shutdown_browser')
def shutdown_browser():
    global current_browser
    if current_browser:
        try:
            current_browser.quit()
            current_browser = None
        except:
            pass
    return jsonify({'success': True})

@app.route('/stop', methods=['POST'])
def stop_collection():
    global stop_flag, stop_requested, current_browser
    
    stop_flag = True
    stop_requested = True
    
    log_queue.put({
        'type': 'log',
        'message': '⏹️ 중단 요청됨...',
        'level': 'warning'
    })
    
    if current_browser:
        try:
            current_browser.quit()
            current_browser = None
        except:
            pass
    
    return jsonify({'success': True, 'message': '중단 요청 완료'})

@app.route('/start_sourcing', methods=['POST'])
def start_sourcing():
    product_codes = request.json.get('product_codes', [])
    
    if not product_codes:
        return jsonify({'success': False, 'error': '상품번호가 없습니다'})
    
    session_id = str(uuid.uuid4())
    
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
    if not hasattr(app, 'sourcing_sessions') or session_id not in app.sourcing_sessions:
        return "세션을 찾을 수 없습니다", 404
    
    html_path = os.path.join('templates', 'sourcing_results.html')
    
    if os.path.exists(html_path):
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        html = html.replace('"/start_sourcing_stream"', f'"/start_sourcing_stream/{session_id}"')
        return html
    
    return "템플릿을 찾을 수 없습니다", 404

@app.route('/start_sourcing_stream/<session_id>')
def start_sourcing_stream(session_id):
    if not hasattr(app, 'sourcing_sessions') or session_id not in app.sourcing_sessions:
        def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': '세션을 찾을 수 없습니다'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')
    
    product_codes = app.sourcing_sessions[session_id]['product_codes']
    
    def generate():
        while not log_queue.empty():
            log_queue.get()
        
        thread = threading.Thread(
            target=run_sourcing_background_with_stream,
            args=(product_codes, session_id)
        )
        thread.daemon = True
        thread.start()
        
        while True:
            try:
                msg = log_queue.get(timeout=30)
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                
                if msg.get('type') in ['complete', 'error']:
                    break
            except:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

def run_sourcing_background_with_stream(product_codes, session_id):
    global is_working, work_start_time, work_type, estimated_items, current_items
    
    is_working = True
    work_start_time = time.time()
    work_type = 'sourcing'
    estimated_items = len(product_codes)
    current_items = 0
    
    try:
        from poizon_data.sourcing_search import run_sourcing_for_products
        
        def stream_callback(message, level='info'):
            log_callback(message, level)
        
        result = run_sourcing_for_products(product_codes, callback=stream_callback)
        
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
        
        if hasattr(app, 'sourcing_sessions') and session_id in app.sourcing_sessions:
            app.sourcing_sessions[session_id]['status'] = 'completed'

@app.route('/stop_sourcing', methods=['POST'])
def stop_sourcing():
    global stop_flag, stop_requested
    
    stop_flag = True
    stop_requested = True
    
    return jsonify({'success': True, 'message': '중단 요청 완료'})


# ==========================================
# 기록 관리 API
# ==========================================

@app.route('/api/history/save', methods=['POST'])
def save_history():
    try:
        data = request.json
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        search_type = data.get('type', 'search')
        
        if search_type == 'keyword':
            keyword = data['params'].get('keyword', 'search').replace(' ', '_')
            filename = f"{ts}_keyword_{keyword}.json"
        elif search_type == 'compare':
            count = len(data.get('results', []))
            filename = f"{ts}_compare_{count}items.json"
        elif search_type == 'price':
            pages = data['params'].get('maxPages', 1)
            filename = f"{ts}_price_{pages}p.json"
        elif search_type == 'growth':
            pages = data['params'].get('maxPages', 1)
            filename = f"{ts}_growth_{pages}p.json"
        else:
            filename = f"{ts}_search.json"
        
        results = data.get('results', [])
        prices = [r.get('sale_price') or r.get('price', 0) for r in results]
        prices = [p for p in prices if p > 0]
        
        record = {
            'metadata': {
                'id': str(int(datetime.now().timestamp() * 1000)),
                'type': search_type,
                'timestamp': datetime.now().isoformat(),
                'params': data.get('params', {}),
                'filename': filename
            },
            'summary': {
                'total_count': len(results),
                'avg_price': int(sum(prices) / len(prices)) if prices else 0,
                'min_price': min(prices) if prices else 0,
                'max_price': max(prices) if prices else 0
            },
            'results': results
        }
        
        filepath = os.path.join(HISTORY_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        
        size = os.path.getsize(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'size': size,
            'size_mb': round(size / 1024 / 1024, 2)
        })
        
    except Exception as e:
        print(f"❌ 기록 저장 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/list', methods=['GET'])
def list_history():
    try:
        records = []
        
        for filename in sorted(os.listdir(HISTORY_DIR), reverse=True):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(HISTORY_DIR, filename)
            size = os.path.getsize(filepath)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records.append({
                'id': data['metadata']['id'],
                'filename': filename,
                'type': data['metadata']['type'],
                'timestamp': data['metadata']['timestamp'],
                'params': data['metadata']['params'],
                'summary': data['summary'],
                'size': size,
                'size_mb': round(size / 1024 / 1024, 2)
            })
        
        return jsonify({
            'success': True,
            'records': records,
            'total': len(records),
            'total_size_mb': round(sum(r['size'] for r in records) / 1024 / 1024, 2)
        })
        
    except Exception as e:
        print(f"❌ 목록 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/load/<filename>', methods=['GET'])
def load_history(filename):
    try:
        filepath = os.path.join(HISTORY_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다'}), 404
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({'success': True, 'data': data})
        
    except Exception as e:
        print(f"❌ 파일 로드 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/download/<filename>', methods=['GET'])
def download_history(filename):
    try:
        filepath = os.path.join(HISTORY_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다'}), 404
        
        return send_file(
            filepath,
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ 다운로드 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/download-all', methods=['GET'])
def download_all_history():
    try:
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(HISTORY_DIR):
                if filename.endswith('.json'):
                    filepath = os.path.join(HISTORY_DIR, filename)
                    zf.write(filepath, filename)
        
        zip_buffer.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'poizon_history_{timestamp}.zip'
        )
        
    except Exception as e:
        print(f"❌ ZIP 다운로드 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/delete/<filename>', methods=['DELETE'])
def delete_history(filename):
    try:
        filepath = os.path.join(HISTORY_DIR, filename)
        
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '파일을 찾을 수 없습니다'}), 404
        
        os.remove(filepath)
        
        return jsonify({'success': True, 'message': f'{filename} 삭제 완료'})
        
    except Exception as e:
        print(f"❌ 삭제 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/delete-selected', methods=['POST'])
def delete_selected_history():
    try:
        ids = request.json.get('record_ids', [])
        
        if not ids:
            return jsonify({'success': False, 'error': '선택된 항목이 없습니다'}), 400
        
        deleted = 0
        failed = 0
        
        for filename in os.listdir(HISTORY_DIR):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(HISTORY_DIR, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data['metadata']['id'] in ids:
                    os.remove(filepath)
                    deleted += 1
                    print(f"✅ 삭제: {filename}")
                    
            except Exception as e:
                print(f"⚠️ 파일 처리 실패 ({filename}): {e}")
                failed += 1
                continue
        
        return jsonify({
            'success': True,
            'deleted': deleted,
            'failed': failed,
            'message': f'{deleted}개 기록 삭제 완료' + (f', {failed}개 실패' if failed > 0 else '')
        })
        
    except Exception as e:
        print(f"❌ 배치 삭제 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    print("=" * 60)
    print("🚀 POIZON 데이터 수집기 서버 시작")
    print("=" * 60)
    print("📱 로컬 접속: http://127.0.0.1:3000")
    print("📁 기록 저장: search_history/")
    print("✅ 함수: poizon_search.run()")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=3000)