# ==========================================
# 서식 / 양식 기능 - Blueprint (PDF 버전)
# ==========================================

import os
import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file

forms_bp = Blueprint('forms', __name__)

FORMS_DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
FORMS_HTML         = os.path.join(FORMS_DATA_DIR, 'forms.html')
CUSTOMERS_FILE     = os.path.join(FORMS_DATA_DIR, 'customers.json')
INVOICE_OUTPUT_DIR = os.path.join(FORMS_DATA_DIR, 'invoices')

def _ensure_dirs():
    os.makedirs(FORMS_DATA_DIR, exist_ok=True)
    os.makedirs(INVOICE_OUTPUT_DIR, exist_ok=True)

_ensure_dirs()

def _load_customers():
    if not os.path.exists(CUSTOMERS_FILE):
        return []
    with open(CUSTOMERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_customers(customers):
    with open(CUSTOMERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(customers, f, ensure_ascii=False, indent=2)

def _register_korean_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font_paths = [
        r'C:\Windows\Fonts\malgun.ttf',
        r'C:\Windows\Fonts\gulim.ttc',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    ]
    bold_paths = [
        r'C:\Windows\Fonts\malgunbd.ttf',
        r'C:\Windows\Fonts\gulim.ttc',
        '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf',
    ]
    fn, fb = 'Helvetica', 'Helvetica-Bold'
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('Korean', fp))
                fn = 'Korean'
                break
            except: pass
    for fp in bold_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('KoreanBold', fp))
                fb = 'KoreanBold'
                break
            except: pass
    return fn, fb

