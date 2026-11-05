# Alerta Criadouro

Global Solution 2026.2 - FIAP - Tecnólogo em Inteligência Artificial - turma 1TIAPZ
Tema: CitizenTech - da cidade ao campo, tecnologia para a vida cotidiana

**Integrantes**

- Matheus Rebelo da Silva de Jesus - RM 570260
- Felipe Olmos - RM 570946
- Luiz Guilherme - RM 573486

## A ideia

Cerca de 75% dos focos do mosquito da dengue ficam dentro das casas. A larva vira mosquito em uns 10 dias, e quase sempre a família só percebe o problema quando alguém já ficou doente.

O Alerta Criadouro é um aparelhinho com ESP32 para famílias que moram em casas com quintal na cidade de São Paulo. Ele fica na parede da área de serviço e fica de olho num "potinho sentinela" deixado no quintal. Quando o potinho junta água e fica assim por dias, com calor e ar úmido, o aparelho acende a luz vermelha e apita. É o lembrete para a família dar uma volta no quintal e esvaziar o que estiver com água.

O aparelho não enxerga cada vaso da casa. Ele avisa a hora certa de olhar.

## Pastas

| Pasta | O que tem | Matéria |
|---|---|---|
| dispositivo | Código do ESP32 e projeto do Wokwi | AI Computer Systems & Sensors |
| api | API em Flask que recebe o JSON e grava em CSV | Computational Thinking with Python e Cybersecurity |
| aws | Função Lambda, tabela do banco e simulador | Plataformas, Serviços Cognitivos & Cloud |
| dados | Base do InfoDengue (Fiocruz) da cidade de São Paulo | todas |
| estatistica | Código .py e base .csv | Statistical Computing |
| ml | Notebook de Machine Learning | Machine Learning & Modelling |
| redes_neurais | Notebook da rede LSTM | Redes Neurais e Deep Learning |
| docs | Contrato JSON e relatórios | todas |

## ODS

- ODS 3 - Saúde e bem-estar: menos casos de dengue dentro de casa.
- ODS 11 - Cidades e comunidades sustentáveis: prevenção no bairro, junto com os agentes de saúde.
- ODS 13 - Ação contra a mudança do clima: o calor e a chuva aumentam a dengue, e o aparelho usa esses dados.
- ODS 6 - Água potável e saneamento (complemento): cuidado com a água parada.
