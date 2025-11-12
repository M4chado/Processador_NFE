import google.generativeai as genai
from supabase import Client
import json
import re

def get_database_schema():
    """
    Define e retorna o esquema simplificado do banco de dados (o "R" do RAG).
    Ajuste as tabelas e colunas conforme o seu banco Supabase.
    """
    return """
    -- Tabela de Pessoas (Fornecedores e Faturados)
    CREATE TABLE pessoas (
      "idPessoas" INT PRIMARY KEY,
      documento VARCHAR(20) UNIQUE, -- (CPF ou CNPJ)
      "razao_social" VARCHAR(255),
      "nome_completo" VARCHAR(255)
    );

    -- Tabela de Classificações de Despesa
    CREATE TABLE classificacao (
      "idClassificacao" INT PRIMARY KEY,
      descricao VARCHAR(100),
      tipo VARCHAR(20) -- (ex: 'DESPESA')
    );

    -- Tabela Principal de Movimentos (Notas Fiscais)
    CREATE TABLE movimentos (
      idMovimento INT PRIMARY KEY,
      "numero_nota_fiscal" VARCHAR(50),
      data_emissao DATE,
      valor_total FLOAT,
      "idFornecedor" INT, -- FK para pessoas."idPessoas"
      "idFaturado" INT, -- FK para pessoas."idPessoas"
      "idClassificacao" INT -- FK para classificacao."idClassificacao"
    );

    -- Tabela de Parcelas
    CREATE TABLE parcelas (
      idParcela INT PRIMARY KEY,
      "idMovimento" INT, -- FK para movimentos.idMovimento
      numero_parcela INT,
      data_vencimento DATE,
      valor_parcela FLOAT
    );
    """

def is_query_safe(sql_query: str) -> bool:
    """
    Verificação de segurança BÁSICA (Cliente-Side).
    Impede que o LLM tente modificar ou apagar dados.
    """
    query = sql_query.strip().upper()
    
    if not query.startswith("SELECT"):
        return False
        
    blocked_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE", "INSERT", "GRANT", "REVOKE"]
    
    for keyword in blocked_keywords:
        if keyword in query:
            return False
            
    return True

def run_text_to_sql(supabase_client: Client, user_question: str):
    """
    Orquestra o fluxo completo de Text-to-SQL.
    """
    try:
        schema = get_database_schema()
        
        # --- ETAPA 1: Gerar a Consulta SQL ---
        
        prompt_sql_generator = f"""
        Você é um especialista em PostgreSQL. Sua tarefa é gerar uma consulta SQL para responder a uma pergunta do usuário,
        com base no seguinte esquema de banco de dados:

        Esquema:
        {schema}

        Pergunta do Usuário:
        "{user_question}"

        Regras:
        1. Gere APENAS a consulta SQL, sem explicações, sem ```sql.
        2. Certifique-se de que a consulta seja compatível com PostgreSQL.
        3. Use os nomes de colunas e tabelas exatamente como estão no esquema (incluindo aspas, se houver).
        4. Sempre use a data de hoje (para perguntas como "este mês") como: CURRENT_DATE
        5. Se a pergunta for sobre "MANUTENÇÃO E OPERAÇÃO", use a tabela 'classificacao' para encontrar o ID (ex: WHERE descricao = 'MANUTENÇÃO E OPERAÇÃO').

        Consulta SQL:
        """
        
        # Usando o modelo que sabemos que funciona para sua API
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response_sql = model.generate_content(prompt_sql_generator)
        sql_query = response_sql.text.strip().replace("```sql", "").replace("```", "")
        
        print(f"DEBUG (Agente 3): SQL Gerado: {sql_query}")

        # --- ETAPA 2: Verificar e Executar a Consulta (CORRIGIDO) ---
        
        if not is_query_safe(sql_query):
            print(f"DEBUG (Agente 3): Consulta bloqueada por segurança: {sql_query}")
            return "Desculpe, sua pergunta resultou em uma consulta que não é permitida por motivos de segurança."

        # CORREÇÃO: Em vez de .sql(), usamos .rpc() para chamar a função que criamos no Supabase
        # O nome da função é 'run_safe_query' e o parâmetro é 'query_text'
        data_result = supabase_client.rpc(
            "run_safe_query", 
            {"query_text": sql_query}
        ).execute()
        
        raw_data = data_result.data
        
        print(f"DEBUG (Agente 3): Dados recebidos do DB: {raw_data}")

        # --- ETAPA 3: Gerar Resposta Amigável ---
        
        prompt_answer_generator = f"""
        Você é um assistente financeiro prestativo.
        A pergunta original do usuário foi: "{user_question}"
        
        Os dados obtidos do banco de dados (em formato JSON) são:
        {json.dumps(raw_data)}

        Sua tarefa é usar os dados para dar uma resposta completa e amigável ao usuário, em português.
        - Se os dados forem um número (como um SUM ou COUNT), responda diretamente (ex: "O valor total é R$ 123,45.").
        - Se os dados estiverem vazios ou forem '[]', diga que não encontrou informações.
        - Se for uma lista de coisas, resuma-as.
        - Não mencione "SQL" ou "banco de dados" na sua resposta.

        Resposta Final:
        """
        
        response_final = model.generate_content(prompt_answer_generator)
        return response_final.text

    except Exception as e:
        print(f"Erro no Agente 3 (Text-to-SQL): {e}")
        # Tenta extrair a mensagem de erro específica do Supabase, se houver
        if hasattr(e, 'message'):
            return f"Desculpe, ocorreu um erro ao processar sua pergunta: {e.message}"
        return f"Desculpe, ocorreu um erro ao processar sua pergunta: {e}"