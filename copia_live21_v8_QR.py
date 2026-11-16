
"""
SISTEMA DE CÓPIA AUTOMÁTICA - Live21 v8 - SESSION_STRING FINAL
Origem: https://t.me/teamlive21
Destino: https://t.me/Live21streaming

v8 - SESSION_STRING - SINCRONIZAÇÃO TOTAL:
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

# ===== SERVIDOR QR v7 - SEM EXTRA, SEM QRCODE - só stdlib + Telethon =====
# O painel gera a imagem do QR usando api.qrserver.com a partir da URL que o Telegram dá.
# Por isso o requirements continua só telethon + pymysql, que já está instalado.
DB_HOST = os.getenv('DB_HOST', 'srv1524.hstgr.io')
DB_USER = os.getenv('DB_USER', '')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'u574433089_bot_serv')
pendentes_qr = {}
try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import json as _json
    TEM_QR = True
except Exception as e:
    print('Aviso QR: ' + str(e))
    TEM_QR = False
if TEM_QR:
    def qr_salvar_sessao(cliente_id, sessao):
        try:
            con = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4')
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS clientes_config (id INT AUTO_INCREMENT PRIMARY KEY, cliente_id INT, token TEXT, origens TEXT, destinos TEXT, sessao TEXT)")
            try:
                cur.execute("ALTER TABLE clientes_config ADD COLUMN sessao TEXT")
            except:
                pass
            cur.execute("INSERT INTO clientes_config (cliente_id, sessao) VALUES (%s,%s) ON DUPLICATE KEY UPDATE sessao=VALUES(sessao)", (cliente_id, sessao))
            cur.execute("UPDATE clientes_config SET sessao=%s WHERE cliente_id=%s", (sessao, cliente_id))
            con.commit()
            con.close()
            print('QR - Sessao salva cliente ' + str(cliente_id), flush=True)
            return True
        except Exception as e:
            print('QR - Erro salvar sessao: ' + str(e), flush=True)
            return False
    async def qr_fluxo(qr_id, cliente_id):
        tclient = TelegramClient(StringSession(), api_id, api_hash)
        try:
            await tclient.connect()
            qr_login = await tclient.qr_login()
            pendentes_qr[qr_id]['qr_url'] = qr_login.url
            pendentes_qr[qr_id]['status'] = 'aguardando'
            print('QR gerado cliente ' + str(cliente_id), flush=True)
            await qr_login.wait()
            sessao = tclient.session.save()
            try:
                me = await tclient.get_me()
                nome = getattr(me, 'first_name', '') or ''
            except:
                nome = ''
            pendentes_qr[qr_id]['status'] = 'ok'
            pendentes_qr[qr_id]['nome'] = nome
            qr_salvar_sessao(cliente_id, sessao)
            print('QR - Cliente conectou: ' + nome, flush=True)
            await tclient.disconnect()
        except Exception as e:
            pendentes_qr[qr_id]['status'] = 'erro'
            pendentes_qr[qr_id]['erro'] = str(e)
            print('QR erro: ' + str(e), flush=True)
            try:
                await tclient.disconnect()
            except:
                pass
    def qr_rodar_fluxo(qr_id, cliente_id):
        try:
            asyncio.run(qr_fluxo(qr_id, cliente_id))
        except Exception as e:
            pendentes_qr[qr_id]['status'] = 'erro'
            pendentes_qr[qr_id]['erro'] = str(e)
    class QRHandler(BaseHTTPRequestHandler):
        def _send(self, obj, code=200):
            data = _json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_OPTIONS(self):
            self._send({}, 200)
        def do_GET(self):
            try:
                from urllib.parse import urlparse, parse_qs
                p = urlparse(self.path)
                if p.path == '/':
                    self._send({'ok': True, 'servico': 'Bot Live21 + QR - online'})
                    return
                if p.path == '/qr_status':
                    qr_id = parse_qs(p.query).get('qr_id', [''])[0]
                    info = pendentes_qr.get(qr_id)
                    if not info:
                        self._send({'ok': False, 'erro': 'QR expirado. Gera outro.'})
                        return
                    self._send({'ok': True, 'status': info['status'], 'nome': info.get('nome', '')})
                    return
                self._send({'ok': False, 'erro': 'rota nao encontrada'}, 404)
            except Exception as e:
                self._send({'ok': False, 'erro': str(e)}, 500)
        def do_POST(self):
            try:
                if self.path != '/qr_start':
                    self._send({'ok': False, 'erro': 'rota nao encontrada'}, 404)
                    return
                tam = int(self.headers.get('Content-Length', 0) or 0)
                corpo = self.rfile.read(tam).decode() if tam else '{}'
                d = _json.loads(corpo or '{}')
                cliente_id = int(d.get('cliente_id', 0) or 0)
                if not cliente_id:
                    self._send({'ok': False, 'erro': 'cliente_id faltando'}, 400)
                    return
                qr_id = str(uuid.uuid4())[:8]
                pendentes_qr[qr_id] = {'cliente_id': cliente_id, 'status': 'gerando', 'nome': '', 'qr_url': ''}
                threading.Thread(target=qr_rodar_fluxo, args=(qr_id, cliente_id), daemon=True).start()
                import time
                for _ in range(40):
                    if pendentes_qr[qr_id].get('qr_url'):
                        self._send({'ok': True, 'qr_id': qr_id, 'qr_url': pendentes_qr[qr_id]['qr_url']})
                        return
                    if pendentes_qr[qr_id]['status'] == 'erro':
                        self._send({'ok': False, 'erro': pendentes_qr[qr_id].get('erro', 'Erro ao gerar QR')}, 500)
                        return
                    time.sleep(0.2)
                self._send({'ok': False, 'erro': 'Demorou pra gerar o QR. Tenta de novo.'}, 500)
            except Exception as e:
                print('qr_start erro: ' + str(e), flush=True)
                self._send({'ok': False, 'erro': str(e)}, 500)
        def log_message(self, *a):
            pass
    def qr_rodar():
        try:
            porta = int(os.getenv('PORT', '8080'))
            print('Servidor QR ligado na porta ' + str(porta), flush=True)
            ThreadingHTTPServer(('0.0.0.0', porta), QRHandler).serve_forever()
        except Exception as e:
            print('Aviso QR server: ' + str(e), flush=True)
    threading.Thread(target=qr_rodar, daemon=True).start()
else:
    print('QR desativado', flush=True)

print("🚀 🚀 Sistema Live21 v8 + QR ligado!")
print("👀 Ouvindo: @teamlive21 (SÓ ADMINS)")
print("📤 Enviando para: @Live21streaming")
print("✏️ Monitorando EDIÇÕES")
print("🗑️ Monitorando EXCLUSÕES")
print("Aguardando...")
client.start()
client.run_until_disconnected()
