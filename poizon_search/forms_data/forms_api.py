# ==========================================
# 서식 / 양식 기능 - Blueprint (PDF 버전)
# ==========================================

import os
import json
import uuid
import sqlite3
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
from config import paths

forms_bp = Blueprint('forms', __name__)

FORMS_DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
FORMS_HTML         = os.path.join(FORMS_DATA_DIR, 'forms.html')

# ✅ 공유 드라이브 경로 사용 (Mac/Windows 동일 데이터)
def _get_customers_file():
    return paths.get('customers_json')

def _get_invoice_output_dir():
    return paths.get('invoices_pdf')

def _get_db_path():
    return paths.get('invoices_db')

def _ensure_dirs():
    os.makedirs(FORMS_DATA_DIR, exist_ok=True)
    try:
        os.makedirs(_get_invoice_output_dir(), exist_ok=True)
        os.makedirs(os.path.dirname(_get_db_path()), exist_ok=True)
    except OSError:
        pass  # 드라이브 미연결 시 무시

def _get_db():
    """SQLite 연결 반환 (없으면 테이블 자동 생성)"""
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date  TEXT NOT NULL,
            memo        TEXT,
            buyer_company TEXT,
            buyer_name  TEXT,
            buyer_bizno TEXT,
            buyer_tel   TEXT,
            buyer_addr  TEXT,
            buyer_biztype TEXT,
            buyer_bizitem TEXT,
            shipping_name TEXT,
            shipping_tel  TEXT,
            shipping_addr TEXT,
            total_amount INTEGER DEFAULT 0,
            deposit      INTEGER DEFAULT 0,
            balance      INTEGER DEFAULT 0,
            receiver     TEXT,
            filename     TEXT,
            products_json TEXT,
            created_at  TEXT NOT NULL
        )
    """)
    # 기존 테이블에 컬럼 추가 (이미 있으면 무시)
    new_cols = [
        'shipping_name TEXT', 'shipping_tel TEXT', 'shipping_addr TEXT',
        'chk_invoice INTEGER DEFAULT 0', 'chk_deposit INTEGER DEFAULT 0',
        'chk_shipping INTEGER DEFAULT 0', 'chk_tax INTEGER DEFAULT 0',
        'tracking_numbers TEXT', 'order_memo TEXT',
    ]
    for col_def in new_cols:
        try:
            conn.execute(f'ALTER TABLE invoices ADD COLUMN {col_def}')
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn

def _save_invoice_to_db(d, filename):
    """거래명세서 데이터를 DB에 저장"""
    try:
        buyer    = d.get('buyer', {})
        shipping = d.get('shipping', {})
        products = d.get('products', [])
        conn = _get_db()
        conn.execute("""
            INSERT INTO invoices
              (trade_date, memo, buyer_company, buyer_name, buyer_bizno,
               buyer_tel, buyer_addr, buyer_biztype, buyer_bizitem,
               shipping_name, shipping_tel, shipping_addr,
               total_amount, deposit, balance, receiver, filename,
               products_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            d.get('date',''),
            d.get('memo',''),
            buyer.get('company',''),
            buyer.get('name',''),
            buyer.get('bizno',''),
            buyer.get('tel',''),
            buyer.get('addr',''),
            buyer.get('biztype',''),
            buyer.get('bizitem',''),
            shipping.get('name',''),
            shipping.get('tel',''),
            shipping.get('addr',''),
            d.get('totalAmount', 0),
            d.get('deposit', 0),
            d.get('balance', 0),
            d.get('receiver',''),
            filename,
            json.dumps(products, ensure_ascii=False),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'DB 저장 오류: {e}')

_ensure_dirs()
_get_db().close()  # DB 및 테이블 초기화

