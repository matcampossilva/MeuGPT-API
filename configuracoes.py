import os
from dotenv import load_dotenv

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
WHATSAPP_FROM = 'whatsapp:+14155238886'

EMAIL_REMETENTE = os.getenv('EMAIL_REMETENTE')
SENHA_REMETENTE = os.getenv('SENHA_REMETENTE')

GOOGLE_SHEETS_URL = 'https://script.google.com/macros/s/AKfycbyyChxdjQiNv8jmJEI--6vamvK6VSqWAZ0bh2gl0ky-vjsus0fYxjdQtHFj8vbHlSjP/exec'
