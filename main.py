import httpx
import logging
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
if not supabase_url or not supabase_key:
    logger.error("Erro: SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY não estão definidos no .env")
    exit(1)


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.form()  # Twilio envia dados como form-data
    logger.info(f"Webhook recebido: {dict(data)}")

    cliente_id = "00000000-0000-0000-0000-000000000001"  # Substitua pela lógica real
    entidade_id = "00000000-0000-0000-0000-000000000002"  # Substitua pela lógica real

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