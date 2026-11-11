# Alerta Criadouro

Global Solution 2026.2 - FIAP - Tecnólogo em Inteligência Artificial - turma 1TIAPZ
Tema: CitizenTech - da cidade ao campo, tecnologia para a vida cotidiana

**Integrantes**

- Matheus Rebelo - RM 570260
- Felipe Olmos - RM 570946
- Luiz Guilherme - RM 573486

## A ideia

Cerca de 75% dos focos do mosquito da dengue ficam dentro das casas. Em 2024 o Brasil teve o pior ano da história, com 6,48 milhões de casos prováveis. A larva vira mosquito em uns 10 dias, e quase sempre a família só percebe o problema quando alguém já ficou doente.

O Alerta Criadouro é um aparelho com ESP32 para famílias que moram em casas com quintal na cidade de São Paulo. Ele fica na parede da área de serviço e observa um "potinho sentinela" deixado no quintal, com uma tela fina na boca para o mosquito não pôr ovos nele. Quando o potinho junta água e fica assim por dias, com calor e ar úmido, o aparelho acende a luz vermelha e apita. É o lembrete para a família dar uma volta no quintal e esvaziar o que estiver com água.

O aparelho não enxerga cada vaso da casa. Ele avisa a hora certa de olhar.

## Como o sistema funciona

```
ESP32 no quintal (DHT22 + HC-SR04)  ->  LED e buzzer avisam na hora
        |
        |  JSON
        v
API em Python (Flask)  ->  valida, classifica e grava em CSV
        |
        |  GET /previsao
        v
Machine Learning (risco da próxima semana) + LSTM (casos das próximas 4 semanas)
        |
        v
Mensagem para a família
```

- **OK (verde):** potinho seco.
- **ATENÇÃO (amarelo):** tem água parada.
- **ALERTA (vermelho):** água há 3 dias ou mais com calor e umidade altos, ou há 5 dias em qualquer clima.

Os modelos de IA usam dados reais do InfoDengue (Fiocruz e FGV) da cidade de São Paulo, de 2015 a 2025.

## Pastas

| Pasta | O que tem | Matéria |
|---|---|---|
| [dispositivo](dispositivo) | Código do ESP32 e circuito do Wokwi | AI Computer Systems & Sensors |
| [api](api) | API em Flask: recebe o JSON, grava em CSV, protege com token, limite de requisições e logs, e faz a previsão integrada | Computational Thinking with Python e Cybersecurity |
| [dados](dados) | Base do InfoDengue da cidade de São Paulo | todas |
| [estatistica](estatistica) | Código .py, base .csv, relatório e gráficos | Statistical Computing with R & Python |
| [ml](ml) | Notebook, slides e modelo do risco da próxima semana | Machine Learning & Modelling |
| [redes_neurais](redes_neurais) | Notebook, documentação e rede LSTM dos casos das próximas semanas | Redes Neurais, Deep Learning e Algoritmos Genéticos |
| [aws](aws) | Lambda, tabela do RDS, simulador do aparelho, relatório e prints da nuvem | Plataformas, Serviços Cognitivos & Cloud Computing |
| [docs](docs) | Relatórios de AICSS, Python e Cybersecurity, contrato JSON e evidências | todas |

## Resultados

- **Dispositivo:** testado no Wokwi nos três estados (OK, ATENÇÃO e ALERTA), enviando o JSON para a API pela internet.
- **API:** 3 cenários de teste, validação dos dados (400), token do aparelho (401) e limite de requisições (429), com log de tudo.
- **Estatística:** a temperatura média da semana tem correlação de 0,41 com o Rt da dengue. A regressão logística acerta 69,8% das semanas em que a dengue está se espalhando.
- **Machine Learning:** Random Forest ajustado com F1 de 0,954 no teste (2023 a 2025). Ele avisou o risco alto do começo da epidemia de 2024 uma semana antes do que repetir o nível atual.
- **Redes Neurais:** LSTM com erro menor que o modelo ingênuo nas 4 semanas à frente, ligada à API pela rota GET /previsao.
- **AWS:** Lambda com Function URL recebe as leituras, registra tudo no CloudWatch, lê o relato da família com um modelo da Hugging Face e grava no RDS PostgreSQL. No teste, 10 leituras gravadas e alerta crítico a partir do dia 4.

## Como rodar

**API no Google Colab:** abra [api/rodar_api_colab.ipynb](https://colab.research.google.com/github/matheusrebelo04-maker/alerta-criadouro/blob/main/api/rodar_api_colab.ipynb) e clique em Ambiente de execução > Executar tudo. O notebook liga a API, abre um endereço público, roda os testes e mostra a previsão integrada.

**Dispositivo:** crie um projeto ESP32 em [wokwi.com](https://wokwi.com), cole o `sketch.ino` e o `diagram.json`, adicione as bibliotecas do `libraries.txt` e troque o endereço da API pelo que o Colab mostrar.

**API no computador:**

```
cd api
pip install flask requests pandas numpy scikit-learn tensorflow
export TOKEN_DISPOSITIVO=ac-quintal-001-demo
python app.py
```

## ODS

- **ODS 3 - Saúde e bem-estar:** menos casos de dengue dentro de casa.
- **ODS 11 - Cidades e comunidades sustentáveis:** prevenção no bairro, junto com os agentes de saúde e a prefeitura.
- **ODS 13 - Ação contra a mudança do clima:** o calor e a chuva aumentam a dengue, e o projeto usa esses dados.
- **ODS 6 - Água potável e saneamento (complemento):** cuidado com a água parada.
