# bot_igf.py

# Importa as bibliotecas necessárias
import os
import time
import re
import requests
from datetime import datetime
from requests.exceptions import HTTPError, RequestException
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

# --- CONFIGURAÇÃO ---
# O script irá pegar essas variáveis do seu arquivo .env
BOT_API_KEY = os.environ.get("BOT_API_KEY")
BOT_LOGS_CHAT_ID = os.environ.get("BOT_LOGS_CHAT_ID")
NEXTCLOUD_BASE_URL = os.environ.get("NEXTCLOUD_BASE_URL")
NEXTCLOUD_SHARE_ID = os.environ.get("NEXTCLOUD_SHARE_ID")

if not all([BOT_API_KEY, BOT_LOGS_CHAT_ID, NEXTCLOUD_BASE_URL, NEXTCLOUD_SHARE_ID]):
    print("ERRO CRÍTICO: Verifique se todas as variáveis foram definidas no seu arquivo .env")
    print("Variáveis necessárias: BOT_API_KEY, BOT_LOGS_CHAT_ID, NEXTCLOUD_BASE_URL, NEXTCLOUD_SHARE_ID")
    exit()

# Monta as URLs que serão usadas pelo bot
base_url = f"https://api.telegram.org/bot{BOT_API_KEY}"
base_file_url = f"https://api.telegram.org/file/bot{BOT_API_KEY}"
nextcloud_upload_path = f"{NEXTCLOUD_BASE_URL}/public.php/dav/files/{NEXTCLOUD_SHARE_ID}/FotosParticipantesIGF2025"

# --- FUNÇÕES DO BOT ---

def get_file_path(file_id):
    """Obtém o caminho de um arquivo para download."""
    res = requests.get(f"{base_url}/getFile?file_id={file_id}", timeout=20)
    res.raise_for_status()
    data = res.json()
    return data["result"]["file_path"]

def download_file(file_path):
    """Baixa o conteúdo do arquivo."""
    res = requests.get(f"{base_file_url}/{file_path}", timeout=120) 
    return res.content

def react_to_message(chat_id, message_id, emoji):
    """Reage a uma mensagem com um emoji."""
    try:
        requests.post(
            f"{base_url}/setMessageReaction",
            json={"chat_id": chat_id, "message_id": message_id, "reaction": [{"type": "emoji", "emoji": emoji}]},
            timeout=5
        )
    except RequestException:
        pass 

def send_message(chat_id, message):
    """Envia uma mensagem de texto para um chat (usado apenas para logs)."""
    try:
        res = requests.post(f"{base_url}/sendMessage", json={"chat_id": chat_id, "text": message}, timeout=10)
        res.raise_for_status()
    except RequestException as e:
        print(f"AVISO: Falha ao enviar mensagem de log para {chat_id}: {e}")

def log_message(message):
    """Imprime e envia uma mensagem de log para o grupo de controle."""
    now = str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log_entry = f"[{now}] {message}"
    print(log_entry)
    send_message(BOT_LOGS_CHAT_ID, log_entry)

def file_already_uploaded(filename):
    """Verifica se um arquivo já existe no Nextcloud."""
    res = requests.head(f"{nextcloud_upload_path}/{filename}")
    return res.status_code == 200

def upload_file(filename, file_content):
    """Faz o upload de um arquivo para o Nextcloud."""
    res = requests.put(f"{nextcloud_upload_path}/{filename}", data=file_content, timeout=300) # Timeout grande para uploads
    res.raise_for_status()

# --- LÓGICA PRINCIPAL DE PROCESSAMENTO ---

def process_update(update):
    """Processa uma única atualização (mensagem) recebida pelo bot."""
    message = update.get("message")
    if not message:
        return

    message_id = message["message_id"]
    date = message["date"]
    chat_id = message["chat"]["id"]
    sender = message["from"].get("username") or message["from"].get("first_name", "Anonimo")
    safe_sender = re.sub(r'[\\/*?:"<>|]', "", sender)

    media = message.get("video") or message.get("document") or (message.get("photo")[-1] if message.get("photo") else None)

    if not media:
        if message.get("text") == "/start":
            log_message(f"[/START] Novo usuário: @{sender} no chat {chat_id}")
            send_message(chat_id, "Olá! Sou o bot de upload do IGF2025. Apenas envie suas fotos, vídeos ou documentos no grupo e eu os salvarei.")
        return

    log_message(f"[MÍDIA] Mídia recebida de @{sender} no chat {chat_id}")

    file_id = media["file_id"]
    media_file_name = media.get("file_name", "")
    file_name_base = f"{date}-{safe_sender}-{message_id}"
    file_name = f"{file_name_base}-{media_file_name}" if media_file_name else file_name_base

    try:
        file_path = get_file_path(file_id)

        if not re.search(r'\.\w+$', file_name) and "." in file_path:
            extension = os.path.splitext(file_path)[-1]
            file_name = f"{file_name}{extension}"

        if file_already_uploaded(file_name):
            log_message(f"==> ARQUIVO JÁ EXISTE: '{file_name}' de @{sender}. Pulando.")
            react_to_message(chat_id, message_id, "👍") 
            return
        
        log_message(f"==> Baixando arquivo: {file_path}")
        file_content = download_file(file_path)

        log_message(f"==> Fazendo upload como: '{file_name}'")
        upload_file(file_name, file_content)
        
        log_message(f"==> SUCESSO! Arquivo '{file_name}' de @{sender} foi salvo.")
        react_to_message(chat_id, message_id, "🎉") 

    except HTTPError as e:
        error_msg = f"==> ERRO HTTP ao processar arquivo de @{sender}: {e.response.status_code}"
        if e.response.status_code == 400:
            error_msg = f"==> ERRO (ARQUIVO GRANDE): Arquivo de @{sender}."
        log_message(error_msg)
        react_to_message(chat_id, message_id, "😢") 
    except Exception as e:
        log_message(f"==> ERRO INESPERADO ao processar arquivo de @{sender}: {e}")
        react_to_message(chat_id, message_id, "🤯")

def main():
    """Função principal que inicia e mantém o bot rodando."""
    log_message("--- BOT INICIADO ---")
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

        except RequestException as e:
            log_message(f"ERRO DE REDE: {e}. Tentando novamente em 30 segundos.")
            time.sleep(30)
        except Exception as e:
            log_message(f"ERRO CRÍTICO NO LOOP PRINCIPAL: {e}. Aguardando 60 segundos.")
            time.sleep(60)

if __name__ == "__main__":
    main()