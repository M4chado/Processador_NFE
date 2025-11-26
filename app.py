import os
import fitz
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, jsonify
)
from supabase import create_client
from dotenv import load_dotenv
import google.generativeai as genai

from agentes import agente1, agente2, agente3

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

load_dotenv()

def get_supabase():
    """
    Recupera o cliente Supabase usando as chaves da sessão (prioridade) ou do .env.
    """
    url = session.get('SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = session.get('SUPABASE_KEY') or os.getenv('SUPABASE_KEY')
    
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"Erro ao conectar Supabase: {e}")
        return None

def configure_genai_session():
    """Configura a API do Gemini com a chave da sessão ou .env"""
    api_key = session.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

@app.before_request
def check_setup():
    """
    Middleware: Verifica se as chaves existem antes de cada requisição.
    Redireciona para /setup se não estiver configurado.
    """

    allowed_routes = ['setup', 'static', 'logout']
    if request.endpoint in allowed_routes:
        return

    supabase = get_supabase()
    has_gemini = session.get('GEMINI_API_KEY') or os.getenv('GEMINI_API_KEY')

    if not supabase or not has_gemini:
        return redirect(url_for('setup'))
    
    configure_genai_session()


REGRAS_DE_CLASSIFICACAO = {
    "INSUMOS AGRÍCOLAS": ["semente", "fertilizante", "defensivo", "agrícola", "corretivo", "herbicida", "fungicida", "inseticida", "adubo", "fert"],
    "MANUTENÇÃO E OPERAÇÃO": ["combustível", "diesel", "etanol", "gasolina", "lubrificante", "oleo", "graxa", "peça", "parafuso", "rolamento", "componente", "mecanico", "mecânica", "manutenção", "conserto", "reparo", "serviço mecânico", "pneu", "filtro", "correia", "bateria", "ferramenta", "utensílio", "equipamento de proteção", "tubo", "cano", "fixacoes", "din", "kit"],
    "RECURSOS HUMANOS": ["mão de obra", "temporária", "salário", "encargo", "folha de pagamento", "adiantamento"],
    "SERVIÇOS OPERACIONAIS": ["frete", "transporte", "logística", "colheita", "terceirizada", "secagem", "armazenagem", "silo", "pulverização", "aplicação"],
    "INFRAESTRUTURA E UTILIDADES": ["energia", "eletrica", "conta de luz", "arrendamento", "aluguel de terra", "construção", "reforma", "obra", "material de construção", "cimento", "areia", "brita", "hidráulico", "elétrico"],
    "ADMINISTRATIVAS": ["honorário", "contábil", "advocatício", "agronômico", "consultoria", "despesa bancária", "tarifa", "juro", "financeira"],
    "SEGUROS E PROTEÇÃO": ["seguro agrícola", "seguro de ativo", "seguro de máquina", "seguro de veículo", "seguro prestamista", "apólice"],
    "IMPOSTOS E TAXAS": ["itr", "iptu", "ipva", "incra", "ccir", "imposto", "taxa", "tributo"],
    "INVESTIMENTOS": ["aquisição de máquina", "aquisição de implemento", "compra de máquina", "trator", "colheitadeira", "aquisição de veículo", "compra de veículo", "caminhonete", "aquisição de imóvel", "compra de terra", "compra de fazenda", "infraestrutura rural", "investimento"]
}

