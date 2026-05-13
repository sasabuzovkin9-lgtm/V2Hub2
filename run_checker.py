import base64
import json
import os
import re
import requests
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# ================= НАСТРОЙКИ СВЕРХСТРОГОГО ФИЛЬТРА ПОД МТС =================
ONLY_VLESS_REALITY = True  

# Белый список SNI (маскировок), которые МТС обязан пропускать без блокировок
ALLOWED_SNI = [
    "mts.ru", "mtsbank.ru", "gosuslugi.ru", "kremlin.ru", "government.ru", 
    "cbr.ru", "sberbank.ru", "vtb.ru", "alfabank.ru", "psbank.ru",
    "mironline.ru", "vgtrk.ru", "kommersant.ru"
]
# =========================================================================

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
    "https://obwl.obprojects.lol/sub.txt",
    "githubusercontent.com",
    "https://raw.githubusercontent.com/kort0881/vpn-checker-backend/refs/heads/main/checked/RU_Best/ru_white_all_WHITE.txt",
    "https://raw.githubusercontent.com/mmaksim9191/my-vpn-configs/refs/heads/main/configs/white-cidr-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
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

def get_flag(country_code):
    if not country_code or len(country_code) != 2:
        return "🇺🇳"
    return "".join(chr(127397 + ord(c)) for c in country_code.upper())

def fetch_country_batch(ips):
    geo_map = {}
    if not list(ips): return geo_map
    try:
        ips_list = list(ips)
        for i in range(0, len(ips_list), 100):
            batch = ips_list[i:i+100]
            payload = [{"query": ip} for ip in batch]
            res = requests.post("ip-api.com", json=payload, timeout=5).json()
            for item in res:
                if item.get('countryCode'):
                    geo_map[item['query']] = item['countryCode']
    except: pass
    return geo_map

def strict_mts_filter(config, geo_map):
    if not config.startswith("vless://"):
        return None

    has_mts_sni = False
    config_lower = config.lower()
    detected_sni = "unknown.ru"
    
    for sni in ALLOWED_SNI:
        if f"sni={sni}" in config_lower or f"peer={sni}" in config_lower:
            has_mts_sni = True
            detected_sni = sni
            break

    if not has_mts_sni:
        return None

    host, port = parse_target(config)
    if not host or not port: return None

    country_code = geo_map.get(str(host), "UN")
    flag = get_flag(country_code)

    try:
        parsed_url = urllib.parse.urlparse(config)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'type' not in query_params:
            query_params['type'] = ['grpc']
            query_params['serviceName'] = ['grpc-service']
        
        query_params['fragment'] = ['1-3,5-12']
        query_params['timeout'] = ['10-20']
        query_params['mux'] = ['max_connections=8']
        query_params['fp'] = ['chrome']
        
        node_id = os.urandom(2).hex().upper()
        server_name = f"{flag} [{detected_sni}] MTS-KURSK-{node_id}"
        
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        mutated_config = urllib.parse.urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, server_name
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
    print(f"[+] Собрано {len(unique_nodes)} уникальных нод.")

    all_ips = set()
    for node in unique_nodes:
        host, _ = parse_target(node)
        if host and re.match(r'^[0-9.]+$', str(host)):
            all_ips.add(str(host))

    print(f"[~] Определение локаций для {len(all_ips)} серверов...")
    geo_map = fetch_country_batch(all_ips)

    print("[+] Распределение параметров фрагментации и РУ-маскировок...")
    working_nodes = []
    for node in unique_nodes:
        res = strict_mts_filter(node, geo_map)
        if res:
            working_nodes.append(res)

    print(f"[+] Фильтрация завершена! Найдено серверов для МТС: {len(working_nodes)}")

    output_text = "\n".join(working_nodes)
    b64_output = base64.b64encode(output_text.encode("utf-8")).decode("utf-8")

    with open("only_working.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    with open("merged_base64", "w", encoding="utf-8") as f:
        f.write(b64_output)
    print("[+] Репозиторий успешно обновлен под белые списки МТС.")

if __name__ == "__main__":
    main()
