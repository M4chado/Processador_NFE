import os
import fitz  # PyMuPDF
import json
from flask import Flask, render_template, request
import google.generativeai as genai
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Inicializa a aplicação Flask
app = Flask(__name__)

# --- INÍCIO: MOTOR DE REGRAS DE CLASSIFICAÇÃO ---
# Centralizamos as regras aqui para fácil manutenção.
# Usamos palavras-chave em minúsculo e singular para facilitar a correspondência.
REGRAS_DE_CLASSIFICACAO = {
    "INSUMOS AGRÍCOLAS": [
        "semente", "fertilizante", "defensivo", "agrícola", "corretivo", 
        "herbicida", "fungicida", "inseticida", "adubo"
    ],
    "MANUTENÇÃO E OPERAÇÃO": [
        "combustível", "diesel", "etanol", "gasolina", "lubrificante", "oleo", "graxa",
        "peça", "parafuso", "rolamento", "componente", "mecanico", "mecânica",
        "manutenção", "conserto", "reparo", "serviço mecânico",
        "pneu", "filtro", "correia", "bateria",
        "ferramenta", "utensílio", "equipamento de proteção"
    ],
    "RECURSOS HUMANOS": [
        "mão de obra", "temporária", "salário", "encargo", "folha de pagamento", "adiantamento"
    ],
    "SERVIÇOS OPERACIONAIS": [
        "frete", "transporte", "logística",
        "colheita", "terceirizada",
        "secagem", "armazenagem", "silo",
        "pulverização", "aplicação"
    ],
    "INFRAESTRUTURA E UTILIDADES": [
        "energia", "eletrica", "conta de luz",
        "arrendamento", "aluguel de terra",
        "construção", "reforma", "obra",
        "material de construção", "cimento", "areia", "brita", "hidráulico", "elétrico"
    ],
    "ADMINISTRATIVAS": [
        "honorário", "contábil", "advocatício", "agronômico", "consultoria",
        "despesa bancária", "tarifa", "juro", "financeira"
    ],
    "SEGUROS E PROTEÇÃO": [
        "seguro agrícola", "seguro de ativo", "seguro de máquina", "seguro de veículo", "seguro prestamista", "apólice"
    ],
    "IMPOSTOS E TAXAS": [
        "itr", "iptu", "ipva", "incra", "ccir", "imposto", "taxa", "tributo"
    ],
    "INVESTIMENTOS": [
        "aquisição de máquina", "aquisição de implemento", "compra de máquina", "trator", "colheitadeira",
        "aquisição de veículo", "compra de veículo", "caminhonete",
        "aquisição de imóvel", "compra de terra", "compra de fazenda",
        "infraestrutura rural", "investimento"
    ]
}

def classificar_nota_fiscal(dados_da_nota):
    """
    Analisa os produtos da nota e atribui categorias de despesa com base nas regras.
    Retorna uma lista de categorias únicas encontradas.
    """
    categorias_encontradas = set()
    
    if not dados_da_nota or 'produtos' not in dados_da_nota or not isinstance(dados_da_nota['produtos'], list):
        return []

    for produto in dados_da_nota['produtos']:
        if 'descricao' in produto and produto['descricao']:
            descricao_produto = produto['descricao'].lower()
            
            for categoria, palavras_chave in REGRAS_DE_CLASSIFICACAO.items():
                if any(palavra in descricao_produto for palavra in palavras_chave):
                    categorias_encontradas.add(categoria)
                    
    return list(categorias_encontradas)
# --- FIM: MOTOR DE REGRAS DE CLASSIFICAÇÃO ---


# Configura a API do Google Gemini
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("A chave GEMINI_API_KEY não foi encontrada no arquivo .env")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"Erro fatal ao configurar a API do Gemini: {e}")
    exit()

def extrair_texto_de_pdf(pdf_file_stream):
    try:
        documento = fitz.open(stream=pdf_file_stream.read(), filetype="pdf")
        texto_completo = ""
        for pagina in documento:
            texto_completo += pagina.get_text()
        return texto_completo
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
        return None

def extrair_dados_com_llm(texto_da_nota):
    generation_config = {"temperature": 0.1}
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", generation_config=generation_config)
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

@app.route('/')
def index():
    return render_template('index.html', resultado_json=None, dados_formatados=None)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf_file' not in request.files:
        return render_template('index.html', resultado_json=None, dados_formatados=None)
    
    file = request.files['pdf_file']
    
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return render_template('index.html', resultado_json=None, dados_formatados=None)

    texto_pdf = extrair_texto_de_pdf(file)
    if not texto_pdf:
        return "Erro: Não foi possível ler o texto do PDF.", 400
        
    json_extraido_str = extrair_dados_com_llm(texto_pdf)
    if not json_extraido_str:
        return "Erro: Falha na comunicação com a API do Gemini.", 500

    clean_json_str = json_extraido_str.strip().replace("```json", "").replace("```", "").strip()

    dados_json = None
    json_formatado_para_exibicao = f"O modelo não retornou um JSON válido. Resposta recebida:\n\n{clean_json_str}"
    
    try:
        dados_json = json.loads(clean_json_str)
        
        # 1. Classificar a despesa com base nos dados extraídos
        categorias_da_despesa = classificar_nota_fiscal(dados_json)
        
        # 2. Adicionar a classificação ao nosso objeto de dados
        dados_json['classificacao_despesa'] = categorias_da_despesa
        
        # 3. Gerar o JSON formatado para exibição, agora com o novo campo
        json_formatado_para_exibicao = json.dumps(dados_json, indent=4, ensure_ascii=False)

    except json.JSONDecodeError:
        pass

    return render_template('index.html', resultado_json=json_formatado_para_exibicao, dados_formatados=dados_json)

if __name__ == '__main__':
    app.run(debug=True)