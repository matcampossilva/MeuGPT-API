# enviar_email.py
import smtplib
from email.mime.text import MIMEText
from configuracoes import EMAIL_REMETENTE, SENHA_REMETENTE

def enviar_email(destinatario, assunto, corpo):
    mensagem = MIMEText(corpo)
    mensagem['Subject'] = assunto
    mensagem['From'] = EMAIL_REMETENTE
    mensagem['To'] = destinatario

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as servidor:
            servidor.login(EMAIL_REMETENTE, SENHA_REMETENTE)
            servidor.sendmail(EMAIL_REMETENTE, destinatario, mensagem.as_string())
        print(f"✅ E-mail enviado com sucesso para {destinatario}.")
    except Exception as e:
        print(f"❌ Falha ao enviar email: {e}")

# Exemplo prático imediato:
if __name__ == "__main__":
    enviar_email("mat.campos.silva@gmail.com", "Teste Meu Conselheiro Financeiro", "Este é um teste de envio automático.")
