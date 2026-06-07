#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.57.0"]
# ///
"""Playwright smoke tests for the vocal web console.

Usage:
  uv run --script skills/vocal/tests/test_web_console_playwright.py
  uv run --script skills/vocal/tests/test_web_console_playwright.py --url http://127.0.0.1:8799
  uv run --script skills/vocal/tests/test_web_console_playwright.py --url http://127.0.0.1:8799 --cloud
  uv run --script skills/vocal/tests/test_web_console_playwright.py --headed --slow-mo 100
"""

from __future__ import annotations

import argparse
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Browser, Page, Playwright, sync_playwright


SKILL_DIR = Path(__file__).resolve().parent.parent
WEB_CONSOLE = SKILL_DIR / "scripts" / "web_console.py"


class SmokeFailure(AssertionError):
    """A focused browser smoke-test failure."""


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def start_server(data_dir: Path) -> tuple[subprocess.Popen[str], str]:
    env = os.environ.copy()
    env["VOCAL_DATA_DIR"] = str(data_dir)
    proc = subprocess.Popen(
        ["uv", "run", "--script", str(WEB_CONSOLE), "--host", "127.0.0.1", "--port", "0"],
        cwd=SKILL_DIR.parent.parent,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    assert proc.stdout is not None
    deadline = time.monotonic() + 15
    url = ""
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise SmokeFailure(f"web console exited before startup: {stderr.strip()}")

        ready, _, _ = select.select([proc.stdout], [], [], 0.25)
        if not ready:
            continue
        line = proc.stdout.readline().strip()
        if line.startswith("Vocal web console:"):
            url = line.split(":", 1)[1].strip()
            break

    if not url:
        stop_server(proc)
        raise SmokeFailure("timed out waiting for web console startup")
    return proc, url


def stop_server(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def new_page(
    playwright: Playwright,
    *,
    headed: bool,
    slow_mo: int,
    width: int,
    height: int,
    mobile: bool,
    color_scheme: str | None = None,
) -> tuple[Browser, Page]:
    browser = playwright.chromium.launch(headless=not headed, slow_mo=slow_mo)
    page = browser.new_page(viewport={"width": width, "height": height}, is_mobile=mobile, color_scheme=color_scheme)
    return browser, page


def assert_no_browser_errors(page: Page, errors: list[str]) -> None:
    assert_true(not errors, "browser errors:\n" + "\n".join(errors))
    overflow = page.evaluate("() => document.body.scrollWidth > window.innerWidth")
    assert_true(not overflow, "page has horizontal body overflow")


def attach_error_collection(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


def assert_loaded(page: Page, base_url: str, screenshot_path: Path | None = None) -> None:
    errors = attach_error_collection(page)
    page.goto(base_url, wait_until="networkidle")

    assert_true(page.locator("h1").inner_text() == "Vocal Console", "missing page title")
    subtitle = page.locator(".subtitle").inner_text()
    assert_true("Preview voices" in subtitle and "Save defaults" in subtitle, "page does not explain preview versus saved defaults")
    assert_true(page.locator("button").count() >= 10, "expected workbench controls")
    assert_true(page.locator("#quickSpeak").count() == 1, "missing first-run sample button")
    assert_true("Play sample" in page.locator("#quickSpeak").inner_text(), "first-run action should read like a button")
    button_style = page.locator("#quickSpeak").evaluate(
        """(button) => {
          const style = getComputedStyle(button);
          return {
            borderWidth: parseFloat(style.borderTopWidth),
            radius: parseFloat(style.borderTopLeftRadius),
            shadow: style.boxShadow,
          };
        }"""
    )
    assert_true(button_style["borderWidth"] >= 2, "first-run action needs a visible button border")
    assert_true(button_style["radius"] >= 8, "first-run action needs a button-like shape")
    assert_true(button_style["shadow"] != "none", "first-run action needs a pressed-button affordance")
    assert_true(page.locator("#quickTtsProvider").count() == 1, "missing first-run provider selector")
    assert_true(page.locator("#samplePlayer").evaluate("(node) => node.classList.contains('hidden')"), "empty audio player should stay hidden before playback")
    assert_true("Generated sample playback" in page.locator("#samplePlayer").inner_text(), "audio player should explain what it is when shown")
    assert_true(page.locator("#quickVoices").count() == 0, "voice loading should not be in the first-run layer")
    assert_true(page.locator("#quickSave").count() == 0, "saving should not be in the first-run layer")
    status = page.locator("#statusStrip").inner_text()
    assert_true("setup" in status.lower(), "status strip should label badges as setup checks")
    assert_true("ElevenLabs" in status, "status strip did not surface ElevenLabs setup")
    assert_true("uv runner ready" in status, "status strip did not find uv")
    assert_true("Local speech ready" in status, "status strip did not find macOS say")
    assert_true(
        "pill" not in (page.locator("[data-status='elevenlabs']").get_attribute("class") or ""),
        "setup checks should not use pill styling",
    )
    status_icon_state = page.evaluate(
        """() => {
          const clean = (value) => value.replace(/^["']|["']$/g, "");
          const ready = document.querySelector("[data-status='elevenlabs']");
          const missing = document.createElement("span");
          missing.className = "status-check bad";
          missing.textContent = "missing";
          document.body.appendChild(missing);
          const state = {
            readyMark: clean(getComputedStyle(ready, "::before").content),
            readyBorder: getComputedStyle(ready).borderTopStyle,
            missingMark: clean(getComputedStyle(missing, "::before").content),
          };
          missing.remove();
          return state;
        }"""
    )
    assert_true(ord(status_icon_state["readyMark"]) == 10003, "ready setup checks should use a check mark")
    assert_true(status_icon_state["missingMark"] == "\u25CB", "missing setup checks should use an open circle")
    assert_true(status_icon_state["readyBorder"] == "none", "setup checks should not look like pills")
    tooltip = page.locator("[data-status='elevenlabs']").get_attribute("data-tooltip") or ""
    assert_true("Cloud voices" in tooltip or "Set ELEVENLABS_API_KEY" in tooltip, "ElevenLabs status tooltip lacks context")
    assert_true(
        "Saving later updates the skill defaults" in page.locator("details[data-section-key='try'] summary").inner_text(),
        "first task should explain that previewing is not saving",
    )
    page.wait_for_function(
        "() => document.querySelector('#defaultsSavedState').textContent.includes('Current controls match saved defaults')",
        timeout=5_000,
    )
    defaults_overview = page.locator("#defaultsOverview").inner_text()
    defaults_overview_lower = defaults_overview.lower()
    assert_true("saved defaults" in defaults_overview_lower, "saved defaults should be visible before the task layers")
    assert_true("preferences the vocal skill will start from" in defaults_overview, "saved defaults overview should explain why it matters")
    assert_true("Change any controls below" in defaults_overview, "saved defaults overview should explain that settings are editable")
    assert_true("preferences.json" in defaults_overview, "saved defaults overview should show where preferences are saved")
    assert_true("speech" in defaults_overview_lower and "listening" in defaults_overview_lower, "saved defaults overview should summarize loaded preferences")
    icon_state = page.evaluate(
        """() => {
          const clean = (value) => value.replace(/^["']|["']$/g, "");
          const open = document.querySelector("details[data-section-key='try'] .summary-icon");
          const closed = document.querySelector("details[data-section-key='voice'] .summary-icon");
          return {
            openMark: clean(getComputedStyle(open, "::before").content),
            openTooltip: clean(getComputedStyle(open, "::after").content),
            openTransform: getComputedStyle(open).transform,
            closedMark: clean(getComputedStyle(closed, "::before").content),
            closedTooltip: clean(getComputedStyle(closed, "::after").content),
          };
        }"""
    )
    assert_true(ord(icon_state["openMark"]) == 8722, "open layer should show a minus, not a rotated plus")
    assert_true(icon_state["openTooltip"] == "Collapse", "open layer icon should explain collapse on hover")
    assert_true(icon_state["openTransform"] == "none", "open layer icon should not rotate into an x")
    assert_true(icon_state["closedMark"] == "+", "closed layer should still show a plus")
    assert_true(icon_state["closedTooltip"] == "Expand", "closed layer icon should explain expand on hover")
    assert_no_browser_errors(page, errors)

    if screenshot_path:
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)


def assert_first_provider_choice(page: Page) -> None:
    page.locator("#quickTtsProvider").select_option("local")
    assert_true(
        page.locator("[data-tts-provider='local']").evaluate("(button) => button.classList.contains('active')"),
        "first-run provider selector did not sync local provider",
    )
    local_hint = page.locator("#quickProviderHint").inner_text()
    assert_true("No account required" in local_hint, "local provider hint is unclear")
    local_detail = page.locator("#quickSpeakDetail").inner_text()
    assert_true("local Mac speech" in local_detail, "sample button detail should describe local provider")

    status = page.locator("#statusStrip").inner_text()
    if "ElevenLabs ready" in status:
        page.locator("#quickTtsProvider").select_option("elevenlabs")
        assert_true(
            page.locator("[data-tts-provider='elevenlabs']").evaluate("(button) => button.classList.contains('active')"),
            "first-run provider selector did not sync ElevenLabs provider",
        )
        cloud_hint = page.locator("#quickProviderHint").inner_text()
        assert_true("ElevenLabs key" in cloud_hint, "ElevenLabs provider hint is unclear")
        cloud_detail = page.locator("#quickSpeakDetail").inner_text()
        assert_true("ElevenLabs audio" in cloud_detail, "sample button detail should describe ElevenLabs provider")
        page.locator("#quickTtsProvider").select_option("local")


def layer_is_open(page: Page, key: str) -> bool:
    return bool(page.locator(f"details[data-section-key='{key}']").evaluate("(layer) => layer.open"))


def ensure_layer_open(page: Page, key: str) -> None:
    if not layer_is_open(page, key):
        page.locator(f"details[data-section-key='{key}'] summary").click()
    assert_true(layer_is_open(page, key), f"{key} layer did not open")


def wait_layer_storage(page: Page, key: str, value: str) -> None:
    page.wait_for_function(
        """([key, value]) => window.localStorage.getItem(`vocal-console.layer.${key}`) === value""",
        arg=[key, value],
        timeout=2_000,
    )


def assert_sticky_layers(page: Page) -> None:
    page.evaluate("() => window.localStorage.clear()")
    page.reload(wait_until="networkidle")
    assert_true(layer_is_open(page, "try"), "first-run sample layer should be open by default")

    ensure_layer_open(page, "voice")
    wait_layer_storage(page, "voice", "open")
    ensure_layer_open(page, "guide")
    wait_layer_storage(page, "guide", "open")

    page.reload(wait_until="networkidle")
    assert_true(layer_is_open(page, "try"), "first-run sample layer should stay open")
    assert_true(layer_is_open(page, "voice"), "voice layer open state did not persist")
    assert_true(layer_is_open(page, "guide"), "guide layer open state did not persist")
    assert_true(not layer_is_open(page, "listen"), "listen layer should stay closed until opened")


def assert_dark_theme(page: Page, base_url: str, screenshot_path: Path | None = None) -> None:
    assert_loaded(page, base_url, screenshot_path)
    luminance = page.evaluate(
        """() => {
          const rgb = (value) => value.match(/\\d+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => 0.2126 * r + 0.7152 * g + 0.0722 * b;
          return {
            body: lum(rgb(getComputedStyle(document.body).backgroundColor)),
            heading: lum(rgb(getComputedStyle(document.querySelector('h1')).color)),
            panel: lum(rgb(getComputedStyle(document.querySelector('.panel')).backgroundColor)),
          };
        }"""
    )
    assert_true(luminance["body"] < 60, f"dark mode body is too light: {luminance}")
    assert_true(luminance["heading"] > 150, f"dark mode text is too dark: {luminance}")
    assert_true(luminance["panel"] < 80, f"dark mode panel is too light: {luminance}")


def assert_voice_loading(page: Page) -> None:
    ensure_layer_open(page, "voice")
    page.locator("[data-tts-provider='local']").click()
    page.locator("#loadVoices").click()
    page.wait_for_function("() => document.querySelectorAll('#localVoices option').length > 0", timeout=10_000)
    voice_count = page.evaluate("() => document.querySelectorAll('#localVoices option').length")
    has_spaced_voice = page.evaluate(
        "() => [...document.querySelectorAll('#localVoices option')].some((option) => option.value === 'Bad News')"
    )
    assert_true(voice_count > 20, f"expected local voices, found {voice_count}")
    assert_true(has_spaced_voice, "voice parser truncated or omitted a multi-word macOS voice")


def assert_listen_feedback(page: Page) -> None:
    ensure_layer_open(page, "listen")
    page.route(
        "**/api/check",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"ok":true,"stdout":"STT dependencies ready","stderr":""}',
        ),
    )
    page.locator("#checkStt").click()
    page.wait_for_function("() => document.querySelector('#sttCheckStatus').textContent.includes('STT ready')", timeout=5_000)
    stt_status = page.locator("#sttCheckStatus").inner_text()
    assert_true("STT dependencies ready" in stt_status, "STT check result should appear beside Check STT")

    page.evaluate(
        """() => {
          Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: {
              getUserMedia: () => Promise.reject(new Error("Permission denied in smoke test")),
            },
          });
        }"""
    )
    page.locator("#record").click()
    page.wait_for_function("() => document.querySelector('#recordStatus').textContent.includes('Microphone unavailable')", timeout=5_000)
    record_status = page.locator("#recordStatus").inner_text()
    assert_true("Permission denied in smoke test" in record_status, "recording errors should be visible in the Voice In layer")

    transcribe_calls: list[str] = []

    def fulfill_transcription(route: Any) -> None:
        transcribe_calls.append(route.request.post_data or "")
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"ok":true,"transcript":"auto transcript from smoke"}',
        )

    page.route("**/api/transcribe", fulfill_transcription)
    page.evaluate(
        """() => {
          Object.defineProperty(navigator, "mediaDevices", {
            configurable: true,
            value: {
              getUserMedia: () => Promise.resolve({
                getTracks: () => [{ stop() {} }],
              }),
            },
          });
          Object.defineProperty(window, "MediaRecorder", {
            configurable: true,
            value: class FakeMediaRecorder {
              constructor() {
                this.mimeType = "audio/webm";
                this.state = "inactive";
                this.ondataavailable = null;
                this.onstop = null;
              }

              start() {
                this.state = "recording";
              }

              stop() {
                if (this.state === "inactive") return;
                this.state = "inactive";
                if (this.ondataavailable) {
                  this.ondataavailable({ data: new Blob(["fake audio"], { type: this.mimeType }) });
                }
                if (this.onstop) this.onstop();
              }
            },
          });
        }"""
    )

    page.locator("#recordSeconds").fill("5")
    page.evaluate("() => { document.querySelector('#transcript').value = ''; }")
    page.locator("#record").click()
    page.wait_for_function("() => document.querySelector('#recordStatus').textContent.includes('Will transcribe automatically')", timeout=5_000)
    page.locator("#stopRecord").click()
    page.wait_for_function("() => document.querySelector('#recordStatus').textContent.includes('Click \"Transcribe recording\"')", timeout=5_000)
    page.wait_for_timeout(300)
    assert_true(len(transcribe_calls) == 0, "manual Stop should not auto-transcribe")
    assert_true(page.locator("#transcript").input_value() == "", "manual Stop should leave transcript empty until requested")

    page.locator("#recordSeconds").fill("1")
    page.evaluate("() => { document.querySelector('#transcript').value = ''; }")
    page.locator("#record").click()
    page.wait_for_function("() => document.querySelector('#recordStatus').textContent.includes('Transcript ready below')", timeout=6_000)
    assert_true(len(transcribe_calls) == 1, "timed recording should auto-transcribe once")
    assert_true(
        "auto transcript from smoke" in page.locator("#transcript").input_value(),
        "timed recording did not put the transcript into the transcript box",
    )