def _make_invoice_pdf(d, filepath):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    fn, fb = _register_korean_font()

    buyer        = d.get('buyer', {})
    supplier     = d.get('supplier', {})
    products     = d.get('products', [])
    trade_date   = d.get('date', '')
    total_amount = d.get('totalAmount', 0)
    deposit      = d.get('deposit', 0)
    balance      = d.get('balance', 0)
    receiver     = d.get('receiver', '')

    W, H = A4
    cv = canvas.Canvas(filepath, pagesize=A4)
    cv.setStrokeColor(colors.black)

    def x(v): return v * mm
    def y(v): return H - v * mm

    GRAY = colors.HexColor('#D9D9D9')
    DARK = colors.HexColor('#1a1a2e')
    WHITE = colors.white

    def cell(px, py, pw, ph, txt='', bold=False, size=9,
             bg=None, fg=colors.black, align='center', lpad=2, lw=0.5):
        cv.setLineWidth(lw)
        if bg:
            cv.setFillColor(bg)
            cv.rect(x(px), y(py+ph), x(pw), x(ph), fill=1, stroke=1)
            cv.setFillColor(fg)
        else:
            cv.setFillColor(fg)
            cv.rect(x(px), y(py+ph), x(pw), x(ph), fill=0, stroke=1)
        cv.setFont(fb if bold else fn, size)
        txt = str(txt) if txt is not None else ''
        # 텍스트 수직 중앙: 셀 중간 - 폰트 높이의 절반(약 size*0.3mm)
        # 수직 중앙: baseline = 셀중앙 - (ascent≈0.72 - descent≈0.21)/2 * size
        ty = y(py + ph/2) - (size * 0.25)
        if align == 'center':
            cv.drawCentredString(x(px + pw/2), ty, txt)
        elif align == 'left':
            cv.drawString(x(px + lpad), ty, txt)
        else:
            cv.drawRightString(x(px + pw - lpad), ty, txt)
        cv.setFillColor(colors.black)

    # ── 제목 ──
    cv.setLineWidth(2)
    cell(10, 5, 190, 16, '거  래  명  세  서', bold=True, size=20, lw=2)

    # ── 거래일자 ──
    cell(10, 23, 35, 7, '거 래 일 자', bold=True, size=8, bg=GRAY)
    cell(45, 23, 80, 7, trade_date or '', size=9)
    cell(125,23, 75, 7, d.get('memo',''), size=8)

    # ── 당사자 헤더 ──
    cell(10,  32, 95, 7, '수  요  자', bold=True, size=10, bg=GRAY)
    cell(105, 32, 95, 7, '공  급  자', bold=True, size=10, bg=GRAY)

    # ── 당사자 정보 ──
    def party(bx, data):
        rows = [
            ('사업자번호', data.get('bizno','')),
            ('상  호',    data.get('company','')),
            ('성  명',    data.get('name','')),
            ('연  락  처', data.get('tel','')),
            ('소  재  지', data.get('addr','')),
            ('업태/종목',  f"{data.get('biztype','')} / {data.get('bizitem','')}"),
        ]
        cy = 39
        for lbl, val in rows:
            rh = 9 if lbl == '소  재  지' else 7
            cell(bx,    cy, 23, rh, lbl, bold=True, size=8, bg=GRAY)
            cell(bx+23, cy, 72, rh, val, size=8, align='left')
            cy += rh

    party(10,  buyer)
    party(105, supplier)

    end_y = 39 + 7*5 + 9  # 5개×7 + 소재지9

    # ── 합계금액 (x=10~200, 총 190mm) ──
    # 상품 컬럼: 품번(10~40) 품명(40~90) 수량(90~110) 소비자가(110~135) 할인율(135~150) 공급가(150~170) 합계(170~200)
    cell(10,  end_y,  40, 10, '합 계 금 액', bold=True, size=10, bg=GRAY)
    cell(50,  end_y, 100, 10, f'₩  {total_amount:,}', bold=True, size=13, align='left', lpad=8)
    cell(150, end_y,  50, 10, '', size=9)  # 오른쪽 여백 (공급가+합계 열)

    # ── 상품 헤더 ──
    ph = end_y + 12
    cols = [
        (10, 30,'품  번'), (40, 50,'품  명'), (90,20,'수 량'),
        (110,25,'소비자가'),(135,15,'할인율'),(150,20,'공급가'),(170,30,'합  계')
    ]
    for cx,cw,cl in cols:
        cell(cx, ph, cw, 7, cl, bold=True, size=8, bg=DARK, fg=WHITE)

    # ── 상품 행 ──
    for i in range(11):
        ry = ph + 7 + i * 8
        p  = products[i] if i < len(products) else {}
        cell(10,  ry, 30, 8, p.get('code',''), size=8)
        cell(40,  ry, 50, 8, p.get('name',''), size=8, align='left')
        cell(90,  ry, 20, 8, f"{p['qty']:,}"    if p.get('qty')    else '', size=8)
        cell(110, ry, 25, 8, f"{p['price']:,}"  if p.get('price')  else '', size=8)
        cell(135, ry, 15, 8, f"{p['disc']}%"    if p.get('disc')   else '', size=8)
        cell(150, ry, 20, 8, f"{p['supply']:,}" if p.get('supply') else '', size=8)
        cell(170, ry, 30, 8, f"{p['total']:,}"  if p.get('total')  else '', size=8)

    # ── 입금계좌 ──
    by = ph + 7 + 11 * 8
    cell(10, by, 190, 7,
         f"  입금 계좌 : {supplier.get('bank','')}", size=8, align='left')

    # ── 총수량/합계 행 ── (상품 컬럼에 정확히 정렬)
    ty2 = by + 7
    total_qty = sum(p.get('qty',0) for p in products)
    total_sum = sum(p.get('total',0) for p in products)
    cell(10,  ty2,  80, 8, '총  수  량',       bold=True, size=9, bg=GRAY)  # 품번+품명 (10~90)
    cell(90,  ty2,  54, 8, f'{total_qty:,}',   size=9)                      # 수량~할인율 (90~144)
    cell(144, ty2,  20, 8, '합    계',          bold=True, size=9, bg=GRAY)  # label (144~164)
    cell(164, ty2,  36, 8, f'₩ {total_sum:,}', size=9)                      # 합계값 (164~200) +20%

    # ── 입금/잔금/인수자 행 ──
    fy2 = ty2 + 8
    cell(10,  fy2,  30, 9, '입  금',            bold=True, size=9, bg=GRAY)  # (10~40)
    cell(40,  fy2, 104, 9, f'₩ {deposit:,}',   size=9)                      # (40~144)
    cell(144, fy2,  20, 9, '잔  금',            bold=True, size=9, bg=GRAY)  # label (144~164)
    cell(164, fy2,  26, 9, f'₩ {balance:,}',   size=9)                      # 잔금값 (164~190) +30%
    cell(190, fy2,  10, 9, receiver or '(인)',  size=8)                      # 인수자 (190~200)

    cv.save()


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
        # 파일명: 날짜_업체명_메모.pdf (메모 없으면 날짜_업체명.pdf)
        # 파일명에 사용 불가한 문자 제거
        import re
        safe_buyer = re.sub(r'[\\/:*?"<>|]', '', buyer_name)[:20]
        safe_memo  = re.sub(r'[\\/:*?"<>|]', '', memo)[:20]
        if safe_memo:
            filename = f"{date_str}_{safe_buyer}_{safe_memo}.pdf"
        else:
            filename = f"{date_str}_{safe_buyer}.pdf"
        filepath   = os.path.join(INVOICE_OUTPUT_DIR, filename)
        _make_invoice_pdf(d, filepath)
        return jsonify({'success': True, 'filename': filename})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@forms_bp.route('/download_invoice/<filename>')
def download_invoice(filename):
    try:
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': '잘못된 파일명'}), 400
        fpath = os.path.join(INVOICE_OUTPUT_DIR, filename)
        if os.path.exists(fpath):
            return send_file(fpath, as_attachment=True, download_name=filename,
                             mimetype='application/pdf')
        return jsonify({'error': '파일 없음'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500