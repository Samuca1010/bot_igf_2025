# Dockerfile (Versão Simplificada e Corrigida)

# 1. Imagem Base
FROM python:3.9-slim

# 2. Diretório de Trabalho
WORKDIR /app

# 3. Copiar o arquivo de dependências
COPY requirements.txt .

# 4. Instalar as Dependências (com a correção)
# Esta é a única linha de instalação, já com a flag que resolve o problema.
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt

# 5. Copiar o Código do Bot
COPY . .

# 6. Comando de Execução Final
CMD ["python3", "config_bot.py"]
