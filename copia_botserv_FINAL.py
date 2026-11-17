# BOTSERVER FINAL - QR de verdade + copia ADM
# Arquivo unico: copia_botserv_FINAL.py
# Rotas: /  /status  /qr  /gerar_qr
# Copia: teamlive21 -> Live21streaming (conta logada via SESSION_STRING ou QR)
import os, io, json, threading, asyncio, base64
from flask import Flask, jsonify, send_file, request
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.getenv('API_ID', '0') or 0)
API_HASH = os.getenv('API_HASH', '')
SESSION_STRING = os.getenv('SESSION_STRING', '')
PORT = int(os.getenv('PORT', '8080'))

ORIGEM = 'teamlive21'
DESTINO = 'Live21streaming'

app = Flask(__name__)

qr_img_bytes = None
qr_status = 'aguardando'  # aguardando | qr_pronto | conectado | erro
qr_erro = ''
client = None
client_loop = None
me_name = ''

def log(*a):
    print(*a, flush=True)

# ---------- SERVIDOR HTTP ----------
@app.route('/')
def home():
    return jsonify({"ok": True, "servico": "Bot Live21 v8 + QR - online"})

@app.route('/status')
def status():
    return jsonify({"ok": True, "status": qr_status, "conectado": qr_status == 'conectado', "usuario": me_name, "erro": qr_erro})

@app.route('/qr')
@app.route('/gerar_qr')
@app.route('/qr_code')
@app.route('/qrcode')
@app.route('/login_qr')
def gerar_qr():
    global qr_img_bytes, qr_status, qr_erro
    if qr_status == 'conectado':
        return jsonify({"ok": True, "conectado": True, "usuario": me_name, "msg": "Ja conectado, nao precisa de QR"})
    if qr_img_bytes:
        return send_file(io.BytesIO(qr_img_bytes), mimetype='image/png')
    # tenta gerar um QR novo em background
    threading.Thread(target=gerar_qr_background, daemon=True).start()
    # espera ate 8s pelo QR
    import time
    for _ in range(16):
        time.sleep(0.5)
        if qr_img_bytes:
            return send_file(io.BytesIO(qr_img_bytes), mimetype='image/png')
    return jsonify({"ok": False, "erro": qr_erro or "QR ainda gerando, clica de novo em Gerar QR Code"})

def gerar_qr_background():
    global qr_img_bytes, qr_status, qr_erro, client, me_name
    try:
        import qrcode
        # client temporario so para QR
        tmp = TelegramClient(StringSession(), API_ID, API_HASH)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(tmp.connect())
        qr_login = loop.run_until_complete(tmp.qr_login())
        # gera imagem do QR a partir do token
        token = qr_login.token
        # Telethon: o QR e o token em bytes -> url tg://login?token=...
        # O Telegram espera o QR com o token codificado
        import base64 as _b
        url = 'tg://login?token=' + _b.urlsafe_b64encode(token).decode()
        img = qrcode.make(url)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_img_bytes = buf.getvalue()
        qr_status = 'qr_pronto'
        log('📱 QR gerado, aguardando escaneio...')
        # espera o usuario escanear (ate 3 min)
        loop.run_until_complete(qr_login.wait(180))
        # conectado!
        me = loop.run_until_complete(tmp.get_me())
        me_name = me.first_name or ''
        qr_status = 'conectado'
        qr_img_bytes = None
        log(f'✅ QR conectado como: {me_name}')
        # salva a sessao para o Railway nao perder na proxima vez (mostra no log)
        sess = tmp.session.save()
        log('SESSION_STRING_NOVA=' + sess[:20] + '... (copia do log completo se precisar)')
        # agora liga a copia com esse client
        iniciar_copia_com_client(tmp, loop)
    except Exception as e:
        qr_erro = str(e)
        qr_status = 'erro'
        log(f'❌ Erro QR: {e}')

def iniciar_copia_com_client(cli, loop):
    global client, client_loop
    client = cli
    client_loop = loop
    # registra handler de copia
    @cli.on(events.NewMessage(chats=ORIGEM))
    async def copiar(event):
        try:
            msg = event.message
            texto = msg.text or ''
            if msg.media:
                await cli.send_file(DESTINO, msg.media, caption=texto)
            else:
                await cli.send_message(DESTINO, texto)
            log(f'✅ Copiado: {texto[:60]}')
        except Exception as e:
            log(f'❌ Erro copiar: {e}')
    log(f'👀 Ouvindo: @{ORIGEM} -> @{DESTINO}')
    try:
        loop.run_until_disconnected()
    except Exception as e:
        log(f'Client desconectado: {e}')

def iniciar_com_session_string():
    global client, qr_status, me_name
    try:
        cli = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cli.start())
        me = loop.run_until_complete(cli.get_me())
        me_name = me.first_name or ''
        qr_status = 'conectado'
        log(f'✅ Conectado via SESSION_STRING como: {me_name}')
        log(f'👀 Ouvindo: @{ORIGEM} -> @{DESTINO}')
        threading.Thread(target=lambda: iniciar_copia_com_client(cli, loop), daemon=True).start()
        # deixa o loop rodando em thread separada ja foi feito em iniciar_copia_com_client
    except Exception as e:
        log(f'⚠️ SESSION_STRING falhou, vai usar QR: {e}')
        qr_status = 'aguardando'

if __name__ == '__main__':
    log('📱 Servidor QR v8 ligado na porta', PORT)
    log('🚀 Sistema Live21 v8 + QR ligado!')
    if SESSION_STRING and API_ID:
        threading.Thread(target=iniciar_com_session_string, daemon=True).start()
    else:
        log('⏳ Sem SESSION_STRING, aguardando QR pelo painel...')
    app.run(host='0.0.0.0', port=PORT)
