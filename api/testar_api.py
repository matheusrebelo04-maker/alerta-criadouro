# Alerta Criadouro - testes da API
# Global Solution 2026.2 - FIAP - 1TIAPZ
# Matheus Rebelo - RM 570260
# Felipe Olmos - RM 570946
# Luiz Guilherme - RM 573486
#
# Manda as mesmas mensagens que o ESP32 manda e mostra o que a API respondeu.
# Uso: python testar_api.py http://127.0.0.1:5000

import json
import os
import sys

import requests

URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:5000"
TOKEN = os.environ.get("TOKEN_DISPOSITIVO", "")
CABECALHO = {"X-Token-Dispositivo": TOKEN}


def leitura(dias, temperatura, umidade, distancia):
    return {
        "dispositivo_id": "esp32-quintal-001",
        "tipo_dispositivo": "esp32",
        "latitude": -23.541,
        "longitude": -46.471,
        "metrica": "dias_agua_parada",
        "valor": dias,
        "leituras": {
            "temperatura_c": temperatura,
            "umidade_pct": umidade,
            "distancia_cm": distancia,
        },
    }


def mostrar(titulo, resposta, enviado=None):
    print("=" * 60)
    print(titulo)
    if enviado is not None:
        print("Enviado:", json.dumps(enviado, ensure_ascii=False))
    print("HTTP", resposta.status_code)
    print("Resposta:", json.dumps(resposta.json(), ensure_ascii=False))


cenarios = [
    ("Cenario 1 - potinho seco (esperado OK)", leitura(0, 22.5, 60.0, 12.0)),
    ("Cenario 2 - agua parada ha 1 dia (esperado ATENCAO)", leitura(1, 27.0, 75.0, 8.0)),
    ("Cenario 3 - agua ha 3 dias com calor e umidade (esperado ALERTA)", leitura(3, 29.4, 78.0, 7.5)),
]
for titulo, corpo in cenarios:
    mostrar(titulo, requests.post(f"{URL}/leituras", json=corpo, headers=CABECALHO), corpo)

invalida = leitura(2, 150.0, 78.0, 7.5)
del invalida["valor"]
mostrar("Teste extra - leitura invalida (sem valor e temperatura absurda)",
        requests.post(f"{URL}/leituras", json=invalida, headers=CABECALHO), invalida)

mostrar("Teste extra - sem token do dispositivo",
        requests.post(f"{URL}/leituras", json=leitura(1, 27, 75, 8)))

mostrar("Consulta GET /leituras", requests.get(f"{URL}/leituras", headers=CABECALHO))
mostrar("Consulta GET /indicadores", requests.get(f"{URL}/indicadores", headers=CABECALHO))
