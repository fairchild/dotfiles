#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.57.0"]
# ///
"""Capture and evaluate an image-gen review gallery with Playwright."""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import default_output_dir


SCRIPTS_DIR = Path(__file__).resolve().parent
REVIEW_SERVER = SCRIPTS_DIR / "review_gallery.py"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture screenshots and layout checks for an image-gen review gallery"
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--run-dir", type=Path, help="Comparison run directory with manifest.json")
    target.add_argument("--url", help="Existing review gallery URL")
    parser.add_argument("--output-dir", type=Path, help="Evaluation output directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host for temporary review server")
    parser.add_argument("--port", type=int, default=8765, help="Preferred temporary server port")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait for the page")
    args = parser.parse_args()

    run_dir = args.run_dir.resolve() if args.run_dir else None
    output_dir = evaluation_output_dir(args.output_dir, run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    server_process: subprocess.Popen[str] | None = None
    try:
        url = args.url
        served_run_dir = run_dir
        if not url:
            port = available_port(args.host, args.port)
            served_run_dir = prepare_served_run_dir(run_dir, output_dir)
            server_process, url = start_review_server(served_run_dir, args.host, port)
        result = evaluate_gallery(url=url, output_dir=output_dir, timeout_ms=args.timeout * 1000)
        result["created_at"] = datetime.now(timezone.utc).isoformat()
        result["url"] = url
        if run_dir:
            result["run_dir"] = str(run_dir)
        if served_run_dir and served_run_dir != run_dir:
            result["served_run_dir"] = str(served_run_dir)
        result["output_dir"] = str(output_dir)
        write_json(output_dir / "checks.json", result)
        write_notes(output_dir / "notes.md", result)
        print(str(output_dir.resolve()))
        if not result["ok"]:
            sys.exit(1)
    finally:
        if server_process:
            stop_process(server_process)


def evaluation_output_dir(output_dir: Path | None, run_dir: Path | None) -> Path:
    if output_dir:
        return output_dir
    run_id = run_dir.name if run_dir else "url"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return default_output_dir() / "evaluations" / run_id / stamp


def available_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError("no available port")


def prepare_served_run_dir(run_dir: Path | None, output_dir: Path) -> Path:
    if run_dir is None:
        raise ValueError("--run-dir is required when --url is omitted")
    served_run_dir = output_dir / "served-run"
    shutil.copytree(run_dir, served_run_dir)
    return served_run_dir


def start_review_server(
    run_dir: Path | None,
    host: str,
    port: int,
) -> tuple[subprocess.Popen[str], str]:
    if run_dir is None:
        raise ValueError("--run-dir is required when --url is omitted")
    process = subprocess.Popen(
        [
            str(REVIEW_SERVER),
            "--run-dir",
            str(run_dir),
            "--host",
            host,
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    started = time.monotonic()
    while time.monotonic() - started < 10:
        line = process.stdout.readline().strip()
        if line.startswith("http://") or line.startswith("https://"):
            return process, line
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(stderr.strip() or "review server exited before printing URL")
    stop_process(process)
    raise TimeoutError("timed out waiting for review server URL")


def stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def evaluate_gallery(url: str, output_dir: Path, timeout_ms: int) -> dict[str, Any]:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as error:  # pragma: no cover - dependency import failure is environment-specific.
        return failure_result(f"Unable to import Playwright: {error}")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            wait_for_images(page, timeout_ms)

            default_layout = collect_layout(page)
            page.screenshot(path=output_dir / "default.png", full_page=True)

            details_only = exercise_details_shortcut_from_hidden(page)
            page.mouse.click(10, 990)
            page.wait_for_timeout(120)
            page.keyboard.press("R")
            page.locator(".candidate").first.hover()
            page.wait_for_timeout(180)
            interaction_layout = collect_layout(page)
            page.screenshot(path=output_dir / "interaction.png", full_page=True)

            chrome_toggle = exercise_chrome_toggle(page)
            click_ranking = exercise_click_ranking(page)
            ensure_details_hidden(page)
            keyboard = exercise_keyboard(page)

            page.keyboard.press("Escape")
            page.mouse.move(1, 1)
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(180)
            mobile_layout = collect_layout(page)
            page.screenshot(path=output_dir / "mobile.png", full_page=True)
            browser.close()
    except PlaywrightError as error:
        return failure_result(playwright_error_message(error))

    checks = build_checks(
        default_layout,
        interaction_layout,
        mobile_layout,
        details_only,
        chrome_toggle,
        click_ranking,
        keyboard,
    )
    write_json(
        output_dir / "layout.json",
        {
            "default": default_layout,
            "interaction": interaction_layout,
            "mobile": mobile_layout,
            "detailsOnly": details_only,
            "chromeToggle": chrome_toggle,
            "clickRanking": click_ranking,
            "keyboard": keyboard,
        },
    )
    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "screenshots": [
            "default.png",
            "interaction.png",
            "mobile.png",
        ],
    }


def wait_for_images(page: Any, timeout_ms: int) -> None:
    page.wait_for_selector(".candidate img", timeout=timeout_ms)
    page.wait_for_function(
        """
        () => [...document.querySelectorAll('.candidate img')]
          .every((img) => img.complete && img.naturalWidth > 0 && img.naturalHeight > 0)
        """,
        timeout=timeout_ms,
    )


def collect_layout(page: Any) -> dict[str, Any]:
    return page.evaluate(
        """
        () => {
          const rect = (node) => {
            if (!node) return null;
            const box = node.getBoundingClientRect();
            return {
              x: box.x,
              y: box.y,
              width: box.width,
              height: box.height,
              top: box.top,
              right: box.right,
              bottom: box.bottom,
              left: box.left
            };
          };
          const overlaps = (a, b) => Boolean(a && b &&
            a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top);
          const cards = [...document.querySelectorAll('.candidate')].map((card, index) => {
            const image = card.querySelector('img');
            const caption = card.querySelector('figcaption');
            const rank = card.querySelector('.rank');
            const regen = card.querySelector('.regen');
            const imageRect = rect(image);
            const captionRect = rect(caption);
            const rankRect = rect(rank);
            const regenRect = rect(regen);
            return {
              index,
              path: card.dataset.path,
              card: rect(card),
              image: imageRect,
              caption: captionRect,
              rank: rankRect,
              regen: regenRect,
              imageLoaded: Boolean(image && image.complete && image.naturalWidth > 0),
              captionOpacity: Number(getComputedStyle(caption).opacity),
              metadataOverlapsImage: [captionRect, rankRect, regenRect].some((box) => overlaps(box, imageRect))
            };
          });
          return {
            title: document.title,
            url: location.href,
            activeIndex: cards.findIndex((card) => card.path === document.activeElement.closest('.candidate')?.dataset.path),
            detailsRevealed: document.querySelector('#toggle-details')?.getAttribute('aria-pressed') === 'true',
            chromeHidden: document.querySelector('#app')?.classList.contains('chrome-hidden') === true,
            saveState: document.querySelector('#save-state')?.textContent || '',
            cards
          };
        }
        """
    )


def exercise_keyboard(page: Any) -> dict[str, Any]:
    page.locator(".candidate .image-button").first.focus()
    order_before = order(page)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(80)
    focused_after_right = focused_index(page)
    focused_path = active_path(page)
    page.keyboard.press("ArrowUp")
    page.wait_for_timeout(80)
    order_after_up = order(page)
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(80)
    order_after_down = order(page)
    page.keyboard.press("R")
    revealed_after_r = page.locator("#toggle-details").get_attribute("aria-pressed")
    page.keyboard.press("R")
    hidden_after_second_r = page.locator("#toggle-details").get_attribute("aria-pressed")
    page.keyboard.press("S")
    page.wait_for_function("() => document.querySelector('#save-state')?.textContent === 'Saved'")
    save_state_after_s = page.locator("#save-state").text_content()
    return {
        "orderBefore": order_before,
        "focusedAfterRight": focused_after_right,
        "focusedPath": focused_path,
        "orderAfterUp": order_after_up,
        "orderAfterDown": order_after_down,
        "revealedAfterR": revealed_after_r == "true",
        "hiddenAfterSecondR": hidden_after_second_r == "false",
        "saveStateAfterS": save_state_after_s,
    }


def exercise_details_shortcut_from_hidden(page: Any) -> dict[str, Any]:
    page.keyboard.press("R")
    page.wait_for_timeout(120)
    revealed = collect_layout(page)
    page.keyboard.press("R")
    page.wait_for_timeout(120)
    hidden = collect_layout(page)
    return {
        "revealedChromeHidden": revealed["chromeHidden"],
        "revealedDetails": revealed["detailsRevealed"],
        "revealedMetadataVisible": all(card["captionOpacity"] > 0.8 for card in revealed["cards"]),
        "hiddenChromeHidden": hidden["chromeHidden"],
        "hiddenDetails": hidden["detailsRevealed"],
        "hiddenMetadataHidden": all(card["captionOpacity"] < 0.05 for card in hidden["cards"]),
    }


def exercise_chrome_toggle(page: Any) -> dict[str, Any]:
    page.mouse.click(10, 990)
    page.wait_for_timeout(80)
    after_hide = collect_layout(page)
    page.mouse.click(10, 990)
    page.wait_for_timeout(80)
    after_show = collect_layout(page)
    return {
        "afterHideChromeHidden": after_hide["chromeHidden"],
        "afterShowChromeHidden": after_show["chromeHidden"],
    }


def exercise_click_ranking(page: Any) -> dict[str, Any]:
    initial_order = order(page)
    if len(initial_order) < 4:
        return {"initialOrder": initial_order, "skipped": True}

    first_choice = initial_order[2]
    second_choice = initial_order[3]
    third_choice = initial_order[1]
    fourth_choice = initial_order[0]

    click_image(page, first_choice)
    order_after_first = order(page)
    click_image(page, second_choice)
    order_after_second = order(page)
    click_image(page, third_choice)
    click_image(page, fourth_choice)
    order_after_completed_pass = order(page)
    click_image(page, third_choice)
    order_after_restart = order(page)

    return {
        "initialOrder": initial_order,
        "firstChoice": first_choice,
        "secondChoice": second_choice,
        "restartChoice": third_choice,
        "orderAfterFirst": order_after_first,
        "orderAfterSecond": order_after_second,
        "orderAfterCompletedPass": order_after_completed_pass,
        "orderAfterRestart": order_after_restart,
    }


def click_image(page: Any, path: str) -> None:
    page.evaluate(
        """
        (path) => {
          const card = [...document.querySelectorAll('.candidate')]
            .find((element) => element.dataset.path === path);
          card?.querySelector('.image-button')?.click();
        }
        """,
        path,
    )
    page.wait_for_timeout(80)


def ensure_details_hidden(page: Any) -> None:
    if page.locator("#toggle-details").get_attribute("aria-pressed") == "true":
        page.keyboard.press("R")


def order(page: Any) -> list[str]:
    return page.evaluate("() => [...document.querySelectorAll('.candidate')].map((card) => card.dataset.path)")


def focused_index(page: Any) -> int:
    return page.evaluate(
        "() => [...document.querySelectorAll('.candidate')].findIndex((card) => card.contains(document.activeElement))"
    )


def active_path(page: Any) -> str | None:
    return page.evaluate("() => document.activeElement.closest('.candidate')?.dataset.path || null")


def build_checks(
    default_layout: dict[str, Any],
    interaction_layout: dict[str, Any],
    mobile_layout: dict[str, Any],
    details_only: dict[str, Any],
    chrome_toggle: dict[str, Any],
    click_ranking: dict[str, Any],
    keyboard: dict[str, Any],
) -> list[dict[str, Any]]:
    default_cards = default_layout["cards"]
    interaction_cards = interaction_layout["cards"]
    mobile_cards = mobile_layout["cards"]
    focused_path = keyboard.get("focusedPath")
    return [
        check("default_images_loaded", all(card["imageLoaded"] for card in default_cards)),
        check("interaction_images_loaded", all(card["imageLoaded"] for card in interaction_cards)),
        check("mobile_images_loaded", all(card["imageLoaded"] for card in mobile_cards)),
        check("default_chrome_hidden", default_layout.get("chromeHidden") is True),
        check("interaction_chrome_visible", interaction_layout.get("chromeHidden") is False),
        check("mobile_chrome_hidden", mobile_layout.get("chromeHidden") is True),
        check("details_shortcut_keeps_chrome_hidden", details_only.get("revealedChromeHidden") is True),
        check("details_shortcut_reveals_metadata", details_only.get("revealedMetadataVisible") is True),
        check("details_shortcut_hides_metadata_again", details_only.get("hiddenMetadataHidden") is True),
        check("outside_click_toggles_chrome_hidden", chrome_toggle.get("afterHideChromeHidden") is True),
        check("outside_click_toggles_chrome_visible", chrome_toggle.get("afterShowChromeHidden") is False),
        check("chrome_reveal_does_not_shift_cards", card_positions_stable(default_cards, interaction_cards)),
        check("default_metadata_hidden", all(card["captionOpacity"] < 0.05 for card in default_cards)),
        check("interaction_metadata_visible", interaction_cards and interaction_cards[0]["captionOpacity"] > 0.8),
        check("default_metadata_does_not_overlap_images", no_metadata_overlap(default_cards)),
        check("interaction_metadata_does_not_overlap_images", no_metadata_overlap(interaction_cards)),
        check("mobile_metadata_does_not_overlap_images", no_metadata_overlap(mobile_cards)),
        check(
            "click_first_image_sets_rank_one",
            click_ranking.get("orderAfterFirst", [None])[0] == click_ranking.get("firstChoice"),
        ),
        check(
            "click_second_image_sets_rank_two",
            len(click_ranking.get("orderAfterSecond", [])) > 1
            and click_ranking["orderAfterSecond"][1] == click_ranking.get("secondChoice"),
        ),
        check(
            "click_after_completed_pass_restarts_ranking",
            click_ranking.get("orderAfterRestart", [None])[0] == click_ranking.get("restartChoice"),
        ),
        check("arrow_right_moves_focus", keyboard.get("focusedAfterRight") == 1),
        check(
            "arrow_up_promotes_focused_card",
            bool(focused_path and keyboard.get("orderAfterUp", [None])[0] == focused_path),
        ),
        check(
            "arrow_down_demotes_focused_card",
            bool(
                focused_path
                and len(keyboard.get("orderAfterDown", [])) > 1
                and keyboard["orderAfterDown"][1] == focused_path
            ),
        ),
        check("r_toggles_details_on", keyboard.get("revealedAfterR") is True),
        check("r_toggles_details_off", keyboard.get("hiddenAfterSecondR") is True),
        check("s_saves_with_visual_indicator", keyboard.get("saveStateAfterS") == "Saved"),
    ]


def check(name: str, ok: bool, **extra: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), **extra}


def no_metadata_overlap(cards: list[dict[str, Any]]) -> bool:
    return all(not card["metadataOverlapsImage"] for card in cards)


def card_positions_stable(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> bool:
    if len(before) != len(after):
        return False
    after_by_path = {card["path"]: card for card in after}
    for card in before:
        match = after_by_path.get(card["path"])
        if not match:
            return False
        for key in ("left", "top", "width", "height"):
            if abs(card["card"][key] - match["card"][key]) > 1:
                return False
    return True


def failure_result(message: str) -> dict[str, Any]:
    return {"ok": False, "checks": [check("playwright_capture", False, message=message)], "screenshots": []}


def playwright_error_message(error: Exception) -> str:
    message = str(error)
    if "Executable doesn't exist" in message or "Please run the following command" in message:
        return (
            "Playwright browser is not installed. Run: "
            "`uv run --with playwright python -m playwright install chromium`. "
            f"Original error: {message.splitlines()[0]}"
        )
    return message


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_notes(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Image-Gen Review Gallery Evaluation",
        "",
        f"- URL: {result.get('url', '')}",
        f"- OK: {result.get('ok')}",
        "",
        "## Checks",
    ]
    for item in result.get("checks", []):
        status = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"- {status}: {item.get('name')}")
    lines.extend(["", "## Screenshots"])
    for screenshot in result.get("screenshots", []):
        lines.append(f"- `{screenshot}`")
    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