def assert_synthesis(page: Page) -> None:
    page.locator("#quickTtsProvider").select_option("local")
    page.locator("#quickSpeak").click()
    page.wait_for_function("() => document.querySelector('#audio').src.startsWith('blob:')", timeout=15_000)
    page.wait_for_function("() => Number.isFinite(document.querySelector('#audio').duration) && document.querySelector('#audio').duration > 0", timeout=15_000)
    page.wait_for_function("() => document.querySelector('#flowStatus').textContent.includes('Sample ready')", timeout=15_000)
    audio_src = page.locator("#audio").get_attribute("src") or ""
    assert_true(audio_src.startswith("blob:"), "TTS did not attach generated audio to the player")
    assert_true(not page.locator("#samplePlayer").evaluate("(node) => node.classList.contains('hidden')"), "audio player should appear after generating a sample")
    flow_status = page.locator("#flowStatus").inner_text()
    assert_true("Sample ready" in flow_status, "quick-start flow did not report playable audio")


def assert_cloud_synthesis(page: Page) -> None:
    status = page.locator("#statusStrip").inner_text()
    assert_true("ElevenLabs ready" in status, "ElevenLabs key is not available to the web console")
    page.locator("#quickTtsProvider").select_option("elevenlabs")
    page.locator("#quickSpeak").click()
    page.wait_for_function("() => document.querySelector('#flowStatus').textContent.includes('Sample ready')", timeout=20_000)
    duration = page.evaluate("() => document.querySelector('#audio').duration")
    assert_true(duration > 0, "ElevenLabs TTS did not produce playable audio")


