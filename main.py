from fastapi import FastAPI
from supabase import create_client, Client
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
import os

load_dotenv()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEFONE_CLIENTE = os.getenv("TELEFONE_CLIENTE")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
GESTOR_NUMBER = os.getenv("GESTOR_WHATSAPP_NUMBER")  # número do gestor

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

app = FastAPI()

@app.get("/vendas-hoje")
def vendas_hoje():
    cliente = supabase.table("clientes").select("id").eq("telefone", TELEFONE_CLIENTE).single().execute()
    if not cliente.data:
        return {"error": "Cliente não encontrado"}

    cliente_id = cliente.data["id"]

    vendas = supabase.table("vendas") \
        .select("valor", "qtd") \
        .eq("cliente_id", cliente_id) \
        .gte("data", "today") \
        .execute()

    total = sum(v["valor"] * v["qtd"] for v in vendas.data)

    mensagem = f"📊 Indicador de hoje:\nTotal vendido: R$ {total:.2f}"

    # Enviar via WhatsApp
    message = twilio_client.messages.create(
        body=mensagem,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=GESTOR_NUMBER
    )

    return {
        "total_vendido_hoje": total,
        "mensagem_enviada": mensagem,
        "sid": message.sid
    }
