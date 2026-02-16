print("=" * 50)
print("App.py 시작됨!")
print("=" * 50)

from flask import Flask, render_template, request, Response, send_file, jsonify
import json
import os
import threading
import queue

app = Flask(__name__)

# 로그 큐
log_queue = queue.Queue()
result_data = {}

def log_callback(message, level='info'):
    """poizon_search에서 호출하는 콜백"""
    if message.startswith("PROGRESS:"):
        # PROGRESS:3/20 형식
        parts = message.split(":")
        if len(parts) == 2:
            current, total = parts[1].split("/")
            log_queue.put({
                'type': 'progress',
                'current': int(current),
                'total': int(total)
            })
    elif message.startswith("DATA:"):
        # DATA:{json} 형식 - 실시간 상품 데이터
        try:
            import json as json_module
            data_str = message[5:]  # "DATA:" 제거
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

def run_scraper(keyword, max_pages):
    """백그라운드에서 스크래핑 실행"""
    global result_data
    try:
        from poizon_data.poizon_search import run_poizon_from_gui
        
        result = run_poizon_from_gui(
            keyword=keyword,
            max_pages=max_pages,
            callback=log_callback
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
        log_queue.put({
            'type': 'error',
            'message': str(e)
        })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start')
def start():
    keyword = request.args.get('keyword', '나이키')
    max_pages = int(request.args.get('max_pages', 20))
    
    # 큐 초기화
    while not log_queue.empty():
        log_queue.get()
    
    # 백그라운드 스레드 시작
    thread = threading.Thread(target=run_scraper, args=(keyword, max_pages))
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
                # 연결 유지
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/download/<path:filename>')
def download(filename):
    """엑셀 파일 다운로드"""
    try:
        # poizon_data 폴더에서 파일 찾기
        file_path = os.path.join(os.path.dirname(__file__), 'poizon_data', filename)
        if not os.path.exists(file_path):
            # 현재 폴더에서 찾기
            file_path = os.path.join(os.path.dirname(__file__), filename)
        
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

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 POIZON 데이터 수집기 서버 시작")
    print("=" * 50)
    print("📱 로컬 접속: http://127.0.0.1:3000")
    print("📱 내부 접속: http://192.168.0.132:3000")
    print("📱 외부 접속: http://공인IP:3000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=3000)  # ← 이 줄!
