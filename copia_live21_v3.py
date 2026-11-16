"""
BOT SERVER - MULTI TOKEN - ADM com SESSION + CLIENTES com BOT TOKEN
ADM: usa SESSION_STRING (sua conta) - le config_geral
CLIENTES: usam Token do @BotFather - le clientes_config (cliente_id, origens, destinos, token)
Cada cliente tem seu proprio bot. Sem API_ID, sem Colab.
"""
import os, json, asyncio
import pymysql
from telethon import TelegramClient, events

API_ID = int(os.getenv('API_ID','0') or 0)
API_HASH = os.getenv('API_HASH','')
SESSION_STRING = os.getenv('SESSION_STRING','')
DB_HOST = os.getenv('DB_HOST','srv1524.hstgr.io')
DB_USER = os.getenv('DB_USER','u574433089_bot_serv')
DB_PASS = os.getenv('DB_PASS','')
DB_NAME = os.getenv('DB_NAME','u574433089_bot_serv')

def limpar(n):
    if not n: return ''
    return str(n).strip().replace('@','').replace('https://t.me/','').replace('t.me/','').strip('/').strip()
def split_lista(s):
    return [limpar(x) for x in str(s or '').replace(';',',').split(',') if limpar(x)]

def buscar_tudo():
    adm_o, adm_d, clientes = [], [], []
    try:
        conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,database=DB_NAME,charset='utf8mb4',connect_timeout=10)
        cur = conn.cursor()
        try:
            cur.execute("SELECT admin_origens, admin_destinos FROM config_geral WHERE id=1 LIMIT 1")
            r=cur.fetchone()
            if r: adm_o, adm_d = split_lista(r[0]), split_lista(r[1])
        except Exception as e: print(f"ADM erro: {e}")
        try:
            cur.execute("SELECT cliente_id, origens, destinos, token FROM clientes_config")
            for cid,o,d,tok in cur.fetchall():
                if tok and tok.strip():
                    clientes.append({'id':cid,'origens':split_lista(o),'destinos':split_lista(d),'token':tok.strip()})
        except Exception as e: print(f"clientes erro: {e}")
        cur.close(); conn.close()
    except Exception as e: print(f"DB erro: {e}")
    print(f"ADM: {adm_o} x {adm_d}")
    print(f"CLIENTES com Token: {len(clientes)}")
    return adm_o, adm_d, clientes

async def roda_bot_adm(origens, destinos):
    if not origens or not SESSION_STRING: return
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    mapa={}
    try:
        with open('mapa_adm.json','r',encoding='utf-8') as f: mapa=json.load(f)
    except: pass
    def salvar():
        try:
            with open('mapa_adm.json','w',encoding='utf-8') as f: json.dump(mapa,f)
        except: pass
    @client.on(events.NewMessage(chats=origens))
    async def nova(event):
        try: ent=await event.get_chat(); origem=limpar(getattr(ent,'username',None) or '')
        except: origem=''
        for dest in destinos:
            if dest.lower()==origem.lower(): continue
            try:
                msg=event.message
                if getattr(msg,'media',None):
                    env=await client.send_file(dest, msg.media, caption=msg.text or None)
                else:
                    if not msg.text: continue
                    env=await client.send_message(dest, msg.text)
                eid=env[0].id if isinstance(env,list) else env.id
                mapa[f"{origem}:{msg.id}:{dest}"]=eid
                print(f"✅ ADM @{origem} -> @{dest}")
            except Exception as e: print(f"❌ ADM @{origem} -> @{dest}: {e}")
        salvar()
    print(f"🚀 ADM ligado ouvindo {origens}")
    await client.start()
    await client.run_until_disconnected()

async def roda_bot_cliente(cli):
    # Bot do cliente usa Token, nao precisa API_ID/HASH do cliente
    client = TelegramClient(f"bot_{cli['id']}", API_ID, API_HASH)
    await client.start(bot_token=cli['token'])
    print(f"🤖 Cliente {cli['id']} ligado: {cli['origens']} -> {cli['destinos']}")
    @client.on(events.NewMessage(chats=cli['origens']))
    async def nova(event):
        try: ent=await event.get_chat(); origem=limpar(getattr(ent,'username',None) or '')
        except: origem=''
        for dest in cli['destinos']:
            if dest.lower()==origem.lower(): continue
            try:
                msg=event.message
                if getattr(msg,'media',None):
                    await client.send_file(dest, msg.media, caption=msg.text or None)
                else:
                    if not msg.text: continue
                    await client.send_message(dest, msg.text)
                print(f"✅ CLI {cli['id']} @{origem} -> @{dest}")
            except Exception as e: print(f"❌ CLI {cli['id']} @{origem} -> @{dest}: {e}")
    await client.run_until_disconnected()

async def main():
    adm_o, adm_d, clientes = buscar_tudo()
    tarefas=[]
    if adm_o: tarefas.append(roda_bot_adm(adm_o, adm_d))
    for cli in clientes: tarefas.append(roda_bot_cliente(cli))
    if not tarefas:
        print("Nenhum bot para ligar. ADM sem origens ou nenhum cliente com Token.")
        return
    await asyncio.gather(*tarefas)

print("🚀 BOT SERVER MULTI TOKEN ligado!")
asyncio.run(main())
