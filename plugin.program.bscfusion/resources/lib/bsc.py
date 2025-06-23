    # -*- coding: utf8 -*-

import os, time
import base64
import requests
import gzip
import urllib
import simplejson as json
import hashlib
import xbmc
import xbmcgui
import re
import xbmcvfs
from Cryptodome.Cipher import AES
import io
import xmltv_p3 as xmltv

recURL = 'http://lb-ndvr.iptv.bulsat.com'

def Mbox(title, text, style):
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

class dodat():
  def __init__(self,
                base,
                login,
                path,
                cachetime=1,
                dbg=False,
                dump_name='',
                timeout=0.5,
                ver = '0.0.0',
                xxx = False,
                os_id = 'pcweb',
                agent_id = 'pcweb',
                app_ver = '1.0.3',
                force_group_name = False,
                use_ua = True,
                use_rec = True,
                gen_m3u = True,
                gen_epg = False,
                compress = True,
                map_url = None,
                proc_cb = None,
                use_ext_logos = False,
                logos_path = '',
                use_local_logos=False,
                logos_local_path=''):

    self.__UA = {
                'Host': 'api.iptv.bulsat.com',
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
                'device_id' : [None, os_id],
                'device_name' : [None, os_id],
                'os_version' : [None, os_id],
                'os_type' : [None, os_id],
                'app_version' : [None, app_ver],
                'pass' : [None,''],
                }
    self.__path = path
    self.__refresh = int(cachetime * 60)
    self.__p_data['user'][1] = login['usr']
    self.__log_in['pw'] = login['pass']
    self.__DEBUG_EN = dbg
    self.__t = timeout
    self.__BLOCK_SIZE = 16
    self.__use_ua = use_ua
    self.__use_rec = use_rec
    self.__URL_EPG  = base + '/epg/long'
    self.__js = None
    self.__app_version = ver
    self.__x = xxx
    self.__en_group_ch = force_group_name
    self.__gen_m3u = gen_m3u
    self.__gen_epg = gen_epg
    self.__compress = compress
    self.__cb = proc_cb
    self.__MAP_URL = map_url
    self.__gen_jd = False
    self.use_ext_logos = use_ext_logos
    if logos_path[-1:] == r'/':
        self.logos_path = logos_path
    else:
        self.logos_path = logos_path + '/'
    self.use_local_logos = use_local_logos
    self.logos_local_path = logos_local_path

    self.__s = requests.Session()

    #if agent_id != 'pcweb':
    #  self.__URL_LOGIN = base + '/?auth'
    #  if self.__use_rec:
    #      self.__refresh = int(480 * 60)
    #      self.__URL_LIST = base + "/tv/full/limit"
    #  else:
    #      self.__URL_LIST = base + '/tv/' + os_id + '/live'  # + '/tv/samsungtv/live'
    #else:
    #  self.__URL_LOGIN = base + '/?auth'
    # self.__URL_LIST = base + '/tv/pcweb/live'

    self.__URL_LOGIN = base + '/?auth'

    if agent_id == 'okhttp/3.12.12':
        self.__URL_LIST = base + "/tv/full/limit"
    else:
        self.__URL_LIST = base + "/tv/"

    #if self.__use_rec:
    #    self.__refresh = int(480 * 60)

    if agent_id != 'pcweb':
      self.__UA['User-Agent'] = agent_id

    if not os.path.exists(self.__path):
      os.makedirs(self.__path)

  def __log_dat(self, d):
    if self.__DEBUG_EN is not True:
      return
    print ('--------- BEGIN ---------')
    if type(d) is str:
      print (d)
    elif type(d) is dict or type(d).__name__ == 'CaseInsensitiveDict':
      for k, v in d.items():
        print (k + ' : ' + str(v))

    elif type(d) is list:
      for l in d:
        print (l)
    else:
      print ('Todo add type %s' % type(d))
    print ('--------- END -----------')

  def __store_data(self):
      with open(os.path.join(self.__path, '', 'data.dat'), 'wb+') as f:
        f.write(json.dumps(self.__js,
                    sort_keys = True,
                    indent = 1,
                    ensure_ascii=False).encode('utf-8'))

      if self.__DEBUG_EN is True:
        import io
        with io.open(os.path.join(self.__path, '', 'src.dump'), 'w+', encoding=self.__char_set) as f:
          f.write(json.dumps(self.__tv_list,
                        sort_keys = True,
                        indent = 1,
                        ensure_ascii=False))

  def __restore_data(self):
    with open(os.path.join(self.__path, '', 'data.dat'), 'r') as f:
      self.__js = json.load(f)

  def __log_out(self):
    r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA, files={'logout': [None,'1']})

    self.__log_dat(r.request.headers)
    self.__log_dat(r.request.body)

    if r.status_code == requests.codes.ok and r.json()['Logged'] == 'false':
      self.__log_dat('Logout ok')
      if self.__cb:
        self.__cb({'pr': 100, 'str': 'Logout ok'})
    else:
      self.__log_dat('Logout Fail')
      raise Exception("LogoutFail")

  def __goforit(self):
    if self.__cb:
      self.__cb({'pr': 10, 'str': 'Session'})
    r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA)

    if r.status_code == requests.codes.ok:
      if self.__cb:
        self.__cb({'pr': 20, 'str': 'Session start'})
      self.__log_in['key'] = r.headers['challenge']
      self.__log_in['session'] = r.headers['ssbulsatapi']

      self.__s.headers.update({'SSBULSATAPI': self.__log_in['session']})

      if self.__p_data['os_type'][1] == 'androidtv':
        _text = self.__p_data['user'][1] + ':bulcrypt:' + self.__log_in['pw']
        length = 16 - (len(_text) % 16)
        _text += chr(0)*length
        digest = hashlib.md5()
        digest.update('ARTS*#234S'.encode('utf-8'))
        enc = AES.new(digest.hexdigest().encode("utf8"), AES.MODE_ECB)
        self.__p_data['pass'][1] = base64.b64encode(enc.encrypt(_text.encode("utf8")))
        digest.update((self.__p_data['user'][1] + xbmc.getInfoLabel('System.FriendlyName')).encode("utf8"))

        self.__p_data['device_id'][1] = digest.hexdigest()[0:16] #must be 64bit hex -> android device uniqueID
        self.__p_data['device_name'][1] = 'unknown_google_atv'
        self.__p_data['os_version'][1] = '7.1.2'
        self.__p_data['app_version'][1] = '1.5.20'
      else:
        _text = self.__log_in['pw'] + (self.__BLOCK_SIZE - len(self.__log_in['pw']) % self.__BLOCK_SIZE) * '\0'
        enc = AES.new(self.__log_in['key'].encode("utf8"), AES.MODE_ECB)
        self.__p_data['pass'][1] = base64.b64encode(enc.encrypt(_text.encode("utf8")))

      self.__log_dat(self.__log_in)
      self.__log_dat(self.__p_data)

      if self.__cb:
        self.__cb({'pr': 30, 'str': 'Login start'})

      r = self.__s.post(self.__URL_LOGIN, timeout=self.__t, headers=self.__UA, files=self.__p_data)

      self.__log_dat(r.request.headers)
      self.__log_dat(r.request.body)

      if r.status_code == requests.codes.ok:
        data = r.json()
        #print(data)

        if data['Logged'] == 'true':
          self.__log_dat('Login ok')

          if self.__cb:
            self.__cb({'pr': 50, 'str': 'Login ok'})

          self.__s.headers.update({'Access-Control-Request-Method': 'POST'})
          self.__s.headers.update({'Access-Control-Request-Headers': 'ssbulsatapi'})

          r = self.__s.options(self.__URL_LIST, timeout=self.__t, headers=self.__UA)

          self.__log_dat(r.request.headers)
          self.__log_dat(r.headers)
          self.__log_dat(str(r.status_code))

          if self.__cb:
            self.__cb({'pr': 70, 'str': 'Fetch data'})

          r = self.__s.post(self.__URL_LIST, timeout=self.__t, headers=self.__UA)

          self.__log_dat(r.request.headers)
          self.__log_dat(r.headers)

          if r.status_code == requests.codes.ok:
            self.__char_set = r.headers['content-type'].split('charset=')[1]
            self.__log_dat('get data ok')
            self.__tv_list = r.json()
            self.__js = {}
            self.__log_dat(self.__js)
            #filepath = 'D:/test3.txt'
            #f_m3u = open(filepath, 'w', encoding="utf-8")
            #f_m3u.write(str(self.__tv_list))
            #f_m3u.close()
            if self.__cb:
              self.__cb({'pr': 90, 'str': 'Fetch data done'})

            if self.__gen_epg:
              for i, ch in enumerate(self.__tv_list):
                if self.__cb:
                  self.__cb(
                              {
                                'pr': int((i * 100) / len(self.__tv_list)),
                                'str': 'Fetch: %s' % ch['epg_name'].encode('utf-8'),
                                'idx': i,
                                'max': len(self.__tv_list)
                              }
                            )
                if ch.__contains__('program'):
                  r = self.__s.post(self.__URL_EPG, timeout=self.__t,
                              headers=self.__UA,
                              data={
                                #'epg': 'nownext',
                                'epg': '1week',
                                #'epg': '1day',
                                'channel': ch['epg_name']
                                }
                            )
                  if r.status_code == requests.codes.ok:
                    ch['program'] = list(r.json().items())[0][1]['programme']

            import html
            self.__js = json.loads(html.unescape(json.dumps(self.__js)))

		  #Disable LogOut for now since the new changes in Fusion platform requires user to be logged in so to can open RTMP streams
          #self.__log_out()
          #if r.status_code != requests.codes.ok:
            #self.__log_dat('Error status code: %d' % (r.status_code, ))
            #raise Exception("FetchFail")

        else:
          raise Exception("LoginFail")

  def __data_fetch(self, f):
    self.__tv_list = None
    if os.path.exists(os.path.join(self.__path, '', 'data.dat')) and f is False:
      self.__restore_data()
      if time.time() - self.__js['ts'] < self.__refresh and self.__js['os_type'] == self.__p_data['os_type'][1]:
        self.__log_dat('Use cache file')
      else:
        self.__log_dat('Use site')
        self.__js = None

    if self.__js is None:
      self.__goforit()
      self.__log_dat('Len: %d' % len(self.__tv_list))
      self.__js['ts'] = divmod(time.time(), self.__refresh)[0] * self.__refresh
      self.__js['app_version'] = self.__app_version
      self.__js['os_type'] = self.__p_data['os_type'][1]
      self.__log_dat('Base time: %s' % time.ctime(self.__js['ts']))
      self.__store_data()

  def gen_all(self, force_refresh = False):
    
    ret = False
    self.__data_fetch(force_refresh)

    if self.__tv_list:
      ret = True
      map = None
      if self.__gen_epg:
        w = xmltv.Writer(encoding=self.__char_set.upper(),
                          date=str(time.time()),
                          source_info_url="",
                          source_info_name="",
                          generator_info_name="",
                          generator_info_url="")
      else:
        if self.__MAP_URL:
          try:
            m = requests.get(self.__MAP_URL, timeout=self.__t, headers={'User-Agent': 'fusion_tv'})
            self.__log_dat(m.request.headers)
            self.__log_dat(m.headers)
            self.__log_dat(m.status_code)
            if m.status_code == requests.codes.ok:
              map = m.json()
              self.__log_dat(map)
          except:
            pass

      pl = u'#EXTM3U\n'
      if self.__gen_jd:
        jdump = {}
      dat = [x for x in self.__tv_list]
      #filepath = 'D:/test1.txt'
      #f_m3u = open(filepath, 'w', encoding="utf-8")
      #f_m3u.write(str(dat))
      #f_m3u.close()
      for i, ch in enumerate(dat):
        if self.__cb:
          self.__cb(
                      {
                        'pr': int((i * 100) / len(dat)),
                        'str': 'Sync: %s' % ch['epg_name'].encode('utf-8'),
                        'idx': i,
                        'max': len(dat)
                      }
                    )

        if  self.__en_group_ch:
          ch_group_name = self.__en_group_ch
        else:
          ch_group_name = ch['genre']

        if self.__x == True or ch_group_name != '18+':
            if self.__gen_m3u:
              if self.__use_rec and ch.__contains__('ndvr'):
                    catchURL = 'catchup="default" catchup-source="' + recURL + ch['ndvr'][ch['ndvr'].index(':',10):] + '&wowzadvrplayliststart={utc:YmdHMS}&wowzadvrplaylistduration={duration}000&request_time=' + str(round(time.time() * 1000)) + 'token=38264607382"'  # !!!!
                    catchURL = catchURL + ',' + ch['title'] + '\n#KODIPROP:inputstream=inputstream.ffmpegdirect\n#KODIPROP:mimetype=application/x-mpegURL\n#KODIPROP:inputstream.ffmpegdirect.stream_mode=timeshift\n#KODIPROP:inputstream.ffmpegdirect.is_realtime_stream=false'
              else:
                    catchURL = ',' + ch['title']

              if ch.__contains__('ndvr'):
                  ch_source = ch['ndvr']
              else:
                  ch_source = ch['sources']

              if self.use_ext_logos:
                  if self.use_local_logos:
                      logoselect = self.logos_local_path + ch['epg_name'] + '.png'
                  else:
                      logoselect = self.logos_path + ch['epg_name'] + '.png'
              else:
                  try:
                      logoselect = ch['logo_selected']
                  except:
                      logoselect = ''

              if self.__use_ua == True:
                  if not map:

                    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s|User-Agent=%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], catchURL, ch_source, urllib.parse.quote_plus(self.__UA['User-Agent']))

                    #if ch.__contains__('pip'):  # LQ
                    #    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s|User-Agent=%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], ',' + ch['title'] + ' LQ', ch['pip'], urllib.parse.quote_plus(self.__UA['User-Agent']))
                  else:
                    e_map = map.get(ch['epg_name'], {ch['epg_name']:{'id': ch['epg_name'], 'offset': '0', 'ch_logo': ch['epg_name']}})
                    gid = e_map.get('id', ch['epg_name'])
                    offset = e_map.get('offset', '0')
                    logo = e_map.get('ch_logo', ch['epg_name'])

                    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s|User-Agent=%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], catchURL, ch_source, urllib.parse.quote_plus(self.__UA['User-Agent']))

                    #if ch.__contains__('pip'):  # LQ
                    #    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s|User-Agent=%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], ',' + ch['title'] + ' LQ', ch['pip'], urllib.parse.quote_plus(self.__UA['User-Agent']))
              else:
                  if not map:

                    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], catchURL, ch_source)

                    #if ch.__contains__('pip'):  # LQ
                    #    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s\n' % (ch['radio'], ch_group_name, logoselect, ch['epg_name'], ',' + ch['title'] + ' LQ', ch['pip'])
                  else:
                    e_map = map.get(ch['epg_name'], {ch['epg_name']:{'id': ch['epg_name'], 'offset': '0', 'ch_logo': ch['epg_name']}})
                    gid = e_map.get('id', ch['epg_name'])
                    offset = e_map.get('offset', '0')
                    logo = e_map.get('ch_logo', ch['epg_name'])

                    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s\n' % (ch['radio'], ch_group_name, ch['logo_favorite'], ch['epg_name'], catchURL, ch_source)

                    #if ch.__contains__('pip'):  # LQ
                    #    pl = pl + '#EXTINF:-1 radio="%s" group-title="%s" tvg-logo="%s" tvg-id="%s" %s\n%s\n' % (ch['radio'], ch_group_name, ch['logo_favorite'], ch['epg_name'], ',' + ch['title'] + ' LQ', ch['pip'])

                    
        if self.__gen_jd:
          jdump[ch['epg_name']]=ch['epg_name']

        if self.__gen_epg:
          w.addChannel(
                      {'display-name': [(ch['title'], u'bg')],
                      'id': ch['epg_name'],
                      'url': ['https://web.iptv.bulsat.com']}
                      )

          if ch.__contains__('program'):
            for p in ch['program']:
              w.addProgramme(
                            {'start': p['start'],
                            'stop': p['stop'],
                            'title': [(p['title'], u'')],
                            'desc': [(p['desc'], u'')],
                            'category': [(ch['genre'], u'')],
                            'channel': ch['epg_name']}
                          )

      if self.__gen_m3u:
        f_m3u =  open(os.path.join(self.__path, '', 'bulsat.m3u'), 'wb+')
        f_m3u.write(pl.encode(self.__char_set, 'replace'))
        f_m3u.close()
        if self.__gen_jd:
          with open(os.path.join(self.__path, '', 'map.json'), 'wb+') as f:
            f.write(json.dumps(jdump,
                        sort_keys = True,
                        indent = 1,
                        ensure_ascii=False))

      if self.__gen_epg:
        if self.__compress:
          out = io.BytesIO()

          w.write(out, pretty_print=True)
          f_lmx = gzip.open(os.path.join(self.__path, '', 'bulsat.xml.gz'), 'w+', 9)
          f_lmx.write(out.getvalue())
          f_lmx.close()
          out.close()
        else:
          out = open(os.path.join(self.__path, '', 'bulsat.xml'), 'wb+')
          w.write(out, pretty_print=True)
          out.close()

    return ret
