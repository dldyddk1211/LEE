import os
import sqlite3
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file, session

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')

INVENTORY_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(INVENTORY_DIR, 'inventory.db')

INVENTORY_PASSWORD = 'dhkdl4213.'

# ==========================================
# DB 초기화
# ==========================================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT, brand TEXT,
            quantity INTEGER DEFAULT 0, price INTEGER DEFAULT 0,
            location TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seq TEXT, date TEXT, sale_date TEXT, brand TEXT, name TEXT,
            product_code TEXT, size TEXT, quantity INTEGER DEFAULT 0,
            status TEXT, sale_site TEXT,
            sale_price INTEGER DEFAULT 0, min_price INTEGER DEFAULT 0,
            deposit_price INTEGER DEFAULT 0, cost_price INTEGER DEFAULT 0,
            margin INTEGER DEFAULT 0, margin_rate TEXT,
            deposit_check TEXT, buyer TEXT, payment TEXT,
            notes TEXT, purchase_link TEXT, synced_at TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ 재고관리 DB 초기화 완료")

init_db()

# ==========================================
# 인증
# ==========================================

def is_authenticated():
    return session.get('inventory_auth') == True

@inventory_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    if data.get('password', '') == INVENTORY_PASSWORD:
        session['inventory_auth'] = True
        session.permanent = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '비밀번호가 틀렸습니다'}), 401

@inventory_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('inventory_auth', None)
    return jsonify({'success': True})

@inventory_bp.route('/check_auth')
def check_auth():
    return jsonify({'authenticated': is_authenticated()})

# ==========================================
# HTML 페이지
# ==========================================

@inventory_bp.route('/page')
def serve_inventory_page():
    try:
        html_path = os.path.join(INVENTORY_DIR, 'inventory.html')
        if os.path.exists(html_path):
            return send_file(html_path)
        return jsonify({'error': 'inventory.html 없음'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==========================================
# 판매 데이터 (구글 시트 동기화)
# ==========================================

@inventory_bp.route('/sales')
def get_sales():
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        keyword = request.args.get('keyword', '')
        brand   = request.args.get('brand', '')
        status  = request.args.get('status', '')
        page    = int(request.args.get('page', 1))
        limit   = int(request.args.get('limit', 100))

        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        where, params = ['1=1'], []
        if keyword:
            where.append('(name LIKE ? OR product_code LIKE ? OR brand LIKE ? OR buyer LIKE ?)')
            params.extend([f'%{keyword}%'] * 4)
        if brand:
            where.append('brand = ?')
            params.append(brand)
        if status:
            where.append('status = ?')
            params.append(status)

        ws = ' AND '.join(where)

        cursor.execute(f'SELECT COUNT(*) FROM sales WHERE {ws}', params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * limit
        cursor.execute(
            f'SELECT * FROM sales WHERE {ws} ORDER BY CAST(NULLIF(seq,"") AS INTEGER) ASC LIMIT ? OFFSET ?',
            params + [limit, offset]
        )
        sales = [dict(r) for r in cursor.fetchall()]

        cursor.execute('SELECT synced_at FROM sales ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        last_synced = row[0] if row else None

        cursor.execute('SELECT DISTINCT brand FROM sales WHERE brand != "" ORDER BY brand')
        brands = [r[0] for r in cursor.fetchall()]

        cursor.execute('SELECT DISTINCT status FROM sales WHERE status != "" ORDER BY status')
        statuses = [r[0] for r in cursor.fetchall()]

        conn.close()

        return jsonify({
            'success': True, 'sales': sales,
            'total': total, 'page': page, 'limit': limit,
            'last_synced': last_synced, 'brands': brands, 'statuses': statuses
        })
    except Exception as e:
        print(f"판매 조회 오류: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/sales/summary')
def get_sales_summary():
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*), SUM(sale_price), SUM(margin), SUM(cost_price) FROM sales')
        row = cursor.fetchone()
        conn.close()
        return jsonify({
            'success': True,
            'total_count':  row[0] or 0,
            'total_sale':   row[1] or 0,
            'total_margin': row[2] or 0,
            'total_cost':   row[3] or 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/sales/sync', methods=['POST'])
def manual_sync():
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        from inventory_data.sheets_sync import sync_once
        count = sync_once()
        return jsonify({'success': True, 'count': count, 'message': f'{count}건 동기화 완료'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# 재고 상품 API
# ==========================================

@inventory_bp.route('/products')
def get_products():
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM products ORDER BY updated_at DESC')
        products = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return jsonify({'success': True, 'products': products})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product', methods=['POST'])
def add_product():
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO products (product_code, name, category, brand, quantity, price, location, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (data['product_code'], data['name'], data.get('category',''), data.get('brand',''),
              data.get('quantity',0), data.get('price',0), data.get('location',''), data.get('notes','')))
        conn.commit()
        pid = cursor.lastrowid
        conn.close()
        return jsonify({'success': True, 'message': '상품이 추가되었습니다', 'product_id': pid})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': '이미 존재하는 상품코드입니다'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        data = request.json
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE products SET name=?, category=?, brand=?, price=?, location=?, notes=?, updated_at=?
            WHERE id=?
        ''', (data['name'], data.get('category',''), data.get('brand',''),
              data.get('price',0), data.get('location',''), data.get('notes',''),
              datetime.now().isoformat(), product_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '수정되었습니다'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@inventory_bp.route('/product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    if not is_authenticated():
        return jsonify({'success': False, 'error': '인증 필요'}), 401
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '삭제되었습니다'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500