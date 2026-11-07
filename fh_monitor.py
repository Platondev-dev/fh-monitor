"""
Freelancehunt -> Telegram: уведомления о новых проектах.
Версия для GitHub Actions: за один запуск делает одну проверку.
Токены берутся из секретов репозитория (FH_TOKEN, TG_TOKEN, TG_CHAT_ID).
"""

import html
import json
import os
import time
import urllib.parse
import urllib.request

FH_TOKEN = os.environ["FH_TOKEN"]
TG_TOKEN = os.environ["TG_TOKEN"]
TG_CHAT_ID = os.environ["TG_CHAT_ID"]

# ===================== НАСТРОЙКИ =====================
# Категории (ID из адреса страницы категории на сайте):
# 180 — Bot Development, 99 — Web Programming, 43 — Web Design
SKILL_IDS = [180, 99, 43]

# Плюс проекты из ЛЮБЫХ категорий, где в названии/описании есть эти слова:
KEYWORDS = ["презентац", "presentation", "лендинг", "landing", "телеграм бот",
            "telegram bot", "python", "парсер", "minecraft", "майнкрафт"]

# Не присылать проекты, где откликов уже больше этого числа:
MAX_BIDS = 30
# =====================================================

SEEN_FILE = "seen_projects.json"
API = "https://api.freelancehunt.com/v2/projects"


def fh_get(params: dict) -> list:
    url = API + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {FH_TOKEN}",
        "Accept-Language": "ru",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("data", [])


def fetch_projects() -> dict:
    found = {}
    for p in fh_get({"filter[skill_id]": ",".join(map(str, SKILL_IDS))}):
        found[p["id"]] = (p, "категория")
    for p in fh_get({}):
        if p["id"] in found:
            continue
        a = p["attributes"]
        text = (a.get("name", "") + " " + (a.get("description") or "")).lower()
        if any(k in text for k in KEYWORDS):
            found[p["id"]] = (p, "ключевое слово")
    return found


def format_project(p: dict, reason: str) -> str:
    a = p["attributes"]
    budget = a.get("budget")
    budget_txt = f'{budget["amount"]} {budget["currency"]}' if budget else "не указан"
    skills = ", ".join(s["name"] for s in a.get("skills", []))
    desc = (a.get("description") or "").strip().replace("\n", " ")
    if len(desc) > 300:
        desc = desc[:300] + "…"
    link = p.get("links", {}).get("self", {}).get("web", "")
    return (
        f'🆕 <b>{html.escape(a.get("name", ""))}</b>\n'
        f'💰 {html.escape(budget_txt)}   •   📨 откликов: {a.get("bid_count", 0)}\n'
        f'🏷 {html.escape(skills)}  <i>({reason})</i>\n\n'
        f'{html.escape(desc)}\n\n'
        f'<a href="{html.escape(link)}">Открыть проект</a>'
    )


def tg_send(text: str) -> None:
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", data=data, timeout=30)


def load_seen() -> set:
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen)[-2000:], f)


def main() -> None:
    seen = load_seen()
    projects = fetch_projects()

    if not seen:
        # Первый запуск: запоминаем текущие проекты, чтобы не заспамить
        tg_send("✅ Мониторинг Freelancehunt запущен. Буду присылать новые проекты.")
    else:
        new = sorted(pid for pid in projects if pid not in seen)
        for pid in new:
            p, reason = projects[pid]
            if p["attributes"].get("bid_count", 0) <= MAX_BIDS:
                tg_send(format_project(p, reason))
                time.sleep(1)
        print(f"Новых проектов: {len(new)}")

    seen.update(projects.keys())
    save_seen(seen)


if __name__ == "__main__":
    main()
