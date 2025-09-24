from dotenv import load_dotenv
import os
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from supabase import create_client, Client
from twilio.rest import Client as TwilioClient
from openai import OpenAI
import time
from typing import Dict, Any

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

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
openai_client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

# Função de interpretação com IA
def interpretar_mensagem(mensagem: str) -> Dict[str, Any]:
    prompt = """
    Você é um assistente que interpreta mensagens de gestores e extrai filtros para consulta de indicadores.
    Sua tarefa é:
    1. Identificar a intenção (ex.: consultar vendas, lucros, produto mais vendido).
    2. Extrair filtros como data (ex.: '2023-10'), loja (ex.: 'Loja A'), produto (ex.: 'Camiseta').
    3. Retornar um JSON com os campos: tipo_consulta, indicador_nome, filtros (contendo data, loja, produto, se aplicável).

    Exemplo de saída:
    ```json
    {
        "tipo_consulta": "indicador",
        "indicador_nome": "total_vendas",
        "filtros": {
            "data": "2023-10",
            "loja": "Loja A",
            "produto": "Camiseta"
        }
    }
    ```

    Mensagem recebida: "{}"
    Retorne o JSON correspondente.
    """.format(mensagem)
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )
        conteudo = response.choices[0].message.content
        return json.loads(conteudo)
    except json.JSONDecodeError:
        logger.error(f"Erro ao parsear JSON da OpenAI: {conteudo}")
        return {"tipo_consulta": "erro", "indicador_nome": "", "filtros": {}}
    except Exception as e:
        logger.error(f"Erro ao interpretar mensagem: {e}")
        return {"tipo_consulta": "erro", "indicador_nome": "", "filtros": {}}

# Função para executar indicadores dinâmicos
def executar_indicador(cliente_id: str, indicador_nome: str, filtros: Dict[str, str]) -> str:
    try:
        # Buscar indicador na tabela indicadores
        indicador = supabase.table("indicadores").select("logica, filtros_padrao") \
            .eq("cliente_id", cliente_id) \
            .eq("nome", indicador_nome).single().execute()
        
        if not indicador.data:
            return f"❌ Indicador '{indicador_nome}' não encontrado."
        
        logica_sql = indicador.data["logica"]
        filtros_padrao = indicador.data["filtros_padrao"] or {}
        
        # Validar filtros recebidos contra filtros permitidos
        filtros_validos = {k: v for k, v in filtros.items() if k in filtros_padrao}
        
        # Construir consulta SQL com filtros
        query_params = {"cliente_id": cliente_id}
        where_clauses = []
        
        for filtro, valor in filtros_validos.items():
            # Sanitizar filtros para evitar SQL injection
            if filtro in ["data", "loja", "produto"]:
                where_clauses.append(f"dados->>'{filtro}' = :{filtro}")
                query_params[filtro] = valor
        
        # Montar consulta SQL
        query = logica_sql
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # Executar consulta via RPC (assumindo que existe uma função RPC 'execute_query')
        result = supabase.rpc("execute_query", {"query": query, "params": query_params}).execute()
        
        if not result.data:
            return "📉 Nenhuma dado encontrado para os filtros fornecidos."
        
        # Formatando o resultado (exemplo simples, ajustar conforme lógica do indicador)
        total = sum(row.get("valor", 0) for row in result.data)
        return f"📊 Resultado do indicador '{indicador_nome}': R$ {total:.2f}"
    
    except Exception as e:
        logger.error(f"Erro ao executar indicador '{indicador_nome}': {e}")
        return "❌ Erro ao processar a consulta."

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    start_time = time.time()
    logger.info("Recebendo webhook do WhatsApp")
    
    try:
        form = await request.form()
        mensagem = form.get("Body", "").strip()
        numero = form.get("From", "").replace("whatsapp:", "")
        
        if not mensagem or not numero:
            logger.warning("Mensagem ou número inválidos")
            raise HTTPException(status_code=400, detail="Mensagem ou número ausentes")
        
        # Verificar gestor
        gestor = supabase.table("gestores").select("cliente_id") \
            .eq("telefone_whatsapp", numero).single().execute()
        
        if not gestor.data:
            resposta = "Gestor não autorizado."
        else:
            cliente_id = gestor.data["cliente_id"]
            # Configurar RLS
            supabase.rpc("set_config", {"key": "gestor.telefone", "value": numero}).execute()
            
            # Interpretar mensagem
            resultado = interpretar_mensagem(mensagem)
            if resultado.get("tipo_consulta") == "erro":
                resposta = "❓ Não entendi sua solicitação."
            elif resultado.get("tipo_consulta") == "indicador":
                # Executar indicador dinâmico
                resposta = executar_indicador(
                    cliente_id, 
                    resultado.get("indicador_nome", ""), 
                    resultado.get("filtros", {})
                )
            else:
                resposta = (
                    "❓ Comando não reconhecido.\n"
                    "Envie algo como:\n"
                    "- 'total de vendas hoje'\n"
                    "- 'produto mais vendido na Loja A'"
                )
        
        # Enviar resposta via Twilio
        twilio_client.messages.create(
            body=resposta,
            from_=TWILIO_NUMBER,
            to=f"whatsapp:{numero}"
        )
        logger.info(f"Webhook processado em {time.time() - start_time:.2f} segundos")
        return {"status": "mensagem enviada", "resposta": resposta}
    
    except Exception as e:
        logger.error(f"Erro no webhook: {e}")
        raise HTTPException(status_code=500, detail="Erro interno no servidor")
