"""
BOT SERVER - MULTI ADM + MULTI CLIENTES
Le do banco:
- ADM: config_geral admin_origens / admin_destinos
- CLIENTES: clientes_config (cliente_id, origens, destinos) OU clientes (origens, destinos)
Cada origem copia para TODOS os destinos daquela pessoa. Pula se origem == destino.
"""
import os, json
import pymysql
from telethon import TelegramClient, events
from telethon.sessions import StringSession

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
    regras = []  # lista de (dono, origem, destino)
    try:
        conn = pymysql.connect(host=DB_HOST,user=DB_USER,password=DB_PASS,database=DB_NAME,charset='utf8mb4',connect_timeout=10)
        cur = conn.cursor()
        # ADM
        try:
            cur.execute("SELECT admin_origens, admin_destinos FROM config_geral WHERE id=1 LIMIT 1")
            r = cur.fetchone()
            if r:
                for o in split_lista(r[0]):
                    for d in split_lista(r[1]):
                        if o.lower()!=d.lower(): regras.append(('ADM',o,d))
                print(f"ADM: {split_lista(r[0])} x {split_lista(r[1])}")
        except Exception as e: print(f"ADM erro: {e}")
        # CLIENTES - tenta clientes_config primeiro, depois clientes
        try:
            cur.execute("SELECT cliente_id, origens, destinos FROM clientes_config")
            for cid,o,d in cur.fetchall():
                # so clientes ativos/teste - verifica status na tabela clientes
                for oo in split_lista(o):
                    for dd in split_lista(d):
                        if oo.lower()!=dd.lower(): regras.append((f"CLI:{cid}",oo,dd))
            print(f"clientes_config: {len(regras)} regras totais")
        except Exception as e:
            print(f"clientes_config nao existe ({e}), tentando clientes.origens")
            try:
                cur.execute("SELECT id, origens, destinos, status FROM clientes")
                for cid,o,d,st in cur.fetchall():
                    if str(st).lower() in ('pausado','bloqueado','vencido'): continue
                    for oo in split_lista(o):
                        for dd in split_lista(d):
                            if oo.lower()!=dd.lower(): regras.append((f"CLI:{cid}",oo,dd))
            except Exception as e2: print(f"clientes.origens erro: {e2}")
        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ Erro DB: {e}")
    print(f"📋 TOTAL: {len(regras)} regras")
    for dono,o,d in regras: print(f"  {dono}: @{o} -> @{d}")
    return regras

REGRAS = buscar_tudo()
ORIGENS = sorted(list(set([o for _,o,_ in REGRAS])))
DESTINOS_POR_ORIGEM = {}
for dono,o,d in REGRAS:
    DESTINOS_POR_ORIGEM.setdefault(o.lower(), []).append(d)
if not ORIGENS: ORIGENS=['teamlive21']

ARQ='mapa_multi.json'
try:
    with open(ARQ,'r',encoding='utf-8') as f: mapa=json.load(f)
except: mapa={}
def salvar_mapa():
    try:
        with open(ARQ,'w',encoding='utf-8') as f: json.dump(mapa,f)
    except: pass

client = TelegramClient(StringSession(SESSION_STRING),API_ID,API_HASH) if SESSION_STRING else TelegramClient('sessao_live21',API_ID,API_HASH)

@client.on(events.NewMessage(chats=ORIGENS))
async def nova(event):
    if getattr(event,'out',False): return
    msg=event.message
    if getattr(msg,'sticker',None): return
    try:
        ent=await event.get_chat()
        origem=limpar(getattr(ent,'username',None) or '')
    except: origem=''
    if not origem: return
    texto=msg.text or ""
    for dest in DESTINOS_POR_ORIGEM.get(origem.lower(),[]):
        try:
            if getattr(msg,'media',None):
                enviada=await client.send_file(dest,msg.media,caption=texto if texto else None)
            else:
                if not texto: continue
                enviada=await client.send_message(dest,texto)
            eid=enviada[0].id if isinstance(enviada,list) else enviada.id
            mapa[f"{origem}:{msg.id}:{dest}"]=eid
            print(f"✅ @{origem} -> @{dest} (id {eid})")
        except Exception as e: print(f"❌ @{origem} -> @{dest}: {e}")
    salvar_mapa()

@client.on(events.MessageEdited(chats=ORIGENS))
async def editada(event):
    msg=event.message
    if getattr(event,'out',False): return
    try:
        ent=await event.get_chat(); origem=limpar(getattr(ent,'username',None) or '')
    except: origem=''
    for dest in DESTINOS_POR_ORIGEM.get(origem.lower(),[]):
        chave=f"{origem}:{msg.id}:{dest}"; id_dest=mapa.get(chave)
        if not id_dest: continue
        try: await client.edit_message(dest,id_dest,msg.text or ""); print(f"✏️ Editado @{dest}")
        except Exception as e: print(f"❌ Editar @{dest}: {e}")

@client.on(events.MessageDeleted(chats=ORIGENS))
async def apagada(event):
    for id_origem in event.deleted_ids:
        for chave in [k for k in list(mapa.keys()) if k.split(':')[1]==str(id_origem)]:
            dest=chave.split(':')[2]
            try: await client.delete_messages(dest,mapa[chave]); print(f"🗑️ Apagado @{dest}"); del mapa[chave]
            except Exception as e: print(f"❌ Apagar @{dest}: {e}")
        salvar_mapa()

print("🚀 BOT MULTI ADM + CLIENTES ligado!")
print(f"👀 Ouvindo: {ORIGENS}")
print(f"📤 Regras: {len(REGRAS)}")
print("Aguardando...")
client.start()
client.run_until_disconnected()
