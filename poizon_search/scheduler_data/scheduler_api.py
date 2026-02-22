import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file

# Blueprint 생성
scheduler_bp = Blueprint('scheduler', __name__, url_prefix='/api/scheduler')

# 경로 설정
SCHEDULER_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(SCHEDULER_DIR, 'task_history.json')

# ==========================================
# HTML 페이지 제공 ✅ 추가!
# ==========================================

@scheduler_bp.route('/page')
def serve_scheduler_page():
    """스케줄러 HTML 페이지 제공"""
    try:
        html_path = os.path.join(SCHEDULER_DIR, 'scheduler.html')
        
        if os.path.exists(html_path):
            return send_file(html_path)
        else:
            return jsonify({'error': 'scheduler.html 파일을 찾을 수 없습니다'}), 404
            
    except Exception as e:
        print(f"❌ HTML 제공 오류: {e}")
        return jsonify({'error': str(e)}), 500


# ==========================================
# 유틸리티 함수
# ==========================================

def load_history():
    """히스토리 파일 로드"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"히스토리 로드 오류: {e}")
            return []
    return []


def save_history(history):
    """히스토리 파일 저장"""
    try:
        os.makedirs(SCHEDULER_DIR, exist_ok=True)
        
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"히스토리 저장 오류: {e}")
        return False


def save_task_to_history(task_data):
    """작업 결과를 히스토리에 저장"""
    try:
        if not isinstance(task_data, dict):
            print(f"⚠️ task_data가 dict가 아님: {type(task_data)}")
            return None
        
        history = load_history()
        
        task_id = f"task_{int(datetime.now().timestamp() * 1000)}"
        
        record = {
            'id': task_id,
            'timestamp': datetime.now().isoformat(),
            'keyword': str(task_data.get('keyword', '알 수 없음')),
            'mode': str(task_data.get('mode', 'keyword')),
            'collected_count': int(task_data.get('collected_count', 0)),
            'kream_count': int(task_data.get('kream_count', 0)),
            'duration_seconds': int(task_data.get('duration_seconds', 0)),
            'data': task_data.get('data', []) if isinstance(task_data.get('data'), list) else [],
            'status': 'completed'
        }
        
        history.insert(0, record)
        history = history[:100]
        
        if save_history(history):
            print(f"✅ 작업 기록 저장 성공: {task_id}")
            print(f"   - 키워드: {record['keyword']}")
            print(f"   - 모드: {record['mode']}")
            print(f"   - 수집: {record['collected_count']}개")
            print(f"   - 소요: {record['duration_seconds']}초")
            return task_id
        else:
            print(f"❌ 파일 저장 실패")
            return None
        
    except Exception as e:
        print(f"❌ save_task_to_history 오류: {e}")
        import traceback
        traceback.print_exc()
        return None


# ==========================================
# API 엔드포인트
# ==========================================

@scheduler_bp.route('/save', methods=['POST'])
def save_task():
    """외부에서 작업 결과를 저장할 때 사용"""
    try:
        data = request.json
        
        if not data:
            return jsonify({'success': False, 'error': '데이터가 없습니다'}), 400
        
        task_id = save_task_to_history(data)
        
        if task_id:
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': f'{data.get("collected_count", 0)}개 데이터 저장 완료'
            })
        else:
            return jsonify({'success': False, 'error': '저장 실패'}), 500
            
    except Exception as e:
        print(f"작업 저장 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/history', methods=['GET'])
def get_history():
    """히스토리 목록 조회"""
    try:
        history = load_history()
        return jsonify({
            'success': True,
            'records': history
        })
    except Exception as e:
        print(f"히스토리 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/task/<task_id>', methods=['GET'])
def get_task(task_id):
    """특정 작업 조회"""
    try:
        history = load_history()
        task = next((t for t in history if t['id'] == task_id), None)
        
        if task:
            return jsonify({'success': True, 'task': task})
        else:
            return jsonify({'success': False, 'error': '작업을 찾을 수 없습니다'}), 404
            
    except Exception as e:
        print(f"작업 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@scheduler_bp.route('/delete/<task_id>', methods=['POST'])
def delete_task(task_id):
    """작업 삭제"""
    try:
        history = load_history()
        original_count = len(history)
        
        history = [t for t in history if t['id'] != task_id]
        
        if len(history) < original_count:
            if save_history(history):
                return jsonify({'success': True, 'message': '삭제 완료'})
            else:
                return jsonify({'success': False, 'error': '저장 실패'}), 500
        else:
            return jsonify({'success': False, 'error': '작업을 찾을 수 없습니다'}), 404
            
    except Exception as e:
        print(f"작업 삭제 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500