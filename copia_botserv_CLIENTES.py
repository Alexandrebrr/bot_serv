# BOTSERVER CLIENTES - 1 thread por cliente, cada um com a CONTA DELE
# NÃO mexe no ADM 100%. ADM fica no copia_botserv_FINAL_100_ADM.py
# Este arquivo roda como 2º serviço no Railway (ou mesma máquina, outra porta)
# Cada cliente: sessão própria, pares próprios, álbum próprio, mapa próprio. 1 cliente quebrado não derruba os outros.
import os, io, json, threading, asyncio, base64, time, urllib.request
from flask import Flask, jsonify, send_file, request
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv('API_ID', '0') or 0)
API_HASH = os.getenv('API_HASH', '')
PORT = int(os.getenv('PORT', '8081'))
PAINEL_API = os.getenv('PAINEL_API', 'https://botserv.pro/api.php?action=get')
PAINEL_SALVAR_SESSAO = os.getenv('PAINEL_SALVAR_SESSAO', 'https://botserv.pro/api.php?action=salvar_sessao_cliente')

app = Flask(__name__)
@app.after_request
def _cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return resp

def log(*a): print(*a, flush=True)
def get_dados():
    req = urllib.request.Request(PAINEL_API, headers={'User-Agent': 'BotServ-Clientes/1.0'})
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read().decode())
        return json.loads(d.get('dados', '{}')) if isinstance(d.get('dados'), str) else d.get('dados', {})
