"""
BOT SERVER - Live21 MULTI ORIGEM x MULTI DESTINO
Le do painel: config_geral admin_origens / admin_destinos
Ex: admin_origens = teamlive21,Live21streaming
    admin_destinos = Live21streaming,Lv21GrupoAberto
Regra: toda origem copia para TODOS os destinos, menos se origem == destino
"""
import os, json, asyncio
import pymysql
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv('API_ID', '0') or 0)
API_HASH = os.getenv('API_HASH', '')
SESSION_STRING = os.getenv('SESSION_STRING', '')

DB_HOST = os.getenv('DB_HOST', 'srv1524.hstgr.io')
DB_USER = os.getenv('DB_USER', 'u574433089_bot_serv')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'u574433089_bot_serv')

def limpar(nome):
    if not nome: return ''
    nome = str(nome).strip().replace('@','').replace('https://t.me/','').replace('t.me/','').strip('/').strip()
    return nome

def buscar_regras():
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT admin_origens, admin_destinos FROM config_geral WHERE id=1 LIMIT 1")
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            print("⚠️ config_geral vazio")
            return [], []
        origens = [limpar(x) for x in str(row[0] or '').split(',') if limpar(x)]
        destinos = [limpar(x) for x in str(row[1] or '').split(',') if limpar(x)]
        print(f"📋 PAINEL: {len(origens)} origens {origens} x {len(destinos)} destinos {destinos}")
        return origens, destinos
    except Exception as e:
        print(f"❌ Erro DB: {e}")
        # fallback pelas variaveis do Railway se o banco falhar
        o = [limpar(x) for x in os.getenv('ADMIN_ORIGENS','teamlive21').split(',') if limpar(x)]
        d = [limpar(x) for x in os.getenv('ADMIN_DESTINOS','Live21streaming').split(',') if limpar(x)]
        return o, d

ORIGENS, DESTINOS = buscar_regras()
if not ORIGENS: ORIGENS = ['teamlive21']
if not DESTINOS: DESTINOS = ['Live21streaming']

# mapa: "origem_id:destino" -> id destino. Salva em arquivo
ARQ = 'mapa_multi.json'
try:
    with open(ARQ,'r',encoding='utf-8') as f: mapa = json.load(f)
except: mapa = {}
def salvar_mapa():
    try:
        with open(ARQ,'w',encoding='utf-8') as f: json.dump(mapa,f)
    except Exception as e: print(f"Erro salvar mapa: {e}")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) if SESSION_STRING else TelegramClient('sessao_live21', API_ID, API_HASH)

async def copiar_para_todos(event, texto_base, media=None):
    msg = event.message
    origem_atual = limpar(getattr(event.chat,'username',None) or '')
    # se nao tem username, descobre pelo chat_id comparando? usa o chat title - fallback: tenta por id
    # Melhor: identifica origem pelo event.chat_id e resolve depois; aqui usamos o nome do chat
    # Para garantir, pegamos a entidade
    try:
        ent = await event.get_chat()
        origem_atual = limpar(getattr(ent,'username',None) or origem_atual)
    except: pass
    print(f"📩 Nova em @{origem_atual} id={msg.id} texto={ (texto_base or '')[:60]}")
    for dest in DESTINOS:
        if dest.lower() == origem_atual.lower():
            print(f"⏭️ Pula {dest} porque é igual a origem")
            continue
        try:
            if media:
                enviada = await client.send_file(dest, media, caption=texto_base)
            else:
                if not texto_base: continue
                enviada = await client.send_message(dest, texto_base)
            eid = enviada[0].id if isinstance(enviada, list) else enviada.id
            chave = f"{origem_atual}:{msg.id}:{dest}"
            mapa[chave] = eid
            print(f"✅ @{origem_atual} -> @{dest} (dest id {eid})")
        except Exception as e:
            print(f"❌ Erro @{origem_atual} -> @{dest}: {e}")
    salvar_mapa()

@client.on(events.NewMessage(chats=ORIGENS))
async def nova(event):
    if getattr(event,'out',False): return
    msg = event.message
    if getattr(msg,'sticker',None): return
    texto = msg.text or ""
    # sem assinatura verde fixa, copia limpo como voce pediu
    await copiar_para_todos(event, texto, media=msg.media if getattr(msg,'media',None) else None)

@client.on(events.MessageEdited(chats=ORIGENS))
async def editada(event):
    msg = event.message
    if getattr(event,'out',False): return
    try:
        ent = await event.get_chat()
        origem_atual = limpar(getattr(ent,'username',None) or '')
    except: origem_atual = ''
    texto = msg.text or ""
    for dest in DESTINOS:
        if dest.lower() == origem_atual.lower(): continue
        chave = f"{origem_atual}:{msg.id}:{dest}"
        id_dest = mapa.get(chave)
        if not id_dest: continue
        try:
            await client.edit_message(dest, id_dest, texto)
            print(f"✏️ Editado @{dest} id {id_dest}")
        except Exception as e:
            print(f"❌ Erro editar @{dest}: {e}")

@client.on(events.MessageDeleted(chats=ORIGENS))
async def apagada(event):
    # deleted_ids vem sem saber a origem, entao apaga em todos os destinos que tem esse id de origem
    for id_origem in event.deleted_ids:
        chaves = [k for k in list(mapa.keys()) if k.split(':')[1] == str(id_origem)]
        for chave in chaves:
            dest = chave.split(':')[2]
            id_dest = mapa.get(chave)
            try:
                await client.delete_messages(dest, id_dest)
                print(f"🗑️ Apagado @{dest} id {id_dest}")
                del mapa[chave]
            except Exception as e:
                print(f"❌ Erro apagar @{dest}: {e}")
        salvar_mapa()

print("🚀 BOT MULTI ligado!")
print(f"👀 Ouvindo: {ORIGENS}")
print(f"📤 Enviando para: {DESTINOS}")
print("Aguardando...")
client.start()
client.run_until_disconnected()
