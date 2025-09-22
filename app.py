import os
import fitz  # PyMuPDF
import json
from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (sua chave de API)
load_dotenv()

# Inicializa a aplicação Flask
app = Flask(__name__)

# Configura a API do Google Gemini com a chave do arquivo .env
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("A chave GEMINI_API_KEY não foi encontrada no arquivo .env")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"Erro fatal ao configurar a API do Gemini: {e}")
    exit()

def extrair_texto_de_pdf(pdf_file_stream):
    """Extrai o texto de um stream de arquivo PDF."""
    try:
        # Abre o arquivo PDF diretamente do stream em memória
        documento = fitz.open(stream=pdf_file_stream.read(), filetype="pdf")
        texto_completo = ""
        for pagina in documento:
            texto_completo += pagina.get_text()
        return texto_completo
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
        return None

def extrair_dados_com_llm(texto_da_nota):
    """Envia o texto para o Gemini e pede para extrair os dados na estrutura JSON definida."""
    
    # Configurações do modelo para respostas mais precisas e menos "criativas"
    generation_config = {"temperature": 0.1}
    
    # Usando o modelo Flash, que é rápido e eficiente para tarefas de extração
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config)
    
    # O prompt é a parte mais importante. Ele define o "contrato" com a IA.
    prompt = f"""
    Sua tarefa é ser um especialista em extração de dados de notas fiscais.
    Analise o texto da nota fiscal abaixo e retorne um objeto JSON VÁLIDO contendo os campos especificados.
    Sua resposta deve ser APENAS o JSON, sem nenhum texto, explicação, ou formatação de markdown como ```json.

    A estrutura do JSON deve ser exatamente a seguinte:
    {{
      "fornecedor": {{
        "razao_social": "string",
        "nome_fantasia": "string (se não houver, pode ser igual à razão social)",
        "cnpj": "string (formatado como XX.XXX.XXX/XXXX-XX)"
      }},
      "faturado": {{
        "nome_completo": "string",
        "cpf_cnpj": "string (formatado como XXX.XXX.XXX-XX ou CNPJ)"
      }},
      "numero_nota_fiscal": "string",
      "data_emissao": "string (formatado como DD/MM/AAAA)",
      "valor_total": "float (use ponto como separador decimal)",
      "produtos": [
        {{
          "descricao": "string",
          "quantidade": "integer",
          "valor_unitario": "float"
        }}
      ],
      "parcelas": [
        {{
          "numero_parcela": "integer",
          "data_vencimento": "string (formatado como DD/MM/AAAA)",
          "valor_parcela": "float"
        }}
      ]
    }}

    Se uma informação não for encontrada no texto, retorne null para o campo correspondente.

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

# Rota principal que exibe a página de upload pela primeira vez
@app.route('/')
def index():
    # Na primeira carga da página, não há resultados, então passamos None.
    return render_template('index.html', resultado_json=None, dados_formatados=None)

# Rota que recebe o arquivo, processa e exibe o resultado na mesma página
@app.route('/upload', methods=['POST'])
def upload_file():
    # Verifica se um arquivo foi enviado na requisição
    if 'pdf_file' not in request.files:
        return render_template('index.html', resultado_json=None, dados_formatados=None)
    
    file = request.files['pdf_file']
    
    # Verifica se o nome do arquivo é válido e se é um PDF
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return render_template('index.html', resultado_json=None, dados_formatados=None)

    # 1. Extrai o texto do PDF
    texto_pdf = extrair_texto_de_pdf(file)
    if not texto_pdf:
        return "Erro: Não foi possível ler o texto do PDF.", 400
        
    # 2. Envia o texto para o LLM (Gemini)
    json_extraido_str = extrair_dados_com_llm(texto_pdf)
    if not json_extraido_str:
        return "Erro: Falha na comunicação com a API do Gemini.", 500

    # 3. Limpa e processa a resposta JSON do modelo
    # Remove possíveis blocos de markdown que a IA possa adicionar
    clean_json_str = json_extraido_str.strip().replace("```json", "").replace("```", "").strip()

    dados_json = None
    json_formatado_para_exibicao = f"O modelo não retornou um JSON válido. Resposta recebida:\n\n{clean_json_str}"
    
    try:
        # Converte a string JSON em um objeto Python (dicionário)
        dados_json = json.loads(clean_json_str)
        # Converte o objeto Python de volta para uma string JSON formatada para exibição
        json_formatado_para_exibicao = json.dumps(dados_json, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        # Se houver um erro na conversão, a mensagem de erro já está na variável
        pass

    # 4. Renderiza a página 'index.html' novamente, agora com os dados do resultado
    # Passamos o JSON formatado (para a aba JSON) e o objeto Python (para a aba de Visualização)
    return render_template('index.html', resultado_json=json_formatado_para_exibicao, dados_formatados=dados_json)

# Inicia o servidor de desenvolvimento do Flask
if __name__ == '__main__':
    app.run(debug=True)