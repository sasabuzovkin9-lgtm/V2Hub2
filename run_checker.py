import base64
import json
import os
import re
import requests
import urllib.parse

# ================= МАКСИМАЛЬНЫЙ ФИЛЬТР И МОДИФИКАТОР ДЛЯ РФ =================
ONLY_VLESS_REALITY = True  

# Бескомпромиссные SNI из ядра белых списков ТСПУ (сервисы авторизации и CDN)
ALLOWED_SNI = [
    "samsung.com", "apple.com", "microsoft.com", "google.com", "dl.pki.goog",
    "sberbank.ru", "vk.com", "yandex.ru", "wildberries.ru", "selectel.ru",
    "timeweb.ru", "beget.com", "cdnvideo.ru", "edgecenter.ru", "speedtest.net"
]

# Полный бан подсетей хостингов, заблокированных регулятором в Курской области
BANNED_KEYWORDS = [
    "aeza", "pq", "mivo", "justhost", "vdsina", "serverspace", "ru-vds", 
    "ip-volume", "zomro", "timeweb", "firstvds", "ispsystem", "vscale", 
    "cloud", "vps", "dedic", "host"
]
# ============================================================================

SOURCES = [
    "https://raw.githubusercontent.com/luxxuria/harvester/refs/heads/main/non_ru.txt",
    "https://raw.githubusercontent.com/prominbro/sub/refs/heads/main/212.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/SilentGhostCodes/WhiteListVpn/refs/heads/main/Whitelist.txt",
    "https://raw.githubusercontent.com/SilentGhostCodes/WhiteListVpn/refs/heads/main/Whitelist%20%E2%84%962.txt",
    "https://raw.githubusercontent.com/ByeWhiteLists/ByeWhiteLists2/refs/heads/main/ByeWhiteLists2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/refs/heads/main/protocols/hy2.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/SilentGhostCodes/WhiteListVpn/refs/heads/main/BlackList.txt",
    "https://raw.githubusercontent.com/gergew452/Generation-Liberty/refs/heads/main/githubmirror/best.txt",
    "https://raw.githubusercontent.com/FLAT447/v2ray-lists/refs/heads/main/githubmirror/1.txt",
    "https://raw.githubusercontent.com/nikita29a/FreeProxyList/refs/heads/main/mirror/1.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/kort0881/vpn-checker-backend/refs/heads/main/checked/RU_Best/ru_white_all_WHITE.txt",
    "https://raw.githubusercontent.com/mmaksim9191/my-vpn-configs/refs/heads/main/configs/white-cidr-checked.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/Sanuyyq/sub-storage1/refs/heads/main/bs.txt",
    "https://gist.githubusercontent.com/pythoneer-dev-q/49c33dd8d4e279611e30a8c6fd938230/raw/mobile.txt",
    "https://gitflic.ru/project/sigil/my-new-cool-project/blob/raw?file=whitelist",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "tgflovv.ru",
    "https://raw.githubusercontent.com/Temnuk/naabuzil/refs/heads/main/whitelist",
    "https://raw.githubusercontent.com/Kirill39127/-my-sub/refs/heads/main/sub.txt",
    "https://raw.githubusercontent.com/likzil/vless1/main/Treetcpvpn",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_universal.txt"
]

def b64_decode(s):
    s = s.strip().replace("\n", "").replace("\r", "")
    pad = len(s) % 4
    if pad: s += "=" * (4 - pad)
    try: return base64.b64decode(s).decode("utf-8", errors="ignore")
    except: return ""

def parse_target(config):
    try:
        match = re.search(r'@([^:]+):(\d+)', config)
        if match: return match.group(1), int(match.group(2))
    except: pass
    return None, None

def transform_and_mutate(config):
    if not config.startswith("vless://"):
        return None

    # 1. Проверка валидности маскировки
    has_valid_sni = False
    config_lower = config.lower()
    for sni in ALLOWED_SNI:
        if f"sni={sni}" in config_lower or f"peer={sni}" in config_lower:
            has_valid_sni = True
            break

    if not has_valid_sni:
        return None

    host, port = parse_target(config)
    if not host or not port: return None
    host_str = str(host).lower()
    
    # 2. Исключение заведомо заблокированных подсетей хостинга
    for banned in BANNED_KEYWORDS:
        if banned in host_str:
            return None

    # Оставляем только системные порты обхода (443 и 8443)
    if int(port) not in [443, 8443]:
        return None

    # 3. МОДИФИКАЦИЯ ССЫЛКИ (Внедрение супер-настроек обхода DPI)
    try:
        parsed_url = urllib.parse.urlparse(config)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Инжектируем агрессивную фрагментацию пакетов (Fragment)
        query_params['fragment'] = ['10-20,30-50']
        
        # Включаем многопоточное маскирование (Mux) для сокрытия паттернов
        query_params['mux'] = ['max_connections=8']
        
        # Пересобираем ссылку обратно
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        mutated_config = urllib.parse.urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, parsed_url.fragment
        ))
        return mutated_config
    except:
        return config

def main():
    print("[+] Скачивание конфигураций из источников...")
    all_nodes = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=5).text
            if not res.startswith(("vless://", "vmess://", "trojan://", "ss://")):
                lines = b64_decode(res).splitlines()
            else:
                lines = res.splitlines()
            all_nodes.extend([l.strip() for l in lines if l.strip()])
        except: continue

    unique_nodes = list(set(all_nodes))
    print(f"[+] Собрано {len(unique_nodes)} нод. Запуск инжектора параметров Fragment...")

    working_nodes = []
    for node in unique_nodes:
        mutated_node = transform_and_mutate(node)
        if mutated_node:
            working_nodes.append(mutated_node)

    print(f"[+] Сверхстрогий отбор завершен! Модифицировано элитных нод под Курск: {len(working_nodes)}")

    output_text = "\n".join(working_nodes)
    b64_output = base64.b64encode(output_text.encode("utf-8")).decode("utf-8")

    with open("only_working.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    with open("merged_base64", "w", encoding="utf-8") as f:
        f.write(b64_output)
    print("[+] Репозиторий успешно обновлен.")

if __name__ == "__main__":
    main()
