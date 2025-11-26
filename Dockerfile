# 1. Imagem Base: Começamos com uma imagem oficial do Python.
# A versão 'slim' é mais leve, o que é ótimo.
FROM python:3.11-slim

# 2. Diretório de Trabalho: Criamos uma pasta /app dentro do contêiner para nosso projeto.
WORKDIR /app

# 3. Copiando e Instalando Dependências:
# Copiamos primeeiro o requirements.txt para aproveitar o cache do Docker.
# Se este arquivo não mudar, o Docker não reinstala tudo de novo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiando o Código do Projeto:
# Agora, copiamos todos os outros arquivos (app.py, static/, templates/) para dentro do /app.
COPY . .

# 5. Expondo a Porta:
# Informamos ao Docker que nossa aplicação Flask rodará na porta 5000.
EXPOSE 5000

# 6. Comando de Execução:
# Este é o comando que será executado quando o contêiner iniciar.
# Usamos "flask run" e o host 0.0.0.0 para permitir acesso externo ao contêiner.
CMD ["flask", "run", "--host=0.0.0.0"]