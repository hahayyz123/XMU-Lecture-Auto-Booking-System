"""User-operated local sign-in. Never submit credentials automatically."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto('https://econpub.xmu.edu.cn/', wait_until='domcontentloaded')
        # Keep Playwright's event loop running while the user signs in and opens popups.
        await asyncio.to_thread(input, '请在打开的浏览器手动登录并进入讲座预约列表，然后回到这里按回车。')
        pages = [p for p in context.pages if p.url.startswith('https://econpub.xmu.edu.cn/event/LectureOrder2.aspx')]
        if not pages:
            raise SystemExit('未找到已登录的讲座列表，没有保存会话。')
        await pages[-1].get_by_role('columnheader', name='My status', exact=True).wait_for(state='visible', timeout=30000)
        Path('.auth').mkdir(exist_ok=True)
        await context.storage_state(path='.auth/session.json')
        print('登录会话已保存到 .auth/session.json。请勿提交此文件或发送到聊天。')
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
