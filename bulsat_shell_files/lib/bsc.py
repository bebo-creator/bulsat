# -*- coding: utf8 -*-

import os
import time
import base64
import requests
import gzip
import urllib.parse # Промяна от urllib
import simplejson as json
import hashlib
# Премахнати Kodi специфични импорти: xbmc, xbmcgui, xbmcvfs
import re
from Cryptodome.Cipher import AES
import io
from . import xmltv_p3 as xmltv # Използване на относителен импорт
import html # За html.unescape

recURL = 'http://lb-ndvr.iptv.bulsat.com'

# Премахната функция Mbox, тъй като зависи от ctypes и Windows, неподходяща за междуплатформен shell

class dodat():
  def __init__(self,
                base, # base_url от config
                login, # {'usr': username, 'pass': password}
                path, # Това е save_dir от main.py, използван за data.dat и изходните файлове
                cachetime=1, # в часове, от config cache_time_min / 60
                dbg=False, # debug_mode от config
                # dump_name не се използва активно
                timeout=0.5, # time_out_sec от config
                ver = '0.0.0', # Версия на скрипта
                xxx = False, # Филтър за съдържание за възрастни
                os_id = 'pcweb', # 'samsungtv' или 'androidtv'
                agent_id = 'pcweb', # User-Agent низ
                app_ver = '1.0.3', # Версия на приложението за конкретния os_id
                force_group_name = False, # Име на групата за каналите
                use_ua = True, # Дали да се включва User-Agent в URL адресите на потоците
                use_rec = True, # Възможност за запис/catchup
                gen_m3u = True, # Генериране на M3U файл
                gen_epg = False, # Генериране на EPG данни
                compress = True, # Компресиране на EPG данните (gzip)
                map_url = None, # Външен URL за EPG мапинг
                proc_cb = None, # Функция за обратна връзка за напредъка
                use_ext_logos = False, # Използване на външни лога
                logos_path = '', # Път до външни лога
                use_local_logos=False, # Използване на локални лога от указан път
                logos_local_path='', # Път до локални лога
                android_device_name='DefaultAndroidDeviceName', # Нов параметър за androidtv парола
                enable_catchup_info=True # Нова опция за контролиране на catchup информацията
                ):

    # Определяне на Host от базовия URL адрес за self.__UA
    parsed_url = urllib.parse.urlparse(base)
    self.__host = parsed_url.netloc if parsed_url.netloc else 'api.iptv.bulsat.com'

    self.__UA = {
                'Host': self.__host,
                'Connection': 'keep-alive',
                'User-Agent': 'Mozilla/5.0 (Linux; Android 7.0; molly Build/NRD91N; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/67.0.3396.87 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'bg-BG,en-US;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Pragma': 'no-cache'
                }

    self.__log_in = {}
    self.__p_data = {
                'user' : [None,''],
                'device_id' : [None, os_id], # os_id се използва като стойност по подразбиране тук
                'device_name' : [None, os_id], # os_id се използва като стойност по подразбиране тук
                'os_version' : [None, os_id], # os_id се използва като стойност по подразбиране тук
                'os_type' : [None, os_id], # Това е важно, ще се настрои на 'samsungtv' или 'androidtv'
                'app_version' : [None, app_ver], # app_ver от параметрите
                'pass' : [None,''],
                }
    self.__path = path # Директория за запис (където ще се съхранява data.dat и изходните файлове)
    self.__refresh = int(cachetime * 60 * 60) # cachetime е в часове, преобразуваме в секунди
    self.__p_data['user'][1] = login['usr']
    self.__log_in['pw'] = login['pass']
    self.__DEBUG_EN = dbg
    self.__t = timeout
    self.__BLOCK_SIZE = 16
    self.__use_ua = use_ua
    self.__use_rec = use_rec # Определя дали да се добавят catchup тагове
    self.__URL_EPG  = base + '/epg/long'
    self.__js = None # Кеширани данни
    self.__app_version = ver # Версия на този скрипт/библиотека
    self.__x = xxx # Филтър за съдържание 18+
    self.__en_group_ch = force_group_name # Принудително име на група или използване на жанр
    self.__gen_m3u = gen_m3u
    self.__gen_epg = gen_epg
    self.__compress = compress # Дали да се компресира EPG с gzip
    self.__cb = proc_cb # Callback функция за прогрес
    self.__MAP_URL = map_url
    self.__gen_jd = False # Не се използва, свързано с map.json
    self.use_ext_logos = use_ext_logos
    if logos_path and logos_path[-1:] == r'/':
        self.logos_path = logos_path
    elif logos_path:
        self.logos_path = logos_path + '/'
    else:
        self.logos_path = ''
    self.use_local_logos = use_local_logos
    self.logos_local_path = logos_local_path
    self.android_device_name = android_device_name # За криптиране на парола за Android TV
    self.__enable_catchup_info = enable_catchup_info # Запазване на новата опция

    self.__s = requests.Session()

    self.__URL_LOGIN = base + '/?auth'

    # Логика за URL_LIST въз основа на agent_id или os_id
    # Оригиналната логика:
    # if agent_id == 'okhttp/3.12.12': self.__URL_LIST = base + "/tv/full/limit"
    # else: self.__URL_LIST = base + "/tv/" -> това изглежда непълно, трябва os_id
    # От exec.py: temp_osid = __addon__.getSetting('dev_id_new1') -> което е '0' (samsung) или '1' (android)
    # __ua_os[temp_osid]['osid']
    #
    # Ако os_id е 'androidtv' (което съответства на okhttp user agent в оригиналния код)
    if self.__p_data['os_type'][1] == 'androidtv': # os_type вече е настроен на os_id от __init__
        self.__URL_LIST = base + "/tv/full/limit"
    else: # За samsungtv и други потенциални (въпреки че тук е само samsungtv)
        self.__URL_LIST = base + '/tv/' + self.__p_data['os_type'][1] + '/live'


    if agent_id != 'pcweb': # Ако е предоставен специфичен agent_id, го използваме
      self.__UA['User-Agent'] = agent_id

    # Директорията за запис (self.__path) вече трябва да съществува, създадена от main.py
    # но за всеки случай, ако се използва самостоятелно:
    if not os.path.exists(self.__path):
      try:
        os.makedirs(self.__path)
      except OSError as e:
        print(f"Грешка при създаване на директория {self.__path}: {e}")
        # Помислете за re-raise на грешката или изход, ако пътят е критичен

  def __log_dat(self, d):
    if self.__DEBUG_EN is not True:
      return
    print ('--------- BEGIN ---------')
    if isinstance(d, str): # Проверка на тип с isinstance
      print (d)
    elif isinstance(d, dict) or type(d).__name__ == 'CaseInsensitiveDict':
      for k, v in d.items():
        print (str(k) + ' : ' + str(v)) # Преобразуване към str за всеки случай
    elif isinstance(d, list):
      for l_item in d: # Промяна на името на променливата, за да не е 'l'
        print (l_item)
    else:
      print ('Todo add type %s' % type(d))
    print ('--------- END -----------')

  def __store_data(self):
      # data.dat се съхранява в self.__path (save_dir от main.py)
      data_file_path = os.path.join(self.__path, 'data.dat')
      try:
        with open(data_file_path, 'wb+') as f: # wb+ за бинарно записване
          f.write(json.dumps(self.__js,
                      sort_keys = True,
                      indent = 1,
                      ensure_ascii=False).encode('utf-8')) # Кодиране в UTF-8
        self.__log_dat(f"Данните са запазени в {data_file_path}")
      except IOError as e:
        self.__log_dat(f"Грешка при запис на data.dat: {e}")


      if self.__DEBUG_EN is True and self.__tv_list is not None and hasattr(self, '__char_set'):
        dump_file_path = os.path.join(self.__path, 'src.dump')
        try:
          # Ensure self.__char_set is available and is a string
          char_set_to_use = self.__char_set if hasattr(self, '__char_set') and isinstance(self.__char_set, str) else 'utf-8'
          with io.open(dump_file_path, 'w+', encoding=char_set_to_use) as f:
            f.write(json.dumps(self.__tv_list,
                          sort_keys = True,
                          indent = 1,
                          ensure_ascii=False))
          self.__log_dat(f"Дебъг дъмп е запазен в {dump_file_path}")
        except IOError as e:
          self.__log_dat(f"Грешка при запис на src.dump: {e}")
        except Exception as e: # По-общо прихващане за проблеми с кодиране или друго
          self.__log_dat(f"Неочаквана грешка при запис на src.dump: {e}")


  def __restore_data(self):
    data_file_path = os.path.join(self.__path, 'data.dat')
    try:
      with open(data_file_path, 'r', encoding='utf-8') as f: # Четене с UTF-8
        self.__js = json.load(f)
      self.__log_dat(f"Данните са възстановени от {data_file_path}")
    except IOError as e:
      self.__log_dat(f"Грешка при четене на data.dat: {e}")
      self.__js = None # Нулиране, ако файлът не може да бъде прочетен
    except json.JSONDecodeError as e:
      self.__log_dat(f"Грешка при декодиране на JSON от data.dat: {e}")
      self.__js = None # Нулиране, ако JSON е невалиден

  def __log_out(self):
    # Излизането от системата може да не е желателно за скрипт, който работи постоянно.
    # Ако се изисква, трябва да се тества внимателно.
    # Засега тази функция остава, но не се извиква активно след __goforit.
    try:
      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA, files={'logout': [None,'1']})
      self.__log_dat(r.request.headers)
      self.__log_dat(r.request.body)

      if r.status_code == requests.codes.ok and r.json()['Logged'] == 'false':
        self.__log_dat('Logout ok')
        if self.__cb:
          self.__cb({'pr': 100, 'str': 'Logout ok'})
      else:
        self.__log_dat(f'Logout Fail - Status: {r.status_code}, Response: {r.text}')
        # Не хвърляме изключение тук, тъй като излизането може да не е критично
    except requests.exceptions.RequestException as e:
        self.__log_dat(f"Грешка при заявка за излизане: {e}")
    except Exception as e:
        self.__log_dat(f"Неочаквана грешка при излизане: {e}")


  def __goforit(self):
    if self.__cb:
      self.__cb({'pr': 10, 'str': 'Инициализиране на сесия...'})

    try:
      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA)
      r.raise_for_status() # Проверка за HTTP грешки

      if self.__cb:
        self.__cb({'pr': 20, 'str': 'Сесията е стартирана. Генериране на данни за вход...'})

      self.__log_in['key'] = r.headers['challenge']
      self.__log_in['session'] = r.headers['ssbulsatapi']
      self.__s.headers.update({'SSBULSATAPI': self.__log_in['session']})

      # Актуализиране на app_version в __p_data, ако е различно от това по подразбиране
      # __p_data['app_version'][1] вече е настроено от self.app_ver в __init__

      # Логика за криптиране на парола
      if self.__p_data['os_type'][1] == 'androidtv':
        _text = self.__p_data['user'][1] + ':bulcrypt:' + self.__log_in['pw']
        length = self.__BLOCK_SIZE - (len(_text) % self.__BLOCK_SIZE)
        _text += chr(0) * length

        digest_key = hashlib.md5()
        digest_key.update('ARTS*#234S'.encode('utf-8'))
        aes_key = digest_key.hexdigest().encode("utf8")

        enc = AES.new(aes_key, AES.MODE_ECB)
        self.__p_data['pass'][1] = base64.b64encode(enc.encrypt(_text.encode("utf8"))).decode('utf-8')

        digest_device_id = hashlib.md5()
        # Използване на self.android_device_name вместо Kodi специфичен код
        device_info_str = self.__p_data['user'][1] + self.android_device_name
        digest_device_id.update(device_info_str.encode("utf8"))

        self.__p_data['device_id'][1] = digest_device_id.hexdigest()[0:16]
        # Стойностите по подразбиране за androidtv, ако не са зададени други в config
        self.__p_data['device_name'][1] = self.__p_data['device_name'][1] if self.__p_data['device_name'][1] != 'androidtv' else 'unknown_google_atv'
        self.__p_data['os_version'][1] = self.__p_data['os_version'][1] if self.__p_data['os_version'][1] != 'androidtv' else '7.1.2'
        # self.__p_data['app_version'][1] вече е настроен

      else: # За samsungtv и други
        _text = self.__log_in['pw'] + (self.__BLOCK_SIZE - len(self.__log_in['pw']) % self.__BLOCK_SIZE) * '\0'
        aes_key = self.__log_in['key'].encode("utf8")
        enc = AES.new(aes_key, AES.MODE_ECB)
        self.__p_data['pass'][1] = base64.b64encode(enc.encrypt(_text.encode("utf8"))).decode('utf-8')

      self.__log_dat(self.__log_in)
      self.__log_dat(self.__p_data)

      if self.__cb:
        self.__cb({'pr': 30, 'str': 'Изпращане на данни за вход...'})

      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA, files=self.__p_data)
      r.raise_for_status()

      self.__log_dat(r.request.headers)
      self.__log_dat(r.request.body) # Може да съдържа чувствителна информация

      login_response_data = r.json()
      self.__log_dat(login_response_data)

      if login_response_data.get('Logged') == 'true':
        self.__log_dat('Входът е успешен.')
        if self.__cb:
          self.__cb({'pr': 50, 'str': 'Входът е успешен. Извличане на списък с канали...'})

        # Тези хедъри може да не са необходими за стандартен POST заявка
        # self.__s.headers.update({'Access-Control-Request-Method': 'POST'})
        # self.__s.headers.update({'Access-Control-Request-Headers': 'ssbulsatapi'})
        # r = self.__s.options(self.__URL_LIST, timeout=self.__t, headers=self.__UA) # OPTIONS заявка може да не е нужна

        r_channels = self.__s.post(self.__URL_LIST, timeout=self.__t, headers=self.__UA)
        r_channels.raise_for_status()

        self.__log_dat(r_channels.request.headers)
        self.__log_dat(r_channels.headers) # Хедъри на отговора

        content_type = r_channels.headers.get('content-type', '')
        match = re.search(r'charset=([^;]+)', content_type)
        self.__char_set = match.group(1) if match else 'utf-8' # Кодиране по подразбиране UTF-8
        self.__log_dat(f'Открито кодиране: {self.__char_set}')

        # Използване на r_channels.content за байтове и ръчно декодиране
        try:
            decoded_content = r_channels.content.decode(self.__char_set)
        except UnicodeDecodeError:
            self.__log_dat(f"Грешка при декодиране с {self.__char_set}, опит с utf-8.")
            decoded_content = r_channels.content.decode('utf-8', errors='replace')
            self.__char_set = 'utf-8' # Актуализиране на charset, ако utf-8 работи

        self.__tv_list = json.loads(decoded_content)
        self.__js = {} # Инициализиране на __js за съхранение на метаданни
        self.__log_dat('Списъкът с канали е извлечен.')
        # self.__log_dat(self.__tv_list) # Може да е много голям

        if self.__cb:
          self.__cb({'pr': 90, 'str': 'Списъкът с канали е извлечен.'})

        if self.__gen_epg:
          if self.__cb:
            self.__cb({'pr': 92, 'str': 'Извличане на EPG данни...'})

          total_channels_for_epg = len(self.__tv_list)
          for i, ch_data in enumerate(self.__tv_list):
            if self.__cb:
              # Показване на името на канала, ако е налично, иначе epg_name
              channel_name_for_progress = ch_data.get('title', ch_data.get('epg_name', 'N/A'))
              self.__cb({
                  'pr': int((i * 100) / total_channels_for_epg) if total_channels_for_epg > 0 else 0,
                  'str': f'EPG за: {channel_name_for_progress}',
                  'idx': i + 1,
                  'max': total_channels_for_epg
              })

            if ch_data.__contains__('program') and ch_data.get('epg_name'): # Трябва epg_name за заявката
              try:
                r_epg = self.__s.post(self.__URL_EPG, timeout=self.__t,
                            headers=self.__UA,
                            data={
                              'epg': '1week', # '1day', 'nownext'
                              'channel': ch_data['epg_name']
                            })
                r_epg.raise_for_status()
                epg_data_raw = r_epg.json()
                # Структурата на отговора може да е { channel_id: { programme: [...] } }
                if epg_data_raw and isinstance(epg_data_raw, dict):
                    first_key = next(iter(epg_data_raw))
                    ch_data['program'] = epg_data_raw[first_key].get('programme', [])
              except requests.exceptions.RequestException as e:
                  self.__log_dat(f"Грешка при извличане на EPG за {ch_data.get('epg_name')}: {e}")
              except Exception as e:
                  self.__log_dat(f"Неочаквана грешка при обработка на EPG за {ch_data.get('epg_name')}: {e}")


        # Декодиране на HTML ентитита, ако има такива в данните (малко вероятно за JSON API, но за всеки случай)
        # Това вече е в оригиналния код, но тук се прилага върху self.__js, което е празно.
        # Трябва да се приложи върху self.__tv_list, ако е необходимо.
        # По-добре е да се прилага селективно, ако се знае къде има HTML ентитита.
        # self.__js = json.loads(html.unescape(json.dumps(self.__js))) -> това няма смисъл
        # Ако трябва да се unescape __tv_list:
        # self.__tv_list = json.loads(html.unescape(json.dumps(self.__tv_list)))

        # Излизането от системата е коментирано в оригиналния код и тук също.
        # self.__log_out()

      else:
        error_msg = login_response_data.get('Error', 'Неуспешен вход без конкретна грешка от API.')
        self.__log_dat(f'LoginFail: {error_msg}')
        raise Exception(f"LoginFail: {error_msg}")

    except requests.exceptions.HTTPError as e:
        self.__log_dat(f"HTTP грешка: {e.response.status_code} - {e.response.text}")
        raise Exception(f"HTTP грешка: {e.response.status_code}") from e
    except requests.exceptions.RequestException as e:
        self.__log_dat(f"Грешка при мрежова заявка: {e}")
        raise Exception("NetworkRequestFail") from e
    except Exception as e: # По-общо прихващане за други грешки
        self.__log_dat(f"Неочаквана грешка в __goforit: {e}")
        import traceback
        self.__log_dat(traceback.format_exc())
        raise Exception("UnexpectedErrorInGoforit") from e


  def __data_fetch(self, force_refresh):
    self.__tv_list = None # Нулиране преди опит за зареждане или извличане
    data_file_path = os.path.join(self.__path, 'data.dat')

    if os.path.exists(data_file_path) and not force_refresh:
      self.__restore_data() # Зарежда данни в self.__js
      if self.__js and 'ts' in self.__js and 'os_type' in self.__js:
        # Проверка дали кешът е валиден
        current_time = time.time()
        is_cache_fresh = (current_time - self.__js['ts']) < self.__refresh
        is_os_type_match = self.__js['os_type'] == self.__p_data['os_type'][1]
        # Добавяне на проверка за app_version, ако е важно за кеша
        is_app_version_match = self.__js.get('app_version') == self.__app_version if 'app_version' in self.__js else True


        if is_cache_fresh and is_os_type_match and is_app_version_match:
          self.__log_dat('Използване на кеширани данни от data.dat')
          # Ако __tv_list се съхранява в data.dat (трябва да се провери)
          # Ако не, __goforit() трябва да се извика.
          # Оригиналният код не съхранява __tv_list в data.dat, а само метаданни.
          # Следователно, __goforit() винаги се извиква, ако __js е None или кешът е стар.
          # За да се избегне повторно извикване, __tv_list трябва да се зареди от някъде.
          # Засега, ако data.dat е валиден, приемаме, че не е нужно ново извличане.
          # Това означава, че __tv_list трябва да се зареди от src.dump, ако съществува.
          dump_file_path = os.path.join(self.__path, 'src.dump')
          if self.__DEBUG_EN and os.path.exists(dump_file_path):
              try:
                  with io.open(dump_file_path, 'r', encoding=self.__js.get('char_set', 'utf-8')) as f:
                      self.__tv_list = json.load(f)
                  self.__log_dat("Възстановен __tv_list от src.dump")
              except Exception as e:
                  self.__log_dat(f"Неуспешно възстановяване на __tv_list от src.dump: {e}")
                  self.__js = None # Принудително обновяване, ако дъмпът е повреден
          else:
              # Ако няма дъмп, но data.dat е валиден, трябва да се изтегли списъка отново.
              # Това поведение не е идеално. Трябва или да се кешира __tv_list, или винаги да се изтегля.
              self.__log_dat("Кешът е валиден, но __tv_list не е наличен локално. Принудително обновяване.")
              self.__js = None # Принудително обновяване

        else:
          self.__log_dat('Кешът е остарял или несъвместим. Извличане от сайта.')
          self.__js = None # Принудително обновяване
      else:
        self.__log_dat('Липсват данни в кеша или кешът е невалиден. Извличане от сайта.')
        self.__js = None # Принудително обновяване
    else:
      if force_refresh:
        self.__log_dat('Принудително обновяване на данните.')
      else:
        self.__log_dat('Липсва файл с кеширани данни. Извличане от сайта.')
      self.__js = None

    if self.__js is None: # Ако кешът не е използван или е невалиден
      self.__goforit() # Извлича __tv_list и инициализира self.__js
      if self.__tv_list is not None: # Проверка дали __goforit е бил успешен
          self.__log_dat('Дължина на списъка с канали: %d' % len(self.__tv_list))
          self.__js['ts'] = time.time() # Запазване на точното време на извличане
          self.__js['app_version'] = self.__app_version # Версия на скрипта, който е генерирал кеша
          self.__js['os_type'] = self.__p_data['os_type'][1] # OS тип, за който е кешът
          if hasattr(self, '__char_set'):
              self.__js['char_set'] = self.__char_set # Запазване на кодирането
          self.__log_dat('Базово време на кеша: %s' % time.ctime(self.__js['ts']))
          self.__store_data() # Запазване на self.__js (метаданни) и евентуално self.__tv_list (в src.dump)
      else:
          # __goforit не е успял да извлече __tv_list
          self.__log_dat("Неуспешно извличане на данни от сървъра.")
          # Не се опитваме да генерираме файлове, ако нямаме данни
          return False # Индикация за неуспех

    return True # Индикация за успех при извличане/зареждане на данни


  def gen_all(self, force_refresh = False):
    ret = False
    if not self.__data_fetch(force_refresh):
        # Ако __data_fetch върне False, това означава, че не е успял да зареди/извлече __tv_list
        if self.__cb:
            self.__cb({'pr': 100, 'str': 'Грешка: Неуспешно извличане на данни за каналите.'})
        return False # Прекратяване, ако няма данни

    if self.__tv_list: # Проверка дали __tv_list съществува и не е празен
      ret = True
      epg_map = None # Променлива за мапинг от map_url

      # --- XMLTV EPG Generation ---
      if self.__gen_epg:
        # __char_set трябва да е наличен от __goforit
        char_set_for_xml = getattr(self, '__char_set', 'UTF-8').upper()
        xml_writer = xmltv.Writer(encoding=char_set_for_xml,
                          date=str(time.time()), # Текущо време като дата на генериране
                          source_info_url="https://bulsat.com", # Примерни стойности
                          source_info_name="Bulsatcom",
                          generator_info_name=f"bulsat_shell_script/{self.__app_version}",
                          generator_info_url="") # Празно, ако няма специфичен URL
      else: # Ако не генерираме EPG, може да заредим мапинг за M3U
        if self.__MAP_URL:
          try:
            if self.__cb: self.__cb({'str': f"Изтегляне на EPG карта от: {self.__MAP_URL}"})
            m = requests.get(self.__MAP_URL, timeout=self.__t, headers={'User-Agent': 'fusion_tv_shell_script'})
            m.raise_for_status()
            epg_map = m.json()
            self.__log_dat(epg_map)
            if self.__cb: self.__cb({'str': "EPG картата е изтеглена успешно."})
          except requests.exceptions.RequestException as e:
            if self.__cb: self.__cb({'str': f"Грешка при изтегляне на EPG карта: {e}"})
            self.__log_dat(f"Грешка при изтегляне на EPG карта: {e}")
          except json.JSONDecodeError as e:
            if self.__cb: self.__cb({'str': f"Грешка при парсване на EPG карта: {e}"})
            self.__log_dat(f"Грешка при парсване на EPG карта: {e}")


      # --- M3U Playlist Generation ---
      m3u_playlist_content = u'#EXTM3U\n'
      # dat = [x for x in self.__tv_list] # Копиране на списъка, ако е необходимо

      total_channels = len(self.__tv_list)
      for i, ch_info in enumerate(self.__tv_list):
        if self.__cb:
          progress_percent = int((i * 100) / total_channels) if total_channels > 0 else 0
          channel_name_progress = ch_info.get('title', ch_info.get('epg_name', 'N/A'))
          self.__cb({
              'pr': progress_percent,
              'str': f'Обработка: {channel_name_progress}',
              'idx': i + 1,
              'max': total_channels
          })

        group_title = self.__en_group_ch if self.__en_group_ch else ch_info.get('genre', 'Undefined')

        # Филтър за съдържание за възрастни
        if not self.__x and group_title == '18+':
          continue # Пропускане на този канал

        if self.__gen_m3u:
          extinf_title_parts = [ch_info.get('title', 'No Title')]
          catchup_tags = ''

          # Добавяне на catchup информация, ако е налична и use_rec е True и новата опция е активна
          if self.__enable_catchup_info and self.__use_rec and 'ndvr' in ch_info and ch_info['ndvr']:
            # Формиране на catchup-source URL. Токенът и request_time може да се нуждаят от актуализация или да са специфични за сесия.
            # Използваме структурата от оригиналния exec.py, но без KODIPROP.
            # ВАЖНО: Токенът '38264607382' е взет от оригиналния код. Ако е динамичен, това няма да работи дългосрочно.
            # Засега го оставяме така, както е бил в оригиналния плъгин.
            # ndvr_link_part = ch_info['ndvr'][ch_info['ndvr'].index(':',10):] if ':' in ch_info['ndvr'][10:] else ch_info['ndvr'] # По-безопасно извличане
            # По-просто: ch_info['ndvr'] често е пълен URL, но понякога е само част.
            # recURL = 'http://lb-ndvr.iptv.bulsat.com'
            # Пример за ndvr от логове: /live/hls/... или пълен URL.
            # Ако ch_info['ndvr'] е относителен път:
            # catchup_source_url = f"{recURL}{ndvr_link_part}&wowzadvrplayliststart={{utc:YmdHMS}}&wowzadvrplaylistduration={{duration}}000&request_time={str(round(time.time() * 1000))}token=38264607382"
            # Ако ch_info['ndvr'] е пълен URL:
            # catchup_source_url = f"{ch_info['ndvr']}&wowzadvrplayliststart={{utc:YmdHMS}}&wowzadvrplaylistduration={{duration}}000&request_time={str(round(time.time() * 1000))}token=38264607382"
            # Засега ще приемем, че ch_info['ndvr'] е основният URL за catchup и ще добавим параметрите.
            # Това е най-близко до оригиналната логика без Kodi.

            # По-безопасен подход към ndvr_link_part, ако ch_info['ndvr'] съдържа ':' преди 10-ти символ
            start_index = ch_info['ndvr'].find(':', 10)
            if start_index == -1: # Ако ':' не е намерен след 10-тия символ, може би е пълен URL или различна структура
                # В този случай, може да не искаме да използваме recURL или да имаме различна логика
                # Засега, ако не намерим ':', ще използваме ndvr както е, ако изглежда като URL
                if "://" in ch_info['ndvr']:
                    base_catchup_url = ch_info['ndvr']
                else: # Ако не е пълен URL и няма ':' след 10-ти символ, може да е само ID или относителен път
                    base_catchup_url = recURL + (ch_info['ndvr'] if ch_info['ndvr'].startswith('/') else '/' + ch_info['ndvr'])
            else:
                ndvr_link_part = ch_info['ndvr'][start_index:] # Вземане на частта след IP:PORT
                base_catchup_url = recURL + ndvr_link_part

            # Добавяне на параметри за Wowza DVR
            # ВАЖНО: {utc:YYYYMMDDHHmmss} и {durationSeconds} са примери за плейсхолдъри, които IPTV Simple Client поддържа.
            # Оригиналният код използва {utc:YmdHMS} и {duration}000. Ще се придържаме към оригиналните плейсхолдъри.
            catchup_source_url = f"{base_catchup_url}" # Основният URL
            # Параметрите ще се добавят от IPTV клиента, ако той поддържа такъв формат за catchup-source.
            # IPTV Simple Client очаква URL с плейсхолдъри.
            # Пример: catchup-source="http://example.com/playlist.m3u8?utc={utc}&lutc={lutc}&offset={offset}&duration={duration}"
            # Оригиналните параметри са: &wowzadvrplayliststart={utc:YmdHMS}&wowzadvrplaylistduration={duration}000&request_time=...token=...
            # Тези параметри са специфични за Wowza и може да не се интерпретират правилно от всички клиенти директно в catchup-source.
            # По-стандартно е да се използват плейсхолдъри, които клиентът замества.
            # Засега ще запазя оригиналната структура на параметрите, тъй като това е, което плъгинът е генерирал.
            # Трябва да се има предвид, че request_time и token може да изтекат.

            # Формиране на catchup атрибутите за M3U
            # ВАЖНО: Използването на str(round(time.time() * 1000)) и фиксиран токен може да не е надеждно за дългосрочен catchup.
            # Това е взето директно от оригиналния код.
            # catchup_params = f"&wowzadvrplayliststart={{utc:YmdHMS}}&wowzadvrplaylistduration={{duration}}000&request_time={str(round(time.time() * 1000))}token=38264607382" # Този токен може да е проблем
            # По-безопасно е да се предоставят само основните плейсхолдъри, ако клиентът ги поддържа.
            # IPTV Simple Client поддържа: {utc} {lutc} {offset} {duration} {timestamp} {datetime} {utcdate} {utctime} {path} {filename} {extension}
            # За Wowza DVR, плейсхолдърите са {wowzadvrplayliststart} и {wowzadvrplaylistduration} (или подобни).
            # Оригиналът е: ch['ndvr'][ch['ndvr'].index(':',10):] + '&wowzadvrplayliststart={utc:YmdHMS}&wowzadvrplaylistduration={duration}000&request_time=' + str(round(time.time() * 1000)) + 'token=38264607382"'
            # Нека се опитаме да го запазим максимално близо до оригинала, но да го направим по-стандартен M3U атрибут.

            # Извличане на основния URL от ndvr, премахвайки query string ако има
            ndvr_base_url = ch_info['ndvr'].split('?')[0]

            # Формиране на catchup атрибута, който IPTV Simple Client би могъл да използва.
            # Клиентът ще добави query параметрите.
            # catchup_tags = f'catchup="default" catchup-days="7" catchup-source="{ndvr_base_url}?&wowzadvrplayliststart={{utc:YmdHMS}}&wowzadvrplaylistduration={{duration}}000&request_time={str(round(time.time() * 1000))}&token=38264607382"'
            # Горният ред е твърде специфичен. По-добре е да се придържаме към стандартни плейсхолдъри, ако е възможно.
            # Ако трябва да се запази оригиналната Wowza структура, тя трябва да е част от URL-а, който клиентът конструира.
            # Засега, ще добавя само `catchup="default"` и ще разчитам, че URL-ът в `ch_info['ndvr']` е правилният за DVR.
            # Ако `ch_info['ndvr']` вече съдържа плейсхолдъри или е базов URL за DVR, това може да е достатъчно.
            # От преглед на оригиналния код, изглежда, че пълният URL с параметри (без плейсхолдъри) се генерира.
            # Това не е стандартно за `catchup-source`.

            # Връщане към по-прост подход: ако има ndvr, маркираме го. Конкретният URL за timeshift ще се вземе от stream_url.
            # Атрибутът `catchup="default"` е достатъчен, за да каже на клиента, че има архив.
            # Клиентът сам трябва да знае как да поиска архив от основния стрийм URL, ако той го поддържа.
            # Ако обаче `ch_info['ndvr']` е специфичният URL за DVR (както изглежда), тогава той трябва да се използва като stream_url за catchup.
            # Това е сложен момент. Оригиналният код добавяше KODIPROP тагове, които указваха на Kodi как да третира това.
            # Без тях, трябва да се разчита на стандартни M3U тагове.

            # Нека да използваме `ch_info['ndvr']` като основен URL за catchup потока,
            # и да добавим стандартни плейсхолдъри, които IPTV Simple Client разбира.
            # Това е компромис.
            # Пример: catchup-source="[ndvr_url_без_плейсхолдъри_от_ch_info_ndvr]?wowzadvrplayliststart={utc:YYYYMMDDHHmmss}&wowzadvrplaylistduration={durationSeconds}"
            # Ще се придържам към това, което е било генерирано като URL в оригиналния код, но ще го сложа в catchup-source.

            # Взимане на частта след IP адреса и порта, ако има такива.
            # Това е рисковано, ако структурата на URL се промени.
            path_and_query = ch_info['ndvr']
            if '://' in path_and_query:
                path_and_query = '/' + '/'.join(path_and_query.split('/')[3:]) # Взема пътя след хоста

            # Формиране на catchup-source URL с плейсхолдъри, които IPTV Simple Client би заместил
            # Използваме recURL като база, както в оригиналния код
            # Токенът и request_time се премахват, тъй като те трябва да се управляват от клиента или сървъра по време на заявката.
            # Клиентът ще добави необходимите параметри за време.
            formatted_ndvr_url = f"{recURL}{path_and_query}&wowzadvrplayliststart={{utc:YmdHMS}}&wowzadvrplaylistduration={{duration}}000"
            # formatted_ndvr_url = f"{recURL}{path_and_query}" # По-просто, клиентът да добавя всичко

            catchup_tags = f'catchup="default" catchup-source="{formatted_ndvr_url}"'
            # extinf_title_parts.append("[Catchup]") # По желание, за индикация в името

          stream_url = ch_info.get('sources', '') # Основен URL на потока
          if not stream_url and 'ndvr' in ch_info and self.__enable_catchup_info and self.__use_rec:
              # Ако няма 'sources', но има 'ndvr' и catchup е активен, може би 'ndvr' е основният поток за гледане с DVR.
              # Това е малко вероятно, обикновено 'sources' е за live, а 'ndvr' за архив.
              # Ако 'sources' липсва, но 'ndvr' го има, ще използваме 'ndvr' като основен поток.
              stream_url = ch_info.get('ndvr', '')
          elif not stream_url:
               stream_url = ch_info.get('ndvr', '') # Fallback ако sources липсва, без значение от catchup опцията

          extinf_title = " ".join(extinf_title_parts)
          if catchup_tags: # Добавяне на catchup таговете към EXTINF, ако са генерирани
              m3u_line_start = f'#EXTINF:-1 {catchup_tags} '
          else:
              m3u_line_start = f'#EXTINF:-1 '

          # Добавяне на останалите атрибути към m3u_line_start
          # (tvg-id, tvg-logo, radio, group-title)
          # и заглавието на канала.
          # Това е малко объркано с extinf_title и extinf_title_parts. Ще го опростя.

          current_title = ch_info.get('title', 'No Title')
          tvg_id = ch_info.get('epg_name', '')
          tvg_logo_val = ch_info.get('logo_selected', '') # Преименуване, за да не се бърка с променливата tvg_logo от по-рано

          if self.use_ext_logos:
              logo_filename = f"{tvg_id}.png"
              if self.use_local_logos and self.logos_local_path:
                  tvg_logo_val = os.path.join(self.logos_local_path, logo_filename)
              elif self.logos_path:
                  tvg_logo_val = urllib.parse.urljoin(self.logos_path, logo_filename)

          if epg_map and tvg_id in epg_map: # epg_map е дефинирано по-горе
              map_entry = epg_map[tvg_id]
              tvg_id = map_entry.get('id', tvg_id)
              if not self.use_ext_logos:
                  tvg_logo_val = map_entry.get('ch_logo', tvg_logo_val)

          m3u_playlist_content += f'{m3u_line_start}tvg-id="{tvg_id}" tvg-logo="{tvg_logo_val}" radio="{str(ch_info.get("radio", False)).lower()}" group-title="{group_title}",{current_title}\n'

          if self.__use_ua and self.__UA.get('User-Agent'):
            m3u_playlist_content += f'{stream_url}|User-Agent={urllib.parse.quote_plus(self.__UA["User-Agent"])}\n'
          else:
            m3u_playlist_content += f'{stream_url}\n'

        # --- XMLTV EPG Channel and Programme Data ---
        if self.__gen_epg and hasattr(xml_writer, 'addChannel'):
          display_names = [(ch_info.get('title', 'N/A'), 'bg')] # Приемаме български по подразбиране

          xml_writer.addChannel({
              'display-name': display_names,
              'id': ch_info.get('epg_name', str(i)), # Уникален ID за канала
              'url': [ch_info.get('url', '')] # URL към уебсайта на канала, ако има
          })

          if 'program' in ch_info and ch_info['program']:
            for prog_item in ch_info['program']:
              prog_title = [(prog_item.get('title', 'N/A'), '')] # Езикът може да се остави празен
              prog_desc = [(prog_item.get('desc', ''), '')]
              prog_category = [(ch_info.get('genre', ''), '')]

              xml_writer.addProgramme({
                  'start': prog_item.get('start', ''),
                  'stop': prog_item.get('stop', ''),
                  'title': prog_title,
                  'desc': prog_desc,
                  'category': prog_category,
                  'channel': ch_info.get('epg_name', str(i)) # ID на канала, към който принадлежи програмата
              })

      # --- Writing M3U file ---
      if self.__gen_m3u:
        m3u_file_path = os.path.join(self.__path, 'bulsat.m3u')
              stream_url = ch_info.get('ndvr', '')


          tvg_id = ch_info.get('epg_name', '')
          tvg_logo = ch_info.get('logo_selected', '') # Лого по подразбиране

          if self.use_ext_logos:
              logo_filename = f"{tvg_id}.png" # Приемаме PNG формат
              if self.use_local_logos and self.logos_local_path:
                  # Проверка дали файлът съществува локално може да е бавна.
                  # По-добре е просто да се конструира пътят.
                  tvg_logo = os.path.join(self.logos_local_path, logo_filename)
              elif self.logos_path: # Външен път (URL)
                  tvg_logo = urllib.parse.urljoin(self.logos_path, logo_filename)

          # Прилагане на EPG мап, ако е наличен
          if epg_map and tvg_id in epg_map:
              map_entry = epg_map[tvg_id]
              tvg_id = map_entry.get('id', tvg_id)
              # tvg_offset = map_entry.get('offset', '0') # Не се използва в M3U директно
              if not self.use_ext_logos: # Ако не използваме външни лога, може да вземем от картата
                  tvg_logo = map_entry.get('ch_logo', tvg_logo)


          m3u_playlist_content += f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{tvg_logo}" radio="{str(ch_info.get("radio", False)).lower()}" group-title="{group_title}",{extinf_title}\n'

          if self.__use_ua and self.__UA.get('User-Agent'):
            m3u_playlist_content += f'{stream_url}|User-Agent={urllib.parse.quote_plus(self.__UA["User-Agent"])}\n'
          else:
            m3u_playlist_content += f'{stream_url}\n'

        # --- XMLTV EPG Channel and Programme Data ---
        if self.__gen_epg and hasattr(xml_writer, 'addChannel'):
          display_names = [(ch_info.get('title', 'N/A'), 'bg')] # Приемаме български по подразбиране

          xml_writer.addChannel({
              'display-name': display_names,
              'id': ch_info.get('epg_name', str(i)), # Уникален ID за канала
              'url': [ch_info.get('url', '')] # URL към уебсайта на канала, ако има
          })

          if 'program' in ch_info and ch_info['program']:
            for prog_item in ch_info['program']:
              prog_title = [(prog_item.get('title', 'N/A'), '')] # Езикът може да се остави празен
              prog_desc = [(prog_item.get('desc', ''), '')]
              prog_category = [(ch_info.get('genre', ''), '')]

              xml_writer.addProgramme({
                  'start': prog_item.get('start', ''),
                  'stop': prog_item.get('stop', ''),
                  'title': prog_title,
                  'desc': prog_desc,
                  'category': prog_category,
                  'channel': ch_info.get('epg_name', str(i)) # ID на канала, към който принадлежи програмата
              })

      # --- Writing M3U file ---
      if self.__gen_m3u:
        m3u_file_path = os.path.join(self.__path, 'bulsat.m3u')
        try:
          with open(m3u_file_path, 'wb+') as f_m3u: # Отваряне в бинарен режим за запис
            # Кодиране към self.__char_set, ако е дефиниран, иначе UTF-8
            encoding_to_use = getattr(self, '__char_set', 'utf-8')
            f_m3u.write(m3u_playlist_content.encode(encoding_to_use, 'replace'))
          if self.__cb: self.__cb({'str': f"M3U файлът е запазен в: {m3u_file_path}"})
        except IOError as e:
          if self.__cb: self.__cb({'str': f"Грешка при запис на M3U файла: {e}"})
          self.__log_dat(f"Грешка при запис на M3U файла: {e}")
          ret = False # Маркиране като неуспешно, ако записът на M3U се провали

      # --- Writing EPG file (XMLTV) ---
      if self.__gen_epg and hasattr(xml_writer, 'write'):
        epg_file_base = os.path.join(self.__path, 'bulsat.xml')
        try:
          if self.__compress:
            epg_file_path_final = epg_file_base + '.gz'
            # Използване на io.BytesIO за компресиране в паметта преди запис
            with io.BytesIO() as temp_buffer:
              xml_writer.write(temp_buffer, pretty_print=True) # Запис в буфера
              temp_buffer.seek(0) # Връщане в началото на буфера
              with gzip.open(epg_file_path_final, 'wb', 9) as f_xml_gz:
                f_xml_gz.write(temp_buffer.read())
            if self.__cb: self.__cb({'str': f"EPG файлът е запазен (компресиран) в: {epg_file_path_final}"})
          else:
            epg_file_path_final = epg_file_base
            with open(epg_file_path_final, 'wb+') as f_xml:
              xml_writer.write(f_xml, pretty_print=True)
            if self.__cb: self.__cb({'str': f"EPG файлът е запазен в: {epg_file_path_final}"})
        except IOError as e:
          if self.__cb: self.__cb({'str': f"Грешка при запис на EPG файла: {e}"})
          self.__log_dat(f"Грешка при запис на EPG файла: {e}")
          ret = False # Маркиране като неуспешно, ако записът на EPG се провали
        except Exception as e: # По-общо прихващане за други грешки при запис на EPG
            if self.__cb: self.__cb({'str': f"Неочаквана грешка при запис на EPG: {e}"})
            self.__log_dat(f"Неочаквана грешка при запис на EPG: {e}")
            ret = False

    else: # Ако self.__tv_list е празен или None
        if self.__cb: self.__cb({'str': "Няма данни за каналите за генериране на файлове."})
        self.__log_dat("Пропускане на генерирането на файлове, тъй като __tv_list е празен.")
        ret = False # Няма данни, така че операцията не е напълно успешна

    if self.__cb:
        if ret:
            self.__cb({'pr': 100, 'str': 'Всички операции са завършени успешно.'})
        else:
            self.__cb({'pr': 100, 'str': 'Операциите са завършени с някои грешки или липсващи данни.'})

    return ret