def assert_save_preferences(page: Page) -> None:
    sample_text = f"Build complete. Save defaults smoke {int(time.time() * 1000)}."
    sample = page.locator("#sampleText")
    sample.fill(sample_text)
    page.wait_for_function(
        "() => document.querySelector('#defaultsSavedState').textContent.includes('Unsaved changes')",
        timeout=5_000,
    )
    assert_true("Unsaved changes" in page.locator("#defaultsSavedState").inner_text(), "top saved defaults band should flag edited controls")
    assert_true(sample_text not in page.locator("#defaultsPreview").inner_text(), "saved defaults band should continue showing the saved file before saving")
    ensure_layer_open(page, "save")
    explainer = page.locator(".save-explainer").inner_text()
    assert_true("Most skills do not persist data" in explainer, "save layer should explain that saving local skill state is unusual")
    assert_true("only saves when you press the button" in explainer, "save layer should make save timing explicit")
    preference_path = page.locator("#preferencesPath").inner_text()
    assert_true("preferences.json" in preference_path, "save layer should show the preference file path")
    assert_true("not sent to ElevenLabs" in page.locator(".save-path").inner_text(), "save layer should explain persistence stays local")
    current_settings = page.locator("#settingsPreview").inner_text()
    current_settings_lower = current_settings.lower()
    assert_true("speech provider" in current_settings_lower, "save layer should summarize current speech settings")
    assert_true("listening provider" in current_settings_lower, "save layer should summarize current listening settings")
    assert_true(sample_text in current_settings, "save layer should show current sample text")
    assert_true("Unsaved changes" in page.locator("#settingsSavedState").inner_text(), "changed settings should be marked unsaved before saving")
    page.locator("#savePrefs").click()
    page.wait_for_function("() => document.querySelector('#saveStatus').textContent.includes('Saved defaults to')", timeout=5_000)
    assert_true("Saved defaults to" in (page.locator("#saveStatus").text_content() or ""), "preferences were not saved")
    assert_true("Matches saved file" in page.locator("#settingsSavedState").inner_text(), "saved settings should be marked current")
    assert_true("Current controls match saved defaults" in page.locator("#defaultsSavedState").inner_text(), "top saved defaults band should update after saving")
    assert_true(sample_text in page.locator("#defaultsPreview").inner_text(), "saved defaults band should show newly saved preferences")
    assert_true("Saved." in page.locator("#flowStatus").inner_text(), "visible quick-start flow did not report saved preferences")


