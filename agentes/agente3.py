import google.generativeai as genai
from supabase import Client
import json
import re

def get_database_schema():
    """
    [CORRIGIDO]
    Define e retorna o esquema do banco, com base na imagem do ERD fornecida.
    """
    return """
    -- Tabela de Pessoas (Fornecedores e Faturados)
    CREATE TABLE pessoas (
      "idPessoas" INT PRIMARY KEY,
      documento VARCHAR(20) UNIQUE,
      razaosocial VARCHAR(255),
      fantasia VARCHAR(255),
      tipo VARCHAR(20),
      status VARCHAR(20)
    );

    -- Tabela de Classificações de Despesa
    CREATE TABLE classificacao (
      "idClassificacao" INT PRIMARY KEY,
      descricao VARCHAR(100),
      tipo VARCHAR(20), -- (ex: 'DESPESA')
      status VARCHAR(20)
    );

    -- Tabela Principal de Movimentos (Notas Fiscais)
    CREATE TABLE movimentocontas (
      "idMovimentoContas" INT PRIMARY KEY,
      numeronotafiscal VARCHAR(50),
      dataemissao DATE,
      valortotal NUMERIC,
      "Pessoas_idFornecedor" INT, -- FK para pessoas."idPessoas"
      "Pessoas_idFaturado" INT, -- FK para pessoas."idPessoas"
      tipo VARCHAR(20),
      descricao TEXT,
      status VARCHAR(20)
    );

    -- Tabela de Parcelas
    CREATE TABLE parcelacontas (
      "idParcelaContas" INT PRIMARY KEY,
      datavencimento DATE,
      valorpago NUMERIC,
      valorsaldo NUMERIC,
      statusparcela VARCHAR(20),
      "MovimentoContas_idMovimentoContas" INT -- FK para movimentocontas."idMovimentoContas"
    );

    -- Tabela de Junção (Muitos-para-Muitos) entre Movimentos e Classificação
    CREATE TABLE movimentocontas_has_classificacao (
      "MovimentoContas_idMovimentoContas" INT, -- FK para movimentocontas
      "Classificacao_idClassificacao" INT -- FK para classificacao
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

        [REGRA IMPORTANTE DE JOIN]
        5. Para filtrar movimentos por uma 'classificacao' (ex: 'MANUTENÇÃO E OPERAÇÃO'), 
           você DEVE criar um JOIN triplo entre 'movimentocontas', 'movimentocontas_has_classificacao', e 'classificacao'.
           Exemplo de JOIN:
           ... FROM movimentocontas AS m
           JOIN movimentocontas_has_classificacao AS mhc ON m."idMovimentoContas" = mhc."MovimentoContas_idMovimentoContas"
           JOIN classificacao AS c ON mhc."Classificacao_idClassificacao" = c."idClassificacao"
           WHERE c.descricao = 'MANUTENÇÃO E OPERAÇÃO' ...

        Consulta SQL:
        """
        
        # Usando o modelo que sabemos que funciona para sua API
        model = genai.GenerativeModel("gemini-2.5-flash") 
        response_sql = model.generate_content(prompt_sql_generator)
        
        # --- Lógica robusta para limpar a resposta do LLM e extrair o SQL. ---
        
        raw_sql_response = response_sql.text.strip()
        sql_query = ""

        # Tentativa 1: Encontrar SQL dentro de um bloco de markdown ```sql
        sql_match = re.search(r"```sql\s*(.*?)\s*```", raw_sql_response, re.DOTALL | re.IGNORECASE)
        
        if sql_match:
            sql_query = sql_match.group(1).strip()
        else:
            # Tentativa 2: Se não houver markdown, encontrar o primeiro "SELECT"
            select_index = raw_sql_response.upper().find("SELECT")
            if select_index != -1:
                sql_query = raw_sql_response[select_index:].strip()
            else:
                sql_query = raw_sql_response

        sql_query = sql_query.replace("```", "").strip().rstrip(';')
        
        print(f"DEBUG (Agente 3): SQL Limpo e Gerado: {sql_query}")

        # --- ETAPA 2: Verificar e Executar a Consulta ---
        
        if not is_query_safe(sql_query):
            print(f"DEBUG (Agente 3): Consulta bloqueada por segurança: {sql_query}")
            return "Desculpe, sua pergunta resultou em uma consulta que não é permitida por motivos de segurança."

        # Chama a função RPC 'run_safe_query' que criamos no Supabase
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
        if hasattr(e, 'message'):
            return f"Desculpe, ocorreu um erro ao processar sua pergunta: {e.message}"
        return f"Desculpe, ocorreu um erro ao processar sua pergunta: {e}"