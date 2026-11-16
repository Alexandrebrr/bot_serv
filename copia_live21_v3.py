
"""
SISTEMA DE CÓPIA AUTOMÁTICA - Live21 v4.0 - SESSION_STRING FINAL
Origem: https://t.me/teamlive21
Destino: https://t.me/Live21streaming

v4.0 - SESSION_STRING - SINCRONIZAÇÃO TOTAL:
- Só copia se for ADMIN do teamlive21
- Se EDITAR lá -> EDITA aqui
- Se APAGAR lá -> APAGA aqui
- Mapa salvo em arquivo, não perde se reiniciar
"""

import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator
import json
import os
import threading, asyncio, io, base64, uuid
import pymysql
try:
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import qrcode
    TEM_QR = True
except Exception as e:
    print(f'Aviso QR: {e}')
    TEM_QR = False

# ===== CONFIGURE AQUI =====
api_id = int(os.getenv('API_ID', '12345678'))
api_hash = os.getenv('API_HASH', 'SEU_API_HASH_AQUI')
SESSION_STRING = os.getenv('SESSION_STRING', '')

ORIGEM = 'teamlive21'
DESTINO = 'Live21streaming'

ASSINATURA = "\n\n📢 _Informação oficial repassada para revendedores_"
PALAVRAS_BLOQUEADAS = ["salário", "demissão", "reunião interna", "senha", "link interno"]
ARQUIVO_MAPA = 'mapa_mensagens.json'
# ===========================

if SESSION_STRING:
    client = TelegramClient(StringSession(SESSION_STRING), api_id, api_hash)
else:
    client = TelegramClient('sessao_live21', api_id, api_hash)

# Carrega mapa salvo, se existir
if os.path.exists(ARQUIVO_MAPA):
    try:
        with open(ARQUIVO_MAPA, 'r', encoding='utf-8') as f:
            mapa_mensagens = json.load(f)
            # JSON salva as chaves como string, converte de volta para int
            mapa_mensagens = {int(k): v for k, v in mapa_mensagens.items()}
    except:
        mapa_mensagens = {}
else:
    mapa_mensagens = {}

def salvar_mapa():
    try:
        with open(ARQUIVO_MAPA, 'w', encoding='utf-8') as f:
            json.dump(mapa_mensagens, f)
    except Exception as e:
        print(f"Erro ao salvar mapa: {e}")

admins_cache = set()

async def e_admin(user_id):
    if user_id in admins_cache:
        return True
    try:
        participante = await client.get_participant(ORIGEM, user_id)
        p = participante.participant
        if isinstance(p, (ChannelParticipantAdmin, ChannelParticipantCreator)):
            admins_cache.add(user_id)
            return True
        return False
    except Exception:
        try:
            async for participante in client.iter_participants(ORIGEM, filter=ChannelParticipantAdmin):
                admins_cache.add(participante.id)
            async for participante in client.iter_participants(ORIGEM, filter=ChannelParticipantCreator):
                admins_cache.add(participante.id)
            return user_id in admins_cache
        except Exception as e2:
            print(f"Aviso admin: {e2} - liberando")
            return True

async def deve_copiar(event, verificar_admin=True):
    msg = event.message
    texto = getattr(msg, 'text', '') or ""
    if getattr(event, 'out', False):
        return False
    if getattr(msg, 'sticker', None):
        return False
    for palavra in PALAVRAS_BLOQUEADAS:
        if palavra.lower() in texto.lower():
            return False
    if verificar_admin:
        sender_id = getattr(event, 'sender_id', None)
        if not sender_id:
            return False
        if not await e_admin(sender_id):
            print(f"⏭️ Ignorado - não é admin: {sender_id}")
            return False
    return True

@client.on(events.NewMessage(chats=ORIGEM))
async def copiar_nova(event):
    if not await deve_copiar(event):
        return
    msg = event.message
    texto = msg.text or ""
    print(f"📩 Nova mensagem de ADMIN: {texto[:80]}...")
    try:
        if msg.media:
            enviada = await client.send_file(DESTINO, msg.media, caption=(texto + ASSINATURA) if texto else ASSINATURA)
        else:
            enviada = await client.send_message(DESTINO, texto + ASSINATURA)
        if isinstance(enviada, list):
            mapa_mensagens[msg.id] = enviada[0].id
        else:
            mapa_mensagens[msg.id] = enviada.id
        salvar_mapa()
        print(f"✅ Enviado (origem {msg.id} -> destino {mapa_mensagens[msg.id]})")
    except Exception as e:
        print(f"❌ Erro ao copiar: {e}")

@client.on(events.MessageEdited(chats=ORIGEM))
async def copiar_edicao(event):
    msg = event.message
    texto = msg.text or ""
    if not await deve_copiar(event):
        return
    id_destino = mapa_mensagens.get(msg.id)
    if not id_destino:
        print(f"⚠️ Editada {msg.id} não encontrada, enviando como nova...")
        await copiar_nova(event)
        return
    print(f"✏️ Admin editou {msg.id}, atualizando...")
    try:
        novo_texto = texto + ASSINATURA + "\n\n✏️ _Atualizado_"
        await client.edit_message(DESTINO, id_destino, novo_texto)
        print("✅ Atualizado no seu canal!")
    except Exception as e:
        print(f"❌ Erro ao editar: {e}")
        try:
            await client.delete_messages(DESTINO, id_destino)
            await copiar_nova(event)
        except Exception as e2:
            print(f"❌ Erro ao reenviar: {e2}")

