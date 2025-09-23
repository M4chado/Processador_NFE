# Processador de Notas Fiscais com IA

Este projeto utiliza Python, Flask e a API Gemini do Google para extrair e classificar dados de notas fiscais em formato PDF. O projeto está containerizado com Docker para fácil execução.

## Pré-requisitos

-   [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução.

## Como Rodar o Projeto

1.  **Configure a Chave de API:**
    -   Renomeie o arquivo `.env.example` para `.env`.
    -   Abra o arquivo `.env` e substitua `"COLOQUE_SUA_CHAVE_DA_API_GEMINI_AQUI"` pela sua chave de API válida do Google Gemini.

2.  **Construa a Imagem Docker:**
    -   Abra um terminal na pasta raiz deste projeto.
    -   Execute o seguinte comando para construir a imagem:
        ```bash
        docker build -t processador-notas .
        ```

3.  **Execute o Contêiner:**
    -   Após a construção da imagem, execute o seguinte comando para iniciar o contêiner:
        ```bash
        docker run -p 5000:5000 --env-file .env processador-notas
        ```

4.  **Acesse a Aplicação:**
    -   Abra seu navegador e acesse o endereço: [http://localhost:5000](http://localhost:5000)

## Para Parar a Aplicação

-   Volte ao terminal onde o comando `docker run` está executando e pressione `Ctrl + C`.