# -*- coding: utf-8 -*-
import os
import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
import re
import simplejson as json
import urllib
import platform
import requests

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString
__icon__ = __addon__.getAddonInfo('icon')
__cwd__ = xbmcvfs.translatePath( __addon__.getAddonInfo('path') )
__profile__ = xbmcvfs.translatePath( __addon__.getAddonInfo('profile') )
__resource__ = xbmcvfs.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) )
__icon_msg__ = xbmcvfs.translatePath( os.path.join( __cwd__, 'resources', 'bulsat.png' ) )
__data__ = xbmcvfs.translatePath(os.path.join( __profile__, '', 'dat') )
__r_path__ = xbmcvfs.translatePath(__addon__.getSetting('w_path'))

sys.path.insert(0, __resource__)  

dp = xbmcgui.DialogProgressBG()
dp.create(heading = __scriptname__)
from xmltv import xmbs

def progress_cb (a):
  _str = __scriptname__
  if a.__contains__('idx') and a.__contains__('max'):
    _str += ' %s of %d' % (a['idx'], a['max'])

  dp.update(a['pr'], _str  , a['str'])

def Notify (msg1, msg2):
    xbmc.executebuiltin((u'Notification(%s,%s,%s,%s)' % (msg1, msg2, '5000', __icon_msg__)))

def check_plg():
  js_resp = xbmc.executeJSONRPC('{"jsonrpc":"2.0","method":"Addons.GetAddons", "id":1}')
  if int(xbmc.getInfoLabel("System.BuildVersion" )[0:2]) > 14: ln = 1
  else: ln = 2

  if len(re.findall(r'bscf', js_resp)) > ln:
    Notify ('%s %s' % (__scriptname__, __version__) , '[COLOR FFFF0000]confilct ![/COLOR]')
    return False
  else:
    return True

def update(name, dat, crash=None):
  payload = {}
  payload['an'] = __scriptname__
  payload['av'] = __version__
  payload['ec'] = name
  payload['ea'] = 'tv_service'
  payload['ev'] = '1'
  payload['dl'] = urllib.parse.quote_plus(dat.encode('utf-8'))

__ua_os = {
  #'0' : {'ua' : 'pcweb', 'osid' : 'androidtv'},     #{'ua' : 'pcweb', 'osid' : 'pcweb'}
  '0' : {'ua' : 'Mozilla/5.0 (SMART-TV; Linux; Tizen 2.3) AppleWebkit/538.1 (KHTML, like Gecko) SamsungBrowser/1.0 TV Safari/538.1', 'osid' : 'samsungtv'},
  '1' : {'ua' : 'okhttp/3.12.12', 'osid' : 'androidtv'},
}

if __addon__.getSetting('en_reload_pvr')== 'true':
    if int(xbmc.getInfoLabel("System.BuildVersion" )[0:2]) < 17:
      xbmc.executebuiltin('XBMC.StopPVRManager')
    else:
      xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Addons.SetAddonEnabled", "params":{ "addonid": "pvr.iptvsimple", "enabled": false }, "id":1}')

if os.path.exists(os.path.join(__data__, '', 'data.dat')):
  with open(os.path.join(__data__, '', 'data.dat'), 'r') as f:
    js = json.load(f)

  #if not (js.__contains__('app_version') and js['app_version'] == __version__):
  if not js.__contains__('app_version'):
    u = __addon__.getSetting('username')
    p = __addon__.getSetting('password')

    for root, dirs, files in os.walk(__data__, topdown=False):
      for name in files:
        os.remove(os.path.join(root, name))
      for name in dirs:
        os.rmdir(os.path.join(root, name))
    __addon__.setSetting('firstrun', 'true')


if __addon__.getSetting('firstrun') == 'true':
  Notify('Settings', 'empty')
  __addon__.openSettings()
  __addon__.setSetting('firstrun', 'false')

if __addon__.getSetting('use_ua_new') == 'true':
  use_ua = True
else:
  use_ua = False

if __addon__.getSetting('dbg') == 'true':
  dbg = True
else:
  dbg = False
  
if __addon__.getSetting('use_rec_new') == 'true':
  use_rec = True
  temp_osid = '1'
else:
  use_rec = False
  temp_osid = __addon__.getSetting('dev_id_new1')

if __addon__.getSetting('xxx') == 'true':
  xxx = True
else:
  xxx = False

if __addon__.getSetting('en_group_ch') == 'true':
  _group_name = False
else:
  _group_name = __scriptid__

if __addon__.getSetting('ext_epg') == 'true':
  etx_epg = True
  map_url = __addon__.getSetting('map_dat')
else:
  etx_epg = False
  map_url = None

if __addon__.getSetting('use_ext_logos') == 'true':
  use_ext_logos = True
else:
  use_ext_logos = False

if __addon__.getSetting('logos_path') == '':
  logos_path = ''
else:
  logos_path = __addon__.getSetting('logos_path')

if __addon__.getSetting('use_local_logos') == 'true':
  use_local_logos = True
else:
  use_local_logos = False

if __addon__.getSetting('logos_local_path') == '':
  logos_local_path = ''
else:
  logos_local_path = __addon__.getSetting('logos_local_path')

