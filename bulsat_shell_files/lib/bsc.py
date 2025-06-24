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
from Cryptodome.Cipher import AES # Ще оставим Cryptodome засега, ако не работи, ще мислим за pyaes
import io
from . import xmltv_p3 as xmltv
import html
import traceback

recURL = 'http://lb-ndvr.iptv.bulsat.com'

class dodat():
  def __init__(self,
                base,
                login,
                path,
                cachetime=1,
                dbg=False,
                timeout=0.5,
                ver = '0.0.0', # Версия на този скрипт
                xxx = False,
                # Параметри, вдъхновени от docker-bulsatcom за API заявката:
                os_id, # Това е стойността от config.ini (напр. "samsungtv", "androidtv", "pcweb")
                       # Ще се използва за device_id, device_name, os_version, os_type в p_data
                       # и за определяне на /tv/{os_id}/live ендпойнта.
                agent_id, # Това е User-Agent за API заявките (подаден от main.py, напр. десктоп UA)
                app_ver,  # Това е app_version за API заявките (подаден от main.py, напр. "0.01")

                force_group_name = False,
                use_ua = True, # Дали да се добавя User-Agent към M3U URL-ите
                m3u_url_user_agent_string = '', # User-Agent стрингът, който да се добави към M3U URL-ите
                use_rec = True, # Дали да се опитва да се генерира catchup инфо (зависи и от enable_catchup_info)
                gen_m3u = True,
                gen_epg = False,
                compress = True,
                map_url = None,
                proc_cb = None,
                use_ext_logos = False,
                logos_path = '',
                use_local_logos=False,
                logos_local_path='',
                android_device_name='DefaultAndroidDeviceName', # Вече не се използва за device_id в този подход
                enable_catchup_info=True,
                append_token_to_url=False, # Дали да се добавя ssbulsatapi към stream URL
                token_param_name='ssbulsatapi'
                ):

    self.__DEBUG_EN = dbg
    self.__log_dat(f"Инициализация на bsc.dodat (docker-bulsatcom стил): os_id_param: {os_id}, agent_id_for_api: {agent_id}, app_ver_for_api: {app_ver}", force_log=True)

    parsed_url = urllib.parse.urlparse(base)
    self.__host = parsed_url.netloc if parsed_url.netloc else 'api.iptv.bulsat.com'

    self.__M3U_USER_AGENT_STRING = m3u_url_user_agent_string # User-Agent за M3U URL-ите

    self.__log_in = {}
    self.__p_data = {
                'user' : [None, login['usr']],
                # Използване на os_id от config.ini като стойност за тези полета, както прави docker-bulsatcom
                'device_id' : [None, os_id],
                'device_name' : [None, os_id],
                'os_version' : [None, os_id], # Може да се наложи да е по-специфично, но docker-bulsatcom ползва os_id
                'os_type' : [None, os_id],
                'app_version' : [None, app_ver], # Трябва да е "0.01" според docker-bulsatcom
                'pass' : [None,''], # Ще се попълни
                }
    self.__log_dat(f"Първоначално p_data за API заявка: {self.__p_data}", force_log=True)

    self.__path = path; self.__refresh = int(cachetime * 60 * 60)
    self.__log_in['pw'] = login['pass']
    self.__t = timeout; self.__BLOCK_SIZE = 16
    self.__use_ua_in_m3u_url = use_ua
    self.__use_rec_for_catchup = use_rec
    self.__URL_EPG  = base + '/epg/long' # docker-bulsatcom ползва /epg/short, но ще оставим long за повече данни
    self.__js = None
    self.__app_version_script = ver
    self.__x = xxx
    self.__en_group_ch = force_group_name; self.__gen_m3u = gen_m3u
    self.__gen_epg = gen_epg; self.__compress = compress
    self.__cb = proc_cb; self.__MAP_URL = map_url
    self.use_ext_logos = use_ext_logos
    if logos_path and logos_path[-1:] == r'/': self.logos_path = logos_path
    elif logos_path: self.logos_path = logos_path + '/'
    else: self.logos_path = ''
    self.use_local_logos = use_local_logos; self.logos_local_path = logos_local_path
    self.__enable_catchup_info = enable_catchup_info
    self.__append_token_to_url = append_token_to_url
    self.__token_param_name = token_param_name

    self.__s = requests.Session()
    # User-Agent за HTTP заявките на сесията (подаден от main.py, вдъхновен от docker-bulsatcom)
    self.__s.headers.update({'User-Agent': agent_id})
    self.__log_dat(f"User-Agent на сесията е зададен на: {agent_id}", force_log=True)

    # URL за логин - docker-bulsatcom има логика за ?auth
    self.__URL_LOGIN = base + '/?auth' # Повечето случаи изискват ?auth
    # Проверка дали os_id е "pcweb" (еквивалент на _os=0 в docker-bulsatcom)
    if os_id.lower() == 'pcweb':
        self.__URL_LOGIN = base + '/auth' # Без '?' за pcweb

    # URL за списък с канали, зависи от os_id
    self.__URL_LIST = base + '/tv/' + os_id + '/live'
    self.__log_dat(f"URL за списък с канали: {self.__URL_LIST}", force_log=True)


    if not os.path.exists(self.__path):
      try: os.makedirs(self.__path)
      except OSError as e: print(f"Грешка при създаване на директория {self.__path}: {e}")

  def __log_dat(self, d, force_log=False):
    if not self.__DEBUG_EN and not force_log: return
    header = '--------- BEGIN DEBUG ---------'; footer = '---------- END DEBUG ----------'
    if isinstance(d, requests.models.Response):
        print(header); print(f"URL: {d.request.url}"); print(f"Method: {d.request.method}")
        request_headers_dict = dict(d.request.headers)
        response_headers_dict = dict(d.headers)
        print(f"Request Headers: {json.dumps(request_headers_dict, indent=2, ensure_ascii=False)}")
        if hasattr(d.request, 'body') and d.request.body: print(f"Request Content-Type: {d.request.headers.get('Content-Type')}")
        print(f"Status Code: {d.status_code}"); print(f"Response Headers: {json.dumps(response_headers_dict, indent=2, ensure_ascii=False)}")
        try: print(f"Response JSON: {json.dumps(d.json(), indent=2, ensure_ascii=False)}")
        except json.JSONDecodeError: print(f"Response Text (първите 500 символа): {d.text[:500]}")
        print(footer); return
    print(header)
    if isinstance(d, str): print (d)
    elif isinstance(d, (dict, requests.structures.CaseInsensitiveDict)):
      try: print(json.dumps(d, indent=2, ensure_ascii=False))
      except TypeError:
          temp_dict = dict(d)
          try: print(json.dumps(temp_dict, indent=2, ensure_ascii=False))
          except Exception as e_inner:
            print(f"Fallback log for dict (json.dumps failed): {e_inner}")
            for k, v in temp_dict.items(): print (f"  {str(k)} : {str(v)}")
    elif isinstance(d, list):
      for i, l_item in enumerate(d): print (f"  [{i}]: {l_item}")
    else: print (f'Тип за логване: {type(d)}, Стойност: {str(d)}')
    print(footer)

  def __store_data(self):
      data_file_path = os.path.join(self.__path, 'data.dat')
      try:
        with open(data_file_path, 'wb+') as f: f.write(json.dumps(self.__js, sort_keys=True, indent=1, ensure_ascii=False).encode('utf-8'))
        self.__log_dat(f"Данните са запазени в {data_file_path}")
      except IOError as e: self.__log_dat(f"Грешка при запис на data.dat: {e}")
      self.__log_dat(f"Проверка за запис на src.dump: DEBUG_EN={self.__DEBUG_EN}, tv_list is not None={self.__tv_list is not None}", force_log=True)
      if self.__DEBUG_EN is True and self.__tv_list is not None:
        dump_file_path = os.path.join(self.__path, 'src.dump')
        self.__log_dat(f"Опит за запис на src.dump в: {dump_file_path}", force_log=True)
        try:
          char_set_to_use = getattr(self, '__char_set', 'utf-8')
          self.__log_dat(f"Използвано кодиране за src.dump: {char_set_to_use}", force_log=True)
          with io.open(dump_file_path, 'w+', encoding=char_set_to_use) as f: f.write(json.dumps(self.__tv_list, sort_keys=True, indent=4, ensure_ascii=False))
          self.__log_dat(f"Дебъг дъмп УСПЕШНО е запазен в {dump_file_path}", force_log=True)
        except Exception as e: self.__log_dat(f"Грешка при запис на src.dump: {e}\n{traceback.format_exc()}", force_log=True)

  def __restore_data(self):
    data_file_path = os.path.join(self.__path, 'data.dat')
    try:
      with open(data_file_path, 'r', encoding='utf-8') as f: self.__js = json.load(f)
      self.__log_dat(f"Данните са възстановени от {data_file_path}")
    except Exception as e: self.__log_dat(f"Грешка при четене/парсване на data.dat: {e}"); self.__js = None

  def __goforit(self):
    if self.__cb: self.__cb({'pr': 10, 'str': 'Инициализиране на сесия...'})
    try:
      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t)
      self.__log_dat(r); r.raise_for_status()
      if self.__cb: self.__cb({'pr': 20, 'str': 'Сесията е стартирана. Генериране на данни за вход...'})
      self.__log_in['key'] = r.headers['challenge']; self.__log_in['session'] = r.headers['ssbulsatapi']
      self.__s.headers.update({'SSBULSATAPI': self.__log_in['session']})

      # Криптиране на паролата ВИНАГИ с challenge ключа (както docker-bulsatcom)
      _text_pass = self.__log_in['pw'] + (self.__BLOCK_SIZE - len(self.__log_in['pw']) % self.__BLOCK_SIZE) * '\0'
      aes_key_pass = self.__log_in['key'].encode("utf8") # Използваме challenge ключа
      enc_pass = AES.new(aes_key_pass, AES.MODE_ECB)
      self.__p_data['pass'][1] = base64.b64encode(enc_pass.encrypt(_text_pass.encode("utf8"))).decode('utf-8')

      # device_id вече е зададен в __init__ на базата на os_id от config (напр. "samsungtv")
      # app_version вече е зададен в __init__ на базата на app_ver от config (напр. "0.01")
      self.__log_dat(f"Използван device_id за API заявка: {self.__p_data['device_id'][1]}", force_log=True)
      self.__log_dat(f"Използван app_version за API заявка: {self.__p_data['app_version'][1]}", force_log=True)

      self.__log_dat({"Login Data Sent to API": self.__p_data})
      if self.__cb: self.__cb({'pr': 30, 'str': 'Изпращане на данни за вход...'})
      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, files=self.__p_data)
      self.__log_dat(r); r.raise_for_status(); login_response_data = r.json()

      if login_response_data.get('Logged') == 'true':
        self.__log_dat('Входът е успешен.', force_log=True)
        if self.__cb: self.__cb({'pr': 50, 'str': 'Входът е успешен. Извличане на списък с канали...'})

        r_channels = self.__s.post(self.__URL_LIST, timeout=self.__t) # __URL_LIST вече е /tv/{os_id}/live
        self.__log_dat(r_channels); r_channels.raise_for_status()
        content_type = r_channels.headers.get('content-type', ''); match = re.search(r'charset=([^;]+)', content_type)
        self.__char_set = match.group(1) if match else 'utf-8'
        self.__log_dat(f'Открито кодиране на каналите: {self.__char_set}')
        try: decoded_content = r_channels.content.decode(self.__char_set)
        except UnicodeDecodeError:
            self.__log_dat(f"Грешка декодиране с {self.__char_set}, опит utf-8.")
            decoded_content = r_channels.content.decode('utf-8', errors='replace')
            self.__char_set = 'utf-8'
        self.__tv_list = json.loads(decoded_content); self.__js = {}
        self.__log_dat('Списъкът с канали е извлечен.', force_log=True)
        if self.__DEBUG_EN and self.__tv_list:
            self.__log_dat("Примерни данни за канали (първите 2):", force_log=True)
            for k_idx, ch_example in enumerate(self.__tv_list[:2]): self.__log_dat(f"Канал {k_idx+1}: {json.dumps(ch_example, indent=2, ensure_ascii=False)}", force_log=True)
        if self.__cb: self.__cb({'pr': 90, 'str': 'Списъкът с канали е извлечен.'})

        if self.__gen_epg:
            if self.__cb: self.__cb({'pr': 92, 'str': 'Извличане на EPG данни...'})
            if self.__tv_list:
                total_channels_for_epg = len(self.__tv_list)
                for i_epg, ch_data_epg in enumerate(self.__tv_list):
                    if self.__cb:
                        channel_name_for_progress_epg = ch_data_epg.get('title', ch_data_epg.get('epg_name', 'N/A'))
                        self.__cb({'pr': int((i_epg*100)/total_channels_for_epg) if total_channels_for_epg > 0 else 0,
                                   'str': f'EPG за: {channel_name_for_progress_epg}', 'idx': i_epg+1, 'max': total_channels_for_epg})
                    if ch_data_epg.get('epg_name') and ch_data_epg.get('program') is not None:
                        try:
                            r_epg = self.__s.post(self.__URL_EPG, timeout=self.__t, data={'epg': '1week', 'channel': ch_data_epg['epg_name']})
                            r_epg.raise_for_status()
                            epg_data_raw = r_epg.json()
                            if epg_data_raw and isinstance(epg_data_raw, dict):
                                first_key = next(iter(epg_data_raw))
                                if isinstance(epg_data_raw[first_key], dict):
                                    ch_data_epg['program'] = epg_data_raw[first_key].get('programme', [])
                                else:
                                    self.__log_dat(f"Неочаквана структура EPG за {ch_data_epg.get('epg_name')}: {epg_data_raw[first_key]}", force_log=True)
                                    ch_data_epg['program'] = []
                            else:
                                self.__log_dat(f"Празен/неочакван EPG отговор за {ch_data_epg.get('epg_name')}", force_log=True)
                                ch_data_epg['program'] = []
                        except requests.exceptions.RequestException as e_req:
                            self.__log_dat(f"Грешка при мрежова заявка за EPG за {ch_data_epg.get('epg_name')}: {e_req}")
                            ch_data_epg['program'] = []
                        except json.JSONDecodeError as e_json:
                            self.__log_dat(f"Грешка при парсване на JSON за EPG за {ch_data_epg.get('epg_name')}: {e_json}")
                            ch_data_epg['program'] = []
                        except Exception as e_other:
                            self.__log_dat(f"Неочаквана грешка при обработка на EPG за {ch_data_epg.get('epg_name')}: {e_other}\n{traceback.format_exc()}")
                            ch_data_epg['program'] = []
                    else:
                        ch_data_epg['program'] = []
            else:
                 if self.__cb: self.__cb({'str': 'Пропускане на EPG извличането, тъй като списъкът с канали е празен.'})

      else:
        error_msg = login_response_data.get('Error', 'Неуспешен вход.');
        self.__log_dat(f'LoginFail: {error_msg}', force_log=True);
        raise Exception(f"LoginFail: {error_msg}")

    except requests.exceptions.HTTPError as e:
        self.__log_dat(f"HTTP грешка: {e}", force_log=True)
        raise
    except requests.exceptions.RequestException as e:
        self.__log_dat(f"Грешка при мрежова заявка: {e}", force_log=True)
        raise
    except Exception as e:
        self.__log_dat(f"Неочаквана грешка в __goforit: {e}\n{traceback.format_exc()}", force_log=True)
        raise

  def __data_fetch(self, force_refresh):
    self.__tv_list = None; data_file_path = os.path.join(self.__path, 'data.dat')
    # За кеша използваме стойностите, с които реално е направена API заявката
    os_type_for_cache_check = self.__p_data['os_type'][1]
    app_version_for_cache_check = self.__p_data['app_version'][1]
    device_id_for_cache_check = self.__p_data['device_id'][1]

    if os.path.exists(data_file_path) and not force_refresh:
      self.__restore_data()
      if self.__js and 'ts' in self.__js and 'os_type_for_request' in self.__js:
        is_cache_fresh = (time.time() - self.__js['ts']) < self.__refresh
        is_os_type_match = self.__js['os_type_for_request'] == os_type_for_cache_check
        is_app_version_match = self.__js.get('app_version_for_request') == app_version_for_cache_check
        is_device_id_match = self.__js.get('device_id_for_request') == device_id_for_cache_check

        if is_cache_fresh and is_os_type_match and is_app_version_match and is_device_id_match:
          self.__log_dat(f'Кешът е валиден.')
          dump_file_path = os.path.join(self.__path, 'src.dump')
          if self.__DEBUG_EN and os.path.exists(dump_file_path):
              try:
                  char_set_to_use_for_dump = self.__js.get('char_set', 'utf-8')
                  with io.open(dump_file_path, 'r', encoding=char_set_to_use_for_dump) as f: self.__tv_list = json.load(f)
                  self.__log_dat(f"Възстановен __tv_list от src.dump (кодиране: {char_set_to_use_for_dump})")
              except Exception as e: self.__log_dat(f"Неуспешно възстановяване на __tv_list от src.dump: {e}"); self.__js = None
          elif self.__DEBUG_EN:
              self.__log_dat("src.dump не е намерен, въпреки че дебъг е активен. Принудително обновяване.")
              self.__js = None
          elif not self.__DEBUG_EN and self.__tv_list is None:
              self.__log_dat("Кешът (data.dat) валиден, но __tv_list не кеширан (src.dump). Обновяване.")
              self.__js = None
        else:
            self.__log_dat(f'Кеш остарял/несъвместим (fresh:{is_cache_fresh}, os_match:{is_os_type_match}, app_ver_match:{is_app_version_match}, device_id_match:{is_device_id_match}).')
            self.__js = None
      else:
          self.__log_dat('Липсват данни в кеша или кешът е невалиден.')
          self.__js = None
    else:
      if force_refresh: self.__log_dat('Принудително обновяване.')
      else: self.__log_dat('Липсва кеш файл.'); self.__js = None

    if self.__js is None:
      self.__goforit()
      if self.__tv_list is not None:
          self.__js['ts'] = time.time(); self.__js['app_version_script'] = self.__app_version_script
          self.__js['os_type_for_request'] = os_type_for_cache_check
          self.__js['app_version_for_request'] = app_version_for_cache_check
          self.__js['device_id_for_request'] = device_id_for_cache_check
          if hasattr(self, '__char_set'): self.__js['char_set'] = self.__char_set
          self.__log_dat('Базово време на кеша: %s' % time.ctime(self.__js['ts'])); self.__store_data()
      else:
          self.__log_dat("Неуспешно извличане данни от сървъра в __goforit.")
          return False
    return True

  def gen_all(self, force_refresh = False):
    ret = False
    if not self.__data_fetch(force_refresh):
        if self.__cb: self.__cb({'pr': 100, 'str': 'Грешка: Неуспешно извличане на данни за каналите.'}); return False
    if not self.__tv_list:
        if self.__cb: self.__cb({'pr':100, 'str': 'Грешка: Списъкът с канали е празен след опит за извличане.'}); return False

    ret = True; epg_map = None; xml_writer = None
    if self.__gen_epg:
      char_set_for_xml = getattr(self, '__char_set', 'UTF-8').upper()
      xml_writer = xmltv.Writer(encoding=char_set_for_xml, date=str(time.time()),
                                source_info_url="https://bulsat.com", source_info_name="Bulsatcom",
                                generator_info_name=f"bulsat_shell_script/{self.__app_version_script}", generator_info_url="")
      for ch_data_epg in self.__tv_list:
          if ch_data_epg.get('epg_name') and ch_data_epg.get('title'):
              display_names = [(ch_data_epg.get('title'), 'bg')]
              xml_writer.addChannel({'display-name': display_names, 'id': ch_data_epg.get('epg_name'), 'url': [ch_data_epg.get('url', '')]})
              if 'program' in ch_data_epg and isinstance(ch_data_epg['program'], list):
                  for prog_item in ch_data_epg['program']:
                      if not isinstance(prog_item, dict): continue
                      prog_title = [(prog_item.get('title', 'N/A'), '')]; prog_desc = [(prog_item.get('desc', ''), '')]
                      prog_category = [(ch_data_epg.get('genre', ''), '')]
                      xml_writer.addProgramme({'start': prog_item.get('start', ''), 'stop': prog_item.get('stop', ''),
                                               'title': prog_title, 'desc': prog_desc, 'category': prog_category,
                                               'channel': ch_data_epg.get('epg_name')})
    elif self.__MAP_URL:
        try:
          if self.__cb: self.__cb({'str': f"Изтегляне на EPG карта от: {self.__MAP_URL}"})
          m = self.__s.get(self.__MAP_URL, timeout=self.__t); m.raise_for_status(); epg_map = m.json()
          self.__log_dat(epg_map);
          if self.__cb: self.__cb({'str': "EPG картата е изтеглена успешно."})
        except Exception as e:
          if self.__cb: self.__cb({'str': f"Грешка при изтегляне/парсване EPG карта: {e}"}); self.__log_dat(f"Грешка изтегляне/парсване EPG карта: {e}")

    m3u_playlist_content = u'#EXTM3U\n'; total_channels = len(self.__tv_list)
    session_token_for_url = self.__log_in.get('session') if self.__append_token_to_url else None

    for i, ch_info in enumerate(self.__tv_list):
      if self.__cb:
        progress_percent = int((i*100)/total_channels) if total_channels > 0 else 0
        ch_title_prog = ch_info.get('title', ch_info.get('epg_name', 'N/A'))
        self.__cb({'pr': progress_percent, 'str': f'Обработка: {ch_title_prog}', 'idx': i+1, 'max': total_channels})
      group_title = self.__en_group_ch if self.__en_group_ch else ch_info.get('genre', 'Undefined')
      if not self.__x and group_title == '18+': continue

      if self.__gen_m3u:
        catchup_tags = ''; stream_url = ''
        # При новия подход (docker-bulsatcom) основно се използва 'sources'
        stream_url = ch_info.get('sources', '')
        url_ndvr = ch_info.get('ndvr') # ndvr се използва само за catchup-source

        if not stream_url: # Fallback, ако 'sources' липсва
            if isinstance(url_ndvr, str) and "wmsAuthSign=" in url_ndvr : stream_url = url_ndvr
            else: stream_url = ch_info.get('pip', '')

        if not stream_url: self.__log_dat(f"Липсва URL за поток: {ch_info.get('title')}", force_log=True); continue
        self.__log_dat(f"Канал '{ch_info.get('title')}': Избран stream_url: {stream_url}", force_log=self.__DEBUG_EN)

        if self.__enable_catchup_info and self.__use_rec_for_catchup and isinstance(url_ndvr, str) and url_ndvr:
          parsed_original_ndvr = urllib.parse.urlparse(url_ndvr)
          path_for_catchup = parsed_original_ndvr.path; query_for_catchup = parsed_original_ndvr.query
          wowza_params = "wowzadvrplayliststart={utc:YmdHMS}&wowzadvrplaylistduration={duration}000"
          final_catchup_url = f"{recURL}{path_for_catchup}" # recURL е lb-ndvr...
          if query_for_catchup: final_catchup_url += f"?{query_for_catchup}&{wowza_params}"
          else: final_catchup_url += f"?{wowza_params}"
          catchup_tags = f'catchup="default" catchup-source="{final_catchup_url}"'

        current_title = ch_info.get('title', 'No Title')
        m3u_line_start = f'#EXTINF:-1 {catchup_tags} ' if catchup_tags else f'#EXTINF:-1 '
        tvg_id = ch_info.get('epg_name', '')
        tvg_logo_val = ch_info.get('logo', ch_info.get('logo_selected', ch_info.get('logo_favorite', '')))

        if self.use_ext_logos:
            logo_filename = f"{tvg_id}.png"
            if self.use_local_logos and self.logos_local_path: tvg_logo_val = os.path.join(self.logos_local_path, logo_filename)
            elif self.logos_path: tvg_logo_val = urllib.parse.urljoin(self.logos_path, logo_filename)
        elif epg_map and tvg_id in epg_map:
            map_entry = epg_map[tvg_id]; tvg_id_from_map = map_entry.get('id', tvg_id)
            logo_from_map = map_entry.get('ch_logo')
            if logo_from_map : tvg_logo_val = logo_from_map
            tvg_id = tvg_id_from_map

        self.__log_dat(f"Канал '{current_title}', tvg-id:'{tvg_id}', лого:'{tvg_logo_val}'", force_log=self.__DEBUG_EN)
        m3u_playlist_content+=f'{m3u_line_start}tvg-id="{tvg_id}" tvg-logo="{tvg_logo_val}" radio="{str(ch_info.get("radio",False)).lower()}" group-title="{group_title}",{current_title}\n'

        final_stream_url = stream_url
        if session_token_for_url and self.__token_param_name: # Добавяне на ssbulsatapi токена, ако е указано
            separator = '&' if '?' in final_stream_url else '?'
            if f"{self.__token_param_name}=" not in final_stream_url: final_stream_url += f"{separator}{self.__token_param_name}={session_token_for_url}"

        # Добавяне на User-Agent към M3U URL-а, ако е указано в config.ini
        # Използваме self.__M3U_USER_AGENT_STRING, който е оригиналният agent_id от config
        if self.__use_ua_in_m3u_url and self.__M3U_USER_AGENT_STRING:
          base_url_part = final_stream_url.split('|User-Agent=',1)[0]
          final_stream_url = f'{base_url_part}|User-Agent={urllib.parse.quote_plus(self.__M3U_USER_AGENT_STRING)}'

        m3u_playlist_content += f'{final_stream_url}\n'

    if self.__gen_m3u:
      m3u_file_path = os.path.join(self.__path, 'bulsat.m3u')
      try:
        with open(m3u_file_path, 'wb+') as f_m3u: f_m3u.write(m3u_playlist_content.encode(getattr(self,'__char_set','utf-8'),'replace'))
        if self.__cb: self.__cb({'str': f"M3U файлът е запазен в: {m3u_file_path}"})
      except IOError as e:
          if self.__cb: self.__cb({'str': f"Грешка запис M3U: {e}"})
          self.__log_dat(f"Грешка запис M3U: {e}"); ret=False

    if self.__gen_epg and xml_writer is not None:
      epg_file_base = os.path.join(self.__path, 'bulsat.xml')
      try:
        if self.__compress:
          epg_file_path_final = epg_file_base + '.gz'
          buffer_for_gzip = io.BytesIO()
          xml_writer.write(buffer_for_gzip, pretty_print=True)
          buffer_for_gzip.seek(0)
          with gzip.open(epg_file_path_final, 'wb', 9) as f_xml_gz:
              f_xml_gz.write(buffer_for_gzip.read())
          buffer_for_gzip.close()
          if self.__cb: self.__cb({'str': f"EPG компресиран в: {epg_file_path_final}"})
        else:
          epg_file_path_final = epg_file_base
          with open(epg_file_path_final, 'wb+') as f_xml: xml_writer.write(f_xml, pretty_print=True)
          if self.__cb: self.__cb({'str': f"EPG запазен в: {epg_file_path_final}"})
      except Exception as e:
          if self.__cb: self.__cb({'str':f"Грешка запис EPG:{e}"})
          self.__log_dat(f"Грешка запис EPG: {e}\n{traceback.format_exc()}");ret=False
    elif self.__gen_epg:
        self.__log_dat("xml_writer не е инициализиран, пропускане запис EPG.", force_log=True)

    if self.__cb:
      if ret: self.__cb({'pr':100,'str':'Операциите завършени успешно.'})
      else: self.__cb({'pr':100,'str':'Операциите завършени с грешки/липсващи данни.'})
    return ret
