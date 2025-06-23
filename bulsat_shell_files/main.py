# -*- coding: utf-8 -*-
import configparser
import os
import time
import sys
from lib import bsc # Assuming bsc.py will be in a 'lib' subdirectory

# --- Global UA and OS settings ---
# These were originally in exec.py and bsc.py, consolidating them here for clarity
# The os_id from config.ini will determine which of these is used.
UA_OS_SETTINGS = {
    'samsungtv': {
        'ua': 'Mozilla/5.0 (SMART-TV; Linux; Tizen 2.3) AppleWebkit/538.1 (KHTML, like Gecko) SamsungBrowser/1.0 TV Safari/538.1',
        'osid': 'samsungtv',
        # 'app_ver': '1.0.3' # App version will be read from config
    },
    'androidtv': {
        'ua': 'okhttp/3.12.12',
        'osid': 'androidtv',
        # 'app_ver': '1.5.20' # App version will be read from config
    }
}

def get_config():
    """Reads configuration from config.ini"""
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
    """Basic progress callback for shell environment."""
    message = progress_info.get('str', '')
    percentage = progress_info.get('pr', None)
    idx = progress_info.get('idx', None)
    max_val = progress_info.get('max', None)

    if percentage is not None:
        progress_bar = f"[{'=' * int(percentage / 10)}{' ' * (10 - int(percentage / 10))}] {percentage}%"
        if idx and max_val:
            print(f"{progress_bar} - {message} ({idx}/{max_val})")
        else:
            print(f"{progress_bar} - {message}")
    else:
        print(message)

