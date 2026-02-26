import os
import json
import sqlite3
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file

# Blueprint 생성
inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')

# 경로 설정
INVENTORY_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(INVENTORY_DIR, 'inventory.db')

# ==========================================
# 데이터베이스 초기화
# ==========================================

def init_db():
    """데이터베이스 테이블 생성"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 재고 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            brand TEXT,
            quantity INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0,
            location TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 입출고 기록 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            before_qty INTEGER,
            after_qty INTEGER,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 재고관리 DB 초기화 완료")

# 앱 시작 시 DB 초기화
init_db()

# ==========================================
# HTML 페이지 제공
# ==========================================

@inventory_bp.route('/page')
def serve_inventory_page():
    """재고관리 HTML 페이지 제공"""
    try:
        html_path = os.path.join(INVENTORY_DIR, 'inventory.html')
        
        if os.path.exists(html_path):
            return send_file(html_path)
        else:
            return jsonify({'error': 'inventory.html 파일을 찾을 수 없습니다'}), 404
            
    except Exception as e:
        print(f"❌ HTML 제공 오류: {e}")
        return jsonify({'error': str(e)}), 500

# ==========================================
# API 엔드포인트
# ==========================================

@inventory_bp.route('/products', methods=['GET'])
def get_products():
    """전체 상품 목록 조회"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products ORDER BY updated_at DESC')
        products = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'success': True,
            'products': products
        })
    except Exception as e:
        print(f"상품 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product/<int:product_id>', methods=['GET'])
def get_product(product_id):
    """특정 상품 조회"""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        product = cursor.fetchone()
        
        conn.close()
        
        if product:
            return jsonify({'success': True, 'product': dict(product)})
        else:
            return jsonify({'success': False, 'error': '상품을 찾을 수 없습니다'}), 404
            
    except Exception as e:
        print(f"상품 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product', methods=['POST'])
def add_product():
    """새 상품 추가"""
    try:
        data = request.json
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO products 
            (product_code, name, category, brand, quantity, price, location, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['product_code'],
            data['name'],
            data.get('category', ''),
            data.get('brand', ''),
            data.get('quantity', 0),
            data.get('price', 0),
            data.get('location', ''),
            data.get('notes', '')
        ))
        
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        
        return jsonify({
            'success': True,
            'message': '상품이 추가되었습니다',
            'product_id': product_id
        })
        
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': '이미 존재하는 상품코드입니다'}), 400
    except Exception as e:
        print(f"상품 추가 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    """상품 정보 수정"""
    try:
        data = request.json
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE products 
            SET name=?, category=?, brand=?, price=?, location=?, notes=?, updated_at=?
            WHERE id=?
        ''', (
            data['name'],
            data.get('category', ''),
            data.get('brand', ''),
            data.get('price', 0),
            data.get('location', ''),
            data.get('notes', ''),
            datetime.now().isoformat(),
            product_id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '상품 정보가 수정되었습니다'})
        
    except Exception as e:
        print(f"상품 수정 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    """상품 삭제"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '상품이 삭제되었습니다'})
        
    except Exception as e:
        print(f"상품 삭제 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/import/sheets', methods=['POST'])
def import_from_sheets():
    """구글 스프레드시트에서 데이터 가져오기"""
    try:
        # TODO: 구글 스프레드시트 API 연동
        return jsonify({
            'success': False,
            'error': '아직 구현되지 않았습니다'
        }), 501
        
    except Exception as e:
        print(f"시트 가져오기 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500