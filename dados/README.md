# Base de dados: InfoDengue - cidade de São Paulo

Global Solution 2026.2 - FIAP - 1TIAPZ
Matheus Rebelo (RM 570260), Felipe Olmos (RM 570946), Luiz Guilherme (RM 573486)

**Fonte:** InfoDengue, sistema de alerta da Fiocruz e da FGV, que junta as notificações de dengue do SINAN com dados de clima.
**Link usado:** https://info.dengue.mat.br/api/alertcity?geocode=3550308&disease=dengue&format=csv&ew_start=1&ew_end=53&ey_start=2015&ey_end=2025
**Arquivo:** infodengue_sp_2015_2025.csv (baixado em 05/11/2026)

São dados reais, públicos e oficiais. Cada linha é uma semana epidemiológica da cidade de São Paulo (código IBGE 3550308), de janeiro de 2015 até dezembro de 2025: 574 semanas e 30 colunas. O arquivo vem da semana mais nova para a mais antiga.

## Por que essa base

Ela junta, na mesma semana, o número de casos de dengue e o clima da cidade (temperatura e umidade). São justamente as coisas que o nosso aparelho mede no quintal. Assim dá para mostrar, com dados reais, que calor e umidade andam junto com a dengue, e treinar os modelos que dizem o risco da semana.

## Colunas que vamos usar

| Coluna | O que é |
|---|---|
| data_iniSE | Data do domingo em que começa a semana |
| SE | Semana epidemiológica (ano + número da semana, ex.: 202410) |
| casos | Casos notificados na semana |
| casos_est | Casos estimados (corrige o atraso das notificações) |
| p_inc100k | Casos por 100 mil habitantes |
| Rt | Número de reprodução (acima de 1 = a dengue está se espalhando) |
| nivel | Nível de alerta: 1 verde, 2 amarelo, 3 laranja, 4 vermelho |
| tempmin, tempmed, tempmax | Temperatura mínima, média e máxima da semana (°C) |
| umidmin, umidmed, umidmax | Umidade mínima, média e máxima da semana (%) |
| pop | População da cidade |
| receptivo | 1 quando o clima está favorável ao mosquito |
| transmissao | 1 quando há transmissão sustentada |

## Primeiras observações

- 2024 foi de longe o pior ano: 1.264.130 casos notificados só na cidade. 2025 vem em seguida, com 351.496.
- Das 574 semanas, 283 ficaram no nível 1 (verde), 66 no 2, 90 no 3 e 135 no 4 (vermelho).
- 13 semanas estão sem os dados de clima (tempmed, tempmax e umidades). Cada parte do projeto explica como tratou essas semanas.
- As colunas casprov_est, casprov_est_min, casprov_est_max e casconf vêm vazias e não são usadas.

## Hash de integridade

SHA-256 do arquivo infodengue_sp_2015_2025.csv:

`741ccfb2a01cf5d98614fcffd4ddfaf41a748b4b0549211435879c1bec97a03b`

Os notebooks de Machine Learning e de Redes Neurais calculam esse hash antes de treinar. Se o arquivo tiver sido alterado, o treino para. Isso protege os modelos de IA contra uma base adulterada (explicado no relatório de Cybersecurity).