def classificar_nota_fiscal(dados_da_nota):
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
            except (ValueError, TypeError):
                pass
    return dados_json

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

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        session['SUPABASE_URL'] = request.form.get('supabase_url')
        session['SUPABASE_KEY'] = request.form.get('supabase_key')
        session['GEMINI_API_KEY'] = request.form.get('gemini_key')
        
        if get_supabase() and configure_genai_session():
            flash('Sistema configurado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Erro ao conectar. Verifique as chaves.', 'error')
            
    return render_template('setup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('setup'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf_file' not in request.files:
        flash("Nenhum arquivo enviado.", "error")
        return redirect(url_for('index'))
    
    file = request.files['pdf_file']
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        flash("Por favor, selecione um arquivo PDF.", "error")
        return redirect(url_for('index'))

    texto_pdf = extrair_texto_de_pdf(file)
    if not texto_pdf:
        flash("Erro: Não foi possível ler o texto do PDF.", "error")
        return redirect(url_for('index'))
        
    json_extraido_str = agente1.extrair_dados_com_llm(texto_pdf)
    if not json_extraido_str:
        flash("Erro: Falha na comunicação com a API do Gemini.", "error")
        return redirect(url_for('index'))

    clean_json_str = json_extraido_str.strip().replace("```json", "").replace("```", "").strip()
    dados_json = None
    json_formatado_para_exibicao = f"O modelo não retornou um JSON válido. Resposta:\n{clean_json_str}"
    analise_db = None

    try:
        dados_json = json.loads(clean_json_str)
        dados_json = gerar_parcela_padrao(dados_json)
        categorias_da_despesa = classificar_nota_fiscal(dados_json)
        dados_json['classificacao_despesa'] = categorias_da_despesa

        supabase_client = get_supabase()
        analise_db = agente2.verificar_dados(supabase_client, dados_json)
        
        json_formatado_para_exibicao = json.dumps(dados_json, indent=4, ensure_ascii=False)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        flash(f"Ocorreu um erro inesperado: {e}", "error")
        return redirect(url_for('index'))

    return render_template('resultado.html', 
                           resultado_json=json_formatado_para_exibicao, 
                           dados_formatados=dados_json,
                           analise_db=analise_db)

@app.route('/salvar', methods=['POST'])
def salvar_dados():
    try:
        dados_json_str = request.form.get('dados_json_para_salvar')
        if not dados_json_str:
            flash("Erro: Nenhum dado recebido para salvar.", "error")
            return redirect(url_for('index'))
            
        dados_json = json.loads(dados_json_str)
        
        supabase_client = get_supabase()
        
        mensagem_sucesso = agente2.salvar_movimento(supabase_client, dados_json)
        flash(mensagem_sucesso, "success")

    except Exception as e:
        flash(f"Erro ao salvar: {e}", "error")

    return redirect(url_for('index'))

@app.route('/chat')
def chat_page():
    return render_template('chat.html')

@app.route('/ask', methods=['POST'])
def ask_agent():
    try:
        data = request.get_json()
        question = data.get('question')
        if not question:
            return jsonify({"error": "Nenhuma pergunta fornecida."}), 400

        supabase_client = get_supabase()
        answer = agente3.run_text_to_sql(supabase_client, question)
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/pessoas')
def view_pessoas():
    return render_template('pessoas.html')

@app.route('/api/pessoas', methods=['GET', 'POST', 'PUT'])
def api_pessoas():
    supabase = get_supabase()
    
    if request.method == 'GET':
        query = request.args.get('q', '').lower()
        tipo_filtro = request.args.get('tipo', '') 
        
        db_query = supabase.table('pessoas').select('*').eq('status', 'ATIVO')
        
        if tipo_filtro:
            db_query = db_query.eq('tipo', tipo_filtro)
        if query:
            db_query = db_query.ilike('razaosocial', f'%{query}%')
            
        result = db_query.order('razaosocial').execute()
        return jsonify(result.data)

    if request.method == 'POST':
        data = request.json
        data['status'] = 'ATIVO' 
        try:
            res = supabase.table('pessoas').insert(data).execute()
            return jsonify(res.data), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    if request.method == 'PUT':
        data = request.json
        p_id = data.get('idPessoas')
        if not p_id:
            return jsonify({'error': 'ID necessário'}), 400
        del data['idPessoas']
        
        try:
            res = supabase.table('pessoas').update(data).eq('idPessoas', p_id).execute()
            return jsonify(res.data), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400

@app.route('/api/pessoas/delete/<int:id>', methods=['DELETE'])
def delete_pessoa(id):
    supabase = get_supabase()
    try:
        res = supabase.table('pessoas').update({'status': 'INATIVO'}).eq('idPessoas', id).execute()
        return jsonify({'message': 'Registro inativado'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/classificacao')
def view_classificacao():
    return render_template('classificacao.html')

@app.route('/api/classificacao', methods=['GET', 'POST', 'PUT'])
def api_classificacao():
    supabase = get_supabase()
    
    if request.method == 'GET':
        query = request.args.get('q', '').lower()
        db_query = supabase.table('classificacao').select('*').eq('status', 'ATIVO')
        if query:
            db_query = db_query.ilike('descricao', f'%{query}%')
        result = db_query.order('descricao').execute()
        return jsonify(result.data)
    
    if request.method == 'POST':
        data = request.json
        data['status'] = 'ATIVO'
        try:
            res = supabase.table('classificacao').insert(data).execute()
            return jsonify(res.data), 201
        except Exception as e:
            return jsonify({'error': str(e)}), 400

    if request.method == 'PUT':
        data = request.json
        c_id = data.get('idClassificacao')
        del data['idClassificacao']
        try:
            res = supabase.table('classificacao').update(data).eq('idClassificacao', c_id).execute()
            return jsonify(res.data), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 400

@app.route('/api/classificacao/delete/<int:id>', methods=['DELETE'])
def delete_classificacao(id):
    supabase = get_supabase()
    try:
        supabase.table('classificacao').update({'status': 'INATIVO'}).eq('idClassificacao', id).execute()
        return jsonify({'message': 'Registro inativado'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')