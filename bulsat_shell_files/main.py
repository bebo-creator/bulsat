# -*- coding: utf-8 -*-
import configparser
import os
import time
import sys
from lib import bsc

# --- User-Agent, който ще се използва за API заявките (вдъхновен от docker-bulsatcom) ---
# Този User-Agent ще се използва за самата комуникация със сървъра на Булсатком.
# User-Agent-ът, който евентуално се добавя към M3U URL-ите, ще дойде от os_id настройката.
API_REQUEST_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
# Твърдо кодирана app_version за API заявките, както е в docker-bulsatcom
API_REQUEST_APP_VERSION = '0.01'

# --- Настройки за User-Agent, който да се добави към M3U URL-ите (ако use_ua_in_m3u е true) ---
# Тези са базирани на оригиналния os_id от config.ini
M3U_URL_USER_AGENTS = {
    'samsungtv': 'Mozilla/5.0 (SMART-TV; Linux; Tizen 2.3) AppleWebkit/538.1 (KHTML, like Gecko) SamsungBrowser/1.0 TV Safari/538.1',
    'androidtv': 'okhttp/3.12.12',
    'pcweb': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36' # Пример за pcweb
}

def get_config():
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        print("Грешка: Файлът config.ini не е намерен. Моля, създайте го.")
        sys.exit(1)
    config.read('config.ini')
    if 'bulsat' not in config:
        print("Грешка: Секцията [bulsat] липсва в config.ini.")
        sys.exit(1)
    return config['bulsat']

def progress_callback_shell(progress_info):
    message = progress_info.get('str', '')
    percentage = progress_info.get('pr', None)
    idx = progress_info.get('idx', None)
    max_val = progress_info.get('max', None)
    if percentage is not None:
        progress_bar = f"[{'=' * int(percentage / 10)}{' ' * (10 - int(percentage / 10))}] {percentage}%"
        if idx and max_val: print(f"{progress_bar} - {message} ({idx}/{max_val})")
        else: print(f"{progress_bar} - {message}")
    else: print(message)

