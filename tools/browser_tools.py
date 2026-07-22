"""Browser automation tools using Playwright — form analysis, filling, screenshots.

Canonical location — replaces app/graph/tools/browser_tools.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FormField:
    field_id: str
    selector: str
    label: str
    type: str
    required: bool = False
    pattern: str | None = None
    maxlength: int | None = None
    minlength: int | None = None
    accepted_values: list[str] | None = None
    placeholder: str | None = None
    css_class: str | None = None


class BrowserTools:
    """Playwright-based browser automation for form analysis and filling."""

    DEFAULT_VIEWPORT = {"width": 1280, "height": 1024}
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
    TYPING_DELAY_MS = 30
    MAX_NAVIGATION_SEC = 30
    MAX_FILL_RETRIES = 3

    def __init__(self):
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None

    async def _ensure_browser(self):
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            self._context = await self._browser.new_context(
                viewport=self.DEFAULT_VIEWPORT, user_agent=self.USER_AGENT,
                locale="en-US", timezone_id="America/New_York",
            )
            self._page = await self._context.new_page()
            logger.info("Playwright browser launched")
        except ImportError:
            logger.warning("playwright not installed")
            raise
        except Exception as e:
            logger.error(f"Failed to launch Playwright: {e}")
            raise

    async def navigate(self, url: str) -> bool:
        try:
            await self._ensure_browser()
            response = await self._page.goto(url, wait_until="networkidle", timeout=self.MAX_NAVIGATION_SEC * 1000)
            status = response.status if response else 0
            if status and 200 <= status < 400:
                return True
            logger.warning(f"Navigation to {url} returned status {status}")
            return False
        except Exception as e:
            logger.error(f"Navigation failed: {url}: {e}")
            return False

    async def extract_form_fields(self, url: str | None = None) -> list[FormField]:
        if url:
            ok = await self.navigate(url)
            if not ok:
                return []
        await self._ensure_browser()
        try:
            fields = await self._page.evaluate("""
                () => {
                    const forms = document.querySelectorAll('form');
                    const fields = [];
                    let fieldCounter = 0;
                    forms.forEach((form, formIdx) => {
                        const elements = form.querySelectorAll('input, select, textarea, button[type="submit"]');
                        elements.forEach((el) => {
                            if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') return;
                            let label = '';
                            const labelEl = document.querySelector(`label[for="${el.id}"]`);
                            if (labelEl) label = labelEl.innerText;
                            else if (el.placeholder) label = el.placeholder;
                            else if (el.name) label = el.name;
                            else if (el.getAttribute('aria-label')) label = el.getAttribute('aria-label');
                            let acceptedValues = null;
                            if (el.tagName === 'SELECT') {
                                acceptedValues = Array.from(el.options).filter(o => o.value).map(o => o.value);
                            } else if (el.type === 'radio') {
                                const radios = document.querySelectorAll(`input[name="${el.name}"]`);
                                acceptedValues = Array.from(radios).map(r => r.value);
                            }
                            fieldCounter++;
                            fields.push({
                                field_id: el.id || `field_${fieldCounter}`,
                                selector: `#${el.id}` || `form:nth-child(${formIdx+1}) ${el.tagName.toLowerCase()}[name="${el.name}"]`,
                                label: label,
                                type: el.type || el.tagName.toLowerCase(),
                                required: el.required || false,
                                pattern: el.pattern || null,
                                maxlength: el.maxLength || null,
                                minlength: el.minLength || null,
                                accepted_values: acceptedValues,
                                placeholder: el.placeholder || null,
                                css_class: el.className || null,
                            });
                        });
                    });
                    return fields;
                }
            """)
            return [FormField(**f) for f in fields]
        except Exception as e:
            logger.error(f"Failed to extract form fields: {e}")
            return []

    async def fill_field(self, selector: str, value: str) -> bool:
        await self._ensure_browser()
        for attempt in range(self.MAX_FILL_RETRIES):
            try:
                await self._page.wait_for_selector(selector, state="visible", timeout=5000)
                await self._page.click(selector)
                await self._page.fill(selector, "")
                await self._page.type(selector, str(value), delay=self.TYPING_DELAY_MS)
                return True
            except Exception as e:
                if attempt < self.MAX_FILL_RETRIES - 1:
                    await self._page.wait_for_timeout(1000)
                    continue
                logger.warning(f"Failed to fill {selector}: {e}")
                return False
        return False

    async def select_option(self, selector: str, value: str) -> bool:
        await self._ensure_browser()
        try:
            await self._page.wait_for_selector(selector, state="visible", timeout=5000)
            await self._page.select_option(selector, value)
            return True
        except Exception as e:
            logger.warning(f"Failed to select {selector}={value}: {e}")
            return False

    async def check_element(self, selector: str, checked: bool = True) -> bool:
        await self._ensure_browser()
        try:
            await self._page.wait_for_selector(selector, state="visible", timeout=5000)
            if checked:
                await self._page.check(selector)
            else:
                await self._page.uncheck(selector)
            return True
        except Exception as e:
            logger.warning(f"Failed to {'check' if checked else 'uncheck'} {selector}: {e}")
            return False

    async def click_next(self) -> bool:
        await self._ensure_browser()
        try:
            for btn_selector in [
                "button:has-text('Next')", "button:has-text('Continue')",
                "button:has-text('Submit')", "[type='submit']", "a:has-text('Next')"
            ]:
                btn = await self._page.query_selector(btn_selector)
                if btn:
                    await btn.click()
                    await self._page.wait_for_load_state("networkidle")
                    return True
            return False
        except Exception as e:
            logger.warning(f"Failed to click Next: {e}")
            return False

    async def screenshot(self, path: str | Path) -> str:
        await self._ensure_browser()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            await self._page.screenshot(path=str(path), full_page=True)
            return str(path)
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""

    async def detect_captcha(self) -> bool:
        await self._ensure_browser()
        try:
            selectors = [
                'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]',
                'div[class*="captcha"]', '#captcha', '[aria-label*="captcha"]',
                'iframe[title*="captcha"]', '.g-recaptcha', '[data-sitekey]',
            ]
            for selector in selectors:
                el = await self._page.query_selector(selector)
                if el:
                    return True
            body_text = await self._page.inner_text("body") or ""
            for phrase in ["verify you are human", "captcha", "i'm not a robot", "security check"]:
                if phrase.lower() in body_text.lower():
                    return True
            return False
        except Exception as e:
            logger.warning(f"CAPTCHA detection failed: {e}")
            return False

    async def get_inner_text(self, selector: str) -> str:
        await self._ensure_browser()
        try:
            el = await self._page.query_selector(selector)
            return await el.inner_text() if el else ""
        except Exception:
            return ""

    async def close(self):
        try:
            if self._page:
                await self._page.close()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None


browser_tools = BrowserTools()
