import os
import logging
from datetime import datetime
from enviar_whatsapp import enviar_whatsapp

# Caminho do arquivo de log
LOG_FILE = "logs/logs_erros.log"

# Número do administrador (quem vai receber os alertas)
ADMIN_WHATSAPP = "+556292782150"

# Configurar logging para gravar em arquivo
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def registrar_erro(msg):
    timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    
    # Grava no arquivo de log
    logging.error(log_msg)

    # Só envia alerta via WhatsApp se for produção
    if os.getenv("ENV") == "PROD":
        try:
            enviar_whatsapp(ADMIN_WHATSAPP, f"⚠️ *Erro no MeuGPT*\n\n{msg}")
        except Exception as e:
            logging.error(f"Falha ao enviar erro por WhatsApp: {e}")