import os
import time
import re
import requests
from datetime import datetime
from requests.exceptions import HTTPError, RequestException
from dotenv import load_dotenv

load_dotenv()

BOT_API_KEY = os.environ.get("BOT_API_KEY")
BOT_LOGS_CHAT_ID = os.environ.get("BOT_LOGS_CHAT_ID")
BOT_USERNAME = os.environ.get("BOT_USERNAME") 
NEXTCLOUD_BASE_URL = os.environ.get("NEXTCLOUD_BASE_URL")
NEXTCLOUD_SHARE_ID = os.environ.get("NEXTCLOUD_SHARE_ID")

if not all([BOT_API_KEY, BOT_LOGS_CHAT_ID, BOT_USERNAME, NEXTCLOUD_BASE_URL, NEXTCLOUD_SHARE_ID]):
    print("ERRO CRÍTICO: Verifique se TODAS as variáveis estão definidas no seu arquivo .env")
    exit()

base_url = f"https://api.telegram.org/bot{BOT_API_KEY}"
base_file_url = f"https://api.telegram.org/file/bot{BOT_API_KEY}"
nextcloud_upload_path = f"{NEXTCLOUD_BASE_URL}/public.php/dav/files/{NEXTCLOUD_SHARE_ID}/FotosParticipantesIGF2025"


def send_message(chat_id, text, reply_markup=None):
    """Envia uma mensagem de texto, opcionalmente com botões."""
    payload = {"chat_id": str(chat_id), "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(f"{base_url}/sendMessage", json=payload, timeout=10)
        res.raise_for_status()
    except RequestException as e:
        print(f"AVISO: Falha ao enviar mensagem para {chat_id}: {e}")

def log_message(message):
    """Imprime e envia uma mensagem de log para o grupo de controle."""
    now = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_entry = f"[{now}] {message}"
    print(log_entry)
    send_message(BOT_LOGS_CHAT_ID, log_entry)


def process_and_upload_file(message):
    """Pega uma mensagem com mídia e faz todo o processo de upload."""
    chat_id = message["chat"]["id"]
    sender = message["from"].get("username") or message["from"].get("first_name", "Anonimo")
    media = message.get("video") or message.get("document") or (message.get("photo")[-1] if message.get("photo") else None)
    
    log_message(f"[MÍDIA PRIVADA] Recebendo arquivo de @{sender}")
    
    file_id = media["file_id"]
    media_file_name = media.get("file_name", "arquivo_sem_nome.tmp")
    safe_sender = re.sub(r'[\\/*?:"<>|]', "", sender)
    file_name = f"{message['date']}-{safe_sender}-{media_file_name}"

    try:
        file_path_res = requests.get(f"{base_url}/getFile?file_id={file_id}", timeout=20)
        file_path_res.raise_for_status()
        file_path = file_path_res.json()["result"]["file_path"]

        if not re.search(r'\.\w+$', file_name) and "." in file_path:
            file_name += os.path.splitext(file_path)[-1]
        
        log_message(f"==> Baixando: {media_file_name}")
        file_content_res = requests.get(f"{base_file_url}/{file_path}", timeout=120)
        file_content_res.raise_for_status()
        file_content = file_content_res.content

        log_message(f"==> Fazendo upload como: '{file_name}'")
        upload_res = requests.put(f"{nextcloud_upload_path}/{filename}", data=file_content, timeout=300)
        upload_res.raise_for_status()
        
        log_message(f"==> SUCESSO! Arquivo '{file_name}' salvo.")
        send_message(chat_id, f"Arquivo '{media_file_name}' salvo com sucesso! ✅\nPode me enviar outro se quiser.")

    except Exception as e:
        log_message(f"==> ERRO ao processar arquivo de @{sender}: {e}")
        send_message(chat_id, f"Ocorreu um erro ao tentar salvar seu arquivo '{media_file_name}'. Por favor, tente novamente. 😢")


def process_update(update):
    """Decide o que fazer baseado em onde a mensagem foi enviada."""
    if not update.get("message"): return
    
    message = update["message"]
    chat_type = message["chat"]["type"]
    text = message.get("text", "")

    if chat_type in ["group", "supergroup"]:
        if BOT_USERNAME in text:
            chat_id = message["chat"]["id"]
            sender_username = message["from"].get("username", "usuário")
            log_message(f"[@MENTION] Bot mencionado por @{sender_username} no grupo {chat_id}")
            
            bot_url = f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=from_group"
            keyboard = {"inline_keyboard": [[{"text": "Clique aqui para me enviar seu arquivo", "url": bot_url}]]}
            response_text = f"Olá, @{sender_username}! Para garantir a organização, por favor, me envie seu arquivo na nossa conversa privada. É só clicar no botão abaixo!"
            
            send_message(chat_id, response_text, reply_markup=keyboard)
    
    elif chat_type == "private":
        chat_id = message["chat"]["id"]
        
        if text.startswith("/start"):
            sender_username = message["from"].get("username", "usuário")
            log_message(f"[/START] @{sender_username} iniciou conversa privada.")
            send_message(chat_id, "Olá! Bem-vindo(a) à área de envio. Por favor, anexe e envie sua foto, vídeo ou documento agora.")
        
        elif message.get("photo") or message.get("video") or message.get("document"):
            process_and_upload_file(message)
        
        else:
            send_message(chat_id, "Não entendi. Por favor, me envie um arquivo (foto, vídeo ou documento).")


def main():
    log_message("--- BOT HÍBRIDO INICIADO ---")
    last_update_id = 0
    while True:
        try:
            offset = last_update_id + 1
            res = requests.get(f"{base_url}/getUpdates?offset={offset}&timeout=100")
            res.raise_for_status()
            updates = res.json().get("result", [])
            for update in updates:
                last_update_id = update["update_id"]
                process_update(update)
            time.sleep(1)
        except RequestException as e:
            log_message(f"ERRO DE REDE: {e}. Tentando novamente em 30s.")
            time.sleep(30)
        except Exception as e:
            log_message(f"ERRO CRÍTICO: {e}. Aguardando 60s.")
            time.sleep(60)

if __name__ == "__main__":
    main()
