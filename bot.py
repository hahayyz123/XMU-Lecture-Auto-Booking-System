"""XMU lecture booking with explicit dry-run and encrypted durable tracking."""
import argparse
import hashlib
import json
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from policy import CST, plan

BASE = 'https://econpub.xmu.edu.cn'
HEADERS = ['Seminar types', 'Seminar title', 'Speaker', 'Language', 'Venue',
           'Date and time', 'Reservation accepted from', 'Reservation accepted until',
           'Quota', 'Number of reservations made', 'Remark', 'Reservation status', 'My status', 'Action']


def parse_date(text):
    text = re.sub(r'\([^)]*\)', '', text).strip()
    match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})(?::(\d{2}))?', text)
    if not match:
        raise ValueError('Unsupported lecture date format')
    return datetime.fromisoformat(f'{match[1]}T{match[2]}:{match[3] or "00"}').replace(tzinfo=CST).isoformat()


def decode_row(cells):
    if len(cells) != len(HEADERS):
        raise ValueError('Lecture table structure changed')
    title, starts, opens, closes = cells[1], parse_date(cells[5]), parse_date(cells[6]), parse_date(cells[7])
    raw = cells[12].strip()
    if raw.startswith('已抽中'):
        status = 'won'
    elif raw.startswith('未预约'):
        status = 'unreserved'
    elif raw.startswith('等待抽签'):
        status = 'waiting'
    elif raw:
        status = 'other'
    else:
        status = 'unknown'
    return dict(id=hashlib.sha256((title + '|' + starts + '|' + cells[2]).encode()).hexdigest(),
                title=title, starts_at=starts, opens_at=opens, closes_at=closes,
                venue=cells[4], status=status, raw_status=raw,
                reservable=cells[11] == 'Open for reservation' and 'Reserve this seminar' in cells[13],
                cancellable='Cancel my reservation' in cells[13])


def cipher():
    from cryptography.fernet import Fernet
    return Fernet(os.environ['STATE_KEY'].encode())


def load_state(path):
    if not path.exists():
        return {'version': 1, 'items': {}}
    state = json.loads(cipher().decrypt(path.read_bytes()))
    if state.get('version') != 1 or not isinstance(state.get('items'), dict):
        raise ValueError('Invalid state file')
    return state


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(cipher().encrypt(json.dumps(state, ensure_ascii=False).encode()))
    tmp.replace(path)


