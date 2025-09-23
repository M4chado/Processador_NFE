# Processador e Classificador de Notas Fiscais com IA

## Descrição do Projeto

Esta aplicação web foi desenvolvida como um projeto acadêmico para processar arquivos de Nota Fiscal Eletrônica (NF-e) em formato PDF. A ferramenta utiliza a API generativa do Google (Gemini) para extrair dados estruturados da nota, como informações do fornecedor, produtos e valores.

Além da extração, o sistema possui uma lógica de classificação de despesas que analisa os produtos da nota e atribui categorias pré-definidas (ex: "MANUTENÇÃO E OPERAÇÃO", "INSUMOS AGRÍCOLAS"), automatizando parte do processo de contas a pagar.

A aplicação foi totalmente containerizada com Docker para garantir a portabilidade e facilitar a execução em qualquer ambiente.

## Tecnologias Utilizadas
- **Backend:** Python 3.11, Flask
- **Inteligência Artificial:** Google Gemini API
- **Frontend:** HTML5, CSS3, JavaScript
- **Processamento de PDF:** PyMuPDF
- **Containerização:** Docker

## Pré-requisitos
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução na máquina.

## Como Executar o Projeto (Passo a Passo)

Siga os passos abaixo para construir e executar a aplicação.

**1. Descompacte o Projeto**
   - Descompacte o arquivo `.zip` enviado em uma pasta de sua preferência.

**2. Configure a Chave de API**
   - Dentro da pasta do projeto, você encontrará um arquivo chamado `.env.example`.
   - Renomeie este arquivo para `.env`.
   - Abra o novo arquivo `.env` com um editor de texto e substitua o texto de placeholder pela sua chave de API do Google Gemini. O arquivo deve ficar assim:
     ```
     GEMINI_API_KEY="AIzaSy...sua_chave_completa_aqui..."
     ```

**3. Construa a Imagem Docker**
   - Abra um terminal (PowerShell, CMD, ou Terminal) e navegue até a pasta raiz do projeto.
   - Execute o seguinte comando para que o Docker construa a imagem da aplicação. Este processo pode levar alguns minutos.
     ```bash
     docker build -t processador-notas .
     ```

**4. Execute o Contêiner Docker**
   - Após a imagem ser construída com sucesso, execute o comando abaixo para iniciar o contêiner. A aplicação estará pronta para uso.
     ```bash
     docker run -p 5000:5000 --env-file .env processador-notas
     ```

**5. Acesse a Aplicação**
   - Abra seu navegador de internet e acesse o seguinte endereço:
     [http://localhost:5000](http://localhost:5000)

## Para Parar a Aplicação
- Volte ao terminal onde o comando `docker run` está executando e pressione as teclas `Ctrl + C`.