"""
Alerta Criadouro - teste local da Lambda, sem AWS
Finge o banco (pg8000) e a Hugging Face para conferir as rotas e o log antes de publicar.
Uso: python3 teste_local.py
"""
import json
import logging
import os
import sys
import types


# banco falso: devolve um id novo a cada INSERT
class Cursor:
    proximo_id = 0

    def execute(self, sql, parametros=None):
        self.sql = sql

    def fetchone(self):
        Cursor.proximo_id += 1
        return (Cursor.proximo_id, "2026-11-06 15:20:00+00")

    def fetchall(self):
        return []


class Conexao:
    def cursor(self):
        return Cursor()

    def commit(self):
        pass

    def close(self):
        pass


falso = types.ModuleType("pg8000")
falso.connect = lambda **kw: Conexao()
sys.modules["pg8000"] = falso

os.environ.update(DB_HOST="rds.local", DB_NAME="alertacriadouro", DB_USER="postgres",
                  DB_PASSWORD="teste", HF_TOKEN="teste")
logging.basicConfig(level=logging.INFO, format="%(levelname)s\t%(message)s", stream=sys.stdout)

import lambda_function as fn  # noqa: E402


# IA falsa: relato com palavra de preocupação vira negative
def analisar_falso(texto):
    if not texto:
        return None, None
    if any(p in texto.lower() for p in ("larva", "medo", "dengue", "parada")):
        return "negative", 0.9312
    return "neutral", 0.8017


fn.analisar_relato = analisar_falso


def evento(metodo, caminho, corpo=None):
    return {"rawPath": caminho, "requestContext": {"http": {"method": metodo}},
            "body": json.dumps(corpo, ensure_ascii=False) if corpo is not None else None}


casos = [
    ("GET", "/health", None),
    ("POST", "/ocorrencias", {"dispositivo_id": "esp32-quintal-002", "tipo_dispositivo": "esp32",
                              "metrica": "dias_agua_parada", "valor": 0,
                              "leituras": {"temperatura_c": 22.4, "umidade_pct": 61.0, "nivel_agua_cm": 0}}),
    ("POST", "/ocorrencias", {"dispositivo_id": "esp32-quintal-001", "tipo_dispositivo": "esp32",
                              "metrica": "dias_agua_parada", "valor": 2,
                              "leituras": {"temperatura_c": 28.1, "umidade_pct": 80.2, "nivel_agua_cm": 3.6},
                              "relato": "Achei larvas no pratinho do vaso, estou com medo da dengue"}),
    ("POST", "/ocorrencias", {"dispositivo_id": "esp32-quintal-001", "tipo_dispositivo": "esp32",
                              "metrica": "dias_agua_parada", "valor": 3,
                              "leituras": {"temperatura_c": 29.5, "umidade_pct": 83.0, "nivel_agua_cm": 3.9}}),
    ("POST", "/ocorrencias", {"dispositivo_id": "esp32-quintal-001", "metrica": "dias_agua_parada",
                              "valor": "muitos"}),
    ("POST", "/ocorrencias", {"dispositivo_id": "esp32-quintal-001"}),
]

for metodo, caminho, corpo in casos:
    print(f"\n===== {metodo} {caminho} =====")
    r = fn.lambda_handler(evento(metodo, caminho, corpo), None)
    print(f"RESPOSTA {r['statusCode']} {r['body']}")
