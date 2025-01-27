from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(record_har_path="network.har")
    page = context.new_page()

    page.goto("https://ubiwebauth.ubisoft.com/login?appId=685a3038-2b04-47ee-9c5a-6403381a46aa")
    context.close()