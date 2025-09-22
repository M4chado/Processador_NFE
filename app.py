import os
import fitz  # PyMuPDF
import json
from flask import Flask, render_template, request, redirect, url_for
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

try:
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print(f"Erro ao configurar a API do Gemini. Verifique sua chave no arquivo .env. Erro: {e}")
    exit()

app = Flask(__name__)

def extrair_texto_de_pdf(pdf_file):
    """Extrai o texto de um arquivo PDF."""
    try:
        documento = fitz.open(stream=pdf_file.read(), filetype="pdf")
        texto_completo = ""
        for pagina in documento:
            texto_completo += pagina.get_text()
        return texto_completo
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
        return None

def extrair_dados_com_llm(texto_da_nota):
    """
    Envia o texto para o Gemini e pede para extrair os dados na nova estrutura JSON.
    ESTA É A FUNÇÃO QUE FOI ALTERADA.
    """
    
    generation_config = {"temperature": 0.1} # Temperatura baixa para menos "criatividade" e mais precisão
    
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config) # Usando o Flash que é rápido e eficiente
    
    # --- INÍCIO DA MUDANÇA CRÍTICA: O NOVO PROMPT ---
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
    # --- FIM DA MUDANÇA CRÍTICA ---

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Erro ao chamar a API do Gemini: {e}")
        return None

# Nenhuma mudança daqui para baixo
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf_file' not in request.files:
        return redirect(url_for('index'))
    
    file = request.files['pdf_file']
    
    if file.filename == '' or not file.filename.endswith('.pdf'):
        return redirect(url_for('index'))

    texto_pdf = extrair_texto_de_pdf(file)
    if not texto_pdf:
        return "Erro: Não foi possível ler o texto do PDF.", 400
        
    json_extraido_str = extrair_dados_com_llm(texto_pdf)
    if not json_extraido_str:
        return "Erro: Falha na comunicação com a API do Gemini.", 500

    clean_json_str = json_extraido_str.strip().replace("```json", "").replace("```", "").strip()

    try:
        dados_json = json.loads(clean_json_str)
        json_formatado = json.dumps(dados_json, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        json_formatado = f"O modelo não retornou um JSON válido. Resposta recebida:\n\n{clean_json_str}"

    return render_template('resultado.html', resultado_json=json_formatado)

if __name__ == '__main__':
    app.run(debug=True)