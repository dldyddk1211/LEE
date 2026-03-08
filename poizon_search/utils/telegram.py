"""
텔레그램 알림 + 명령어 수신 + Claude AI 챗봇 모듈
===================================
설정 방법:
1. 텔레그램에서 @BotFather 에게 /newbot 명령으로 봇 생성 → BOT_TOKEN 발급
2. 봇과 대화 후 https://api.telegram.org/bot{BOT_TOKEN}/getUpdates 접속 → chat_id 확인
3. 아래 BOT_TOKEN, CHAT_ID, ANTHROPIC_API_KEY 에 실제 값 입력
"""

import base64
import time
import requests
import threading

# ──────────────────────────────────────
# ★ 여기에 실제 값을 입력하세요 ★
BOT_TOKEN        = '8771610716:AAEVKdw6GU97fNzir18rbWrVeA_ItD2be0E'
CHAT_ID          = '6382036414'
ANTHROPIC_API_KEY = ''   # ← 직접 입력하거나 환경변수 ANTHROPIC_API_KEY 설정
# ──────────────────────────────────────

BASE_URL = f'https://api.telegram.org/bot{BOT_TOKEN}'

# 명령어 핸들러 등록 테이블 { '/cmd': fn(args) }
_handlers = {}
_last_update_id = 0

# Claude 대화 히스토리 (멀티턴 유지)
_claude_history = []
_claude_lock = threading.Lock()


# ══════════════════════════════════════
# 메시지 전송
# ══════════════════════════════════════

def send_telegram(message: str, silent: bool = False, use_html: bool = True) -> bool:
    """텔레그램 메시지 전송 (4096자 초과시 분할)"""
    if not BOT_TOKEN or not CHAT_ID:
        return False

    def _send_chunk(text: str, html: bool):
        payload = {
            'chat_id': CHAT_ID,
            'text': text,
            'disable_notification': silent,
        }
        if html:
            payload['parse_mode'] = 'HTML'
        try:
            resp = requests.post(f'{BASE_URL}/sendMessage', json=payload, timeout=10)
            if resp.status_code != 200 and html:
                # HTML 파싱 실패시 plain text 로 재시도
                payload.pop('parse_mode')
                resp = requests.post(f'{BASE_URL}/sendMessage', json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f'[Telegram] 전송 실패: {e}')
            return False

    # 4096자 초과시 분할 전송
    max_len = 4000
    if len(message) <= max_len:
        return _send_chunk(message, use_html)

    ok = True
    for i in range(0, len(message), max_len):
        ok = _send_chunk(message[i:i + max_len], use_html) and ok
    return ok


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
# Claude AI 챗봇
# ══════════════════════════════════════

CLAUDE_SYSTEM = """당신은 Python/Flask 웹 개발 전문 코딩 어시스턴트입니다.
현재 프로젝트: Flask 기반 포이즌(Poizon) 가격 검색 사이트
- 무신사 / 크림 / 포이즌 가격 자동 검색
- 구글 시트 재고 동기화
- 텔레그램 알림 및 명령어 제어
- SQLite DB, Playwright, SSE(서버전송이벤트) 사용

코드 질문에는 항상 실제 사용 가능한 코드를 제공하세요.
답변은 간결하고 실용적으로, 텔레그램 메시지 길이를 고려해 핵심만 답하세요."""


def _download_telegram_photo(file_id: str) -> bytes | None:
    """텔레그램에서 사진 다운로드 → bytes 반환"""
    try:
        r = requests.get(f'{BASE_URL}/getFile', params={'file_id': file_id}, timeout=10)
        file_path = r.json()['result']['file_path']
        img_r = requests.get(
            f'https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}',
            timeout=30
        )
        return img_r.content
    except Exception as e:
        print(f'[Telegram] 사진 다운로드 실패: {e}')
        return None


def _ask_claude(user_text: str = '', image_bytes: bytes | None = None) -> str:
    """Claude API 호출 (멀티턴 대화 유지)"""
    if not ANTHROPIC_API_KEY:
        return '⚠️ ANTHROPIC_API_KEY 가 설정되지 않았습니다.\nutils/telegram.py 에서 ANTHROPIC_API_KEY 를 입력해주세요.'

    try:
        import anthropic

        # 사용자 메시지 구성
        user_content = []
        if image_bytes:
            b64 = base64.standard_b64encode(image_bytes).decode()
            user_content.append({
                'type': 'image',
                'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}
            })
        if user_text:
            user_content.append({'type': 'text', 'text': user_text})

        if not user_content:
            return '메시지가 비어있습니다.'

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        with _claude_lock:
            _claude_history.append({'role': 'user', 'content': user_content})

            response = client.messages.create(
                model='claude-haiku-4-5',
                max_tokens=1500,
                system=CLAUDE_SYSTEM,
                messages=_claude_history,
            )

            reply_text = response.content[0].text
            _claude_history.append({'role': 'assistant', 'content': reply_text})

            # 히스토리 30턴(60개 메시지) 이상이면 오래된것 제거
            if len(_claude_history) > 60:
                _claude_history[:] = _claude_history[-40:]

        return reply_text

    except Exception as e:
        return f'❌ Claude 오류: {e}'


def clear_claude_history():
    """Claude 대화 히스토리 초기화"""
    with _claude_lock:
        _claude_history.clear()
    return '🗑️ Claude 대화 기록이 초기화되었습니다.'


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

            text    = msg.get('text', '').strip()
            caption = msg.get('caption', '').strip()
            photos  = msg.get('photo', [])

            # ── 슬래시 명령어 처리 ──
            if text.startswith('/'):
                parts = text.split()
                cmd   = parts[0].lower()
                args  = parts[1:]

                # /reset : Claude 히스토리 초기화
                if cmd == '/reset':
                    send_telegram(clear_claude_history())
                    continue

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
                    send_telegram(f'❓ 알 수 없는 명령어: <code>{cmd}</code>\n\n사용 가능:\n{cmds}\n  /reset (Claude 대화 초기화)')
                continue

            # ── 사진 메시지 → Claude에게 전달 ──
            if photos:
                best_photo = max(photos, key=lambda p: p.get('file_size', 0))
                send_telegram('🖼️ 사진 분석 중...', silent=True)
                image_bytes = _download_telegram_photo(best_photo['file_id'])
                threading.Thread(
                    target=lambda t=caption, b=image_bytes: send_telegram(_ask_claude(t, b)),
                    daemon=True
                ).start()
                continue

            # ── 일반 텍스트 → Claude에게 전달 ──
            if text:
                print(f'[Telegram→Claude] {text[:50]}')
                send_telegram('💭 생각 중...', silent=True)
                def _reply(t=text):
                    try:
                        result = _ask_claude(t)
                        send_telegram(result)
                    except Exception as e:
                        send_telegram(f'❌ 스레드 오류: {e}')
                threading.Thread(target=_reply, daemon=True).start()

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
