"""
Live21 BOT - LIGADO NO PAINEL NOVO botserv.pro
- Le clientes do MySQL (tabela clientes)
- So copia se status = Ativo ou Teste e dentro do vencimento / trial
- Bloqueado / Vencido / Pendente = NAO copia
- Origens/destinos vem do painel, nao fixo no codigo
- ADM tambem e filho de Deus: 5 origens + 5 destinos do ADM
- Mantem fallback: se o banco falhar, copia @teamlive21 -> @Live21streaming
- Foto como foto, album junto, edicao e exclusao sincronizadas
"""
import os, json, asyncio, io
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv('API_ID','0') or '0')
API_HASH = os.getenv('API_HASH','')
SESSION_STRING = os.getenv('SESSION_STRING','')

DB_HOST = os.getenv('DB_HOST','')
DB_USER = os.getenv('DB_USER','')
DB_PASS = os.getenv('DB_PASS','')
DB_NAME = os.getenv('DB_NAME','u574433089_bot_serv')

# Fallback Live21 (se banco nao responder)
FALLBACK = [('@teamlive21','@Live21streaming')]

mapa = {}
try:
    import pymysql
    HAS_MYSQL = True
except:
    HAS_MYSQL = False
    print('Aviso: pymysql nao instalado, usando fallback Live21', flush=True)

def limpar(v):
    v=(v or '').strip().replace('https://t.me/','').replace('http://t.me/','').replace('t.me/','').replace('@','')
    return v.split('/')[0].strip()

def hoje():
    from datetime import date
    return date.today().isoformat()

def buscar_regras():
    """Le painel novo. Retorna lista [(origem, destino)]"""
    if not HAS_MYSQL or not DB_HOST or not DB_USER:
        print('Banco nao configurado, usando fallback Live21', flush=True)
        return FALLBACK
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4', connect_timeout=8)
        cur = conn.cursor()
        cur.execute("SHOW COLUMNS FROM clientes")
        cols = [c[0] for c in cur.fetchall()]
        cur.execute("SELECT * FROM clientes")
        rows = cur.fetchall()
        regras=[]
        h=hoje()
        for r in rows:
            d=dict(zip(cols, r))
            status=(str(d.get('status') or '')).strip()
            if status in ('Bloqueado','Vencido','Pendente','Inativo','Pausado'):
                continue
            venc=str(d.get('venc') or d.get('vencimento') or d.get('data_vencimento') or '')
            trial=str(d.get('trialFim') or d.get('trial_fim') or d.get('fim_teste') or '')
            if status=='Teste' and trial and trial < h:
                continue
            if status=='Ativo' and venc and venc < h:
                continue
            origens=[]
            destinos=[]
            for k,v in d.items():
                if not v: continue
                kl=k.lower()
                if 'origem' in kl:
                    origens.append(limpar(str(v)))
                if 'destino' in kl:
                    destinos.append(limpar(str(v)))
            for k in ('origens','destinos','origem','destino'):
                if k in d and d[k]:
                    vals=[limpar(x) for x in str(d[k]).split(',') if limpar(x)]
                    if k.startswith('orig'): origens.extend(vals)
                    else: destinos.extend(vals)
            origens=[x for x in dict.fromkeys(origens) if x]
            destinos=[x for x in dict.fromkeys(destinos) if x]
            for o in origens:
                for dest in destinos:
                    regras.append((o, dest))
        # ADM tambem e filho de Deus: 5 origens + 5 destinos do ADM - JA COLOCADO NO LUGAR CERTO
        try:
            cur.execute("SELECT admin_origens, admin_destinos FROM config_geral WHERE id=1 LIMIT 1")
            row=cur.fetchone()
            if row:
                ao=[limpar(x) for x in str(row[0] or '').split(',') if limpar(x)]
                ad=[limpar(x) for x in str(row[1] or '').split(',') if limpar(x)]
                for o in ao:
                    for dest in ad:
                        regras.append((o, dest))
                if ao and ad:
                    print(f'ADM: {len(ao)} origens x {len(ad)} destinos = {len(ao)*len(ad)} regras', flush=True)
        except Exception as e:
            print(f'ADM sem origens no config_geral (ok, usa clientes): {e}', flush=True)
        conn.close()
        if not regras and rows:
            print('Tem cliente no banco mas sem origem/destino salvo - usando fallback Live21 ate o painel salvar', flush=True)
            return FALLBACK
        if not regras:
            print('Nenhum cliente liberado no painel, usando fallback Live21', flush=True)
            return FALLBACK
        print(f'Painel novo: {len(regras)} regras liberadas: {regras}', flush=True)
        return regras
    except Exception as e:
        print(f'Erro ler painel: {e} - usando fallback Live21', flush=True)
        return FALLBACK

