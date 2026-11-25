# BOTSERVER FINAL - QR de verdade + copia ADM - CORRIGIDO v9
# Arquivo unico: copia_botserv_FINAL.py
# Rotas: /  /status  /qr  /gerar_qr
# Copia: teamlive21 -> Live21streaming (conta logada via SESSION_STRING ou QR)
# CORRECOES v9:
# 1) SEM input() - no Railway nao tem teclado, por isso dava EOF when reading a line
# 2) QR unico - trava pra nao gerar QR novo a cada /qr, por isso dava AUTH_TOKEN_EXPIRED
# 3) SESSION_STRING sem cli.start() - start() pede telefone no terminal, agora usa connect() sem pedir nada
import os, io, json, threading, asyncio, base64, time
from flask import Flask, jsonify, send_file, request
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv('API_ID', '0') or 0)
API_HASH = os.getenv('API_HASH', '')
SESSION_STRING = os.getenv('SESSION_STRING', '').strip()
TELEGRAM_2FA = os.getenv('TELEGRAM_2FA', '').strip()
PORT = int(os.getenv('PORT', '8080'))

ORIGEM = 'teamlive21'
DESTINO = 'Live21streaming'

app = Flask(__name__)

@app.after_request
def _cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return resp

@app.route('/status', methods=['OPTIONS'])
@app.route('/qr', methods=['OPTIONS'])
@app.route('/login_qr', methods=['OPTIONS'])
@app.route('/', methods=['OPTIONS'])
def _options():
    return ('', 204)

qr_img_bytes = None
qr_status = 'aguardando'  # aguardando | qr_pronto | conectado | erro
qr_erro = ''
client = None
client_loop = None
me_name = ''
_qr_lock = threading.Lock()
_qr_gerando = False
_qr_criado_em = 0

def log(*a):
    print(*a, flush=True)

@app.route('/')
def home():
    return jsonify({"ok": True, "servico": "Bot Live21 v9 + QR - online"})

@app.route('/senha_2fa', methods=['POST'])
def senha_2fa():
    global qr_erro
    try:
        d = request.get_json(force=True) or {}
        senha = (d.get('senha') or d.get('password') or '').strip()
        if not senha: return jsonify({"ok": False, "erro": "Senha vazia"})
        # Salva em memoria para a thread do QR usar
        globals()['TELEGRAM_2FA'] = senha
        return jsonify({"ok": True, "msg": "Senha 2FA recebida, escaneia o QR de novo"})
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)})

@app.route('/status')
def status():
    return jsonify({"ok": True, "status": qr_status, "conectado": qr_status == 'conectado', "usuario": me_name, "erro": qr_erro})

@app.route('/qr')
@app.route('/gerar_qr')
@app.route('/qr_code')
@app.route('/qrcode')
@app.route('/login_qr')
def gerar_qr():
    global qr_img_bytes, qr_status, qr_erro, _qr_gerando, _qr_criado_em
    if qr_status == 'conectado':
        return jsonify({"ok": True, "conectado": True, "usuario": me_name, "msg": "Ja conectado, nao precisa de QR"})
    # Se ja tem QR pronto e tem menos de 50s, devolve o MESMO QR - nao gera outro e nao invalida
    if qr_img_bytes and qr_status == 'qr_pronto' and (time.time() - _qr_criado_em) < 50:
        return send_file(io.BytesIO(qr_img_bytes), mimetype='image/png')
    # Se QR expirou, limpa e gera novo
    if qr_img_bytes and (time.time() - _qr_criado_em) >= 50:
        qr_img_bytes = None
        qr_status = 'aguardando'
    # Trava: so 1 geracao por vez
    with _qr_lock:
        if _qr_gerando:
            # ja esta gerando, espera
            pass
        else:
            _qr_gerando = True
            threading.Thread(target=gerar_qr_background, daemon=True).start()
    # espera ate 8s pelo QR
    for _ in range(16):
        time.sleep(0.5)
        if qr_img_bytes:
            return send_file(io.BytesIO(qr_img_bytes), mimetype='image/png')
    return jsonify({"ok": False, "erro": qr_erro or "QR ainda gerando, clica de novo em Gerar QR Code"})

