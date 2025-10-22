# app.py

import os
import fitz
import json
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
# Importações do Gemini foram movidas para o agente
from datetime import datetime
from dateutil.relativedelta import relativedelta # Para manipulação de datas

# --- Importação do novo agente ---
from agentes import agente1
from agentes import agente2

# Inicializa a aplicação Flask
app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(24)

# --- INÍCIO: MOTOR DE REGRAS DE CLASSIFICAÇÃO ---
# (Seu código de regras permanece inalterado)
REGRAS_DE_CLASSIFICACAO = {
    "INSUMOS AGRÍCOLAS": [
        "semente", "fertilizante", "defensivo", "agrícola", "corretivo", 
        "herbicida", "fungicida", "inseticida", "adubo", "fert"
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

def gerar_parcela_padrao(dados_json):
    """Verifica se há parcelas; se não houver, cria uma parcela única com vencimento em 1 mês."""
    if not dados_json.get('parcelas'):
        data_emissao_str = dados_json.get('data_emissao')
        valor_total = dados_json.get('valor_total')

        if data_emissao_str and valor_total is not None:
            try:
                data_emissao = datetime.strptime(data_emissao_str, "%d/%m/%Y")
                data_vencimento = data_emissao + relativedelta(months=1)
                data_vencimento_str = data_vencimento.strftime("%d/%m/%Y")

                dados_json['parcelas'] = [{
                    "numero_parcela": 1,
                    "data_vencimento": data_vencimento_str,
                    "valor_parcela": float(valor_total)
                }]
                print("INFO: Nenhuma parcela encontrada na extração. Gerando parcela padrão.")
            except (ValueError, TypeError) as e:
                print(f"AVISO: Não foi possível gerar parcela padrão. Dados de origem inválidos. Erro: {e}")
    
    return dados_json

# --- Configuração do Agente Gemini ---
# Agora chamamos a função de configuração do nosso módulo de agente
try:
    agente1.configurar_agente()
    supabase_client = agente2.configurar_agente_db()
except Exception as e:
    # Se a configuração falhar (ex: sem API key), a aplicação não deve iniciar.
    print(f"Falha crítica ao iniciar o agente de IA. A aplicação será encerrada. Erro: {e}")
    exit()

def extrair_texto_de_pdf(pdf_file_stream):
    """Extrai o texto de um stream de arquivo PDF."""
    try:
        documento = fitz.open(stream=pdf_file_stream.read(), filetype="pdf")
        texto_completo = ""
        for pagina in documento:
            texto_completo += pagina.get_text()
        return texto_completo
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
        return None

# A função extrair_dados_com_llm() foi movida para agentes/agente1.py

@app.route('/')
def index():
    """Renderiza a página inicial."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Recebe o PDF, processa e retorna a página com os resultados."""
    if 'pdf_file' not in request.files:
        flash("Nenhum arquivo enviado.", "error")
        return redirect(url_for('index'))
    
    file = request.files['pdf_file']
    
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        flash("Por favor, selecione um arquivo PDF.", "error")
        return redirect(url_for('index'))

    # 1. Extração do texto
    texto_pdf = extrair_texto_de_pdf(file)
    if not texto_pdf:
        flash("Erro: Não foi possível ler o texto do PDF.", "error")
        return redirect(url_for('index'))
        
    # 2. Extração dos dados com LLM (Agente 1)
    json_extraido_str = agente1.extrair_dados_com_llm(texto_pdf)
    if not json_extraido_str:
        flash("Erro: Falha na comunicação com a API do Gemini.", "error")
        return redirect(url_for('index'))

    # 3. Limpeza e processamento do JSON
    clean_json_str = json_extraido_str.strip().replace("```json", "").replace("```", "").strip()

    dados_json = None
    json_formatado_para_exibicao = f"O modelo não retornou um JSON válido. Resposta recebida:\n\n{clean_json_str}"
    analise_db = None

    try:
        dados_json = json.loads(clean_json_str)
        
        # 4. Gerar parcela padrão, se necessário
        dados_json = gerar_parcela_padrao(dados_json)

        # 5. Classificar a despesa com base nos dados
        categorias_da_despesa = classificar_nota_fiscal(dados_json)
        dados_json['classificacao_despesa'] = categorias_da_despesa

        # 6. VERIFICAR DADOS NO BANCO (Agente 2 - Verificação)
        analise_db = agente2.verificar_dados(supabase_client, dados_json)
        
        # 7. Gerar o JSON formatado para exibição, agora com todas as alterações
        json_formatado_para_exibicao = json.dumps(dados_json, indent=4, ensure_ascii=False)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", "error")
        return redirect(url_for('index'))

    # 8. Renderiza a PÁGINA DE RESULTADO com os dados
    return render_template('resultado.html', 
                           resultado_json=json_formatado_para_exibicao, 
                           dados_formatados=dados_json,
                           analise_db=analise_db)

@app.route('/salvar', methods=['POST'])
def salvar_dados():
    """
    Recebe os dados extraídos (via formulário oculto) e 
    chama o Agente 2 para salvar no banco de dados.
    """
    try:
        dados_json_str = request.form.get('dados_json_para_salvar')
        
        if not dados_json_str:
            flash("Erro: Nenhum dado recebido para salvar.", "error")
            return redirect(url_for('index'))
            
        dados_json = json.loads(dados_json_str)

        # Chama o Agente 2 para executar a função de salvamento
        mensagem_sucesso = agente2.salvar_movimento(supabase_client, dados_json)
        
        flash(mensagem_sucesso, "success") # Mostra "Registro lançado com sucesso."

    except Exception as e:
        flash(f"Erro ao salvar: {e}", "error")

    # Após salvar (ou falhar), volta para a página inicial de upload
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)