def main():
    cfg = get_config()

    username = cfg.get('username', '')
    password = cfg.get('password', '')
    save_dir = cfg.get('save_dir', './output')
    debug_mode = cfg.getboolean('debug', False)
    cache_time_min = cfg.getint('cache_time', 240)
    time_out_sec = cfg.getfloat('time_out', 10)

    # os_id от config ще се използва за избор на ендпойнт (/tv/samsungtv/live или /tv/androidtv/live)
    # и за User-Agent-а, който се добавя към M3U URL-ите.
    # За самата API заявка към Булсатком, bsc.py ще използва твърдо кодирани стойности,
    # вдъхновени от docker-bulsatcom (десктоп User-Agent, app_version "0.01", device_id = os_id_str).
    os_id_str = cfg.get('os_id', 'samsungtv').lower()

    # app_version от config.ini вече не се използва за API заявката, тъй като bsc.py ще ползва "0.01"
    # cfg.get('app_version') # Запазваме го, ако решим да го ползваме за нещо друго

    base_url = cfg.get('base_url', 'https://api.iptv.bulsat.com')
    # android_friendly_name вече не е нужен за генериране на device_id по новия метод,
    # но го оставяме за момента, ако потребителят го е задал. bsc.py ще го игнорира.
    # cfg.get('android_friendly_name', 'DefaultAndroidDevice')

    enable_catchup_config = cfg.getboolean('enable_catchup', True)
    append_token_to_url_config = cfg.getboolean('append_token_to_stream_url', False)
    token_param_name_config = cfg.get('stream_url_token_param_name', 'ssbulsatapi')

    # Нова опция: Дали да се добавя |User-Agent= към M3U URL-ите
    # По подразбиране ще е false, тъй като docker-bulsatcom не го прави.
    use_ua_in_m3u_url_config = cfg.getboolean('use_user_agent_in_m3u_url', False)

    if not username or not password:
        print("Моля, въведете вашето потребителско име и парола в config.ini")
        sys.exit(1)

    if os_id_str not in M3U_URL_USER_AGENTS: # Проверка дали os_id_str е валиден ключ
        print(f"Грешка: Невалидна стойност за 'os_id' в config.ini: '{os_id_str}'. Трябва да е една от {list(M3U_URL_USER_AGENTS.keys())}")
        sys.exit(1)

    # User-Agent, който ще се добави към M3U URL-ите (ако use_ua_in_m3u_url_config е True)
    m3u_url_user_agent_to_pass = M3U_URL_USER_AGENTS[os_id_str]

    if not os.path.exists(save_dir):
        try: os.makedirs(save_dir)
        except OSError as e: print(f"Грешка при създаване на директория {save_dir}: {e}"); sys.exit(1)

    print(f"Използване на os_id (за ендпойнт и M3U User-Agent): {os_id_str}")
    print(f"User-Agent за API заявки (твърдо кодиран в bsc.py): {API_REQUEST_USER_AGENT}")
    print(f"App Version за API заявки (твърдо кодирана в bsc.py): {API_REQUEST_APP_VERSION}")
    print(f"User-Agent за M3U URL-и (ако е активна опцията): {m3u_url_user_agent_to_pass}")
    print(f"Директория за запис: {os.path.abspath(save_dir)}")

    try:
        bulsat_client = bsc.dodat(
            base=base_url,
            login={'usr': username, 'pass': password},
            path=save_dir,
            cachetime=float(cache_time_min / 60),
            dbg=debug_mode,
            timeout=time_out_sec,
            ver="2.0.0-docker-bulsatcom-inspired",
            xxx=False,
            # Тези параметри се подават към bsc.py, който ще ги използва по новия начин:
            os_id=os_id_str,  # Ще се използва за избор на ендпойнт /tv/{os_id}/live и като device_id
            agent_id=API_REQUEST_USER_AGENT, # User-Agent за API заявките
            app_ver=API_REQUEST_APP_VERSION,   # app_version "0.01" за API заявките

            force_group_name=False,
            use_ua=use_ua_in_m3u_url_config, # Дали да се добавя User-Agent към M3U URL-ите
            # use_rec се базира на оригиналния os_id (androidtv имаше use_rec=true)
            # За новия подход, може би трябва да е винаги false, или да зависи от това дали API-то връща ndvr
            use_rec=True if os_id_str == 'androidtv' else False, # Запазваме старата логика за use_rec, но тя може да не е релевантна
                                                                # ако API-то за samsungtv/pcweb не връща ndvr инфо по същия начин.
                                                                # docker-bulsatcom не изглежда да има сложна catchup логика.
            gen_m3u=True,
            gen_epg=cfg.getboolean('generate_epg', True), # Четене от config
            compress=True,
            map_url=None,
            proc_cb=progress_callback_shell,
            use_ext_logos=cfg.getboolean('use_ext_logos', False), # Четене от config
            logos_path=cfg.get('logos_path', ''), # Четене от config
            use_local_logos=cfg.getboolean('use_local_logos', False), # Четене от config
            logos_local_path=cfg.get('logos_local_path', ''), # Четене от config
            # android_friendly_name се подава, но bsc.py (в новата логика) няма да го ползва за device_id
            android_device_name=cfg.get('android_friendly_name', 'DefaultAndroidDevice'),
            enable_catchup_info=enable_catchup_config,
            append_token_to_url=append_token_to_url_config,
            token_param_name=token_param_name_config,
            # Нов параметър, за да знае bsc.py кой User-Agent да сложи в M3U URL-ите
            m3u_url_user_agent_string=m3u_url_user_agent_to_pass
        )

        while True:
            print("\nЗапочва генериране на файлове...")
            success = bulsat_client.gen_all(force_refresh=True)

            if success:
                print("Файловете са генерирани успешно.")
                m3u_path = os.path.join(save_dir, 'bulsat.m3u')
                epg_path = os.path.join(save_dir, 'bulsat.xml.gz' if cfg.getboolean('generate_epg', True) and True else 'bulsat.xml') # compress е True по подразбиране в bsc
                print(f"M3U файл: {os.path.abspath(m3u_path)}")
                if cfg.getboolean('generate_epg', True): print(f"EPG файл: {os.path.abspath(epg_path)}")
            else:
                print("Грешка при генериране на файловете.")

            print(f"\nИзчакване {cache_time_min} минути преди следващото обновяване...")
            print("Натиснете Ctrl+C за изход.")
            try:
                time.sleep(cache_time_min * 60)
            except KeyboardInterrupt:
                print("\nИзлизане..."); break

    except Exception as e:
        print(f"Възникна неочаквана грешка в main: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    if not os.path.exists('lib'):
        os.makedirs('lib')
    main()