def gerar_qr_background():
    global qr_img_bytes, qr_status, qr_erro, client, me_name, _qr_gerando, _qr_criado_em
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
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_img_bytes = buf.getvalue()
        _qr_criado_em = time.time()
        qr_status = 'qr_pronto'
        _qr_gerando = False
        log('QR gerado, aguardando escaneio... (vale 50s, nao aperte Gerar de novo enquanto tenta escanear)')
        # espera o usuario escanear (ate 50s - mesmo tempo do painel)
        try:
            loop.run_until_complete(qr_login.wait(50))
        except Exception as e:
            # Timeout = QR expirou porque ninguem escaneou a tempo
            log('QR venceu sem escaneio, gere outro. Detalhe: ' + str(e))
            qr_img_bytes = None
            qr_status = 'aguardando'
            qr_erro = 'QR venceu, clica em Atualizar QR'
            try: loop.run_until_complete(tmp.disconnect())
            except Exception: pass
            return
        me = loop.run_until_complete(tmp.get_me())
        me_name = me.first_name or ''
        qr_status = 'conectado'
        qr_img_bytes = None
        log(f'QR conectado como: {me_name}')
        sess = tmp.session.save()
        log('SESSION_STRING_NOVA gerada - copia do log e cola no Railway como SESSION_STRING pra nao precisar de QR de novo. Comeco: ' + sess[:20] + '...')
        iniciar_copia_com_client(tmp, loop)
    except Exception as e:
        _qr_gerando = False
        # Se for senha 2FA, mostra status certo pro painel em vez de erro generico
        if 'password' in str(e).lower() or 'SessionPasswordNeeded' in str(e) or '2FA' in str(e):
            qr_status = 'precisa_senha_2fa'
            qr_erro = 'Precisa da senha de 2 etapas do Telegram. Desliga ela ou coloca TELEGRAM_2FA no Railway.'
            log('Telegram pediu senha de 2 etapas.')
            return
        qr_erro = str(e)
        qr_status = 'erro'
        log(f'Erro QR: {e}')

def iniciar_copia_com_client(cli, loop):
    global client, client_loop
    client = cli
    client_loop = loop
    @cli.on(events.NewMessage(chats=ORIGEM))
    async def copiar(event):
        try:
            msg = event.message
            texto = msg.text or ''
            if msg.media:
                await cli.send_file(DESTINO, msg.media, caption=texto)
            else:
                await cli.send_message(DESTINO, texto)
            log(f'Copiado: {texto[:60]}')
        except Exception as e:
            log(f'Erro copiar: {e}')
    log(f'Ouvindo: @{ORIGEM} -> @{DESTINO}')
    try:
        loop.run_until_disconnected()
    except Exception as e:
        log(f'Client desconectado: {e}')

def iniciar_com_session_string():
    global client, qr_status, me_name
    try:
        # NUNCA usa cli.start() aqui - start() pede telefone no terminal e no Railway da EOF
        cli = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cli.connect())
        # Se SESSION_STRING for invalida, is_user_authorized() = False, cai pro QR sem pedir telefone
        autorizado = loop.run_until_complete(cli.is_user_authorized())
        if not autorizado:
            raise Exception('SESSION_STRING invalida ou expirada')
        me = loop.run_until_complete(cli.get_me())
        me_name = me.first_name or ''
        qr_status = 'conectado'
        log(f'Conectado via SESSION_STRING como: {me_name}')
        log(f'Ouvindo: @{ORIGEM} -> @{DESTINO}')
        iniciar_copia_com_client(cli, loop)
    except Exception as e:
        # SEM input(), SEM pedir telefone - so vai pro QR
        log(f'SESSION_STRING falhou, vai usar QR: {e}')
        qr_status = 'aguardando'

if __name__ == '__main__':
    log('Servidor QR v9 ligado na porta', PORT)
    log('Sistema Live21 v9 + QR ligado!')
    if SESSION_STRING and API_ID:
        threading.Thread(target=iniciar_com_session_string, daemon=True).start()
    else:
        log('Sem SESSION_STRING, aguardando QR pelo painel...')
    app.run(host='0.0.0.0', port=PORT, threaded=True)
