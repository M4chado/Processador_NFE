# agentes/agente1.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

def configurar_agente():
    """
    Carrega as variáveis de ambiente e configura a API do Gemini.
    Levanta um erro se a chave não for encontrada.
    """
    try:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("A chave GEMINI_API_KEY não foi encontrada no arquivo .env")
        genai.configure(api_key=api_key)
        print("INFO: Agente Gemini configurado com sucesso.")
    except Exception as e:
        print(f"Erro fatal ao configurar a API do Gemini: {e}")
        # Propaga o erro para que a aplicação principal possa parar
        raise 

def extrair_dados_com_llm(texto_da_nota):
    """Envia o texto para o Gemini e pede para extrair os dados na estrutura JSON definida."""
    
    # Nota: A configuração (genai.configure) deve ter sido chamada
    # antes desta função (ex: no início da aplicação).
    
    generation_config = {"temperature": 0.1}
    model = genai.GenerativeModel(model_name="gemini-2.5-flash", generation_config=generation_config)
    
    prompt = f"""
    Sua tarefa é ser um especialista em extração de dados de notas fiscais.
    Analise o texto da nota fiscal abaixo e retorne um objeto JSON VÁLIDO contendo os campos especificados.
    Sua resposta deve ser APENAS o JSON, sem nenhum texto, explicação, ou formatação de markdown como ```json.
    A estrutura do JSON deve ser exatamente a seguinte:
    {{
      "fornecedor": {{"razao_social": "string", "nome_fantasia": "string", "cnpj": "string"}},
      "faturado": {{"nome_completo": "string", "cpf_cnpj": "string"}},
      "numero_nota_fiscal": "string", "data_emissao": "string", "valor_total": "float",
      "produtos": [{{"descricao": "string", "quantidade": "integer", "valor_unitario": "float"}}],
      "parcelas": [{{"numero_parcela": "integer", "data_vencimento": "string", "valor_parcela": "float"}}]
    }}
    Se uma informação não for encontrada no texto, retorne null para o campo correspondente. Se a nota não detalhar as parcelas, retorne uma lista vazia para o campo "parcelas".
    Texto da Nota Fiscal para análise:
    ---
    {texto_da_nota}
    ---
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API do Gemini: {e}")
        return None