"""
텔레그램 알림 모듈
===================
설정 방법:
1. 텔레그램에서 @BotFather 에게 /newbot 명령으로 봇 생성 → BOT_TOKEN 발급
2. 봇과 대화 후 https://api.telegram.org/bot{BOT_TOKEN}/getUpdates 접속 → chat_id 확인
3. 아래 BOT_TOKEN, CHAT_ID 에 실제 값 입력
"""

import requests
import threading

# ──────────────────────────────────────
# ★ 여기에 실제 값을 입력하세요 ★
BOT_TOKEN = '8771610716:AAEVKdw6GU97fNzir18rbWrVeA_ItD2be0E'
CHAT_ID   = '6382036414'
# ──────────────────────────────────────

TELEGRAM_URL = 'https://api.telegram.org/bot{token}/sendMessage'


def send_telegram(message: str, silent: bool = False) -> bool:
    """
    텔레그램 메시지 전송
    - silent=True: 무음 알림
    - 설정값(BOT_TOKEN/CHAT_ID)이 없으면 조용히 스킵
    """
    if not BOT_TOKEN or not CHAT_ID:
        return False

    try:
        url = TELEGRAM_URL.format(token=BOT_TOKEN)
        payload = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML',
            'disable_notification': silent,
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f'[Telegram] 전송 실패: {e}')
        return False


def send_telegram_async(message: str, silent: bool = False):
    """백그라운드 스레드로 전송 (메인 로직 블로킹 없음)"""
    threading.Thread(
        target=send_telegram,
        args=(message, silent),
        daemon=True
    ).start()