def email(subject, body, message_id=None):
    msg = EmailMessage()
    msg['From'] = os.environ['QQ_EMAIL']
    msg['To'] = os.environ.get('NOTIFY_EMAIL') or os.environ['QQ_EMAIL']
    msg['Subject'] = subject
    if message_id:
        msg['Message-ID'] = f'<xmu-{message_id}@lecture.local>'
    msg.set_content(body)
    with smtplib.SMTP_SSL('smtp.qq.com', 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(os.environ['QQ_EMAIL'], os.environ['QQ_SMTP_CODE'])
        smtp.send_message(msg)


def scan(page, student):
    page.goto(f'{BASE}/event/LectureOrder2.aspx?stuno={student}', wait_until='domcontentloaded')
    table = page.get_by_role('table').filter(has=page.get_by_role('columnheader', name='My status', exact=True))
    table.wait_for(state='visible', timeout=30000)
    # Prevent operating on another user's restored session.
    if page.locator('strong').filter(has_text=re.compile('^' + re.escape(student) + '$')).count() != 1:
        raise RuntimeError('Account identity could not be verified')
    headers = table.get_by_role('columnheader').all_text_contents()
    if [x.strip() for x in headers] != HEADERS:
        raise RuntimeError('Lecture table headers changed')
    rows = []
    for row in table.get_by_role('row').all()[1:]:
        cells = [x.strip() for x in row.get_by_role('cell').all_text_contents()]
        rows.append(decode_row(cells))
    if len({r['id'] for r in rows}) != len(rows):
        raise RuntimeError('Ambiguous lecture identity')
    return rows


def act(page, row, action):
    target = page.get_by_role('row').filter(has=page.get_by_role('cell', name=row['title'], exact=True))
    target = target.filter(has=page.get_by_role('cell', name=row['raw_status'], exact=True))
    if target.count() != 1:
        raise RuntimeError('Reservation row is ambiguous')
    name = 'Reserve this seminar' if action == 'reserve' else 'Cancel my reservation'
    target.get_by_role('link', name=name, exact=True).click(timeout=20000)


def run(args):
    from playwright.sync_api import sync_playwright
    student = os.environ['XMU_STUNO']
    if not re.fullmatch(r'\d+', student):
        raise ValueError('Invalid student number format')
    path = Path(args.state)
    state = load_state(path)
    if args.apply:
        cipher()  # Validate before any mutation.
        for name in ('QQ_EMAIL', 'QQ_SMTP_CODE'):
            if not os.environ.get(name):
                raise ValueError('Missing mail configuration')
    auth = json.loads(os.environ['XMU_STORAGE_STATE']) if os.environ.get('XMU_STORAGE_STATE') else args.auth
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(storage_state=auth, timezone_id='Asia/Shanghai')
        page = context.new_page()
        # Do not auto-accept unknown confirmation wording. Log no raw page or credential data.
        page.on('dialog', lambda dialog: dialog.dismiss())
        rows = scan(page, student)
        actions = plan(rows, datetime.now(CST), args.mode, state['items'])
        counts = {}
        for action in actions:
            counts[action['action']] = counts.get(action['action'], 0) + 1
        print(json.dumps({'mode': args.mode, 'dry_run': not args.apply, 'actions': counts}))
        if not args.apply:
            browser.close()
            return
        # Notify from a previously confirmed win even if the lecture left the active list.
        for item_id, record in state['items'].items():
            if record.get('won') and not record.get('notified'):
                email('讲座已抽中', f"你已抽中：{record['title']}\n时间：{record['starts_at']}\n地点：{record['venue']}", item_id)
                record['notified'] = True
                save_state(path, state)
        for action in actions:
            item_id, kind = action['id'], action['action']
            fresh = {r['id']: r for r in scan(page, student)}
            if item_id not in fresh:
                continue
            row = fresh[item_id]
            # Recheck status and clock immediately before every side effect.
            allowed = plan([row], datetime.now(CST), args.mode, state['items'])
            if not any(a['action'] == kind for a in allowed):
                continue
            if kind == 'notify_winner':
                record = state['items'][item_id]
                record['won'] = True
                save_state(path, state)
                if not record.get('notified'):
                    email('讲座已抽中', f"你已抽中：{row['title']}\n时间：{row['starts_at']}\n地点：{row['venue']}", item_id)
                    record['notified'] = True
                    save_state(path, state)
            elif kind in ('reserve', 'cancel'):
                if kind == 'reserve':
                    state['items'][item_id] = {**row, 'phase': 'reserve_pending'}
                else:
                    state['items'][item_id]['phase'] = 'cancel_pending'
                # Write ahead: uncertain outcomes must not cause repeated booking.
                save_state(path, state)
                act(page, row, kind)
                after = {r['id']: r for r in scan(page, student)}.get(item_id)
                expected = ('waiting', 'won') if kind == 'reserve' else ('unreserved',)
                if not after or after['status'] not in expected:
                    raise RuntimeError('Action outcome unconfirmed; manual review required')
                state['items'][item_id]['phase'] = 'reserved' if kind == 'reserve' else 'cancelled'
                save_state(path, state)
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['reserve', 'results'])
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--auth', default='.auth/session.json')
    parser.add_argument('--state', default='runtime/state.enc')
    args = parser.parse_args()
    try:
        run(args)
    except Exception as exc:
        print('Run failed: ' + type(exc).__name__ + '; check login, configuration or action outcome locally.')
        if args.apply:
            try:
                email('讲座自动化需要处理', '本次运行失败，可能是登录失效、页面变化或操作结果未确认。请检查 GitHub Actions，并在本地验证登录。')
            except Exception:
                print('Failure email could not be sent.')
        raise SystemExit(1)
