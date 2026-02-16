# Selenium 통합 가이드

## 📋 파일 구조

```
E:\vscode\poizon_gui_search\
├── app.py                          # Flask 앱 (수정 필요)
├── poizon_data/
│   ├── poizon_search.py           # POIZON 검색 + 엑셀 저장 (수정 필요)
│   └── sourcing_search.py         # 네이버 구매처 검색 (NEW)
└── outputs/
    └── sourcing_result_*.xlsx     # 자동 저장되는 엑셀
```

## 🔧 적용 방법

### 1단계: sourcing_search.py 복사

다운로드 받은 `sourcing_search.py` 파일을:
```
E:\vscode\poizon_gui_search\poizon_data\sourcing_search.py
```
이 위치에 복사하세요.

---

### 2단계: poizon_search.py에 함수 추가

`poizon_data\poizon_search.py` 파일을 VSCode로 열고:

**파일 맨 위 import 부분에 추가:**
```python
from datetime import datetime
from openpyxl.styles import Font, Alignment, PatternFill
```

**파일 맨 아래에 함수 추가:**

`excel_save_function.py`의 `save_sourcing_results_to_excel` 함수를 복사해서
`poizon_search.py` 파일 맨 끝에 붙여넣기

---

### 3단계: app.py 수정

`app.py` 파일 수정:

**Before:**
```python
from poizon_data.poizon_search import run_sourcing_for_products
```

**After:**
```python
from poizon_data.sourcing_search import run_sourcing_for_products
```

즉, import 경로를 `poizon_search`에서 `sourcing_search`로 변경!

---

### 4단계: Flask 서버 재시작

```powershell
# 기존 서버 중단 (Ctrl+C)

# 재시작
py -u app.py
```

---

## ✅ 테스트

1. 브라우저에서 `http://localhost:3000` 접속
2. 엑셀 업로드
3. **구매처 검색** 버튼 클릭
4. Chrome 브라우저 자동으로 열림
5. 네이버 로그인 (2차 인증 직접 처리)
6. 상품 검색 진행

**중단 테스트:**
- 검색 중 **멈춤** 버튼 클릭
- `outputs` 폴더에 엑셀 파일 생성 확인!

---

## 📊 엑셀 파일 구조

| # | 상품번호 | 검색결과 | 쇼핑몰 | 상품명 | 가격 | 배송비 | URL | 비고 |
|---|---------|---------|-------|--------|-----|-------|-----|------|
| 1 | AR3565-600 | 성공 | 네이버쇼핑 | ... | 120,000 | 무료 | https://... | |
| 2 | HF9460-010 | 실패 | | | | | | 오류: 접속제한 |

---

## 🚨 문제 해결

**Q: Chrome 버전 오류**
```
A: Chrome 브라우저 업데이트 또는
   py -m pip install --upgrade undetected-chromedriver
```

**Q: 엑셀 저장 안 됨**
```
A: poizon_search.py에 save_sourcing_results_to_excel 함수 추가 확인
```

**Q: import 오류**
```
A: app.py에서 import 경로 확인
   from poizon_data.sourcing_search import run_sourcing_for_products
```

---

## 📝 주요 기능

✅ Selenium으로 네이버 차단 우회
✅ 2차 인증 자동 대기
✅ 중단 시 자동 엑셀 저장
✅ 상품별 대기 시간 (10-20초)
✅ 접속 제한 시 5분 대기