@client.on(events.MessageDeleted(chats=ORIGEM))
async def copiar_exclusao(event):
    # event.deleted_ids pode ter 1 ou vários IDs
    ids_apagados = event.deleted_ids
    print(f"🗑️ Detectado apagamento no trabalho: {ids_apagados}")
    for id_origem in ids_apagados:
        id_destino = mapa_mensagens.get(id_origem)
        if not id_destino:
            print(f"   - ID {id_origem} não estava no seu canal, ignorando")
            continue
        try:
            await client.delete_messages(DESTINO, id_destino)
            print(f"   ✅ Apagado no seu canal também (destino {id_destino})")
            del mapa_mensagens[id_origem]
            salvar_mapa()
        except Exception as e:
            print(f"   ❌ Erro ao apagar {id_destino}: {e}")


# ===== SERVIDOR QR - DENTRO DO MESMO BOT, SEM PAGAR NADA A MAIS =====
# O painel chama https://SEU-BOT-RAILWAY.up.railway.app/qr_start
# Cliente escaneia o QR no Telegram e a sessao dele salva no MySQL.
DB_HOST = os.getenv('DB_HOST', 'srv1524.hstgr.io')
DB_USER = os.getenv('DB_USER', '')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'u574433089_bot_serv')
pendentes_qr = {}
if TEM_QR:
    qr_app = Flask(__name__)
    CORS(qr_app)
    def qr_salvar_sessao(cliente_id, sessao):
        try:
            con = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4')
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS clientes_config (id INT AUTO_INCREMENT PRIMARY KEY, cliente_id INT, token TEXT, origens TEXT, destinos TEXT, sessao TEXT)")
            try: cur.execute("ALTER TABLE clientes_config ADD COLUMN sessao TEXT")
            except: pass
            cur.execute("INSERT INTO clientes_config (cliente_id, sessao) VALUES (%s,%s) ON DUPLICATE KEY UPDATE sessao=VALUES(sessao)", (cliente_id, sessao))
            cur.execute("UPDATE clientes_config SET sessao=%s WHERE cliente_id=%s", (sessao, cliente_id))
            con.commit(); con.close()
            print(f"✅ QR - Sessao salva cliente {cliente_id}", flush=True)
            return True
        except Exception as e:
            print(f"❌ QR - Erro salvar sessao: {e}", flush=True)
            return False
    def qr_esperar(qr_id, cliente_id, tclient, qr_login):
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(qr_login.wait())
            sessao = tclient.session.save()
            try:
                me = loop.run_until_complete(tclient.get_me()); nome = getattr(me, 'first_name', '') or ''
            except: nome = ''
            pendentes_qr[qr_id]['status'] = 'ok'; pendentes_qr[qr_id]['nome'] = nome; pendentes_qr[qr_id]['sessao'] = sessao
            qr_salvar_sessao(cliente_id, sessao)
            loop.run_until_complete(tclient.disconnect())
        except Exception as e:
            pendentes_qr[qr_id]['status'] = 'erro'; pendentes_qr[qr_id]['erro'] = str(e)
            print(f"❌ QR erro: {e}", flush=True)
        finally: loop.close()
    @qr_app.route('/qr_start', methods=['POST'])
    def qr_start():
        d = request.get_json(force=True, silent=True) or {}
        cliente_id = int(d.get('cliente_id', 0) or 0)
        if not cliente_id: return jsonify({'ok': False, 'erro': 'cliente_id faltando'}), 400
        qr_id = str(uuid.uuid4())[:8]
        pendentes_qr[qr_id] = {'cliente_id': cliente_id, 'status': 'aguardando', 'nome': ''}
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        tclient = TelegramClient(StringSession(), api_id, api_hash)
        loop.run_until_complete(tclient.connect())
        qr_login = loop.run_until_complete(tclient.qr_login())
        img = qrcode.make(qr_login.url); buf = io.BytesIO(); img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        threading.Thread(target=qr_esperar, args=(qr_id, cliente_id, tclient, qr_login), daemon=True).start()
        loop.close()
        return jsonify({'ok': True, 'qr_id': qr_id, 'qr_image': 'data:image/png;base64,' + b64})
    @qr_app.route('/qr_status', methods=['GET'])
    def qr_status():
        p = pendentes_qr.get(request.args.get('qr_id',''))
        if not p: return jsonify({'ok': False, 'erro': 'QR expirado. Gera outro.'})
        return jsonify({'ok': True, 'status': p['status'], 'nome': p.get('nome','')})
    @qr_app.route('/', methods=['GET'])
    def qr_home():
        return jsonify({'ok': True, 'servico': 'Bot Live21 + QR - online'})
    def qr_rodar():
        try:
            porta = int(os.getenv('PORT', '8080'))
            print(f"📱 Servidor QR ligado na porta {porta}", flush=True)
            qr_app.run(host='0.0.0.0', port=porta)
        except Exception as e:
            print(f"Aviso QR server: {e}", flush=True)
    threading.Thread(target=qr_rodar, daemon=True).start()
else:
    print("QR desativado - falta Flask/qrcode no requirements", flush=True)

print("🚀 Sistema Live21 v4.0 - SESSION_STRING FINAL ligado!")
print("👀 Ouvindo: @teamlive21 (SÓ ADMINS)")
print("📤 Enviando para: @Live21streaming")
print("✏️ Monitorando EDIÇÕES")
print("🗑️ Monitorando EXCLUSÕES")
print("Aguardando...")
client.start()
client.run_until_disconnected()
