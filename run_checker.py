import base64
import json
import os
import re
import socket
import requests
from concurrent.futures import ThreadPoolExecutor

# ================== НАСТРОЙКИ ЧЕКЕРА ==================
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
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/Sanuyyq/sub-storage1/refs/heads/main/bs.txt"
]

TEST_SITE = "google.com"  # Сайт проверки
TIMEOUT_SEC = 2            # Ожидание ответа от прокси (в сек)
THREADS = 40               # Количество потоков для быстрой проверки
# ======================================================

def b64_decode(s):
    s = s.strip().replace("\n", "").replace("\r", "")
    pad = len(s) % 4
    if pad: s += "=" * (4 - pad)
    try: return base64.b64decode(s).decode("utf-8", errors="ignore")
    except: return ""

def parse_target(config):
    try:
        if "vmess://" in config:
            data = json.loads(b64_decode(config.replace("vmess://", "")))
            return data.get("add"), int(data.get("port"))
        match = re.search(r'@([^:]+):(\d+)', config)
        if match: return match.group(1), int(match.group(2))
    except: pass
    return None, None

def ping_check(config):
    host, port = parse_target(config)
    if not host or not port: return None
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT_SEC):
            return config
    except: return None

def main():
    print("[+] Скачивание конфигураций...")
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
    print(f"[+] Собрано {len(unique_nodes)} уникальных нод. Запуск пинг-теста...")

    working_nodes = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        results = executor.map(ping_check, unique_nodes)
        for r in results:
            if r: working_nodes.append(r)

    print(f"[+] Проверка завершена! Рабочих серверов: {len(working_nodes)} из {len(unique_nodes)}")

    output_text = "\n".join(working_nodes)
    b64_output = base64.b64encode(output_text.encode("utf-8")).decode("utf-8")

    with open("only_working.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    with open("merged_base64", "w", encoding="utf-8") as f:
        f.write(b64_output)
    print("[+] Файлы обновлены.")

if __name__ == "__main__":
    main()
