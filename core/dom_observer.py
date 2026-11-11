import re
from typing import List, Dict, Tuple
from playwright.sync_api import Page
from models.actions import InteractiveElement, PageSnapshot


class DomObserver:
    """
    Extracts semantic accessibility trees and interactive elements from a live Playwright page.
    Converts complex DOM structures into token-efficient, unambiguous representations for the LLM.
    """

    EXTRACT_JS = """
    () => {
        const results = [];
        let index = 1;
        const selectorQuery = 'button, a, input, select, textarea, [role="button"], [role="link"], [role="menuitem"], [role="tab"], [role="checkbox"], [role="radio"]';
        const elements = document.querySelectorAll(selectorQuery);

        for (const el of elements) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            
            // Filter out hidden, zero-size, or off-screen elements
            const isVisible = style.display !== 'none' && 
                              style.visibility !== 'hidden' && 
                              style.opacity !== '0' &&
                              (rect.width > 2 || rect.height > 2 || el.type === 'radio' || el.type === 'checkbox');
            if (!isVisible) continue;

            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type') || '';
            const text = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
            const placeholder = el.getAttribute('placeholder') || '';
            const id = el.getAttribute('id') || '';
            const name = el.getAttribute('name') || '';
            const ariaLabel = el.getAttribute('aria-label') || '';
            const role = el.getAttribute('role') || '';
            const href = el.getAttribute('href') || '';
            
            let val = el.value || '';
            if (type === 'password' && val.length > 0) {
                val = '******';
            }

            // Assign a unique temporary attribute for bulletproof targeting
            const elementId = `e${index++}`;
            el.setAttribute('data-agent-id', elementId);

            results.push({
                id: elementId,
                tag: tag,
                role: role,
                text: text,
                id_attr: id,
                name: name,
                input_type: type,
                placeholder: placeholder,
                value: val.slice(0, 50),
                aria_label: ariaLabel,
                href: href,
                selector: `[data-agent-id="${elementId}"]`,
                bounding_box: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
            });
        }
        return results;
    }
    """

    PAGE_TEXT_JS = """
    () => {
        const snippets = [];
        const targets = document.querySelectorAll('h1, h2, h3, h4, .alert, .badge, .notification, .toast, p, [role="alert"], [data-testid]');
        for (const t of targets) {
            const s = (t.innerText || '').trim().replace(/\\s+/g, ' ');
            if (s && s.length > 2 && s.length < 250) {
                snippets.push(s);
            }
        }
        return Array.from(new Set(snippets)).slice(0, 30).join(' | ');
    }
    """

    @classmethod
    def capture_snapshot(cls, page: Page, screenshot_path: str = None) -> PageSnapshot:
        """Takes a complete snapshot of the page with interactive elements and text."""
        raw_elements = page.evaluate(cls.EXTRACT_JS)
        text_summary = page.evaluate(cls.PAGE_TEXT_JS)

        interactive_elements: List[InteractiveElement] = []
        for raw in raw_elements:
            interactive_elements.append(InteractiveElement(
                id=raw["id"],
                tag=raw["tag"],
                role=raw.get("role") or None,
                text=raw.get("text") or None,
                name=raw.get("name") or None,
                input_type=raw.get("input_type") or None,
                placeholder=raw.get("placeholder") or None,
                value=raw.get("value") or None,
                aria_label=raw.get("aria_label") or None,
                href=raw.get("href") or None,
                selector=raw["selector"],
                bounding_box=raw.get("bounding_box")
            ))

        return PageSnapshot(
            url=page.url,
            title=page.title(),
            interactive_elements=interactive_elements,
            clean_text_summary=text_summary,
            screenshot_path=screenshot_path
        )

    @classmethod
    def format_elements_for_prompt(cls, elements: List[InteractiveElement], limit: int = 65) -> str:
        """Formats interactive elements into concise, high-signal text for the LLM."""
        lines = []
        for el in elements[:limit]:
            attrs = []
            if el.tag: attrs.append(f"tag='{el.tag}'")
            if el.input_type: attrs.append(f"type='{el.input_type}'")
            if el.role: attrs.append(f"role='{el.role}'")
            if el.name: attrs.append(f"name='{el.name}'")
            if el.placeholder: attrs.append(f"placeholder='{el.placeholder}'")
            if el.aria_label: attrs.append(f"aria-label='{el.aria_label}'")
            if el.text: attrs.append(f"text='{el.text}'")
            if el.value: attrs.append(f"value='{el.value}'")
            if el.href and len(el.href) < 60: attrs.append(f"href='{el.href}'")

            attr_str = ", ".join(attrs)
            lines.append(f"[{el.id}] <{el.tag} {attr_str}>")

        if len(elements) > limit:
            lines.append(f"... (+{len(elements) - limit} additional interactive elements omitted for brevity)")

        return "\n".join(lines)
