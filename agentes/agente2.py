# agentes/agente2.py

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import json
import re

# Variável global para o cliente Supabase
supabase: Client = None

def configurar_agente_db():
    """
    Configura e retorna o cliente Supabase.
    """
    global supabase
    if supabase:
        return supabase

    try:
        load_dotenv()
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY não encontradas no .env")
            
        supabase = create_client(url, key)
        print("INFO: Agente DB (Supabase) configurado com sucesso.")
        return supabase
    except Exception as e:
        print(f"Erro fatal ao configurar o Supabase: {e}")
        raise

def formatar_data_para_db(data_str):
    """Converte data 'DD/MM/YYYY' para 'YYYY-MM-DD'."""
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    
def limpar_documento(doc):
    """Remove toda formatação (pontos, barras, traços) de um documento."""
    if not doc:
        return None
    return re.sub(r'[^0-9]', '', doc) # Remove tudo que não for um número

def verificar_dados(supabase_client: Client, dados_json: dict):
    """
    Verifica no banco se Fornecedor, Faturado e Classificação existem.
    """
    analise = {
        "fornecedor": {"status": "NÃO EXISTE", "id": None},
        "faturado": {"status": "NÃO EXISTE", "id": None},
        "classificacao": {"status": "NÃO EXISTE", "id": None}
    }

    lista_classificacao = dados_json.get("classificacao_despesa") or []
    classificacao_desc = lista_classificacao[0] if lista_classificacao else None

    try:
        # 1. Verificar Fornecedor (com sanitização)
        doc_fornecedor = limpar_documento(dados_json.get("fornecedor", {}).get("cnpj"))
        if doc_fornecedor:
            # Chama a tabela "pessoas" (minúscula)
            response = supabase_client.table("pessoas").select("idPessoas").eq("documento", doc_fornecedor).execute()
            if response.data:
                analise["fornecedor"]["status"] = f"EXISTE - ID: {response.data[0]['idPessoas']}"
                analise["fornecedor"]["id"] = response.data[0]['idPessoas']

        # 2. Verificar Faturado (com sanitização)
        doc_faturado = limpar_documento(dados_json.get("faturado", {}).get("cpf_cnpj"))
        if doc_faturado:
            # Chama a tabela "pessoas" (minúscula)
            response = supabase_client.table("pessoas").select("idPessoas").eq("documento", doc_faturado).execute()
            if response.data:
                analise["faturado"]["status"] = f"EXISTE - ID: {response.data[0]['idPessoas']}"
                analise["faturado"]["id"] = response.data[0]['idPessoas']

        # 3. Verificar Classificação
        if classificacao_desc:
            # Chama a tabela "classificacao" (minúscula)
            response = supabase_client.table("classificacao").select("idClassificacao").eq("tipo", "DESPESA").eq("descricao", classificacao_desc).execute()
            if response.data:
                analise["classificacao"]["status"] = f"EXISTE - ID: {response.data[0]['idClassificacao']}"
                analise["classificacao"]["id"] = response.data[0]['idClassificacao']

    except Exception as e:
        print(f"Erro ao verificar dados no Supabase: {e}")
    
    return analise

def salvar_movimento(supabase_client: Client, dados_json: dict):
    """
    Chama a função 'salvar_nota_fiscal_completa' no Supabase
    """
    try:
        lista_parcelas = dados_json.get("parcelas") or []
        lista_classificacao = dados_json.get("classificacao_despesa") or []
        classificacao_principal = lista_classificacao[0] if lista_classificacao else None

        # 1. Preparar os parâmetros (com sanitização)
        params = {
            "p_forn_razao": dados_json.get("fornecedor", {}).get("razao_social"),
            "p_forn_doc": limpar_documento(dados_json.get("fornecedor", {}).get("cnpj")),
            "p_fat_nome": dados_json.get("faturado", {}).get("nome_completo"),
            "p_fat_doc": limpar_documento(dados_json.get("faturado", {}).get("cpf_cnpj")),
            "p_class_desc": classificacao_principal,
            "p_mov_numnf": dados_json.get("numero_nota_fiscal"),
            "p_mov_emissao": formatar_data_para_db(dados_json.get("data_emissao")),
            "p_mov_valor_total": dados_json.get("valor_total"),
            "p_parcelas_json": None
        }
        
        parcelas_formatadas = []
        for p in lista_parcelas:
            p_copy = p.copy() 
            p_copy["data_vencimento"] = formatar_data_para_db(p.get("data_vencimento"))
            parcelas_formatadas.append(p_copy)
        
        params["p_parcelas_json"] = json.dumps(parcelas_formatadas)

        # 2. Chamar a função RPC
        response = supabase_client.rpc("salvar_nota_fiscal_completa", params).execute()
        
        return response.data
        
    except Exception as e:
        print(f"Erro ao salvar movimento: {e}")
        if hasattr(e, 'message'):
            return f"Erro no banco de dados: {e.message}"
        return f"Erro desconhecido ao salvar: {e}"