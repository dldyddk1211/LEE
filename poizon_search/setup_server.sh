#!/bin/bash
# =============================================
# Mac 운영 서버 초기 폴더 생성 + 권한 설정
# 루트: /theone/srv/data
# 실행: sudo bash setup_server.sh
# =============================================

set -e

DATA_ROOT="/theone/srv/data"
APP_USER="${SUDO_USER:-$(whoami)}"   # 실행한 사용자 계정으로 소유권 설정

echo "======================================"
echo "  운영 서버 데이터 폴더 초기화"
echo "  루트  : $DATA_ROOT"
echo "  사용자: $APP_USER"
echo "======================================"

# ---- 폴더 생성 ----
mkdir -p \
  "$DATA_ROOT/customers/raw" \
  "$DATA_ROOT/customers/processed" \
  "$DATA_ROOT/customers/exports" \
  "$DATA_ROOT/orders/raw" \
  "$DATA_ROOT/orders/processed" \
  "$DATA_ROOT/orders/invoices" \
  "$DATA_ROOT/products/metadata" \
  "$DATA_ROOT/products/analytics" \
  "$DATA_ROOT/products/images" \
  "$DATA_ROOT/operations/hr" \
  "$DATA_ROOT/operations/finance" \
  "$DATA_ROOT/operations/legal" \
  "$DATA_ROOT/operations/projects" \
  "$DATA_ROOT/backups/daily" \
  "$DATA_ROOT/backups/weekly" \
  "$DATA_ROOT/backups/monthly" \
  "$DATA_ROOT/logs" \
  "$DATA_ROOT/tmp/shots" \
  "$DATA_ROOT/vault"

echo "✅ 폴더 생성 완료"

# ---- 소유권 설정 ----
chown -R "$APP_USER":staff "$DATA_ROOT"
echo "✅ 소유권 설정: $APP_USER"

# ---- 기본 권한 (755) ----
chmod -R 755 "$DATA_ROOT"

# ---- 민감 폴더 권한 강화 (750) ----
chmod 750 "$DATA_ROOT/customers/raw"
chmod 750 "$DATA_ROOT/customers/processed"
chmod 750 "$DATA_ROOT/orders/raw"
chmod 750 "$DATA_ROOT/orders/processed"
chmod 750 "$DATA_ROOT/operations/hr"
chmod 750 "$DATA_ROOT/operations/finance"
chmod 750 "$DATA_ROOT/operations/legal"

# ---- vault 최강 제한 (700) ----
chmod 700 "$DATA_ROOT/vault"

echo "✅ 권한 설정 완료"

# ---- 결과 출력 ----
echo ""
echo "======================================"
echo "  폴더 구조 확인"
echo "======================================"
find "$DATA_ROOT" -type d | sort | while read dir; do
  perm=$(stat -f "%Sp" "$dir" 2>/dev/null || stat -c "%A" "$dir" 2>/dev/null)
  echo "  $perm  $dir"
done

echo ""
echo "======================================"
echo "  ✅ 서버 초기화 완료!"
echo "======================================"
