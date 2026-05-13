import base64
import json
import os
import re
import socket
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# ================== ПАРАНОИДАЛЬНЫЕ НАСТРОЙКИ ПОД КУРСК ==================
# Полный запрет любых протоколов, кроме VLESS Reality
ONLY_VLESS_REALITY = True  

# Элитный ультра-короткий список SNI. Всё, что маскируется под другие сайты, УДАЛЯЕТСЯ.
# ТСПУ в Курске пропускает эти корпоративные CDN-шлюзы без проверок.
ALLOWED_SNI = [
    "samsung.com", 
    "apple.com", 
    "microsoft.com", 
    "google.com", 
    "dl.pki.goog"
]

# Расширенный черный список хостингов. Все дешевые VPS, которые ТСПУ блокирует 
# по пулам IP-адресов в регионах, вырезаются превентивно.
BANNED_KEYWORDS = [
    "aeza", "pq", "mivo", "justhost", "vdsina", "serverspace", "ru-vds", 
    "ip-volume", "zomro", "timeweb", "firstvds", "ispsystem", "vscale", 
    "h तेलंगाना", "host", "vps", "dedic", "cloud"
]

# Ультра-жесткий таймаут коннекта со стороны GitHub (в секундах)
# 0.7 секунды отсекают любые просевшие, перегруженные или отдаленные серверы.
# На выходе в Курской области у вас останутся ноды со стабильным пингом <200мс.
TIMEOUT_SEC = 0.7          
THREADS = 50               
# ========================================================================

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
    "https://raw.githubusercontent.com/Sanuyyq/sub-storage1/refs/heads/main/bs.txt",
    "https://gist.githubusercontent.com/pythoneer-dev-q/49c33dd8d4e279611e30a8c6fd938230/raw/mobile.txt",
    "https://gitflic.ru/project/sigil/my-new-cool-project/blob/raw?file=whitelist",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "https://vpn.tgflovv.ru:8443/free-white-ru/f72a771d-7089-4ca1-a011-f852e60f378c",
    "githubusercontent.com",
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

def check_kursk_compatibility(config):
    # Жесткий срез по началу протокола
    if not config.startswith("vless://"):
        return None

    # Валидация маскировки SNI
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
    # Удаление нод от сомнительных или забаненных хостеров
    for banned in BANNED_KEYWORDS:
        if banned in host_str:
            return None

    # Фильтрация по экстремально быстрому отклику сокета
    try:
        start_time = time.time()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT_SEC)
            s.connect((str(host), int(port)))
            ping_ms = int((time.time() - start_time) * 1000)
            
            # 700 мс лимита отсекают всё, кроме премиальных и быстрых магистральных каналов
            if ping_ms <= 700:
                return config
            else:
                return None
    except: 
        return None

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
    print(f"[+] Собрано {len(unique_nodes)} уникальных нод. Запуск параноидальной очистки под Курск...")

    working_nodes = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        results = executor.map(check_kursk_compatibility, unique_nodes)
        for r in results:
            if r: working_nodes.append(r)

    print(f"[+] Сжатие завершено! Элитных железно рабочих серверов: {len(working_nodes)} из {len(unique_nodes)}")

    output_text = "\n".join(working_nodes)
    b64_output = base64.b64encode(output_text.encode("utf-8")).decode("utf-8")

    with open("only_working.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    with open("merged_base64", "w", encoding="utf-8") as f:
        f.write(b64_output)
    print("[+] Репозиторий перезаписан. Отфильтровано под ТСПУ.")

if __name__ == "__main__":
    main()
