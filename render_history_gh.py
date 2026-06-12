import os
import json
import subprocess
import tempfile
from datetime import datetime
import git
from tqdm import tqdm
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.transforms import Bbox

# ========== НАСТРОЙКИ ==========
ALERTS_FILE = "alerts.json"
OUTPUT_VIDEO = "alerts_timelapse.mp4"
FPS = 20
MAX_COMMITS = 450
COLORS = {
    "clear": "#6c757d",
    "droneDanger": "#ffc107",
    "droneAlert": "#dc3545",
    "rocket": "#8B0000"
}
GEOJSON_URL = "https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/russia.geojson"

# Границы европейской части России
XLIM = (20, 60)   # долгота
YLIM = (40, 70)   # широта

# Параметры отображения времени
TIME_POS = (0.97, 0.03)
TIME_FONTSIZE = 24
TIME_COLOR = "#ffc107"
TIME_BG_ALPHA = 0.6

# Размер кадра (чётные)
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080
DPI = 100
# ================================

REGION_MAPPING = {
    "Adygea": "Адыгея", "Altai Krai": "Алтайский край", "Altai Republic": "Алтай",
    "Amur Oblast": "Амурская область", "Arkhangelsk Oblast": "Архангельская область",
    "Astrakhan Oblast": "Астраханская область", "Bashkortostan": "Башкортостан",
    "Belgorod Oblast": "Белгородская область", "Bryansk Oblast": "Брянская область",
    "Buryatia": "Бурятия", "Chechnya": "Чечня", "Chelyabinsk Oblast": "Челябинская область",
    "Chukotka Autonomous Okrug": "Чукотский АО", "Chuvash Republic": "Чувашская Республика",
    "Dagestan": "Дагестан", "Ingushetia": "Ингушетия", "Irkutsk Oblast": "Иркутская область",
    "Ivanovo Oblast": "Ивановская область", "Jewish Autonomous Oblast": "Еврейская АО",
    "Kabardino-Balkaria": "Кабардино-Балкария", "Kaliningrad Oblast": "Калининградская область",
    "Kalmykia": "Калмыкия", "Kaluga Oblast": "Калужская область", "Kamchatka Krai": "Камчатский край",
    "Karachay-Cherkessia": "Карачаево-Черкесия", "Karelia": "Республика Карелия",
    "Kemerovo Oblast": "Кемеровская область", "Khabarovsk Krai": "Хабаровский край",
    "Khakassia": "Хакасия", "Khanty-Mansi Autonomous Okrug": "ХМАО", "Kirov Oblast": "Кировская область",
    "Komi": "Республика Коми", "Kostroma Oblast": "Костромская область", "Krasnodar Krai": "Краснодарский край",
    "Krasnoyarsk Krai": "Красноярский край", "Kurgan Oblast": "Курганская область", "Kursk Oblast": "Курская область",
    "Leningrad Oblast": "Ленинградская область", "Lipetsk Oblast": "Липецкая область", "Magadan Oblast": "Магаданская область",
    "Mari El": "Марий Эл", "Mordovia": "Республика Мордовия", "Moscow": "Москва", "Moscow Oblast": "Московская область",
    "Murmansk Oblast": "Мурманская область", "Nenets Autonomous Okrug": "Ненецкий АО", "Nizhny Novgorod Oblast": "Нижегородская область",
    "North Ossetia-Alania": "Северная Осетия", "Novgorod Oblast": "Новгородская область", "Novosibirsk Oblast": "Новосибирская область",
    "Omsk Oblast": "Омская область", "Orenburg Oblast": "Оренбургская область", "Oryol Oblast": "Орловская область",
    "Penza Oblast": "Пензенская область", "Perm Krai": "Пермский край", "Primorsky Krai": "Приморский край",
    "Pskov Oblast": "Псковская область", "Rostov Oblast": "Ростовская область", "Ryazan Oblast": "Рязанская область",
    "Saint Petersburg": "Санкт-Петербург", "Sakha (Yakutia)": "Республика Саха (Якутия)", "Sakhalin Oblast": "Сахалинская область",
    "Samara Oblast": "Самарская область", "Saratov Oblast": "Саратовская область", "Smolensk Oblast": "Смоленская область",
    "Stavropol Krai": "Ставропольский край", "Sverdlovsk Oblast": "Свердловская область", "Tambov Oblast": "Тамбовская область",
    "Tatarstan": "Татарстан", "Tomsk Oblast": "Томская область", "Tula Oblast": "Тульская область", "Tuva": "Тыва",
    "Tver Oblast": "Тверская область", "Tyumen Oblast": "Тюменская область", "Udmurt Republic": "Удмуртская Республика",
    "Ulyanovsk Oblast": "Ульяновская область", "Vladimir Oblast": "Владимирская область", "Volgograd Oblast": "Волгоградская область",
    "Vologda Oblast": "Вологодская область", "Voronezh Oblast": "Воронежская область", "Yamalo-Nenets Autonomous Okrug": "ЯНАО",
    "Yaroslavl Oblast": "Ярославская область", "Zabaykalsky Krai": "Забайкальский край"
}

