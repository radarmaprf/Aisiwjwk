import json
import re
import time
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

# ---------- НАСТРОЙКИ ----------
CHANNEL = "vrv_radar"
BASE_URL = f"https://t.me/s/{CHANNEL}"
POSTS_LIMIT = 200
IGNORED_REGIONS = ["Астраханская область", "Архангельская область", "Омская область", "Курганская область","Москва"]

# Стоп-слова для фильтрации рекламных / информационных сообщений
STOP_WORDS = [
    "реклама", "подпишись", "подписаться", "каналы", "телеграм", "telegram",
    "бот", "сводки", "новости", "срочно", "важно", "обзор", "дайджест",
    "канал", "чат", "группа", "вконтакте", "vk", "youtube", "инстаграм",
    "instagram", "facebook", "twitter", "ссылка", "поддержать", "донат",
    "промокод", "скидка", "акция", "партнёр", "репост", "лайк", "комментарий"
]

REGION_ALIASES = {
    "Москва": ["москва"], "Московская область": ["московская область", "подмосковье"],
    "Санкт-Петербург": ["санкт-петербург", "питер", "спб"],
    "Ленинградская область": ["ленинградская область", "ленобласть"],
    "Белгородская область": ["белгородская область", "белгород"],
    "Брянская область": ["брянская область", "брянск"],
    "Владимирская область": ["владимирская область", "владимир"],
    "Воронежская область": ["воронежская область", "воронеж"],
    "Ивановская область": ["ивановская область", "иваново"],
    "Калужская область": ["калужская область", "калуга"],
    "Костромская область": ["костромская область", "кострома"],
    "Курская область": ["курская область", "курск"],
    "Липецкая область": ["липецкая область", "липецк"],
    "Нижегородская область": ["нижегородская область", "нижний новгород"],
    "Новгородская область": ["новгородская область", "великий новгород", "новгород"],
    "Орловская область": ["орловская область", "орёл"],
    "Пензенская область": ["пензенская область", "пенза"],
    "Псковская область": ["псковская область", "псков"],
    "Рязанская область": ["рязанская область", "рязань"],
    "Смоленская область": ["смоленская область", "смоленск"],
    "Тамбовская область": ["тамбовская область", "тамбов"],
    "Тверская область": ["тверская область", "тверь"],
    "Тульская область": ["тульская область", "тула"],
    "Ярославская область": ["ярославская область", "ярославль"],
    "Краснодарский край": ["краснодарский край", "краснодар", "кубань"],
    "Ставропольский край": ["ставропольский край", "ставрополь"],
    "Ростовская область": ["ростовская область", "ростов-на-дону", "ростов"],
    "Волгоградская область": ["волгоградская область", "волгоград"],
    "Татарстан": ["татарстан", "республика татарстан", "казань"],
    "Башкортостан": ["башкортостан", "республика башкортостан", "уфа"],
    "Марий Эл": ["марий эл", "республика марий эл", "йошкар-ола"],
    "Чувашия": ["чувашия", "чувашская республика", "чебоксары"],
    "Республика Мордовия": ["мордовия", "республика мордовия", "саранск"],
    "Удмуртская Республика": ["республика удмуртия", "удмуртская республика", "ижевск"],
    "Самарская область": ["самарская область", "самара"],
    "Саратовская область": ["саратовская область", "саратов"],
    "Ульяновская область": ["ульяновская область"],
    "Свердловская область": ["свердловская область", "екатеринбург"],
    "Челябинская область": ["челябинская область", "челябинск"],
    "Курганская область": ["курганская область", "курган"],
    "Оренбургская область": ["оренбургская область", "оренбург"],
    "Пермский край": ["пермский край", "пермь"],
    "Новосибирская область": ["новосибирская область", "новосибирск"],
    "Томская область": ["томская область", "томск"],
    "Кемеровская область": ["кемеровская область", "кемерово", "кузбасс"],
    "Иркутская область": ["иркутская область", "иркутск"],
    "Красноярский край": ["красноярский край", "красноярск"],
    "Алтайский край": ["алтайский край", "барнаул"],
    "Забайкальский край": ["забайкальский край", "чита"],
    "Приморский край": ["приморский край", "владивосток"],
    "Хабаровский край": ["хабаровский край", "хабаровск"],
    "Амурская область": ["амурская область", "благовещенск"],
    "Сахалинская область": ["сахалинская область", "сахалин", "южно-сахалинск"],
    "Магаданская область": ["магаданская область", "магадан"],
    "Камчатский край": ["камчатский край", "камчатка", "петропавловск-камчатский"],
    "Мурманская область": ["мурманская область", "мурманск"],
    "Крым": ["крым", "республика крым"],
    "Дагестан": ["дагестан", "республика дагестан", "махачкала"],
    "Республика Карелия": ["карелия", "республика карелия", "петрозаводск"],
    "Республика Коми": ["коми", "республика коми", "сыктывкар"],
    "Республика Саха (Якутия)": ["якутия", "саха", "якутск"],
    "ХМАО": ["хмао", "ханты-мансийский", "ханты-мансийск", "сургут"],
    "ЯНАО": ["янао", "ямало-ненецкий", "новый уренгой", "ноябрьск"],
    "Адыгея": ["адыгея", "республика адыгея", "майкоп"]
}
for ign in IGNORED_REGIONS:
    REGION_ALIASES.pop(ign, None)

