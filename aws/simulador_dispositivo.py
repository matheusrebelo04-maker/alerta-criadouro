#!/usr/bin/env python3
"""
Alerta Criadouro - simulador do aparelho do quintal
Global Solution 2026.2 - Plataformas, Serviços Cognitivos & Cloud Computing - FIAP 1TIAPZ
Matheus Rebelo (RM 570260), Felipe Olmos (RM 570946), Luiz Guilherme (RM 573486)

Faz o mesmo POST que o ESP32 faz: cada envio é um dia no quintal.
O aparelho mede o nível de água do potinho sentinela (HC-SR04), a temperatura
e a umidade (DHT22) e conta há quantos dias o potinho está com água.

Uso:
    export FUNCTION_URL="https://xxxx.lambda-url.us-east-1.on.aws"
    python3 simulador_dispositivo.py --cenario normal --dias 4
    python3 simulador_dispositivo.py --cenario risco --dias 7
    python3 simulador_dispositivo.py --invalida      # leitura com erro, para ver o 400 no log
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

# Quintais monitorados na cidade de São Paulo (só 3 casas decimais: o bairro, não a casa)
QUINTAIS = {
    "normal": ("esp32-quintal-002", -23.548, -46.585),   # Mooca
    "risco": ("esp32-quintal-001", -23.632, -46.736),    # Campo Limpo
}

RELATOS = {
    "normal": [
        "Virei os baldes e limpei a calha, ficou ótimo",
        "Passei no quintal agora e está tudo certo por aqui",
    ],
    "risco": [
        "Choveu forte hoje e o quintal ficou cheio de poças",
        "Choveu muito essa semana e tem água parada em todo canto do quintal",
        "Achei larvas no pratinho do vaso, estou com medo da dengue",
        "O vizinho está com dengue e aqui em casa ainda tem água acumulada",
    ],
}


def gerar_leitura(cenario, dia):
    """Monta a leitura de um dia. No cenário de risco a água chega no dia 1 e não seca mais."""
    if cenario == "normal":
        dias_agua = 0
        nivel = 0.0
        temperatura = random.uniform(21.0, 24.0)
        umidade = random.uniform(55.0, 66.0)
    else:
        dias_agua = dia - 1          # dia 1 a chuva enche o potinho, depois vai contando
        nivel = 0.0 if dias_agua == 0 else random.uniform(3.0, 4.5)
        temperatura = random.uniform(27.0, 31.0)
        umidade = random.uniform(74.0, 88.0)
    return dias_agua, round(nivel, 1), round(temperatura, 1), round(umidade, 1)


def enviar(url, payload, tempo_limite=30):
    corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    cabecalhos = {"Content-Type": "application/json", "User-Agent": "AlertaCriadouro-Simulador/1.0"}
    if os.environ.get("TOKEN_DISPOSITIVO"):
        cabecalhos["X-Token-Dispositivo"] = os.environ["TOKEN_DISPOSITIVO"]
    requisicao = urllib.request.Request(url.rstrip("/") + "/ocorrencias", data=corpo,
                                        headers=cabecalhos, method="POST")
    try:
        with urllib.request.urlopen(requisicao, timeout=tempo_limite) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        return erro.code, erro.read().decode("utf-8", "replace")
    except Exception as erro:
        return None, str(erro)


def main():
    p = argparse.ArgumentParser(description="Simulador do Alerta Criadouro")
    p.add_argument("--url", default=os.environ.get("FUNCTION_URL"), help="Function URL da Lambda")
    p.add_argument("--cenario", default="normal", choices=["normal", "risco"])
    p.add_argument("--dias", type=int, default=7, help="quantos dias simular (um envio por dia)")
    p.add_argument("--intervalo", type=float, default=2.0, help="segundos entre os envios")
    p.add_argument("--invalida", action="store_true", help="envia uma leitura com erro e sai")
    args = p.parse_args()

    if not args.url:
        print("Defina a Function URL: export FUNCTION_URL=https://....on.aws")
        sys.exit(1)

    if args.invalida:
        payload = {"dispositivo_id": "esp32-quintal-001", "metrica": "dias_agua_parada", "valor": "muitos"}
        status, resposta = enviar(args.url, payload)
        print(f"POST leitura com erro -> HTTP {status}")
        print(f"resposta: {resposta}")
        return

    dispositivo, lat, lon = QUINTAIS[args.cenario]
    inicio = datetime.now(timezone.utc) - timedelta(days=args.dias - 1)

    print(f"Aparelho ........: {dispositivo} (esp32 simulado)")
    print(f"Local ...........: {lat}, {lon} - São Paulo")
    print(f"Cenário .........: {args.cenario} / métrica dias_agua_parada")
    print(f"Destino .........: {args.url.rstrip('/')}/ocorrencias")
    print("-" * 72)

    for dia in range(1, args.dias + 1):
        dias_agua, nivel, temperatura, umidade = gerar_leitura(args.cenario, dia)
        payload = {
            "dispositivo_id": dispositivo,
            "tipo_dispositivo": "esp32",
            "latitude": lat,
            "longitude": lon,
            "metrica": "dias_agua_parada",
            "valor": dias_agua,
            "leituras": {"temperatura_c": temperatura, "umidade_pct": umidade, "nivel_agua_cm": nivel},
            "medido_em": (inicio + timedelta(days=dia - 1)).isoformat(timespec="seconds"),
        }
        # o relato é o texto da família que vai para a IA (nem todo dia tem)
        if dia == 1:
            payload["relato"] = RELATOS[args.cenario][0]
        elif dia == args.dias or random.random() < 0.4:
            payload["relato"] = random.choice(RELATOS[args.cenario][1:])

        status, resposta = enviar(args.url, payload)
        print(f"[dia {dia}] água há {dias_agua} dia(s) | {temperatura} °C | {umidade}% | "
              f"nível {nivel} cm -> HTTP {status}")
        if isinstance(resposta, dict):
            aviso = "  << ALERTA PARA A FAMÍLIA" if resposta.get("alerta") else ""
            print(f"         id={resposta.get('id')} risco={resposta.get('nivel_risco')} "
                  f"sentimento={resposta.get('sentimento')} confianca={resposta.get('confianca')}{aviso}")
        else:
            print(f"         resposta: {resposta}")

        if dia < args.dias:
            time.sleep(args.intervalo)

    print("-" * 72)
    print("Fim do envio. As leituras estão no CloudWatch Logs e na tabela ocorrencias do RDS.")


if __name__ == "__main__":
    main()