def main():
    cfg = get_config()

    username = cfg.get('username', 'your_username')
    password = cfg.get('password', 'your_password')
    save_dir = cfg.get('save_dir', './output')
    debug_mode = cfg.getboolean('debug', False)
    cache_time_min = cfg.getint('cache_time', 240)
    time_out_sec = cfg.getfloat('time_out', 10)
    os_id_key = cfg.get('os_id', 'samsungtv').lower()
    app_version_cfg = cfg.get('app_version') # Will be used by bsc.py
    base_url = cfg.get('base_url', 'https://api.iptv.bulsat.com')
    android_friendly_name = cfg.get('android_friendly_name', 'DefaultAndroidDevice')
    enable_catchup_config = cfg.getboolean('enable_catchup', True)


    if username == 'your_username' or password == 'your_password':
        print("Моля, въведете вашето потребителско име и парола в config.ini")
        sys.exit(1)

    if os_id_key not in UA_OS_SETTINGS:
        print(f"Грешка: Невалидна стойност за 'os_id' в config.ini. Трябва да е една от {list(UA_OS_SETTINGS.keys())}")
        sys.exit(1)

    selected_os_settings = UA_OS_SETTINGS[os_id_key]
    user_agent = cfg.get('user_agent', selected_os_settings['ua'])

    # Ensure save_dir exists
    if not os.path.exists(save_dir):
        try:
            os.makedirs(save_dir)
            print(f"Създадена е директория: {save_dir}")
        except OSError as e:
            print(f"Грешка при създаване на директория {save_dir}: {e}")
            sys.exit(1)

    # The bsc.dodat class will expect app_ver for the specific os_id
    # It's better to pass it directly, or let bsc.py handle default if not provided.
    # For now, we pass the one from config.
    if not app_version_cfg:
        print(f"Предупреждение: 'app_version' не е зададена в config.ini. bsc.py може да използва стойност по подразбиране.")


    print(f"Използване на OS ID: {selected_os_settings['osid']}")
    print(f"User Agent: {user_agent}")
    print(f"App Version (от config): {app_version_cfg}")
    print(f"Директория за запис: {os.path.abspath(save_dir)}")
    print(f"Време за кеширане: {cache_time_min} минути")

    # --- Initialize bsc.dodat ---
    # Parameters for bsc.dodat need to be mapped from our config
    # Original exec.py call:
    # b = bsc.dodat(base = __addon__.getSetting('base'), # base_url from config
    #               login = {'usr': usern, 'pass': passn},
    #               path = __data__, # save_dir from config (for data.dat, etc.)
    #               cachetime = float(__addon__.getSetting('refresh_new')), # cache_time_min from config
    #               dbg = dbg, # debug_mode from config
    #               timeout = float(__addon__.getSetting('timeout')), # time_out_sec from config
    #               ver = __version__, # Script version, can be hardcoded or omitted
    #               xxx = xxx, # Not implemented, assume False
    #               use_ua = use_ua, # True by default in this script
    #               use_rec = use_rec, # True by default if androidtv, needs confirmation
    #               os_id = __ua_os[temp_osid]['osid'], # selected_os_settings['osid']
    #               agent_id = __ua_os[temp_osid]['ua'], # user_agent
    #               app_ver = __addon__.getSetting('app_ver'), # app_version_cfg from config
    #               force_group_name = _group_name, # False by default
    #               gen_m3u = True, # True by default
    #               gen_epg = not etx_epg, # True by default (etx_epg=False)
    #               compress = True, # True by default
    #               map_url = map_url, # None by default
    #               proc_cb = progress_cb, # progress_callback_shell
    #               use_ext_logos = use_ext_logos, # False
    #               logos_path = logos_path, # ''
    #               use_local_logos = use_local_logos, # False
    #               logos_local_path = logos_local_path) # ''
    #               android_device_name is a new param for password encryption

    try:
        bulsat_client = bsc.dodat(
            base=base_url,
            login={'usr': username, 'pass': password},
            path=save_dir,  # This path is where bsc.py might store its own cache like 'data.dat'
            cachetime=float(cache_time_min / 60), # bsc.py expects hours for cachetime
            dbg=debug_mode,
            timeout=time_out_sec,
            ver="1.0.0-shell", # Script version
            xxx=False, # Not exposing this in config for now
            os_id=selected_os_settings['osid'],
            agent_id=user_agent,
            app_ver=app_version_cfg, # Pass the version from config
            force_group_name=False, # Not exposing this
            use_ua=True, # Always use UA string for requests
            use_rec=True if selected_os_settings['osid'] == 'androidtv' else False, # Based on original logic for use_rec
            gen_m3u=True,
            gen_epg=True,
            compress=True,
            map_url=None, # Not exposing this
            proc_cb=progress_callback_shell,
            use_ext_logos=False, # Not exposing this
            logos_path='', # Not exposing this
            use_local_logos=False, # Not exposing this
            logos_local_path='', # Not exposing this
            android_device_name=android_friendly_name, # For password encryption if os_id is androidtv
            enable_catchup_info=enable_catchup_config # New parameter for catchup
        )

        while True:
            print("\nЗапочва генериране на файлове...")
            force_refresh = True # Always refresh on the first run of the loop or manual trigger
            # Subsequent runs within the cache time might not need full refresh if bsc.py handles it well.
            # For now, let's assume gen_all will internally check its cache unless forced.
            # The original exec.py logic implies 'force=True' on manual runs.

            success = bulsat_client.gen_all(force_refresh=force_refresh)

            if success:
                print("Файловете са генерирани успешно.")
                m3u_path = os.path.join(save_dir, 'bulsat.m3u')
                epg_path = os.path.join(save_dir, 'bulsat.xml.gz')
                print(f"M3U файл: {os.path.abspath(m3u_path)}")
                print(f"EPG файл: {os.path.abspath(epg_path)}")
            else:
                print("Грешка при генериране на файловете.")

            print(f"\nИзчакване {cache_time_min} минути преди следващото обновяване...")
            print(f"Натиснете Ctrl+C за изход.")
            try:
                time.sleep(cache_time_min * 60)
            except KeyboardInterrupt:
                print("\nИзлизане...")
                break

    except Exception as e:
        print(f"Възникна неочаквана грешка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # Create lib directory if it doesn't exist, for bsc.py etc.
    if not os.path.exists('lib'):
        os.makedirs('lib')
    main()
