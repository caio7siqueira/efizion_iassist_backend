from dotenv import load_dotenv
import os

load_dotenv()

from fastapi import FastAPI, Request
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient
import openai

# Variáveis de ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicialização
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
twilio_client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)
openai.api_key = OPENAI_API_KEY

app = FastAPI()

# Função de interpretação com IA
def interpretar_mensagem(mensagem):
    prompt = f"""
    Você é um assistente que interpreta mensagens de gestores e extrai filtros para consulta de indicadores.
    Mensagem: "{mensagem}"
    Retorne um JSON com os campos: tipo_consulta, data, categoria_produto.
    """
    resposta = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    conteudo = resposta.choices[0].message.content
    try:
        return eval(conteudo)
    except:
        return {}

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    mensagem = form.get("Body", "").strip()
    numero = form.get("From", "").replace("whatsapp:", "")

    gestor = supabase.table("gestores").select("cliente_id").eq("telefone_whatsapp", numero).single().execute()
    if not gestor.data:
        resposta = "Gestor não autorizado."
    else:
        cliente_id = gestor.data["cliente_id"]
        supabase.rpc("set_config", {"key": "gestor.telefone", "value": numero})

        filtros = interpretar_mensagem(mensagem)
        registros = supabase.table("registros").select("dados").execute()

        if filtros.get("tipo_consulta") == "total_vendas":
            total = sum(r["dados"].get("valor_total", 0) for r in registros.data)
            resposta = f"📊 Total vendido: R$ {total:.2f}"

        elif filtros.get("tipo_consulta") == "mais_vendido":
            contagem = {}
            for r in registros.data:
                produto = r["dados"].get("categoria_produto")
                qtd = r["dados"].get("quantidade", 0)
                if produto:
                    contagem[produto] = contagem.get(produto, 0) + qtd
            if contagem:
                mais_vendido = max(contagem, key=contagem.get)
                resposta = f"🏆 Produto mais vendido: {mais_vendido} – {contagem[mais_vendido]} unidades"
            else:
                resposta = "Nenhuma venda registrada."

        else:
            resposta = (
                "❓ Comando não reconhecido.\n"
                "Envie algo como:\n"
                "- 'total de vendas hoje'\n"
                "- 'produto mais vendido'"
            )

    twilio_client.messages.create(
        body=resposta,
        from_=TWILIO_NUMBER,
        to=form.get("From")
    )
    return {"status": "mensagem enviada", "resposta": resposta}
