# -*- coding: utf8 -*-

import os
import time
import base64
import requests
import gzip
import urllib.parse
import simplejson as json
import hashlib
import re
from Cryptodome.Cipher import AES
import io
from . import xmltv_p3 as xmltv
import html
import traceback # За по-добро логване на грешки

recURL = 'http://lb-ndvr.iptv.bulsat.com'

class dodat():
  def __init__(self,
                base,
                login,
                path,
                cachetime=1,
                dbg=False,
                timeout=0.5,
                ver = '0.0.0',
                xxx = False,
                os_id = 'pcweb', # От config.ini, използва се за User-Agent в M3U
                agent_id = 'pcweb', # От config.ini (или избран по os_id), използва се за User-Agent в M3U
                app_ver = '1.0.3', # От config.ini, НЕ СЕ ИЗПОЛЗВА за API заявката (тя е твърдо androidtv)
                force_group_name = False,
                use_ua = True, # Дали да се добавя User-Agent към M3U URL-ите
                use_rec = True, # Дали os_id по принцип поддържа записи (влияе на catchup)
                gen_m3u = True,
                gen_epg = False,
                compress = True,
                map_url = None,
                proc_cb = None,
                use_ext_logos = False,
                logos_path = '',
                use_local_logos=False,
                logos_local_path='',
                android_device_name='DefaultAndroidDeviceName', # От config.ini
                enable_catchup_info=True,
                append_token_to_url=False,
                token_param_name='ssbulsatapi'
                ):

    self.__DEBUG_EN = dbg # Задаваме го първо, за да работи __log_dat веднага
    self.__log_dat(f"Инициализация на bsc.dodat с os_id (от config): {os_id}, agent_id (за M3U): {agent_id}, app_ver (от config): {app_ver}", force_log=True)

    parsed_url = urllib.parse.urlparse(base)
    self.__host = parsed_url.netloc if parsed_url.netloc else 'api.iptv.bulsat.com'

    # --- Параметри, твърдо зададени за API заявката (имитираме androidtv) ---
    self.__API_REQUEST_USER_AGENT = 'okhttp/3.12.12'
    self.__API_REQUEST_OS_TYPE = 'androidtv'
    self.__API_REQUEST_APP_VERSION = '1.5.20'
    self.__API_REQUEST_DEVICE_NAME = 'unknown_google_atv'
    self.__API_REQUEST_OS_VERSION = '7.1.2'
    self.__API_URL_LIST = base + "/tv/full/limit"
    # ---------------------------------------------------------------------

    # User-Agent, който ще се използва за M3U URL-ите (ако use_ua е true)
    # Това е User-Agent-ът, който съответства на os_id от config.ini
    self.__M3U_USER_AGENT = agent_id

    self.__log_in = {}
    self.__p_data = { # Тези данни ще се попълнят в __goforit
                'user' : [None,''],
                'device_id' : [None, ''], # Ще се генерира
                'device_name' : [None, self.__API_REQUEST_DEVICE_NAME],
                'os_version' : [None, self.__API_REQUEST_OS_VERSION],
                'os_type' : [None, self.__API_REQUEST_OS_TYPE],
                'app_version' : [None, self.__API_REQUEST_APP_VERSION],
                'pass' : [None,''],
                }
    self.__path = path
    self.__refresh = int(cachetime * 60 * 60)
    self.__p_data['user'][1] = login['usr']
    self.__log_in['pw'] = login['pass']
    self.__t = timeout
    self.__BLOCK_SIZE = 16
    self.__use_ua_in_m3u_url = use_ua
    self.__use_rec_for_catchup = use_rec # Това идва от main.py и зависи от оригиналния os_id
    self.__URL_EPG  = base + '/epg/long'
    self.__js = None
    self.__app_version_script = ver
    self.__x = xxx
    self.__en_group_ch = force_group_name
    self.__gen_m3u = gen_m3u
    self.__gen_epg = gen_epg
    self.__compress = compress
    self.__cb = proc_cb
    self.__MAP_URL = map_url
    self.use_ext_logos = use_ext_logos
    if logos_path and logos_path[-1:] == r'/': self.logos_path = logos_path
    elif logos_path: self.logos_path = logos_path + '/'
    else: self.logos_path = ''
    self.use_local_logos = use_local_logos
    self.logos_local_path = logos_local_path
    self.android_device_name = android_device_name # Използва се за генериране на device_id
    self.__enable_catchup_info = enable_catchup_info
    self.__append_token_to_url = append_token_to_url
    self.__token_param_name = token_param_name

    self.__s = requests.Session()
    # User-Agent за HTTP заявките на сесията ВИНАГИ ще е този за androidtv
    self.__s.headers.update({'User-Agent': self.__API_REQUEST_USER_AGENT})
    self.__log_dat(f"User-Agent на сесията е зададен на: {self.__API_REQUEST_USER_AGENT}", force_log=True)

    self.__URL_LOGIN = base + '/?auth'
    # self.__URL_LIST вече е твърдо зададен по-горе

    if not os.path.exists(self.__path):
      try: os.makedirs(self.__path)
      except OSError as e: print(f"Грешка при създаване на директория {self.__path}: {e}")

  def __log_dat(self, d, force_log=False):
    if not self.__DEBUG_EN and not force_log: return
    header = '--------- BEGIN DEBUG ---------'
    footer = '---------- END DEBUG ----------'
    if isinstance(d, requests.models.Response):
        print(header)
        print(f"URL: {d.request.url}")
        print(f"Method: {d.request.method}")
        print(f"Request Headers: {json.dumps(dict(d.request.headers), indent=2)}")
        if hasattr(d.request, 'body') and d.request.body:
            # Опит за показване на тялото, ако е multipart, може да е сложно
            # Засега ще покажем само Content-Type
            print(f"Request Content-Type: {d.request.headers.get('Content-Type')}")
            # Ако не е multipart, може да се опита декодиране, но внимателно
        print(f"Status Code: {d.status_code}")
        print(f"Response Headers: {json.dumps(dict(d.headers), indent=2)}")
        # Опит за показване на отговора, ако е JSON
        try:
            print(f"Response JSON: {json.dumps(d.json(), indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError:
            print(f"Response Text (първите 500 символа): {d.text[:500]}")
        print(footer)
        return

    print(header)
    if isinstance(d, str): print (d)
    elif isinstance(d, (dict, requests.structures.CaseInsensitiveDict)):
      # Използване на json.dumps за по-добро форматиране на речници
      try:
          print(json.dumps(d, indent=2, ensure_ascii=False))
      except TypeError: # Ако има несериализируеми обекти
          for k, v in d.items(): print (f"  {str(k)} : {str(v)}")
    elif isinstance(d, list):
      for i, l_item in enumerate(d): print (f"  [{i}]: {l_item}")
    else: print (f'Тип за логване: {type(d)}, Стойност: {str(d)}')
    print(footer)


  def __store_data(self):
      data_file_path = os.path.join(self.__path, 'data.dat')
      try:
        with open(data_file_path, 'wb+') as f:
          f.write(json.dumps(self.__js, sort_keys=True, indent=1, ensure_ascii=False).encode('utf-8'))
        self.__log_dat(f"Данните са запазени в {data_file_path}")
      except IOError as e: self.__log_dat(f"Грешка при запис на data.dat: {e}")

      self.__log_dat(f"Проверка за запис на src.dump: DEBUG_EN={self.__DEBUG_EN}, tv_list is not None={self.__tv_list is not None}", force_log=True)
      if self.__DEBUG_EN is True and self.__tv_list is not None:
        dump_file_path = os.path.join(self.__path, 'src.dump')
        self.__log_dat(f"Опит за запис на src.dump в: {dump_file_path}", force_log=True)
        try:
          char_set_to_use = getattr(self, '__char_set', 'utf-8')
          self.__log_dat(f"Използвано кодиране за src.dump: {char_set_to_use}", force_log=True)
          with io.open(dump_file_path, 'w+', encoding=char_set_to_use) as f:
            f.write(json.dumps(self.__tv_list, sort_keys=True, indent=4, ensure_ascii=False)) # По-четлив дъмп
          self.__log_dat(f"Дебъг дъмп УСПЕШНО е запазен в {dump_file_path}", force_log=True)
        except Exception as e:
          self.__log_dat(f"Грешка при запис на src.dump: {e}\n{traceback.format_exc()}", force_log=True)

  def __restore_data(self):
    data_file_path = os.path.join(self.__path, 'data.dat')
    try:
      with open(data_file_path, 'r', encoding='utf-8') as f: self.__js = json.load(f)
      self.__log_dat(f"Данните са възстановени от {data_file_path}")
    except Exception as e:
      self.__log_dat(f"Грешка при четене/парсване на data.dat: {e}"); self.__js = None

  def __goforit(self):
    if self.__cb: self.__cb({'pr': 10, 'str': 'Инициализиране на сесия...'})
    try:
      # User-Agent за сесията е вече твърдо зададен на self.__API_REQUEST_USER_AGENT в __init__
      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t)
      self.__log_dat(r) # Логване на целия отговор
      r.raise_for_status()
      if self.__cb: self.__cb({'pr': 20, 'str': 'Сесията е стартирана. Генериране на данни за вход...'})

      self.__log_in['key'] = r.headers['challenge']
      self.__log_in['session'] = r.headers['ssbulsatapi']
      self.__s.headers.update({'SSBULSATAPI': self.__log_in['session']})

      # Попълване на __p_data с твърдо зададените стойности за androidtv API заявка
      # username и password вече са зададени
      _text_pass = self.__p_data['user'][1] + ':bulcrypt:' + self.__log_in['pw']
      length_pass = self.__BLOCK_SIZE - (len(_text_pass) % self.__BLOCK_SIZE)
      _text_pass += chr(0) * length_pass
      digest_key_pass = hashlib.md5(); digest_key_pass.update('ARTS*#234S'.encode('utf-8'))
      aes_key_pass = digest_key_pass.hexdigest().encode("utf8")
      enc_pass = AES.new(aes_key_pass, AES.MODE_ECB)
      self.__p_data['pass'][1] = base64.b64encode(enc_pass.encrypt(_text_pass.encode("utf8"))).decode('utf-8')

      digest_device_id = hashlib.md5()
      # self.android_device_name идва от config.ini
      device_info_str_for_id = self.__p_data['user'][1] + self.android_device_name
      digest_device_id.update(device_info_str_for_id.encode("utf8"))
      generated_device_id = digest_device_id.hexdigest()[0:16]
      self.__p_data['device_id'][1] = generated_device_id
      self.__log_dat(f"Генериран device_id (за androidtv тип заявка): {generated_device_id} (от user + '{self.android_device_name}')", force_log=True)

      # Останалите p_data полета вече са зададени с API_REQUEST_ стойности в __init__

      self.__log_dat({"Login Data Sent": self.__p_data})
      if self.__cb: self.__cb({'pr': 30, 'str': 'Изпращане на данни за вход...'})

      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, files=self.__p_data)
      self.__log_dat(r)
      r.raise_for_status()
      login_response_data = r.json() # Вече се логва от self.__log_dat(r)

      if login_response_data.get('Logged') == 'true':
        self.__log_dat('Входът е успешен.', force_log=True)
        if self.__cb: self.__cb({'pr': 50, 'str': 'Входът е успешен. Извличане на списък с канали...'})

        # self.__URL_LIST е вече твърдо зададен на /tv/full/limit
        r_channels = self.__s.post(self.__API_URL_LIST, timeout=self.__t)
        self.__log_dat(r_channels)
        r_channels.raise_for_status()

        content_type = r_channels.headers.get('content-type', '')
        match = re.search(r'charset=([^;]+)', content_type)
        self.__char_set = match.group(1) if match else 'utf-8'
        self.__log_dat(f'Открито кодиране на каналите: {self.__char_set}')
        try: decoded_content = r_channels.content.decode(self.__char_set)
        except UnicodeDecodeError:
            self.__log_dat(f"Грешка при декодиране с {self.__char_set}, опит с utf-8."); decoded_content = r_channels.content.decode('utf-8', errors='replace'); self.__char_set = 'utf-8'
        self.__tv_list = json.loads(decoded_content)
        self.__js = {}
        self.__log_dat('Списъкът с канали е извлечен.', force_log=True)
        if self.__DEBUG_EN and self.__tv_list:
            self.__log_dat("Примерни данни за канали (първите 2):", force_log=True)
            for k_idx, ch_example in enumerate(self.__tv_list[:2]): self.__log_dat(f"Канал {k_idx+1}: {json.dumps(ch_example, indent=2, ensure_ascii=False)}", force_log=True)
        if self.__cb: self.__cb({'pr': 90, 'str': 'Списъкът с канали е извлечен.'})
        if self.__gen_epg:
            # ... (EPG логика - без промяна) ...
      else:
        error_msg = login_response_data.get('Error', 'Неуспешен вход.'); self.__log_dat(f'LoginFail: {error_msg}', force_log=True); raise Exception(f"LoginFail: {error_msg}")
    except requests.exceptions.HTTPError as e: self.__log_dat(f"HTTP грешка: {e}", force_log=True); raise
    except requests.exceptions.RequestException as e: self.__log_dat(f"Грешка при мрежова заявка: {e}", force_log=True); raise
    except Exception as e: self.__log_dat(f"Неочаквана грешка в __goforit: {e}\n{traceback.format_exc()}", force_log=True); raise

  def __data_fetch(self, force_refresh):
    self.__tv_list = None; data_file_path = os.path.join(self.__path, 'data.dat')
    # p_data_for_cache_check е копие на p_data, но с финалните стойности след __goforit (напр. device_id)
    # Засега ще използваме self.__p_data['os_type'][1] и self.__p_data['app_version'][1] директно,
    # тъй като те се попълват с твърдите androidtv стойности преди __goforit да модифицира self.__p_data за паролата.
    # По-правилно: app_version_for_cache_check = self.__API_REQUEST_APP_VERSION
    # os_type_for_cache_check = self.__API_REQUEST_OS_TYPE

    if os.path.exists(data_file_path) and not force_refresh:
      self.__restore_data()
      if self.__js and 'ts' in self.__js and 'os_type_for_request' in self.__js: # Промяна на името на ключа
        is_cache_fresh = (time.time() - self.__js['ts']) < self.__refresh
        is_os_type_match = self.__js['os_type_for_request'] == self.__API_REQUEST_OS_TYPE
        is_app_version_match = self.__js.get('app_version_for_request') == self.__API_REQUEST_APP_VERSION

        if is_cache_fresh and is_os_type_match and is_app_version_match:
          self.__log_dat(f'Кешът е валиден (fresh:{is_cache_fresh}, os_match:{is_os_type_match}, app_ver_match:{is_app_version_match}).')
          dump_file_path = os.path.join(self.__path, 'src.dump')
          if self.__DEBUG_EN and os.path.exists(dump_file_path):
              try:
                  char_set_to_use_for_dump = self.__js.get('char_set', 'utf-8')
                  with io.open(dump_file_path, 'r', encoding=char_set_to_use_for_dump) as f: self.__tv_list = json.load(f)
                  self.__log_dat(f"Възстановен __tv_list от src.dump (кодиране: {char_set_to_use_for_dump})")
              except Exception as e: self.__log_dat(f"Неуспешно възстановяване на __tv_list от src.dump: {e}"); self.__js = None
          elif self.__DEBUG_EN:
              self.__log_dat("src.dump не е намерен, въпреки че дебъг е активен. Принудително обновяване."); self.__js = None
          elif not self.__DEBUG_EN and self.__tv_list is None:
              self.__log_dat("Кешът (data.dat) е валиден, но __tv_list не е кеширан (src.dump). Принудително обновяване."); self.__js = None
        else: self.__log_dat(f'Кешът е остарял/несъвместим (fresh:{is_cache_fresh}, os_match:{is_os_type_match}, app_ver_match:{is_app_version_match}). Извличане от сайта.'); self.__js = None
      else: self.__log_dat('Липсват данни в кеша или кешът е невалиден. Извличане от сайта.'); self.__js = None
    else:
      if force_refresh: self.__log_dat('Принудително обновяване на данните.')
      else: self.__log_dat('Липсва файл с кеширани данни. Извличане от сайта.'); self.__js = None

    if self.__js is None:
      self.__goforit()
      if self.__tv_list is not None:
          self.__js['ts'] = time.time()
          self.__js['app_version_script'] = self.__app_version_script
          self.__js['os_type_for_request'] = self.__API_REQUEST_OS_TYPE # Записаният OS тип, използван за заявката
          self.__js['app_version_for_request'] = self.__API_REQUEST_APP_VERSION # Записаната app версия, използвана за заявката
          if hasattr(self, '__char_set'): self.__js['char_set'] = self.__char_set
          self.__log_dat('Базово време на кеша: %s' % time.ctime(self.__js['ts']))
          self.__store_data()
      else:
          self.__log_dat("Неуспешно извличане на данни от сървъра в __goforit."); return False
    return True

  def gen_all(self, force_refresh = False):
    # ... (Логиката за EPG и M3U генериране остава същата, но с корекции за tvg-logo и stream_url)
    ret = False
    if not self.__data_fetch(force_refresh):
        if self.__cb: self.__cb({'pr': 100, 'str': 'Грешка: Неуспешно извличане на данни за каналите.'}); return False

    if self.__tv_list:
      ret = True; epg_map = None
      # ... EPG/Map URL логика ...

      m3u_playlist_content = u'#EXTM3U\n'
      total_channels = len(self.__tv_list)
      session_token_for_url = self.__log_in.get('session') if self.__append_token_to_url else None

      for i, ch_info in enumerate(self.__tv_list):
        # ... (логване на прогрес) ...
        group_title = self.__en_group_ch if self.__en_group_ch else ch_info.get('genre', 'Undefined')
        if not self.__x and group_title == '18+': continue

        if self.__gen_m3u:
          catchup_tags = ''; stream_url = ''
          url_ndvr = ch_info.get('ndvr')
          url_sources = ch_info.get('sources')

          # Приоритет на 'ndvr' ако съдържа '?DVR&' и 'wmsAuthSign='
          if isinstance(url_ndvr, str) and "?DVR&" in url_ndvr and "wmsAuthSign=" in url_ndvr:
              stream_url = url_ndvr
          elif isinstance(url_sources, str) and "wmsAuthSign=" in url_sources: # Проверка и за wmsAuthSign в sources
              stream_url = url_sources
          elif isinstance(url_ndvr, str): # Fallback към ndvr, ако sources липсва или е невалиден
              stream_url = url_ndvr
          else:
              stream_url = ch_info.get('pip', '') # Последен fallback

          if not stream_url:
              self.__log_dat(f"Липсва URL за поток за канал: {ch_info.get('title')}", force_log=True); continue

          self.__log_dat(f"Канал '{ch_info.get('title')}': Избран stream_url: {stream_url}", force_log=self.__DEBUG_EN)

          # Catchup логика
          if self.__enable_catchup_info and self.__use_rec_for_catchup and isinstance(url_ndvr, str) and url_ndvr:
            parsed_original_ndvr = urllib.parse.urlparse(url_ndvr)
            path_for_catchup = parsed_original_ndvr.path
            query_for_catchup = parsed_original_ndvr.query
            wowza_params = "wowzadvrplayliststart={utc:YmdHMS}&wowzadvrplaylistduration={duration}000"
            # Използваме recURL (lb-ndvr...) за catchup-source, както е в Kodi примера
            final_catchup_url = f"{recURL}{path_for_catchup}"
            if query_for_catchup: final_catchup_url += f"?{query_for_catchup}&{wowza_params}"
            else: final_catchup_url += f"?{wowza_params}"
            catchup_tags = f'catchup="default" catchup-source="{final_catchup_url}"'

          current_title = ch_info.get('title', 'No Title')
          m3u_line_start = f'#EXTINF:-1 {catchup_tags} ' if catchup_tags else f'#EXTINF:-1 '

          tvg_id = ch_info.get('epg_name', '')
          # Коригирана логика за tvg-logo:
          tvg_logo_val = ch_info.get('logo', '') # Опитай 'logo' първо
          if not tvg_logo_val: tvg_logo_val = ch_info.get('logo_selected', '') # После 'logo_selected'
          if not tvg_logo_val: tvg_logo_val = ch_info.get('logo_favorite', '') # Накрая 'logo_favorite'

          self.__log_dat(f"Канал '{current_title}', tvg-id: '{tvg_id}', първоначално tvg-logo: '{tvg_logo_val}'", force_log=self.__DEBUG_EN)

          if self.use_ext_logos:
              logo_filename = f"{tvg_id}.png"
              if self.use_local_logos and self.logos_local_path: tvg_logo_val = os.path.join(self.logos_local_path, logo_filename)
              elif self.logos_path: tvg_logo_val = urllib.parse.urljoin(self.logos_path, logo_filename)
          elif epg_map and tvg_id in epg_map:
              map_entry = epg_map[tvg_id]
              tvg_id_from_map = map_entry.get('id', tvg_id) # tvg-id може да се промени от картата
              logo_from_map = map_entry.get('ch_logo')
              if logo_from_map : tvg_logo_val = logo_from_map # Лого от картата, ако го има
              tvg_id = tvg_id_from_map # Използване на tvg-id от картата, ако е променен

          self.__log_dat(f"Канал '{current_title}', tvg-id: '{tvg_id}', финално tvg-logo: '{tvg_logo_val}'", force_log=self.__DEBUG_EN)
          m3u_playlist_content += f'{m3u_line_start}tvg-id="{tvg_id}" tvg-logo="{tvg_logo_val}" radio="{str(ch_info.get("radio", False)).lower()}" group-title="{group_title}",{current_title}\n'

          final_stream_url = stream_url
          if session_token_for_url and self.__token_param_name:
              separator = '&' if '?' in final_stream_url else '?'
              if f"{self.__token_param_name}=" not in final_stream_url:
                  final_stream_url += f"{separator}{self.__token_param_name}={session_token_for_url}"

          if self.__use_ua_in_m3u_url and self.__M3U_USER_AGENT: # Използване на M3U User-Agent
            final_stream_url_parts = final_stream_url.split('|User-Agent=', 1)
            base_url_part = final_stream_url_parts[0]
            final_stream_url = f'{base_url_part}|User-Agent={urllib.parse.quote_plus(self.__M3U_USER_AGENT)}'

          m3u_playlist_content += f'{final_stream_url}\n'

        # ... (EPG генериране без промяна) ...
      # ... (Запис на M3U и EPG файлове без промяна) ...
    # ... (Край на gen_all) ...
    # Трябва да върна ret, както беше преди
    # Този код е само част от __init__ и gen_all. Пълният файл е по-голям.
    # Трябва да се внимава при интегрирането на тези фрагменти.

    # Пълният код за gen_all и останалата част на файла трябва да се запази,
    # като се интегрират само промените в __init__, __goforit, __data_fetch
    # и съответните части на gen_all за избор на URL и лого.
    # За простота, тук ще върна ret, но реално целият метод gen_all трябва да е тук.
    # ... (останалата част от gen_all метода, включително запис на файлове и връщане на ret)
    if self.__gen_m3u:
        m3u_file_path = os.path.join(self.__path, 'bulsat.m3u')
        try:
            with open(m3u_file_path, 'wb+') as f_m3u:
                encoding_to_use = getattr(self, '__char_set', 'utf-8')
                f_m3u.write(m3u_playlist_content.encode(encoding_to_use, 'replace'))
            if self.__cb: self.__cb({'str': f"M3U файлът е запазен в: {m3u_file_path}"})
        except IOError as e:
            if self.__cb: self.__cb({'str': f"Грешка при запис на M3U файла: {e}"}); self.__log_dat(f"Грешка при запис на M3U файла: {e}"); ret = False

    if self.__gen_epg and hasattr(self, 'xml_writer'): # Проверка дали xml_writer е дефиниран
        epg_file_base = os.path.join(self.__path, 'bulsat.xml')
        try:
            if self.__compress:
                epg_file_path_final = epg_file_base + '.gz'
                with io.BytesIO() as temp_buffer:
                    xml_writer.write(temp_buffer, pretty_print=True); temp_buffer.seek(0)
                    with gzip.open(epg_file_path_final, 'wb', 9) as f_xml_gz: f_xml_gz.write(temp_buffer.read())
                if self.__cb: self.__cb({'str': f"EPG файлът е запазен (компресиран) в: {epg_file_path_final}"})
            else:
                epg_file_path_final = epg_file_base
                with open(epg_file_path_final, 'wb+') as f_xml: xml_writer.write(f_xml, pretty_print=True)
                if self.__cb: self.__cb({'str': f"EPG файлът е запазен в: {epg_file_path_final}"})
        except Exception as e:
            if self.__cb: self.__cb({'str': f"Грешка при запис на EPG файла: {e}"}); self.__log_dat(f"Грешка при запис на EPG файла: {e}"); ret = False
    elif self.__gen_epg:
        self.__log_dat("xml_writer не е инициализиран, пропускане на запис на EPG.", force_log=True)


    if self.__cb:
        if ret: self.__cb({'pr': 100, 'str': 'Всички операции са завършени успешно.'})
        else: self.__cb({'pr': 100, 'str': 'Операциите са завършени с някои грешки или липсващи данни.'})
    return ret