def load_previous_state() -> Dict[str, Dict]:
    try:
        with open("alerts.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            if "regions" in data:
                return data["regions"]
    except Exception:
        pass
    return {}

def save_alerts(state: Dict[str, Dict]):
    data = {"last_updated": datetime.now(timezone.utc).isoformat(), "regions": {}}
    for region in REGION_ALIASES:
        st = state.get(region, {"rocket": False, "droneAlert": False, "droneDanger": False})
        out = {
            "rocket": st.get("rocket", False),
            "droneAlert": st.get("droneAlert", False),
            "droneDanger": st.get("droneDanger", False)
        }
        if st.get("droneAlert", False) and "droneAlert_time" in st:
            out["droneAlert_time"] = st["droneAlert_time"]
        data["regions"][region] = out
    with open("alerts.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[{datetime.now().isoformat()}] alerts.json обновлён, регионов: {len(data['regions'])}")

# ---------- ФУНКЦИИ ПАРСИНГА ----------
def fetch_page(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

def extract_posts(html: str) -> List[Tuple[int, str]]:
    pattern = r'data-post="[^/]+/(\d+)".*?(?:tgme_widget_message_text|tgme_widget_message_caption)[^>]*>(.*?)</div>'
    posts = []
    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        post_id = int(match.group(1))
        raw_text = re.sub(r'<[^>]+>', ' ', match.group(2))
        text = re.sub(r'\s+', ' ', raw_text).strip().lower()
        if text:
            posts.append((post_id, text))
    return posts

def is_advertisement(text: str) -> bool:
    """Проверяет, содержит ли текст рекламные/информационные маркеры"""
    text_lower = text.lower()
    for word in STOP_WORDS:
        if word in text_lower:
            return True
    return False

def classify_message(text: str):
    # Глобальный отбой БПЛА по всем регионам
    if re.search(r'отбой.*бпла.*всех.*регион|снята угроза бпла во всех регионах|отбой опасности по бпла во всех ранее объявленных регионах', text):
        return ('globalCancelDrone', None)
    
    # Проверяем отбой с указанием типа
    is_cancel = re.search(r'отбой|снят[ао]|завершен[ао]|отменен[ао]|нет\s*угрозы|угроза\s*снят[ао]', text)
    if is_cancel:
        cancel_rocket = re.search(r'ракетн(?:ая|ую|ой|ая)\s*опасность\s*отменен|отбой\s*ракетн', text)
        cancel_drone = re.search(r'отбой\s*бпла|снят[ао]\s*бпла|отбой\s*опасности\s*бпла', text)
        if cancel_rocket:
            return ('cancel', 'rocket')
        if cancel_drone:
            return ('cancel', 'drone')
        # Если нет уточнения, считаем отменой всего
        return ('cancel', 'all')
    
    is_rocket = re.search(r'ракетн(?:ая|ую|ой|ая)\s*(?:опасность|тревога)|баллистическ(?:ая|ую)|крылат(?:ая|ую)', text)
    is_drone_danger = re.search(r'бпла|беспилотн(?:ик|ый|ая)|опасность\s*бпла|угроза\s*бпла', text)
    is_fixation = re.search(r'фиксаци[яи]|работа\s*пво|пво\s*работает|заходит группа|сбитие|тревога\s*бпла', text)
    
    if is_rocket:
        return ('alert', 'rocket')
    if is_fixation:
        return ('alert', 'droneAlert')
    if is_drone_danger:
        return ('alert', 'droneDanger')
    return (None, None)

def get_affected_regions(text: str) -> List[str]:
    matched = []
    for official, keywords in REGION_ALIASES.items():
        if any(kw in text for kw in keywords):
            matched.append(official)
    return matched

def fetch_all_posts() -> List[Tuple[int, str]]:
    all_posts = []
    next_url = BASE_URL
    oldest_id = None
    pages = 0
    while len(all_posts) < POSTS_LIMIT and pages < 25:
        pages += 1
        html = fetch_page(next_url)
        posts = extract_posts(html)
        if not posts:
            break
        for pid, ptext in posts:
            if pid not in [x[0] for x in all_posts]:
                all_posts.append((pid, ptext))
        current_oldest = min(p[0] for p in posts)
        if current_oldest == oldest_id:
            break
        oldest_id = current_oldest
        next_url = f"{BASE_URL}?before={oldest_id}"
        time.sleep(0.8)
    all_posts.sort(key=lambda x: x[0])
    return all_posts[-POSTS_LIMIT:]

def apply_timeout(state: Dict[str, Dict]):
    now = datetime.now(timezone.utc)
    timeout = timedelta(hours=1)
    for region, st in state.items():
        if st.get("droneAlert", False) and "droneAlert_time" in st:
            try:
                alert_time = datetime.fromisoformat(st["droneAlert_time"])
                if now - alert_time > timeout:
                    st["droneAlert"] = False
                    st["droneDanger"] = True
                    del st["droneAlert_time"]
                    print(f"[{region}] Автоматический переход из droneAlert в droneDanger (истек час)")
            except Exception as e:
                print(f"Ошибка разбора времени для {region}: {e}")

def compute_status() -> Dict[str, Dict]:
    previous = load_previous_state()
    status = {}
    for region in REGION_ALIASES:
        if region in previous:
            st = previous[region]
            status[region] = {
                "rocket": st.get("rocket", False),
                "droneAlert": st.get("droneAlert", False),
                "droneDanger": st.get("droneDanger", False)
            }
            if "droneAlert_time" in st:
                status[region]["droneAlert_time"] = st["droneAlert_time"]
        else:
            status[region] = {"rocket": False, "droneAlert": False, "droneDanger": False}

    posts = fetch_all_posts()
    for pid, text in posts:
        # ---------- ФИЛЬТР РЕКЛАМЫ ----------
        if is_advertisement(text):
            print(f"[{pid}] Сообщение пропущено (реклама/информация): {text[:50]}...")
            continue

        msg_type, subtype = classify_message(text)
        if msg_type == 'globalCancelDrone':
            # Глобальный отбой БПЛА: снимаем все тревоги БПЛА
            for region in REGION_ALIASES:
                status[region]["droneAlert"] = False
                status[region]["droneDanger"] = False
                if "droneAlert_time" in status[region]:
                    del status[region]["droneAlert_time"]
            continue
        
        regions = get_affected_regions(text)
        if not regions:
            continue
        
        if msg_type == 'cancel':
            for reg in regions:
                if subtype == 'rocket':
                    status[reg]["rocket"] = False
                elif subtype == 'drone':
                    status[reg]["droneAlert"] = False
                    status[reg]["droneDanger"] = False
                    if "droneAlert_time" in status[reg]:
                        del status[reg]["droneAlert_time"]
                elif subtype == 'all':
                    status[reg]["rocket"] = False
                    status[reg]["droneAlert"] = False
                    status[reg]["droneDanger"] = False
                    if "droneAlert_time" in status[reg]:
                        del status[reg]["droneAlert_time"]
        elif msg_type == 'alert':
            for reg in regions:
                if subtype == 'rocket':
                    status[reg]["rocket"] = True
                elif subtype == 'droneAlert':
                    status[reg]["droneAlert"] = True
                    status[reg]["droneDanger"] = False
                    status[reg]["droneAlert_time"] = datetime.now(timezone.utc).isoformat()
                elif subtype == 'droneDanger':
                    status[reg]["droneDanger"] = True
                    if status[reg].get("droneAlert"):
                        status[reg]["droneAlert"] = False
                        if "droneAlert_time" in status[reg]:
                            del status[reg]["droneAlert_time"]
    # Применяем тайм-аут
    apply_timeout(status)
    return status

def main():
    try:
        status = compute_status()
        save_alerts(status)
    except Exception as e:
        print(f"Ошибка: {e}")
        raise

if __name__ == "__main__":
    main()
