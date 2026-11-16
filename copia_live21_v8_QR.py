import os, asyncio, re
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
ORIGEM = os.environ.get("ORIGEM", "teamlive21")
DESTINO = os.environ.get("DESTINO", "Live21streaming")

# Se ORIGEM/DESTINO vierem com @ ou link, limpa
def limpar(v):
    v = v.strip()
    v = v.replace("https://t.me/", "").replace("http://t.me/", "").replace("t.me/", "").replace("@", "")
    return v.split("/")[0]

ORIGEM = limpar(ORIGEM)
DESTINO = limpar(DESTINO)

ASSINATURA = "\n\n✅ Informação oficial para revendedores Live21"
PALAVRAS_BLOQUEADAS = ["xxx", "porno"]
BLOQUEAR_STICKER = True


# ===== SERVIDOR QR v8 - SEM BIBLIOTECA NOVA, SEM NADA NOVO PRA INSTALAR =====
# Usa só http.server (já vem no Python) + Telethon (já instalado).
# O painel chama https://worker-production-bb98434f.up.railway.app/qr_start
# Cliente escaneia, a sessão dele salva no MySQL, o bot começa a copiar.
import threading, asyncio, io, base64, uuid, json as _json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import pymysql
DB_HOST = os.getenv('DB_HOST', 'srv1524.hstgr.io')
DB_USER = os.getenv('DB_USER', '')
DB_PASS = os.getenv('DB_PASS', '')
DB_NAME = os.getenv('DB_NAME', 'u574433089_bot_serv')
pendentes_qr = {}
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
        print(f"✅ QR v8 - Sessao salva cliente {cliente_id}", flush=True)
        return True
    except Exception as e:
        print(f"❌ QR v8 - Erro salvar sessao: {e}", flush=True)
        return False
def qr_esperar(qr_id, cliente_id, tclient, qr_login):
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(qr_login.wait())
        sessao = tclient.session.save()
        try:
            me = loop.run_until_complete(tclient.get_me()); nome = getattr(me, 'first_name', '') or ''
        except: nome = ''
        pendentes_qr[qr_id]['status'] = 'ok'; pendentes_qr[qr_id]['nome'] = nome
        qr_salvar_sessao(cliente_id, sessao)
        loop.run_until_complete(tclient.disconnect())
    except Exception as e:
        pendentes_qr[qr_id]['status'] = 'erro'; pendentes_qr[qr_id]['erro'] = str(e)
        print(f"❌ QR v8 erro: {e}", flush=True)
    finally: loop.close()
def qr_gerar(cliente_id):
    qr_id = str(uuid.uuid4())[:8]
    pendentes_qr[qr_id] = {'cliente_id': cliente_id, 'status': 'aguardando', 'nome': ''}
    loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
    tclient = TelegramClient(StringSession(), api_id, api_hash)
    loop.run_until_complete(tclient.connect())
    qr_login = loop.run_until_complete(tclient.qr_login())
    url = qr_login.url
    threading.Thread(target=qr_esperar, args=(qr_id, cliente_id, tclient, qr_login), daemon=True).start()
    loop.close()
    # QR como imagem externa: o painel gera a imagem a partir da URL, sem precisar de biblioteca
    return qr_id, url
class QRHandler(BaseHTTPRequestHandler):
    def _send(self, obj):
        data = _json.dumps(obj).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Content-Length', str(len(data))); self.end_headers()
        self.wfile.write(data)
    def do_OPTIONS(self):
        self.send_response(200); self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.end_headers()
    def do_GET(self):
        p = urlparse(self.path)
        if p.path == '/':
            self._send({'ok': True, 'servico': 'Bot Live21 v8 + QR - online'}); return
        if p.path == '/qr_status':
            q = parse_qs(p.query); qr_id = (q.get('qr_id',[''])[0])
            d = pendentes_qr.get(qr_id)
            if not d: self._send({'ok': False, 'erro': 'QR expirado. Gera outro.'}); return
            self._send({'ok': True, 'status': d['status'], 'nome': d.get('nome','')}); return
        self._send({'ok': False, 'erro': 'rota nao encontrada'})
    def do_POST(self):
        if urlparse(self.path).path != '/qr_start':
            self._send({'ok': False, 'erro': 'rota nao encontrada'}); return
        try: n = int(self.headers.get('Content-Length','0') or 0)
        except: n = 0
        try: d = _json.loads(self.rfile.read(n).decode() or '{}')
        except: d = {}
        cliente_id = int(d.get('cliente_id', 0) or 0)
        if not cliente_id: self._send({'ok': False, 'erro': 'cliente_id faltando'}); return
        try:
            qr_id, url = qr_gerar(cliente_id)
            self._send({'ok': True, 'qr_id': qr_id, 'qr_url': url})
        except Exception as e:
            self._send({'ok': False, 'erro': str(e)})
    def log_message(self, *a): pass
def qr_rodar():
    try:
        porta = int(os.getenv('PORT', '8080'))
        print(f"📱 Servidor QR v8 ligado na porta {porta}", flush=True)
        HTTPServer(('0.0.0.0', porta), QRHandler).serve_forever()
    except Exception as e:
        print(f"Aviso QR v8: {e}", flush=True)
threading.Thread(target=qr_rodar, daemon=True).start()
print("🚀 Sistema Live21 v8 ligado!", flush=True)
print(f"👀 Ouvindo: @{ORIGEM} -> @{DESTINO}", flush=True)

async def main():
    if not SESSION_STRING:
        print("❌ ERRO: SESSION_STRING vazio! Coloque em Variables no Railway.", flush=True)
        return
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("✅ Conectado no Telegram!", flush=True)

    @client.on(events.NewMessage(chats=ORIGEM))
    async def copiar(event):
        try:
            # Só admins
            try:
                sender = await event.get_sender()
                # Se for canal, verifica se é admin pelo chat
                # Simplificação: copia tudo de ORIGEM, pois ORIGEM é canal de admins
            except:
                pass
            msg = event.message
            if not msg:
                return
            texto = msg.text or ""
            if any(p.lower() in texto.lower() for p in PALAVRAS_BLOQUEADAS):
                print("🚫 Bloqueada palavra proibida", flush=True)
                return
            if BLOQUEAR_STICKER and msg.sticker:
                print("🚫 Sticker bloqueado", flush=True)
                return
            # Reposta sem forward: envia texto + mídia como nova mensagem
            if msg.media:
                await client.send_file(DESTINO, msg.media, caption=(texto + ASSINATURA) if texto else ASSINATURA)
            else:
                if texto:
                    await client.send_message(DESTINO, texto + ASSINATURA)
            print(f"✅ Copiado: {texto[:60]}", flush=True)
        except Exception as e:
            print(f"Erro copiar: {e}", flush=True)

    @client.on(events.MessageEdited(chats=ORIGEM))
    async def editar(event):
        try:
            # Apaga e reposta simplificado: avisa edição
            print(f"✏️ Edição detectada id={event.id}", flush=True)
        except Exception as e:
            print(f"Erro editar: {e}", flush=True)

    @client.on(events.MessageDeleted(chats=ORIGEM))
    async def deletar(event):
        try:
            print(f"🗑️ Deleção detectada ids={event.deleted_ids}", flush=True)
        except Exception as e:
            print(f"Erro deletar: {e}", flush=True)

    print("Aguardando...", flush=True)
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
