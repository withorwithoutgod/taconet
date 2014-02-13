import taco.bottle as bottle
import taco.settings
import taco.globals
import taco.constants
import taco.filesystem
import taco.commands
import urllib
import re,time
import os,uuid
import logging
import json

#static content
@bottle.route('/static/<filename:path>')
def send_file(filename):
  return bottle.static_file(filename, root=os.path.normpath(os.getcwd() + '/static/'))

#terminate taconet
@bottle.route('/shutitdown')
def taco_page():
  taco.globals.properexit(1,1)
  return

#template routes
@bottle.route('/')
def index():
  return bottle.template('templates/home.tpl')

@bottle.route('/<name>.taco')
def taco_page(name):
  return bottle.template('templates/'+str(name)+'.tpl')


@bottle.post('/api.post')
def index():
  try:
    api_call = bottle.request.json
  except:
    return "0"
  if not bottle.request.json.has_key("action"): return "0"
  if not bottle.request.json.has_key("data"): return "0"

  if bottle.request.json[u"action"] == u"threadstatus":
    output = {}
    output["threads"] = {}
    output["threads"]["clients"] = {}
    output["threads"]["server"] = {}

    output["threads"]["clients"]["alive"] = taco.globals.clients.is_alive()
    (output["threads"]["clients"]["status"],output["threads"]["clients"]["lastupdate"]) = taco.globals.clients.get_status()
    output["threads"]["clients"]["lastupdate"] = abs(time.time() - float(output["threads"]["clients"]["lastupdate"]))

    output["threads"]["server"]["alive"] = taco.globals.server.is_alive()
    (output["threads"]["server"]["status"],output["threads"]["server"]["lastupdate"]) = taco.globals.server.get_status()
    output["threads"]["server"]["lastupdate"] = abs(time.time() - float(output["threads"]["server"]["lastupdate"]))

    return json.dumps(output)

  if bottle.request.json[u"action"] == u"peerstatus":
    output = {}
    with taco.globals.settings_lock:
      for peer_uuid in taco.globals.settings["Peers"].keys():
        if taco.globals.settings["Peers"][peer_uuid]["enabled"]:
          incoming = taco.globals.server.get_client_last_request(peer_uuid)
          outgoing = taco.globals.clients.get_client_last_reply(peer_uuid)
          timediffinc = abs(time.time()-incoming)
          timediffout = abs(time.time()-outgoing)
          output[peer_uuid] = [incoming,outgoing,timediffinc,timediffout,taco.globals.settings["Peers"][peer_uuid]["nickname"],taco.globals.settings["Peers"][peer_uuid]["localnick"]]
    return json.dumps(output)

  if bottle.request.json[u"action"] == u"settingssave":
    if type(bottle.request.json[u"data"]) == type([]):
      if len(bottle.request.json[u"data"]) >= 0:
        with taco.globals.settings_lock:
          logging.info("API Access: SETTINGS -- Action: SAVE")
          for (keyname,value) in bottle.request.json[u"data"]:
            taco.globals.settings[keyname] = value
          taco.settings.Save_Settings(False)
          return "1"

  if bottle.request.json[u"action"] == u"sharesave":
    if type(bottle.request.json[u"data"]) == type([]):
      if len(bottle.request.json[u"data"]) >= 0:
        with taco.globals.settings_lock:
          logging.info("API Access: SHARE -- Action: SAVE")
          taco.globals.settings["Shares"] = []
          for (sharename,sharelocation) in bottle.request.json[u"data"]:
            taco.globals.settings["Shares"].append([sharename,sharelocation])
          taco.settings.Save_Settings(False)
          return "1"

  if bottle.request.json[u"action"] == u"getchat":
    output_chat = []
    with taco.globals.settings_lock:
      localuuid  = taco.globals.settings["Local UUID"]
      with taco.globals.chat_log_lock:
        for [puuid,thetime,msg] in taco.globals.chat_log:
          if taco.globals.settings["Peers"].has_key(puuid) and taco.globals.settings["Peers"][puuid].has_key("nickname"):
            nickname = taco.globals.settings["Peers"][puuid]["nickname"]
          elif taco.globals.settings["Local UUID"] == puuid:
            nickname = taco.globals.settings["Nickname"]
          else:
            nickname = puuid
          if puuid==localuuid: 
            output_chat.append([0,nickname,puuid,thetime,msg])
          else:
            output_chat.append([1,nickname,puuid,thetime,msg])
    return json.dumps(output_chat)

  if bottle.request.json[u"action"] == u"sendchat":
    if type(bottle.request.json[u"data"]) == type(u""):
      if len(bottle.request.json[u"data"]) > 0:
        taco.commands.Request_Chat(bottle.request.json[u"data"])
        return "1"
  
  if bottle.request.json[u"action"] == u"chatuuid":
    with taco.globals.chat_uuid_lock:
      return json.dumps([taco.globals.chat_uuid])
   
  if bottle.request.json[u"action"] == u"peersave":
    if type(bottle.request.json[u"data"]) == type([]):
      if len(bottle.request.json[u"data"]) >= 0:
        with taco.globals.settings_lock:
          logging.info("API Access: PEER -- Action: SAVE")
          taco.globals.settings["Peers"] = {}
          for (hostname,port,localnick,peeruuid,clientpub,serverpub,dynamic,enabled) in bottle.request.json[u"data"]:
            taco.globals.settings["Peers"][unicode(peeruuid)] = {"hostname":hostname,"port": int(port),"localnick":localnick,"dynamic":int(dynamic),"enabled":int(enabled),"clientkey":clientpub,"serverkey":serverpub}
          taco.settings.Save_Settings(False)
        taco.globals.server.stop_running()
        taco.globals.clients.stop_running()
        taco.globals.server.join()
        taco.globals.clients.join()
        taco.globals.server = taco.server.TacoServer()
        taco.globals.clients = taco.clients.TacoClients()
        taco.globals.server.start()
        taco.globals.clients.start()
        return "1"



  return "-1"

@bottle.route('/browselocaldirs/')
@bottle.route('/browselocaldirs/<browse_path:path>')
def index(browse_path="/"):
  if browse_path=="": browse_path ="/"
  browse_path = "/" + browse_path
  browse_path = unicode(browse_path)
  contents = os.listdir(browse_path)
  final_contents = []
  for item in contents:
    if os.path.isdir(os.path.join(browse_path,item)):
      final_contents.append(item)
  final_contents.sort()
  return json.dumps(final_contents)
      
  

@bottle.route('/get/<what>')
def getData(what):
  output = ""
  logging.debug("Route -- Getting your: " + what)
  if what=="uuid":
    return str(uuid.uuid4())
  if what=="ip":
    data = urllib.urlopen("http://checkip.dyndns.org/").read()
    m = re.match(r'.*Current IP Address: (.*)</body>',data)
    if m:
      output = m.group(1)
  if what =="diskfree":
    with taco.globals.settings_lock:
      down_dir = taco.globals.settings["Download Location"]
    if os.path.isdir(down_dir):
      (free,total) = taco.filesystem.Get_Free_Space(down_dir)
      if free == 0 and total == 0:
        output = 0.0
      else:
        output = free/taco.constants.GB
  return str(output)
