from fastapi import FastAPI
from supabase import create_client, Client
from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEFONE_CLIENTE = os.getenv("TELEFONE_CLIENTE")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
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
    return {"total_vendido_hoje": total}
