"""
텔레그램 알림 + 명령어 수신 모듈
===================================
설정 방법:
1. 텔레그램에서 @BotFather 에게 /newbot 명령으로 봇 생성 → BOT_TOKEN 발급
2. 봇과 대화 후 https://api.telegram.org/bot{BOT_TOKEN}/getUpdates 접속 → chat_id 확인
3. 아래 BOT_TOKEN, CHAT_ID 에 실제 값 입력
"""

import time
import requests
import threading

# ──────────────────────────────────────
# ★ 여기에 실제 값을 입력하세요 ★
BOT_TOKEN = '8771610716:AAEVKdw6GU97fNzir18rbWrVeA_ItD2be0E'
CHAT_ID   = '6382036414'
# ──────────────────────────────────────

BASE_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'

# 명령어 핸들러 등록 테이블 { '/cmd': fn(args) }
_handlers = {}
_last_update_id = 0


# ══════════════════════════════════════
# 메시지 전송
# ══════════════════════════════════════

def send_telegram(message: str, silent: bool = False) -> bool:
    """텔레그램 메시지 전송"""
    if not BOT_TOKEN or not CHAT_ID:
        return False
    try:
        resp = requests.post(
            f'{BASE_URL}/sendMessage',
            json={
                'chat_id': CHAT_ID,
                'text': message,
                'parse_mode': 'HTML',
                'disable_notification': silent,
            },
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f'[Telegram] 전송 실패: {e}')
        return False


def send_telegram_async(message: str, silent: bool = False):
    """백그라운드 스레드로 전송"""
    threading.Thread(target=send_telegram, args=(message, silent), daemon=True).start()


# ══════════════════════════════════════
# 명령어 핸들러 등록
# ══════════════════════════════════════

def register_handler(command: str, fn):
    """
    명령어 핸들러 등록
    예: register_handler('/status', lambda args: '작업 없음')
    fn(args: list[str]) -> str  (반환값이 텔레그램으로 전송됨)
    """
    _handlers[command.lower()] = fn


# ══════════════════════════════════════
# 폴링 루프
# ══════════════════════════════════════

def _poll_once():
    """새 메시지 1회 확인 및 처리"""
    global _last_update_id
    try:
        resp = requests.get(
            f'{BASE_URL}/getUpdates',
            params={'offset': _last_update_id + 1, 'timeout': 2},
            timeout=10
        )
        data = resp.json()
        if not data.get('ok'):
            return

        for update in data.get('result', []):
            _last_update_id = update['update_id']

            msg = update.get('message', {})
            if not msg:
                continue

            # 인증된 사용자만 처리
            sender_id = str(msg.get('chat', {}).get('id', ''))
            if sender_id != str(CHAT_ID):
                continue

            text = msg.get('text', '').strip()
            if not text.startswith('/'):
                continue

            parts = text.split()
            cmd   = parts[0].lower()
            args  = parts[1:]

            print(f'[Telegram] 명령어 수신: {text}')

            handler = _handlers.get(cmd)
            if handler:
                try:
                    reply = handler(args)
                    if reply:
                        send_telegram(reply)
                except Exception as e:
                    send_telegram(f'❌ 오류: {e}')
            else:
                cmds = '\n'.join(f'  {c}' for c in _handlers)
                send_telegram(f'❓ 알 수 없는 명령어: <code>{cmd}</code>\n\n사용 가능:\n{cmds}')

    except Exception as e:
        print(f'[Telegram] 폴링 오류: {e}')


def _poll_loop():
    """백그라운드 폴링 루프 (3초마다)"""
    print('[Telegram] 명령어 폴링 시작')
    while True:
        _poll_once()
        time.sleep(3)


def start_polling():
    """백그라운드에서 텔레그램 명령어 폴링 시작"""
    if not BOT_TOKEN or not CHAT_ID:
        print('[Telegram] 토큰/CHAT_ID 미설정 → 폴링 스킵')
        return
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()
