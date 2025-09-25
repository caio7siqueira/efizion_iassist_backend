import httpx
import logging
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request
from twilio.rest import Client

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
twilio_account_sid = os.getenv('TWILIO_ACCOUNT_SID')
twilio_auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')

if not all([supabase_url, supabase_key, twilio_account_sid, twilio_auth_token, twilio_whatsapp_number]):
    logger.error("Erro: Variáveis de ambiente ausentes")
    exit(1)

twilio_client = Client(twilio_account_sid, twilio_auth_token)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.form()
    logger.info(f"Webhook recebido: {dict(data)}")

    cliente_id = "00000000-0000-0000-0000-000000000001"
    entidade_id = "00000000-0000-0000-0000-000000000002"

    payload = {
        "query_text": "SELECT SUM((dados->>'valor_total')::numeric) AS valor FROM registros WHERE cliente_id = $1 AND entidade_id = $2",
        "param1": cliente_id,
        "param2": entidade_id
    }

    logger.info(f"Payload enviado: {payload}")
    response = httpx.post(
        f"{supabase_url}/rest/v1/rpc/execute_query",
        json=payload,
        headers={"Authorization": f"Bearer {supabase_key}", "apiKey": supabase_key}
    )

    logger.info(f"Resposta: {response.status_code} - {response.json()}")
    if response.status_code == 200:
        result = response.json()
        valor = result[0]["valor"]
        message_body = f"R${valor:,.2f}"  # Para usar no template
        logger.info("Sucesso! Resultado: %s", result)

        # Usar template de teste do sandbox
        message = twilio_client.messages.create(
            from_=twilio_whatsapp_number,
            to=data['From'],
            content_sid="HX8e1719f69f8c769ae4cf2ed83e4c2866",  # Template sample_issue_resolution
            content_variables='{"1": "Cliente", "2": "' + message_body + '"}'
        )
        logger.info(f"Resposta do Twilio: {message.sid} - Status: {message.status}")
        return {"status": "sucesso", "resultado": result}
    else:
        logger.error("Erro na API: %s - %s", response.status_code, response.json())
        return {"status": "error", "mensagem": response.json()}


@app.get("/test-query")
async def test_query():
    cliente_id = "00000000-0000-0000-0000-000000000001"
    entidade_id = "00000000-0000-0000-0000-000000000002"
    payload = {
        "query_text": "SELECT SUM((dados->>'valor_total')::numeric) AS valor FROM registros WHERE cliente_id = $1 AND entidade_id = $2",
        "param1": cliente_id,
        "param2": entidade_id
    }
    logger.info(f"Payload enviado: {payload}")
    response = httpx.post(
        f"{supabase_url}/rest/v1/rpc/execute_query",
        json=payload,
        headers={"Authorization": f"Bearer {supabase_key}", "apiKey": supabase_key}
    )
    logger.info(f"Resposta: {response.status_code} - {response.json()}")
    if response.status_code == 200:
        logger.info("Sucesso! Resultado: %s", response.json())
        return {"status": "sucesso", "resultado": response.json()}
    else:
        logger.error("Erro na API: %s - %s", response.status_code, response.json())
        return {"status": "error", "mensagem": response.json()}