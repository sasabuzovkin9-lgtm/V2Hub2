import base64
import json
import os
import random
import re
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# ================= НАСТРОЙКИ СВЕРХСТРОГОГО КОММЕРЧЕСКОГО ФИЛЬТРА =================
ONLY_VLESS_REALITY = True  

# Элитные SNI из ядра белых списков ТСПУ (сервисы авторизации и CDN)
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

STATIC_SOURCES = [
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
    "https://obwl.obprojects.lol/sub.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/kort0881/vpn-checker-backend/refs/heads/main/checked/RU_Best/ru_white_all_WHITE.txt",
    "https://raw.githubusercontent.com/mmaksim9191/my-vpn-configs/refs/heads/main/configs/white-cidr-checked.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/Kirillo4ka/eavevpn-configs/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/Sanuyyq/sub-storage1/refs/heads/main/bs.txt",
    "https://gitverse.ru/api/repos/rstnnl/sb/raw/branch/master/gen.txt",
    "https://gist.githubusercontent.com/pythoneer-dev-q/49c33dd8d4e279611e30a8c6fd938230/raw/mobile.txt",
    "https://gitflic.ru/project/sigil/my-new-cool-project/blob/raw?file=whitelist",
    "https://raw.githubusercontent.com/zieng2/wl/main/vless_lite.txt",
    "https://vpn.tgflovv.ru:8443/free-white-ru/f72a771d-7089-4ca1-a011-f852e60f378c",
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

def get_dynamic_sources():
    discovered_urls = []
    keywords = ["vless-reality-russia", "vpn-whitelist-ru", "vless-whitelist"]
    print("[~] Поиск новых актуальных подписок на GitHub...")
    for kw in keywords:
        try:
            api_url = f"github.com{kw}&sort=updated&order=desc"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(api_url, headers=headers, timeout=5).json()
            repos = res.get('items', [])
            for repo in repos[:3]:
                owner = repo['owner']['login']
                name = repo['name']
                for filename in ["sub.txt", "merged_base64", "main.txt", "vless.txt"]:
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/main/{filename}"
                    discovered_urls.append(raw_url)
        except: continue
    return list(set(discovered_urls))

def transform_and_mutate(config):
    if not config.startswith("vless://"):
        return None

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
    
    for banned in BANNED_KEYWORDS:
        if banned in host_str:
            return None

    # Оставляем только системные порты обхода (443 и 8443)
    if int(port) not in [443, 8443]:
        return None

    try:
        parsed_url = urllib.parse.urlparse(config)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        f_start, f_mid = random.randint(1, 4), random.randint(5, 12)
        f_end, f_last = random.randint(15, 35), random.randint(40, 65)
        t_start, t_end = random.randint(5, 15), random.randint(20, 35)
        
        query_params['fragment'] = [f"{f_start}-{f_mid},{f_end}-{f_last}"]
        query_params['timeout'] = [f"{t_start}-{t_end}"]
        query_params['mux'] = ['max_connections=8']
        
        node_id = random.randint(100, 999)
        server_name = f"SYS-SERVICE-TR-{node_id}"
        
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        mutated_config = urllib.parse.urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, server_name
        ))
        return mutated_config
    except:
        return config

def fetch_url(url):
    try:
        res = requests.get(url, timeout=5).text
        if not res.startswith(("vless://", "vmess://", "trojan://", "ss://")):
            return b64_decode(res).splitlines()
        return res.splitlines()
    except:
        return []

def main():
    dynamic_urls = get_dynamic_sources()
    all_sources = STATIC_SOURCES + dynamic_urls
    print(f"[+] Всего источников для скачивания: {len(all_sources)} (39 ваших + {len(dynamic_urls)} автопоиск)")

    all_nodes = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(fetch_url, all_sources)
        for lines in results:
            all_nodes.extend([l.strip() for l in lines if l.strip()])

    unique_nodes = list(set(all_nodes))
    print(f"[+] Собрано {len(unique_nodes)} уникальных нод. Запуск коммерческой мутации сигнатур...")

    working_nodes = []
    for node in unique_nodes:
        mutated_node = transform_and_mutate(node)
        if mutated_node:
            working_nodes.append(mutated_node)

    print(f"[+] Сверхстрогий отбор завершен! Сгенерировано элитных нод под Курск: {len(working_nodes)}")

    output_text = "\n".join(working_nodes)
    b64_output = base64.b64encode(output_text.encode("utf-8")).decode("utf-8")

    with open("only_working.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    with open("merged_base64", "w", encoding="utf-8") as f:
        f.write(b64_output)
    print("[+] Репозиторий успешно обновлен.")

if __name__ == "__main__":
    main()