def _load_customers():
    cf = _get_customers_file()
    if not os.path.exists(cf):
        return []
    with open(cf, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_customers(customers):
    cf = _get_customers_file()
    os.makedirs(os.path.dirname(cf), exist_ok=True)
    with open(cf, 'w', encoding='utf-8') as f:
        json.dump(customers, f, ensure_ascii=False, indent=2)

def _load_font(size, bold=False):
    """한글 폰트 로드 (Pillow용)"""
    from PIL import ImageFont
    if bold:
        candidates = [
            r'C:\Windows\Fonts\malgunbd.ttf',
            r'C:\Windows\Fonts\NanumGothicBold.ttf',
            '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        ]
    else:
        candidates = [
            r'C:\Windows\Fonts\malgun.ttf',
            r'C:\Windows\Fonts\NanumGothic.ttf',
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/System/Library/Fonts/AppleSDGothicNeo.ttc',
        ]
    for fp in candidates:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

# 폰트 캐시
_font_cache = {}
def _get_font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = _load_font(size, bold)
    return _font_cache[key]


def _make_invoice_image(d, filepath):
    """거래명세서를 JPG 이미지로 생성"""
    from PIL import Image, ImageDraw

    # A4 비율 이미지 (210mm x 297mm → 2100 x 2970 px, ~254 DPI)
    SCALE = 10  # 1mm = 10px
    W = 210 * SCALE
    H = 297 * SCALE

    img = Image.new('RGB', (W, H), '#FFFFFF')
    draw = ImageDraw.Draw(img)

    buyer        = d.get('buyer', {})
    supplier     = d.get('supplier', {})
    products     = d.get('products', [])
    trade_date   = d.get('date', '')
    total_amount = d.get('totalAmount', 0)
    deposit      = d.get('deposit', 0)
    balance      = d.get('balance', 0)
    receiver     = d.get('receiver', '')

    GRAY  = '#D9D9D9'
    DARK  = '#1a1a2e'
    WHITE = '#FFFFFF'
    BLACK = '#000000'

    def mm(v):
        return int(v * SCALE)

    def cell(px, py, pw, ph, txt='', bold=False, size=9,
             bg=None, fg=BLACK, align='center', lpad=2, lw=1, wrap=False):
        x1, y1 = mm(px), mm(py)
        x2, y2 = mm(px + pw), mm(py + ph)

        # 배경 채우기
        if bg:
            draw.rectangle([x1, y1, x2, y2], fill=bg, outline=BLACK, width=lw)
        else:
            draw.rectangle([x1, y1, x2, y2], fill=WHITE, outline=BLACK, width=lw)

        # 텍스트
        txt = str(txt) if txt is not None else ''
        if not txt:
            return

        font = _get_font(mm(size * 0.35), bold)
        max_w = x2 - x1 - mm(lpad) * 2

        # 줄바꿈 처리
        if wrap:
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw = bbox[2] - bbox[0]
            if tw > max_w:
                # 글자 단위로 줄바꿈 위치 찾기
                lines = []
                line = ''
                for ch in txt:
                    test = line + ch
                    tb = draw.textbbox((0, 0), test, font=font)
                    if tb[2] - tb[0] > max_w and line:
                        lines.append(line)
                        line = ch
                    else:
                        line = test
                if line:
                    lines.append(line)

                # 여러 줄 그리기
                line_h = draw.textbbox((0, 0), '가', font=font)
                single_h = line_h[3] - line_h[1]
                total_h = single_h * len(lines) + mm(1) * (len(lines) - 1)
                start_y = y1 + (y2 - y1 - total_h) // 2

                for i, ln in enumerate(lines):
                    lb = draw.textbbox((0, 0), ln, font=font)
                    lw2 = lb[2] - lb[0]
                    ly = start_y + i * (single_h + mm(1)) - lb[1]
                    if align == 'center':
                        lx = x1 + (x2 - x1 - lw2) // 2
                    elif align == 'left':
                        lx = x1 + mm(lpad)
                    else:
                        lx = x2 - lw2 - mm(lpad)
                    draw.text((lx, ly), ln, fill=fg, font=font)
                return

        bbox = draw.textbbox((0, 0), txt, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        # 수직 중앙
        ty = y1 + (y2 - y1 - th) // 2 - bbox[1]

        if align == 'center':
            tx = x1 + (x2 - x1 - tw) // 2
        elif align == 'left':
            tx = x1 + mm(lpad)
        else:  # right
            tx = x2 - tw - mm(lpad)

        draw.text((tx, ty), txt, fill=fg, font=font)

    # ── 제목 ──
    cell(10, 5, 190, 16, '거  래  명  세  서', bold=True, size=20, lw=3)

    # ── 거래일자 ──
    cell(10, 23, 35, 7, '거 래 일 자', bold=True, size=8, bg=GRAY)
    cell(45, 23, 80, 7, trade_date or '', size=9)
    cell(125, 23, 75, 7, d.get('memo', ''), size=8)

    # ── 당사자 헤더 ──
    cell(10,  32, 95, 7, '수  요  자', bold=True, size=10, bg=GRAY)
    cell(105, 32, 95, 7, '공  급  자', bold=True, size=10, bg=GRAY)

    # ── 당사자 정보 ──
    def party(bx, data):
        rows = [
            ('사업자번호', data.get('bizno', '')),
            ('상  호',    data.get('company', '')),
            ('성  명',    data.get('name', '')),
            ('연  락  처', data.get('tel', '')),
            ('소  재  지', data.get('addr', '')),
            ('업태/종목',  f"{data.get('biztype', '')} / {data.get('bizitem', '')}"),
        ]
        cy = 39
        for lbl, val in rows:
            is_addr = lbl == '소  재  지'
            rh = 13 if is_addr else 7
            cell(bx,      cy, 23, rh, lbl, bold=True, size=8, bg=GRAY)
            cell(bx + 23, cy, 72, rh, val, size=8, align='left', wrap=is_addr)
            cy += rh

    party(10,  buyer)
    party(105, supplier)

    end_y = 39 + 7 * 5 + 13

    # ── 합계금액 ──
    cell(10,  end_y,  40, 10, '합 계 금 액', bold=True, size=10, bg=GRAY)
    cell(50,  end_y, 100, 10, f'\u20a9  {total_amount:,}', bold=True, size=13, align='left', lpad=8)
    cell(150, end_y,  50, 10, '', size=9)

    # ── 상품 헤더 ──
    ph = end_y + 12
    cols = [
        (10, 30, '품  번'), (40, 50, '품  명'), (90, 20, '수 량'),
        (110, 25, '소비자가'), (135, 15, '할인율'), (150, 20, '공급가'), (170, 30, '합  계')
    ]
    for cx, cw, cl in cols:
        cell(cx, ph, cw, 7, cl, bold=True, size=8, bg=DARK, fg=WHITE)

    # ── 상품 행 ──
    for i in range(11):
        ry = ph + 7 + i * 8
        p = products[i] if i < len(products) else {}
        cell(10,  ry, 30, 8, p.get('code', ''), size=8)
        cell(40,  ry, 50, 8, p.get('name', ''), size=8, align='left')
        cell(90,  ry, 20, 8, f"{p['qty']:,}"    if p.get('qty')    else '', size=8)
        cell(110, ry, 25, 8, f"{p['price']:,}"  if p.get('price')  else '', size=8)
        cell(135, ry, 15, 8, f"{p['disc']}%"    if p.get('disc')   else '', size=8)
        cell(150, ry, 20, 8, f"{p['supply']:,}" if p.get('supply') else '', size=8)
        cell(170, ry, 30, 8, f"{p['total']:,}"  if p.get('total')  else '', size=8)

    # ── 입금계좌 ──
    by = ph + 7 + 11 * 8
    cell(10, by, 190, 7,
         f"  입금 계좌 : {supplier.get('bank', '')}", size=8, align='left')

    # ── 총수량/합계 행 ──
    ty2 = by + 7
    total_qty = sum(p.get('qty', 0) for p in products)
    total_sum = sum(p.get('total', 0) for p in products)
    cell(10,  ty2,  80, 8, '총  수  량',        bold=True, size=9, bg=GRAY)
    cell(90,  ty2,  54, 8, f'{total_qty:,}',    size=9)
    cell(144, ty2,  20, 8, '합    계',           bold=True, size=9, bg=GRAY)
    cell(164, ty2,  36, 8, f'\u20a9 {total_sum:,}', size=9)

    # ── 입금/잔금/인수자 행 ──
    fy2 = ty2 + 8
    cell(10,  fy2,  30, 9, '입  금',             bold=True, size=9, bg=GRAY)
    cell(40,  fy2, 104, 9, f'\u20a9 {deposit:,}', size=9)
    cell(144, fy2,  20, 9, '잔  금',             bold=True, size=9, bg=GRAY)
    cell(164, fy2,  26, 9, f'\u20a9 {balance:,}', size=9)
    cell(190, fy2,  10, 9, receiver or '(인)',   size=8)

    # JPG로 저장
    img.save(filepath, 'JPEG', quality=95)


# ── 라우트 ──

@forms_bp.route('/forms')
def forms_page():
    with open(FORMS_HTML, 'r', encoding='utf-8') as f:
        content = f.read()
    return content, 200, {'Content-Type': 'text/html; charset=utf-8'}

@forms_bp.route('/forms/customers', methods=['GET'])
def get_customers():
    return jsonify(_load_customers())

@forms_bp.route('/forms/customers', methods=['POST'])
def add_customer():
    data = request.json
    customers = _load_customers()
    data['id'] = str(uuid.uuid4())
    data['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    customers.append(data)
    _save_customers(customers)
    return jsonify(data)

@forms_bp.route('/forms/customers/<customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    customers = _load_customers()
    customers = [c for c in customers if c.get('id') != customer_id]
    _save_customers(customers)
    return jsonify({'success': True})

@forms_bp.route('/generate_invoice', methods=['POST'])
def generate_invoice():
    try:
        d          = request.json
        buyer      = d.get('buyer', {})
        trade_date = d.get('date', '')
        buyer_name = buyer.get('company') or buyer.get('name') or '거래처'
        memo       = d.get('memo', '').strip()
        date_str   = trade_date.replace('-','') if trade_date else datetime.now().strftime('%Y%m%d')
        # 파일명에 사용 불가한 문자 제거
        import re
        safe_buyer = re.sub(r'[\\/:*?"<>|]', '', buyer_name)[:20]
        safe_memo  = re.sub(r'[\\/:*?"<>|]', '', memo)[:20]
        if safe_memo:
            filename = f"{date_str}_{safe_buyer}_{safe_memo}.jpg"
        else:
            filename = f"{date_str}_{safe_buyer}.jpg"
        filepath   = os.path.join(_get_invoice_output_dir(), filename)
        _make_invoice_image(d, filepath)
        _save_invoice_to_db(d, filename)   # ← DB에 주문 내역 저장
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@forms_bp.route('/forms/orders/save', methods=['POST'])
def save_order_only():
    """PDF 없이 DB에만 저장"""
    try:
        d = request.json
        if not d.get('products'):
            return jsonify({'success': False, 'error': '상품 없음'})
        _save_invoice_to_db(d, filename='')
        return jsonify({'success': True})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@forms_bp.route('/forms/orders', methods=['GET'])
def get_orders():
    """거래처별 주문 내역 조회 (buyer_company 또는 buyer_name으로 검색)"""
    try:
        company = request.args.get('company', '').strip()
        name    = request.args.get('name', '').strip()
        limit   = int(request.args.get('limit', 50))

        conn = _get_db()
        if company:
            rows = conn.execute("""
                SELECT id, trade_date, memo, buyer_company, buyer_name,
                       shipping_name, shipping_tel, shipping_addr,
                       total_amount, deposit, balance, receiver, filename,
                       products_json, created_at
                FROM invoices
                WHERE buyer_company = ?
                ORDER BY trade_date DESC, created_at DESC
                LIMIT ?
            """, (company, limit)).fetchall()
        elif name:
            rows = conn.execute("""
                SELECT id, trade_date, memo, buyer_company, buyer_name,
                       shipping_name, shipping_tel, shipping_addr,
                       total_amount, deposit, balance, receiver, filename,
                       products_json, created_at
                FROM invoices
                WHERE buyer_name = ?
                ORDER BY trade_date DESC, created_at DESC
                LIMIT ?
            """, (name, limit)).fetchall()
        else:
            # 전체 최신 50건
            rows = conn.execute("""
                SELECT id, trade_date, memo, buyer_company, buyer_name,
                       shipping_name, shipping_tel, shipping_addr,
                       total_amount, deposit, balance, receiver, filename,
                       products_json, created_at
                FROM invoices
                ORDER BY trade_date DESC, created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        conn.close()

        result = []
        for r in rows:
            item = dict(r)
            try:
                item['products'] = json.loads(item.pop('products_json') or '[]')
            except:
                item['products'] = []
            result.append(item)

        return jsonify(result)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@forms_bp.route('/forms/orders/all', methods=['GET'])
def get_all_orders():
    """전체 최근 거래내역 조회 (체크리스트/송장/메모 포함)"""
    try:
        limit = int(request.args.get('limit', 100))
        conn = _get_db()
        rows = conn.execute("""
            SELECT id, trade_date, memo, buyer_company, buyer_name,
                   shipping_name, shipping_tel, shipping_addr,
                   total_amount, deposit, balance, receiver, filename,
                   products_json, created_at,
                   chk_invoice, chk_deposit, chk_shipping, chk_tax,
                   tracking_numbers, order_memo
            FROM invoices
            ORDER BY trade_date DESC, created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
        conn.close()

        result = []
        for r in rows:
            item = dict(r)
            try:
                item['products'] = json.loads(item.pop('products_json') or '[]')
            except:
                item['products'] = []
            result.append(item)

        return jsonify({'success': True, 'orders': result})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@forms_bp.route('/forms/orders/<int:order_id>/update', methods=['POST'])
def update_order(order_id):
    """거래 내역 체크리스트/송장/메모 업데이트"""
    try:
        data = request.json
        conn = _get_db()
        conn.execute("""
            UPDATE invoices SET
                chk_invoice = ?, chk_deposit = ?, chk_shipping = ?, chk_tax = ?,
                tracking_numbers = ?, order_memo = ?
            WHERE id = ?
        """, (
            int(data.get('chk_invoice', 0)),
            int(data.get('chk_deposit', 0)),
            int(data.get('chk_shipping', 0)),
            int(data.get('chk_tax', 0)),
            data.get('tracking_numbers', ''),
            data.get('order_memo', ''),
            order_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@forms_bp.route('/forms/orders/delete', methods=['POST'])
def delete_orders():
    """선택된 거래 내역 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'success': False, 'error': '삭제할 항목이 없습니다'})
        conn = _get_db()
        placeholders = ','.join('?' * len(ids))
        conn.execute(f'DELETE FROM invoices WHERE id IN ({placeholders})', ids)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'deleted': len(ids)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@forms_bp.route('/download_invoice/<filename>')
def download_invoice(filename):
    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '잘못된 파일명'}), 400
        fpath = os.path.join(_get_invoice_output_dir(), filename)
        if os.path.exists(fpath):
            mime = 'image/jpeg' if filename.endswith('.jpg') else 'application/pdf'
            return send_file(fpath, as_attachment=True, download_name=filename,
                             mimetype=mime)
        return jsonify({'error': '파일 없음'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500