"""User-operated local sign-in. Never submit credentials automatically."""
from pathlib import Path
from playwright.sync_api import sync_playwright

if __name__ == '__main__':
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://econpub.xmu.edu.cn/', wait_until='domcontentloaded')
        input('请在打开的浏览器手动登录并进入讲座预约列表，然后回到这里按回车。')
        pages = [p for p in context.pages if p.url.startswith('https://econpub.xmu.edu.cn/event/LectureOrder2.aspx')]
        if len(pages) != 1 or pages[0].get_by_role('columnheader', name='My status', exact=True).count() != 1:
            raise SystemExit('未找到已登录的讲座列表，没有保存会话。')
        Path('.auth').mkdir(exist_ok=True)
        context.storage_state(path='.auth/session.json')
        print('登录会话已保存到 .auth/session.json。请勿提交此文件或发送到聊天。')
        browser.close()
