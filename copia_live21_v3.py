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

# ===== SERVIDOR QR v6 - CORRIGIDO =====
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
            try:
                cur.execute("ALTER TABLE clientes_config ADD COLUMN sessao TEXT")
            except:
                pass
            cur.execute("INSERT INTO clientes_config (cliente_id, sessao) VALUES (%s,%s) ON DUPLICATE KEY UPDATE sessao=VALUES(sessao)", (cliente_id, sessao))
            cur.execute("UPDATE clientes_config SET sessao=%s WHERE cliente_id=%s", (sessao, cliente_id))
            con.commit()
            con.close()
            print("QR - Sessao salva cliente " + str(cliente_id), flush=True)
            return True
        except Exception as e:
            print("QR - Erro salvar sessao: " + str(e), flush=True)
            return False
    async def qr_fluxo(qr_id, cliente_id):
        tclient = TelegramClient(StringSession(), api_id, api_hash)
        try:
            await tclient.connect()
            qr_login = await tclient.qr_login()
            img = qrcode.make(qr_login.url)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            pendentes_qr[qr_id]['qr_image'] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
            pendentes_qr[qr_id]['status'] = 'aguardando'
            print("QR gerado cliente " + str(cliente_id), flush=True)
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
            print("QR - Cliente conectou: " + nome, flush=True)
            await tclient.disconnect()
        except Exception as e:
            pendentes_qr[qr_id]['status'] = 'erro'
            pendentes_qr[qr_id]['erro'] = str(e)
            print("QR erro: " + str(e), flush=True)
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
    @qr_app.route('/qr_start', methods=['POST'])
    def qr_start():
        try:
            d = request.get_json(force=True, silent=True) or {}
            cliente_id = int(d.get('cliente_id', 0) or 0)
            if not cliente_id:
                return jsonify({'ok': False, 'erro': 'cliente_id faltando'}), 400
            qr_id = str(uuid.uuid4())[:8]
            pendentes_qr[qr_id] = {'cliente_id': cliente_id, 'status': 'gerando', 'nome': '', 'qr_image': ''}
            threading.Thread(target=qr_rodar_fluxo, args=(qr_id, cliente_id), daemon=True).start()
            import time
            for _ in range(40):
                if pendentes_qr[qr_id].get('qr_image'):
                    return jsonify({'ok': True, 'qr_id': qr_id, 'qr_image': pendentes_qr[qr_id]['qr_image']})
                if pendentes_qr[qr_id]['status'] == 'erro':
                    return jsonify({'ok': False, 'erro': pendentes_qr[qr_id].get('erro', 'Erro ao gerar QR')}), 500
                time.sleep(0.2)
            return jsonify({'ok': False, 'erro': 'Demorou pra gerar o QR. Tenta de novo.'}), 500
        except Exception as e:
            print("qr_start erro: " + str(e), flush=True)
            return jsonify({'ok': False, 'erro': str(e)}), 500
    @qr_app.route('/qr_status', methods=['GET'])
    def qr_status():
        p = pendentes_qr.get(request.args.get('qr_id', ''))
        if not p:
            return jsonify({'ok': False, 'erro': 'QR expirado. Gera outro.'})
        return jsonify({'ok': True, 'status': p['status'], 'nome': p.get('nome', '')})
    @qr_app.route('/', methods=['GET'])
    def qr_home():
        return jsonify({'ok': True, 'servico': 'Bot Live21 + QR - online'})
    def qr_rodar():
        try:
            porta = int(os.getenv('PORT', '8080'))
            print("Servidor QR ligado na porta " + str(porta), flush=True)
            qr_app.run(host='0.0.0.0', port=porta)
        except Exception as e:
            print("Aviso QR server: " + str(e), flush=True)
    threading.Thread(target=qr_rodar, daemon=True).start()
else:
    print("QR desativado - falta Flask/qrcode no requirements", flush=True)

print("🚀 Sistema Live21 v4.0 ligado!", flush=True)
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