usern = ''
passn = ''
if __addon__.getSetting('logontype') == 'true':
    if not __addon__.getSetting('username'):
        Notify('User', 'empty')
    else:
        usern = __addon__.getSetting('username')
    if not __addon__.getSetting('password'):
        Notify('Password', 'empty')
    else:
        passn = __addon__.getSetting('password')
else:
    if not __addon__.getSetting('urllogin'):
        Notify('URL address', 'empty')
    else:
        logon_url = __addon__.getSetting('urllogin')
        if logon_url[-1] != '/':
            logon_url = logon_url + '/'
        else:
            pass
        logon_url = logon_url + 'bulsatlogin.txt'
        r_user = requests.get(logon_url)
        matchuser = re.search('user":"(.+?)"', r_user.text)
        if matchuser:
            usern = matchuser.group(1)
        else:
            Notify('User', 'empty')
        matchpass = re.search('pass":"(.+?)"', r_user.text)
        if matchpass:
            passn = matchpass.group(1)
        else:
            Notify('Password', 'empty')
  
nrepeats = __addon__.getSetting('repeats')
nrepeats = float(nrepeats)
nrepeats = int(nrepeats)
checkFail = 0

def dbg_msg(msg):
  if dbg:
    print ('### %s: %s' % (__scriptid__, msg))

import traceback
if __addon__.getSetting('chsen') == 'false':
    __addon__.setSetting('chsen', 'true')
    try:
        xmbs(usern, passn)
    except:
        pass

for x in range(nrepeats):
  try:
    import bsc

    b = bsc.dodat(base = __addon__.getSetting('base'),
                  login = {'usr': usern,
                          'pass': passn
                          },
                  path = __data__,
                  cachetime = float(__addon__.getSetting('refresh_new')),
                  dbg = dbg,
                  timeout=float(__addon__.getSetting('timeout')),
                  ver = __version__,
                  xxx = xxx,
                  use_ua = use_ua,
                  use_rec = use_rec,
                  os_id = __ua_os[temp_osid]['osid'],
                  agent_id = __ua_os[temp_osid]['ua'],
                  app_ver = __addon__.getSetting('app_ver'),
                  force_group_name = _group_name,
                  gen_m3u = True,
                  gen_epg = not etx_epg,
                  compress = True,
                  map_url = map_url,
                  proc_cb = progress_cb,
                  use_ext_logos = use_ext_logos,
                  logos_path = logos_path,
                  use_local_logos = use_local_logos,
                  logos_local_path = logos_local_path)
  
    if check_plg(): 
      force = True
      if len(sys.argv) > 1 and sys.argv[1] == 'False':
        force = False
        dbg_msg('Reload timer')
        #update('reload_timer',  __addon__.getSetting('check_interval'))
        update('reload_timer', __addon__.getSetting('refresh_new'))
        #xbmc.executebuiltin('AlarmClock (%s, RunScript(plugin.program.bscfusion, False), %s, silent)' % (__scriptid__, __addon__.getSetting('check_interval')))
        xbmc.executebuiltin('AlarmClock (%s, RunScript(plugin.program.bscfusion, False), %s, silent)' % (__scriptid__, __addon__.getSetting('refresh_new')))
          
      if b.gen_all(force):
        if __addon__.getSetting('en_cp') == 'true' and __addon__.getSetting('w_path') != '' and xbmcvfs.exists(__r_path__):
          if os.path.isfile(os.path.join(__data__, '', 'bulsat.xml.gz')):
            xbmcvfs.copy(os.path.join(__data__, '', 'bulsat.xml.gz'), os.path.join(__r_path__, '', 'bulsat.xml.gz'))
          if os.path.isfile(os.path.join(__data__, '', 'bulsat.m3u')):
            xbmcvfs.copy(os.path.join(__data__, '', 'bulsat.m3u'), os.path.join(__r_path__, '', 'bulsat.m3u'))
          dbg_msg('Copy Files')
  
        if __addon__.getSetting('en_custom_cmd') == 'true':
          __builtin = __addon__.getSetting('builtin_cmd')
          __script = __addon__.getSetting('script_cmd')
  
          if __builtin != '':
            dbg_msg ('builtin exec %s' % __builtin)
            update('builtin_exec %s' % __builtin, __ua_os[__addon__.getSetting('dev_id_new1')]['osid'])
            xbmc.executebuiltin('%s' % __builtin)
  
          if __script != '':
            dbg_msg ('script exec %s' % __script)
            update('script_exec %s' % __script, __ua_os[__addon__.getSetting('dev_id_new1')]['osid'])
            os.system(__script)
    checkFail = 0
    break
  
  except Exception as e:
    checkFail = 1
    traceback.print_exc()
    errMsg = str(e.args[0])

    pass
    
if checkFail == 1:
    Notify('Module Import', 'Fail')
    update('exception', errMsg, sys.exc_info())

dp.close()

if __addon__.getSetting('en_reload_pvr')== 'true':
  if int(xbmc.getInfoLabel("System.BuildVersion" )[0:2]) < 17:
    xbmc.executebuiltin('XBMC.StartPVRManager')
  else:
    xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Addons.SetAddonEnabled", "params":{ "addonid": "pvr.iptvsimple", "enabled": true }, "id":1}')
