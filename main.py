from fastapi import FastAPI
from supabase import create_client, Client
from dotenv import load_dotenv
from twilio.rest import Client as TwilioClient
from fastapi import Request
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


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    
    try:
        form = await request.form()
    except Exception as e:
        return {"error": f"Erro ao processar formulário: {str(e)}"}

    form = await request.form()
    mensagem_recebida = form.get("Body", "").strip().lower()
    numero_remetente = form.get("From")

    cliente = supabase.table("clientes").select("id").eq("telefone", TELEFONE_CLIENTE).single().execute()
    if not cliente.data:
        resposta = "Cliente não encontrado."
    else:
        cliente_id = cliente.data["id"]

        if "total" in mensagem_recebida:
            vendas = supabase.table("vendas") \
                .select("valor", "qtd") \
                .eq("cliente_id", cliente_id) \
                .gte("data", "today") \
                .execute()
            total = sum(v["valor"] * v["qtd"] for v in vendas.data)
            resposta = f"📊 Total vendido hoje: R$ {total:.2f}"

        elif "produto" in mensagem_recebida:
            vendas = supabase.table("vendas") \
                .select("produto", "qtd") \
                .eq("cliente_id", cliente_id) \
                .execute()

            if not vendas.data:
                resposta = "Nenhuma venda registrada."
            else:
                produto_quantidade = {}
                for venda in vendas.data:
                    produto = venda["produto"]
                    qtd = venda["qtd"]
                    produto_quantidade[produto] = produto_quantidade.get(produto, 0) + qtd

                produto_mais_vendido = max(produto_quantidade, key=produto_quantidade.get)
                total_vendido = produto_quantidade[produto_mais_vendido]
                resposta = f"🏆 Produto mais vendido:\n{produto_mais_vendido} – {total_vendido} unidades"

        elif "estoque" in mensagem_recebida:
            estoque = supabase.table("estoque") \
                .select("produto", "qtd_atual", "qtd_minima") \
                .eq("cliente_id", cliente_id) \
                .lt("qtd_atual", "qtd_minima") \
                .execute()

            if not estoque.data:
                resposta = "✅ Todos os produtos estão com estoque acima do mínimo."
            else:
                lista = "\n".join([f"{item['produto']}: {item['qtd_atual']} unid (mínimo: {item['qtd_minima']})" for item in estoque.data])
                resposta = f"⚠️ Produtos com estoque baixo:\n{lista}"

        else:
            resposta = "❓ Comando não reconhecido.\nEnvie:\n- 'total' para ver vendas de hoje\n- 'produto' para ver o mais vendido\n- 'estoque' para ver produtos críticos"

    # Enviar resposta via WhatsApp
    twilio_client.messages.create(
        body=resposta,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=numero_remetente
    )

    return {"status": "mensagem processada"}