def salvar_sessao_cliente(cliente_id, sess):
    try:
        data = json.dumps({"cliente_id": cliente_id, "session_string": sess}).encode()
        req = urllib.request.Request(PAINEL_SALVAR_SESSAO, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as r:
            log(f'Sessão salva no painel p/ cliente {cliente_id}: {r.read()[:100]}')
    except Exception as e:
        log(f'Não consegui salvar sessão do cliente {cliente_id} no painel: {e} - Copia do log e cola no painel')

# QR por cliente - guardado em memória por cliente_id
qr_por_cliente = {}  # id -> {img, status, erro, nome}

@app.route('/')
def home(): return jsonify({"ok": True, "servico": "Bot Clientes - 1 thread por cliente"})

@app.route('/status_cliente/<int:cid>')
def status_cliente(cid):
    q = qr_por_cliente.get(cid, {})
    return jsonify({"ok": True, "status": q.get('status','aguardando'), "conectado": q.get('status')=='conectado', "usuario": q.get('nome',''), "erro": q.get('erro','')})

@app.route('/qr_cliente/<int:cid>')
def qr_cliente(cid):
    q = qr_por_cliente.get(cid)
    if q and q.get('status')=='conectado':
        return jsonify({"ok": True, "conectado": True, "usuario": q.get('nome','')})
    if q and q.get('img') and q.get('status')=='qr_pronto' and (time.time()-q.get('criado',0))<50:
        return send_file(io.BytesIO(q['img']), mimetype='image/png')
    # Gera novo QR em thread separada por cliente
    if not q or q.get('status') not in ('qr_pronto',):
        qr_por_cliente[cid] = {'status': 'gerando', 'erro': ''}
        threading.Thread(target=gerar_qr_cliente, args=(cid,), daemon=True).start()
    for _ in range(16):
        time.sleep(0.5)
        q2 = qr_por_cliente.get(cid, {})
        if q2.get('img') and q2.get('status')=='qr_pronto':
            return send_file(io.BytesIO(q2['img']), mimetype='image/png')
    return jsonify({"ok": False, "erro": "QR ainda gerando, clica de novo"})

def gerar_qr_cliente(cid):
    try:
        import qrcode
        tmp = TelegramClient(StringSession(), API_ID, API_HASH)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(tmp.connect())
        qr_login = loop.run_until_complete(tmp.qr_login())
        token = qr_login.token
        url = 'tg://login?token=' + base64.urlsafe_b64encode(token).decode()
        img = qrcode.make(url)
        buf = io.BytesIO(); img.save(buf, format='PNG')
        qr_por_cliente[cid] = {'img': buf.getvalue(), 'status': 'qr_pronto', 'criado': time.time(), 'erro': ''}
        log(f'[Cliente {cid}] QR gerado, aguardando escaneio...')
        try:
            loop.run_until_complete(qr_login.wait(50))
        except Exception as e:
            log(f'[Cliente {cid}] QR venceu: {e}')
            qr_por_cliente[cid] = {'status': 'aguardando', 'erro': 'QR venceu, clica de novo'}
            try: loop.run_until_complete(tmp.disconnect())
            except Exception: pass
            return
        me = loop.run_until_complete(tmp.get_me())
        nome = me.first_name or ''
        sess = tmp.session.save()
        qr_por_cliente[cid] = {'status': 'conectado', 'nome': nome, 'img': None}
        log(f'[Cliente {cid}] QR conectado como: {nome}')
        salvar_sessao_cliente(cid, sess)
        # Começa a copiar só desse cliente, isolado
        iniciar_copia_cliente(cid, tmp, loop)
    except Exception as e:
        qr_por_cliente[cid] = {'status': 'erro', 'erro': str(e)}
        log(f'[Cliente {cid}] Erro QR: {e}')

def iniciar_copia_cliente(cid, cli, loop):
    # Carrega pares SÓ desse cliente, 1-para-1
    try:
        dados = get_dados()
        c = next((x for x in (dados.get('clientes') or []) if int(x.get('id',0))==int(cid)), None)
        if not c:
            log(f'[Cliente {cid}] Não achei no painel')
            return
        if (c.get('status') or '') not in ('Ativo','Teste'):
            log(f'[Cliente {cid}] Status {c.get("status")} - não copia')
            return
        co = c.get('origens') or []
        cd = c.get('destinos') or []
        plano = (c.get('plano') or '').strip()
        max_par = 1 if c.get('status')=='Teste' else (1 if plano=='Básico' else (3 if plano=='Pro' else 5))
        pares = []
        for i in range(min(max_par,5)):
            o = ((co[i] if i < len(co) else '') or '').strip().lstrip('@').strip()
            dst = ((cd[i] if i < len(cd) else '') or '').strip().lstrip('@').strip()
            if o and dst: pares.append((o,dst))
        if not pares:
            log(f'[Cliente {cid}] Sem pares salvos')
            return
        log(f'[Cliente {cid}] Pares: {pares}')
    except Exception as e:
        log(f'[Cliente {cid}] Erro carregar pares: {e}')
        return
    # Buffers isolados por cliente
    album_buf = {}
    mapa = {}
    async def flush_album(chave, destino, origem):
        await asyncio.sleep(1.5)
        item = album_buf.pop(chave, None)
        if not item: return
        msgs = item['msgs']
        try:
            arquivos=[]; legenda=''
            for idx,m in enumerate(msgs):
                if m.text and not legenda: legenda=m.text
                if m.media:
                    nome = getattr(getattr(m,'file',None),'name',None) or f'banner_{idx+1}.jpg'
                    if '.' not in nome: nome+='.jpg'
                    buf=io.BytesIO(); buf.name=nome
                    await cli.download_media(m.media, file=buf); buf.seek(0); arquivos.append(buf)
            if arquivos:
                enviados = await cli.send_file(destino, arquivos, caption=legenda, force_document=False)
                lista = enviados if isinstance(enviados, list) else [enviados]
                for idx,ev in enumerate(lista):
                    if idx < len(msgs): mapa[(origem,destino,msgs[idx].id)]=ev.id
                log(f'[Cliente {cid}] Copiado álbum: @{origem} -> @{destino} : {len(arquivos)} banners')
            elif legenda:
                await cli.send_message(destino, legenda)
        except Exception as e:
            log(f'[Cliente {cid}] Erro álbum @{origem}->{destino}: {e}')
    for origem, destino in pares:
        def fazer_handler(o=origem, d=destino):
            async def copiar(event):
                try:
                    msg=event.message
                    gid=getattr(msg,'grouped_id',None)
                    if gid:
                        chave=(d,str(gid))
                        if chave not in album_buf:
                            album_buf[chave]={'msgs':[]}
                            loop.create_task(flush_album(chave,d,o))
                        album_buf[chave]['msgs'].append(msg); return
                    texto=msg.text or ''
                    if msg.media: enviado=await cli.send_file(d, msg.media, caption=texto)
                    else: enviado=await cli.send_message(d, texto)
                    try:
                        lista=enviado if isinstance(enviado,list) else [enviado]
                        for ev in lista: mapa[(o,d,msg.id)]=ev.id
                    except Exception: pass
                    log(f'[Cliente {cid}] Copiado: @{o} -> @{d} : {texto[:60]}')
                except Exception as e:
                    log(f'[Cliente {cid}] Erro copiar @{o}->{d}: {e}')
            return copiar
        def fazer_apagar(o=origem, d=destino):
            async def apagar(event):
                try:
                    for mid in event.deleted_ids:
                        did=mapa.pop((o,d,mid),None)
                        if did:
                            await cli.delete_messages(d, did)
                            log(f'[Cliente {cid}] Apagado no destino: @{o} -> @{d}')
                except Exception as e:
                    log(f'[Cliente {cid}] Erro apagar: {e}')
            return apagar
        try:
            cli.add_event_handler(fazer_handler(), events.NewMessage(chats=origem))
            cli.add_event_handler(fazer_apagar(), events.MessageDeleted(chats=origem))
            log(f'[Cliente {cid}] Ouvindo par: @{origem} -> @{destino}')
        except Exception as e:
            log(f'[Cliente {cid}] Par ignorado @{origem}->{destino}: {e}')
            continue
    try:
        loop.run_forever()
    except Exception as e:
        log(f'[Cliente {cid}] Desconectado: {e}')

def iniciar_cliente_por_sessao(c):
    cid = int(c.get('id',0))
    sess = (c.get('session_string') or '').strip()
    if not sess: return
    try:
        cli = TelegramClient(StringSession(sess), API_ID, API_HASH)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cli.connect())
        autorizado = loop.run_until_complete(cli.is_user_authorized())
        if not autorizado:
            log(f'[Cliente {cid}] SESSION_STRING inválida, vai precisar de QR de novo')
            return
        me = loop.run_until_complete(cli.get_me())
        qr_por_cliente[cid] = {'status':'conectado','nome': me.first_name or ''}
        log(f'[Cliente {cid}] Conectado via SESSION_STRING como: {me.first_name}')
        iniciar_copia_cliente(cid, cli, loop)
    except Exception as e:
        log(f'[Cliente {cid}] Erro iniciar por sessão: {e}')

def loop_clientes():
    vistos=set()
    while True:
        try:
            dados=get_dados()
            for c in (dados.get('clientes') or []):
                cid=int(c.get('id',0))
                if cid in vistos: continue
                if (c.get('status') or '') not in ('Ativo','Teste'): continue
                if (c.get('session_string') or '').strip():
                    vistos.add(cid)
                    threading.Thread(target=iniciar_cliente_por_sessao, args=(c,), daemon=True).start()
        except Exception as e:
            log(f'Loop clientes erro: {e}')
        time.sleep(30)

if __name__ == '__main__':
    log('Servidor CLIENTES ligado na porta', PORT)
    threading.Thread(target=loop_clientes, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, threaded=True)