def normalize_region_name(geo_name):
    return REGION_MAPPING.get(geo_name, geo_name)

def get_color(region_status, region_name):
    st = region_status.get(region_name, {})
    if st.get("rocket", False):
        return COLORS["rocket"]
    if st.get("droneAlert", False):
        return COLORS["droneAlert"]
    if st.get("droneDanger", False):
        return COLORS["droneDanger"]
    return COLORS["clear"]

def render_frame(gdf, region_status, output_png, timestamp):
    """Отрисовывает кадр с точным размером и обрезкой по координатам"""
    # Создаём фигуру нужного размера
    fig, ax = plt.subplots(figsize=(FRAME_WIDTH/DPI, FRAME_HEIGHT/DPI), dpi=DPI)
    ax.set_facecolor('#0a0e1a')
    
    # Рисуем карту
    gdf.plot(ax=ax, color=[get_color(region_status, normalize_region_name(row.get('name', ''))) for _, row in gdf.iterrows()],
             edgecolor='white', linewidth=0.6, alpha=0.85)
    
    # Устанавливаем границы области (европейская часть)
    ax.set_xlim(XLIM)
    ax.set_ylim(YLIM)
    
    # Убираем оси
    ax.set_axis_off()
    
    # Легенда
    legend_elements = [
        mpatches.Patch(color=COLORS["rocket"], label='Ракетная опасность'),
        mpatches.Patch(color=COLORS["droneAlert"], label='Тревога БПЛА (ПВО)'),
        mpatches.Patch(color=COLORS["droneDanger"], label='Опасность БПЛА'),
        mpatches.Patch(color=COLORS["clear"], label='Спокойно / Отбой')
    ]
    ax.legend(handles=legend_elements, loc='lower left',
              facecolor='#0a0e1a', edgecolor='white',
              labelcolor='white', fontsize=14, framealpha=0.8)
    
    # Часы (только время)
    if timestamp:
        time_str = timestamp.strftime("%H:%M:%S")
    else:
        time_str = "--:--:--"
    
    ax.text(TIME_POS[0], TIME_POS[1], time_str,
            transform=ax.transAxes,
            fontsize=TIME_FONTSIZE,
            color=TIME_COLOR,
            fontweight='bold',
            ha='right',
            va='bottom',
            bbox=dict(boxstyle="round,pad=0.4", facecolor='black', alpha=TIME_BG_ALPHA))
    
    # Сохраняем с точным размером, без обрезки
    plt.savefig(output_png, facecolor='#0a0e1a', dpi=DPI, pad_inches=0)
    plt.close(fig)

def get_historical_versions(repo_path, file_path, max_commits=MAX_COMMITS):
    repo = git.Repo(repo_path)
    all_commits = list(repo.iter_commits(paths=file_path))
    commits = all_commits[:max_commits]
    commits.reverse()
    versions = []
    for commit in tqdm(commits, desc="Загрузка версий"):
        try:
            blob = commit.tree / file_path
            content = blob.data_stream.read().decode('utf-8')
            data = json.loads(content)
            dt = commit.committed_datetime
            versions.append((dt, data))
        except Exception as e:
            print(f"Пропускаем коммит {commit.hexsha}: {e}")
    return versions

def main():
    print("Загрузка границ регионов...")
    try:
        gdf = gpd.read_file(GEOJSON_URL)
    except Exception as e:
        print(f"Ошибка загрузки GeoJSON: {e}")
        return

    versions = get_historical_versions(".", ALERTS_FILE)
    print(f"Найдено {len(versions)} версий (ограничение: {MAX_COMMITS})")
    if not versions:
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, (dt, data) in enumerate(versions):
            region_status = data.get("regions", {})
            frame_path = os.path.join(tmpdir, f"frame_{i:05d}.png")
            render_frame(gdf, region_status, frame_path, dt)
            print(f"Кадр {i+1}/{len(versions)} сохранён")
        
        # Команда ffmpeg: принудительно делаем чётные размеры и добавляем масштабирование
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", os.path.join(tmpdir, "frame_%05d.png"),
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # обеспечиваем чётность
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            OUTPUT_VIDEO
        ]
        subprocess.run(cmd, check=True)
        print(f"Видео сохранено: {OUTPUT_VIDEO}")

if __name__ == "__main__":
    main()