async def main():
    if not SESSION_STRING:
        print('ERRO: SESSION_STRING vazio no Railway', flush=True)
        return
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print('✅ Conectado no Telegram - BOT LIGADO NO PAINEL NOVO', flush=True)
    regras = buscar_regras()
    origens = list(set([o for o,_ in regras]))
    async def recarregar():
        nonlocal regras, origens
        while True:
            await asyncio.sleep(60)
            regras = buscar_regras()
            origens = list(set([o for o,_ in regras]))
    asyncio.create_task(recarregar())
    @client.on(events.NewMessage())
    async def copiar(event):
        try:
            try:
                chat = await event.get_chat()
                username = getattr(chat, 'username', '') or ''
                chat_id = event.chat_id
            except:
                return
            dests=[]
            for o,dest in regras:
                if o.lower()==username.lower() or str(chat_id)==str(o):
                    dests.append(dest)
            if not dests:
                return
            msg=event.message
            if not msg: return
            texto=msg.text or ''
            if getattr(msg,'sticker',None):
                return
            print(f'📩 Copiando de @{username} para {dests}: {texto[:60]}', flush=True)
            for dest in dests:
                try:
                    if msg.media:
                        buf=io.BytesIO()
                        await client.download_media(msg, file=buf)
                        buf.seek(0)
                        if getattr(msg,'photo',None):
                            buf.name='foto.jpg'
                        elif getattr(msg,'video',None):
                            buf.name='video.mp4'
                        else:
                            buf.name='arquivo'
                        enviado=await client.send_file(dest, buf, caption=texto if texto else None, force_document=False)
                    else:
                        if texto:
                            enviado=await client.send_message(dest, texto)
                        else:
                            continue
                    mapa[(event.chat_id, event.id)] = mapa.get((event.chat_id, event.id),[])+[(dest, enviado.id)]
                    print(f'✅ Copiado para @{dest}', flush=True)
                except Exception as e:
                    print(f'Erro enviar para {dest}: {e}', flush=True)
        except Exception as e:
            print(f'Erro copiar: {e}', flush=True)
    @client.on(events.MessageEdited())
    async def editar(event):
        try:
            chaves=[k for k in mapa if k[1]==event.id]
            for k in chaves:
                for dest, mid in mapa[k]:
                    try:
                        await client.edit_message(dest, mid, event.message.text or '')
                        print(f'✏️ Editado em @{dest}', flush=True)
                    except Exception as e:
                        print(f'Erro editar {dest}: {e}', flush=True)
        except Exception as e:
            print(f'Erro editar: {e}', flush=True)
    @client.on(events.MessageDeleted())
    async def deletar(event):
        try:
            for mid in event.deleted_ids:
                chaves=[k for k in mapa if k[1]==mid]
                for k in chaves:
                    for dest, did in mapa[k]:
                        try:
                            await client.delete_messages(dest, did)
                            print(f'🗑️ Apagado em @{dest}', flush=True)
                        except Exception as e:
                            print(f'Erro apagar {dest}: {e}', flush=True)
        except Exception as e:
            print(f'Erro deletar: {e}', flush=True)
    print('Aguardando... (lendo painel novo a cada 60s)', flush=True)
    await client.run_until_disconnected()

if __name__=='__main__':
    asyncio.run(main())
