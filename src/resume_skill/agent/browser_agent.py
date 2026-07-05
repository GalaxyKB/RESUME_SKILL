from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

from ..config import CONFIG
from .utils import ensure_dirs, safe_filename, timestamp


APPLY_KEYWORDS = [
    "申请", "投递", "立即申请", "立即投递", "投递简历",
    "申请职位", "我要投递", "开始申请",
    "Apply", "Apply Now", "Submit Application", "Start Application",
]

SUBMIT_KEYWORDS = [
    "提交", "确认提交", "完成投递", "投递", "提交申请",
    "Submit", "Submit Application", "Send Application", "Finish",
]


class BrowserAgent:
    def __init__(
        self,
        *,
        session_profile_dir: str = "",
        cdp_endpoint: str = "",
        reuse_existing_tab: bool = False,
        keep_browser_open: bool = False,
        browser_channel: str = "",
        browser_executable_path: str = "",
        headless: bool = False,
        slow_motion: int = 300,
    ) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._session_profile_dir = session_profile_dir or str(CONFIG.session_dir)
        self._cdp_endpoint = cdp_endpoint
        self._reuse_existing_tab = reuse_existing_tab
        self._keep_browser_open = keep_browser_open
        self._is_attached_external_browser = False
        self._browser_channel = browser_channel or CONFIG.browser.browser_channel
        self._browser_executable_path = browser_executable_path or CONFIG.browser.browser_executable_path
        self._headless = headless or CONFIG.browser.headless
        self._slow_motion = slow_motion or CONFIG.browser.slow_motion

    @property
    def page(self) -> Page:
        if self._page is not None:
            try:
                if not self._page.is_closed():
                    return self._page
            except Exception:
                pass
            self._page = None

        if self._context is None:
            raise RuntimeError("Browser has not been started")

        try:
            pages = list(self._context.pages)
            for existing in pages:
                try:
                    if not existing.is_closed():
                        self._page = existing
                        return self._page
                except Exception:
                    continue
            self._page = self._context.new_page()
        except Exception as exc:
            raise RuntimeError("Browser page is unavailable") from exc
        return self._page

    def _harden_context(self) -> None:
        if self._context is None:
            return
        try:
            self._context.add_init_script(
                r"""
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                });
                const plugin1 = {name:'Chrome PDF Plugin',description:'Portable Document Format',filename:'internal-pdf-viewer',version:'1.0'};
                const plugin2 = {name:'Chrome PDF Viewer',description:'Portable Document Format',filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai',version:'2.1'};
                const plugin3 = {name:'Native Client Executable',description:'Native Client Executable',filename:'internal-nacl-plugin',version:'1.0'};
                Object.defineProperty(navigator, 'plugins', { get: () => [plugin1, plugin2, plugin3] });
                Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN','zh','en-US','en'] });
                window.chrome = { runtime: {} };
                """
            )
        except Exception:
            pass

    def start(self) -> None:
        ensure_dirs()
        if self._page is not None:
            return

        self._playwright = sync_playwright().start()
        anti_bot_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            "--disable-extensions",
            "--disable-default-apps",
            "--start-maximized",
        ]
        ignore_default_args = ["--enable-automation"]

        if self._cdp_endpoint:
            self._browser = self._playwright.chromium.connect_over_cdp(self._cdp_endpoint)
            self._is_attached_external_browser = True
            contexts = list(self._browser.contexts)
            self._context = contexts[0] if contexts else self._browser.new_context(viewport=None)
            self._harden_context()
            self._page = self._context.pages[0] if self._reuse_existing_tab and self._context.pages else self._context.new_page()
            return

        if self._session_profile_dir:
            profile_dir = Path(self._session_profile_dir)
            profile_dir.mkdir(parents=True, exist_ok=True)
            launch_kwargs = {
                "user_data_dir": str(profile_dir),
                "headless": self._headless,
                "slow_mo": self._slow_motion,
                "args": anti_bot_args,
                "ignore_default_args": ignore_default_args,
            }
            if self._browser_channel and self._browser_channel != "chromium":
                launch_kwargs["channel"] = self._browser_channel
            if self._browser_executable_path:
                launch_kwargs["executable_path"] = self._browser_executable_path
            self._context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
            self._browser = self._context.browser
            self._harden_context()
            self._page = self._context.pages[0] if self._reuse_existing_tab and self._context.pages else self._context.new_page()
            return

        launch_kwargs = {
            "headless": self._headless,
            "slow_mo": self._slow_motion,
            "args": anti_bot_args,
            "ignore_default_args": ignore_default_args,
        }
        if self._browser_channel and self._browser_channel != "chromium":
            launch_kwargs["channel"] = self._browser_channel
        if self._browser_executable_path:
            launch_kwargs["executable_path"] = self._browser_executable_path
        self._browser = self._playwright.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            viewport={"width": CONFIG.browser.viewport_width, "height": CONFIG.browser.viewport_height},
            locale=CONFIG.browser.locale,
            timezone_id=CONFIG.browser.timezone_id,
        )
        self._harden_context()
        self._page = self._context.new_page()

    def open_url(self, url: str) -> None:
        if not url.strip():
            return
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeout:
            pass

    def get_page_text(self) -> str:
        try:
            text = self.page.evaluate(
                "() => (document.body?.innerText || document.body?.textContent || '')"
            )
        except Exception:
            return ""
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        return "\n".join(lines).strip()[:30000]

    def save_screenshot(self, name: str) -> str:
        ensure_dirs()
        from ..config import CONFIG as cfg
        screenshot_dir = cfg.outputs_dir / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        file_path = screenshot_dir / f"{timestamp()}_{safe_filename(name)}.png"
        self.page.screenshot(path=str(file_path), full_page=True)
        return str(file_path)

    def get_current_url(self) -> str:
        return self.page.url

    def wait_for_user_ready(self, message: str) -> None:
        input(message)

    def close(self) -> None:
        if self._keep_browser_open:
            # Keep browser running, only disconnect Python references
            self._page = None
            self._context = None  
            # Don't set _browser = None to keep reference
            # Don't call _playwright.stop() to keep browser alive
            return

        for attr in ("_page", "_context"):
            obj = getattr(self, attr)
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, attr, None)

        if self._browser is not None and not self._is_attached_external_browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def _click_candidate(self, keywords: list[str]) -> bool:
        page = self.page
        for keyword in keywords:
            selectors = [
                page.get_by_role("button", name=re.compile(re.escape(keyword), re.I)),
                page.get_by_role("link", name=re.compile(re.escape(keyword), re.I)),
                page.locator("button, a, [role='button'], [role='link']").filter(has_text=keyword),
                page.get_by_text(keyword, exact=False),
            ]
            for locator in selectors:
                try:
                    locator.first.click(timeout=2500)
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except PlaywrightTimeout:
                        pass
                    return True
                except Exception:
                    continue
        return False

    def click_apply_button(self) -> bool:
        return self._click_candidate(APPLY_KEYWORDS)

    def click_submit_button(self) -> bool:
        return self._click_candidate(SUBMIT_KEYWORDS)

    def click_by_keywords(self, keywords: list[str]) -> bool:
        """Public wrapper for _click_candidate."""
        return self._click_candidate(keywords)