def assert_api(playwright: Playwright, base_url: str) -> None:
    request = playwright.request.new_context()
    try:
        status = request.get(f"{base_url}/api/status")
        assert_true(status.ok, f"/api/status failed: {status.status}")
        payload: dict[str, Any] = status.json()
        assert_true(payload.get("hasUv") is True, "/api/status did not report uv")
        assert_true(payload.get("hasSay") is True, "/api/status did not report say")

        synth = request.post(
            f"{base_url}/api/synthesize",
            headers={"content-type": "application/json"},
            data='{"provider":"local","text":"Vocal console Playwright smoke test.","voice":"Alex","rate":190}',
        )
        if not synth.ok:
            preview = synth.body()[:200].decode("utf-8", errors="replace")
            raise SmokeFailure(f"/api/synthesize failed: {synth.status} {preview}")
        assert_true("audio/mp4" in (synth.headers.get("content-type") or ""), "synthesize did not return browser-playable local audio")
        assert_true(len(synth.body()) > 1000, "synthesize returned too little audio data")
    finally:
        request.dispose()


def run_smoke(args: argparse.Namespace) -> None:
    screenshots_dir = Path(args.screenshots_dir).expanduser().resolve() if args.screenshots_dir else None
    owned_proc: subprocess.Popen[str] | None = None

    with tempfile.TemporaryDirectory(prefix="vocal-web-console-") as tmp:
        if args.url:
            base_url = args.url.rstrip("/")
        else:
            owned_proc, base_url = start_server(Path(tmp) / "data")

        try:
            with sync_playwright() as playwright:
                assert_api(playwright, base_url)

                desktop_browser, desktop = new_page(
                    playwright,
                    headed=args.headed,
                    slow_mo=args.slow_mo,
                    width=1280,
                    height=900,
                    mobile=False,
                )
                try:
                    assert_loaded(desktop, base_url, screenshots_dir / "desktop.png" if screenshots_dir else None)
                    assert_first_provider_choice(desktop)
                    assert_sticky_layers(desktop)
                    assert_voice_loading(desktop)
                    assert_listen_feedback(desktop)
                    assert_synthesis(desktop)
                    if args.cloud:
                        assert_cloud_synthesis(desktop)
                    assert_save_preferences(desktop)
                finally:
                    desktop_browser.close()

                mobile_browser, mobile = new_page(
                    playwright,
                    headed=args.headed,
                    slow_mo=args.slow_mo,
                    width=390,
                    height=900,
                    mobile=True,
                )
                try:
                    assert_loaded(mobile, base_url, screenshots_dir / "mobile.png" if screenshots_dir else None)
                finally:
                    mobile_browser.close()

                dark_browser, dark = new_page(
                    playwright,
                    headed=args.headed,
                    slow_mo=args.slow_mo,
                    width=1280,
                    height=900,
                    mobile=False,
                    color_scheme="dark",
                )
                try:
                    assert_dark_theme(dark, base_url, screenshots_dir / "dark.png" if screenshots_dir else None)
                finally:
                    dark_browser.close()
        finally:
            if owned_proc is not None:
                stop_server(owned_proc)

    print(f"PASS vocal web console Playwright smoke: {base_url}")
    if screenshots_dir:
        print(f"screenshots: {screenshots_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Playwright smoke tests for the vocal web console")
    parser.add_argument("--url", help="Validate an already-running console instead of starting one")
    parser.add_argument("--headed", action="store_true", help="Run Chromium headed so you can watch the test")
    parser.add_argument("--cloud", action="store_true", help="Also validate ElevenLabs TTS through the UI")
    parser.add_argument("--slow-mo", type=int, default=0, help="Slow Playwright actions by N milliseconds")
    parser.add_argument("--screenshots-dir", help="Optional directory for desktop/mobile screenshots")
    args = parser.parse_args()

    if shutil.which("uv") is None:
        raise SmokeFailure("uv is required to start the web console")

    try:
        run_smoke(args)
    except PlaywrightError as exc:
        print(f"FAIL Playwright error: {exc}", file=sys.stderr)
        print("If Chromium is missing, run: uv run --with playwright==1.57.0 playwright install chromium", file=sys.stderr)
        sys.exit(1)
    except SmokeFailure as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
