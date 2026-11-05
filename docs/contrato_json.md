# Contrato JSON do Alerta Criadouro

Global Solution 2026.2 - FIAP - Tecnólogo em IA - turma 1TIAPZ

- Matheus Rebelo da Silva de Jesus - RM 570260
- Felipe Olmos - RM 570946
- Luiz Guilherme - RM 573486

Este é o formato da mensagem que o dispositivo manda a cada leitura. É o mesmo JSON para todas as partes do projeto: o ESP32 no Wokwi (AICSS), a API em Flask (Computational Thinking with Python) e a função Lambda na AWS (Cloud). Assim o sistema é um só.

## Exemplo de mensagem

```json
{
  "dispositivo_id": "esp32-quintal-001",
  "tipo_dispositivo": "esp32",
  "latitude": -23.541,
  "longitude": -46.471,
  "metrica": "dias_agua_parada",
  "valor": 3,
  "relato": "Choveu ontem e o pratinho do vaso encheu de novo",
  "medido_em": "2026-11-06T14:30:00-03:00",
  "leituras": {
    "temperatura_c": 29.4,
    "umidade_pct": 78.0,
    "distancia_cm": 7.5,
    "nivel_agua_cm": 4.5
  },
  "status_sensores": {
    "temperatura": "ALERTA",
    "umidade": "ALERTA",
    "agua": "ALERTA"
  },
  "status_local": "ALERTA"
}
```

## O que é cada campo

| Campo | Tipo | Obrigatório | O que é |
|---|---|---|---|
| dispositivo_id | texto | sim | Nome do aparelho instalado na casa |
| tipo_dispositivo | texto | não | esp32, simulador ou app |
| latitude / longitude | número | não | Posição aproximada, só com 3 casas decimais (mostra o bairro, não a casa exata) |
| metrica | texto | sim | Sempre "dias_agua_parada" |
| valor | número | sim | Há quantos dias o potinho sentinela está com água. 0 = seco |
| relato | texto | não | O que a família escreveu no app, se escreveu algo |
| medido_em | data e hora | não | Hora da leitura no aparelho (se não vier, a API usa a hora em que recebeu) |
| leituras | objeto | não | Valores dos sensores: temperatura (°C), umidade do ar (%), distância do ultrassônico até a água (cm) e altura da água no potinho (cm) |
| status_sensores | objeto | não | OK ou ALERTA de cada sensor, calculado no próprio ESP32 |
| status_local | texto | não | Estado que o LED está mostrando: OK, ATENCAO ou ALERTA |

Os três campos obrigatórios (dispositivo_id, metrica e valor) são os mesmos que o enunciado da AWS pede. Os outros completam a leitura para o relatório do AICSS e a API em Python.

## Limiares de cada sensor

| Sensor | OK | ALERTA | Por quê |
|---|---|---|---|
| Temperatura (DHT22) | abaixo de 25 °C | 25 °C ou mais | Entre 25 e 30 °C a larva do Aedes se desenvolve mais rápido |
| Umidade (DHT22) | abaixo de 70% | 70% ou mais | Ar úmido ajuda o mosquito adulto a sobreviver e os ovos a não secarem |
| Água no potinho (HC-SR04) | menos de 1 cm de água | 1 cm de água ou mais | Pouca água já basta para o mosquito pôr ovos |

O potinho tem 12 cm do sensor até o fundo. A altura da água é: nivel_agua_cm = 12 - distancia_cm.

## Estados do dispositivo

| Estado | LED | Buzzer | Regra | Na API da AWS |
|---|---|---|---|---|
| OK | verde | desligado | Potinho seco | normal |
| ATENCAO | amarelo | um bipe curto | Tem água, mas ainda não chegou no ponto de alerta | atencao |
| ALERTA | vermelho | bipes repetidos | Água há 3 dias ou mais com calor e umidade altos, ou água há 5 dias ou mais em qualquer clima | critico |

Por que 3 e 5 dias: o ovo vira mosquito em cerca de 10 dias, e mais rápido no calor. Avisar no 3º dia (ou no 5º, quando o clima está mais frio) dá tempo de a família esvaziar os recipientes antes da larva virar mosquito.

No protótipo do Wokwi não dá para esperar dias de verdade. Por isso 1 dia vale 10 segundos na simulação. No aparelho real seria 1 dia de verdade.

## Respostas da API

Leitura aceita (HTTP 201):

```json
{
  "id": 12,
  "dispositivo_id": "esp32-quintal-001",
  "metrica": "dias_agua_parada",
  "valor": 3,
  "nivel_risco": "critico",
  "status": "ALERTA",
  "alerta": true
}
```

Leitura recusada por faltar campo ou por valor errado (HTTP 400):

```json
{
  "erro": "campos obrigatorios ausentes",
  "campos": ["valor"]
}
```

## Segurança

O dispositivo manda junto um cabeçalho `X-Token-Dispositivo`. Sem ele a API responde 401. O token fica guardado em variável de ambiente, nunca escrito no código. Isso é explicado no relatório de Cybersecurity.
