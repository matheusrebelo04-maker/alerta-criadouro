# Alerta Criadouro - API que recebe as leituras do dispositivo
# Global Solution 2026.2 - FIAP - 1TIAPZ
# Matheus Rebelo - RM 570260
# Felipe Olmos - RM 570946
# Luiz Guilherme - RM 573486
#
# Rotas:
#   GET  /health        - mostra se a API está no ar
#   POST /leituras      - recebe o JSON do ESP32, valida, classifica e grava no CSV
#   GET  /leituras      - lista as leituras gravadas
#   GET  /indicadores   - números calculados a partir das leituras
#   GET  /previsao      - risco da próxima semana (ML) + casos das próximas 4 semanas (LSTM)
#                         + status do quintal = mensagem final para a família

import csv
import logging
import os
import re
import time
from collections import defaultdict, deque
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

from regras import NIVEL_RISCO, classificar, nivel_agua

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_CSV = os.path.join(PASTA, "leituras.csv")
ARQUIVO_LOG = os.path.join(PASTA, "seguranca.log")
FUSO = ZoneInfo("America/Sao_Paulo")

# o token não fica no código: vem de variável de ambiente
TOKEN_DISPOSITIVO = os.environ.get("TOKEN_DISPOSITIVO")
LIMITE_POR_MINUTO = int(os.environ.get("LIMITE_POR_MINUTO", "20"))

COLUNAS_CSV = [
    "data_hora", "dispositivo_id", "temperatura_c", "umidade_pct", "distancia_cm",
    "nivel_agua_cm", "dias_agua_parada", "status", "nivel_risco", "alerta",
]

# só letras minúsculas, números e hífen (evita fórmula maliciosa no CSV)
PADRAO_ID = re.compile(r"^[a-z0-9-]{3,40}$")

# faixas aceitas para cada valor (fora disso a leitura é recusada)
FAIXAS = {
    "temperatura_c": (-10, 60),
    "umidade_pct": (0, 100),
    "distancia_cm": (0, 400),
}

app = Flask(__name__)
app.json.ensure_ascii = False   # acentos legíveis nas respostas

log = logging.getLogger("alerta_criadouro")
log.setLevel(logging.INFO)
if not log.handlers:
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    formato.converter = lambda *args: datetime.now(FUSO).timetuple()  # horário de São Paulo
    for destino in (logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"), logging.StreamHandler()):
        destino.setFormatter(formato)
        log.addHandler(destino)

# guarda o horário das últimas requisições de cada IP
requisicoes_por_ip = defaultdict(deque)


def ip_do_cliente():
    # atrás do túnel o IP real vem neste cabeçalho
    return request.headers.get("CF-Connecting-IP") or request.remote_addr or "desconhecido"


def passou_do_limite(ip):
    agora = time.time()
    fila = requisicoes_por_ip[ip]
    while fila and agora - fila[0] > 60:
        fila.popleft()
    if len(fila) >= LIMITE_POR_MINUTO:
        return True
    fila.append(agora)
    return False


def validar(dados):
    """Devolve a lista de problemas encontrados no JSON."""
    erros = []
    if not isinstance(dados, dict):
        return ["o corpo precisa ser um objeto JSON"]

    for campo in ("dispositivo_id", "metrica", "valor"):
        if dados.get(campo) is None:
            erros.append(f"campo obrigatorio ausente: {campo}")

    dispositivo = dados.get("dispositivo_id")
    if dispositivo is not None and (not isinstance(dispositivo, str) or not PADRAO_ID.match(dispositivo)):
        erros.append("dispositivo_id invalido (use so letras minusculas, numeros e hifen)")
    if dados.get("metrica") is not None and dados["metrica"] != "dias_agua_parada":
        erros.append("metrica precisa ser dias_agua_parada")

    valor = dados.get("valor")
    if valor is not None:
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            erros.append("valor precisa ser um numero")
        elif not 0 <= valor <= 365:
            erros.append("valor fora da faixa (0 a 365 dias)")

    leituras = dados.get("leituras", {})
    if not isinstance(leituras, dict):
        erros.append("leituras precisa ser um objeto")
        return erros
    for campo, (minimo, maximo) in FAIXAS.items():
        if campo not in leituras:
            continue
        numero = leituras[campo]
        if isinstance(numero, bool) or not isinstance(numero, (int, float)):
            erros.append(f"{campo} precisa ser um numero")
        elif not minimo <= numero <= maximo:
            erros.append(f"{campo} fora da faixa ({minimo} a {maximo})")
    return erros


def gravar_csv(linha):
    arquivo_novo = not os.path.exists(ARQUIVO_CSV)
    with open(ARQUIVO_CSV, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_CSV)
        if arquivo_novo:
            escritor.writeheader()
        escritor.writerow(linha)


def ler_csv():
    if not os.path.exists(ARQUIVO_CSV):
        return []
    with open(ARQUIVO_CSV, newline="", encoding="utf-8") as arquivo:
        return list(csv.DictReader(arquivo))


def token_valido():
    token = request.headers.get("X-Token-Dispositivo")
    return bool(TOKEN_DISPOSITIVO) and token == TOKEN_DISPOSITIVO


@app.get("/health")
def health():
    return jsonify({"status": "ok", "servico": "alerta-criadouro"})


@app.post("/leituras")
def receber_leitura():
    ip = ip_do_cliente()

    if passou_do_limite(ip):
        log.warning("BLOQUEADO por excesso de requisicoes ip=%s", ip)
        return jsonify({"erro": "muitas requisicoes, tente de novo em 1 minuto"}), 429

    if not token_valido():
        log.warning("RECUSADO token invalido ip=%s", ip)
        return jsonify({"erro": "token do dispositivo ausente ou invalido"}), 401

    dados = request.get_json(silent=True)
    if dados is None:
        log.warning("RECUSADO corpo nao e JSON ip=%s", ip)
        return jsonify({"erro": "corpo nao e um JSON valido"}), 400

    erros = validar(dados)
    if erros:
        log.warning("RECUSADO dados invalidos ip=%s erros=%s", ip, erros)
        return jsonify({"erro": "leitura recusada", "detalhes": erros}), 400

    leituras = dados.get("leituras", {})
    temperatura = leituras.get("temperatura_c")
    umidade = leituras.get("umidade_pct")
    distancia = leituras.get("distancia_cm")
    nivel = nivel_agua(distancia) if distancia is not None else leituras.get("nivel_agua_cm")
    dias = int(dados["valor"])

    # a API refaz a classificação: não confia só no que o aparelho mandou
    status = classificar(dias, temperatura, umidade)

    linha = {
        "data_hora": datetime.now(FUSO).strftime("%Y-%m-%d %H:%M:%S"),
        "dispositivo_id": dados["dispositivo_id"],
        "temperatura_c": temperatura,
        "umidade_pct": umidade,
        "distancia_cm": distancia,
        "nivel_agua_cm": nivel,
        "dias_agua_parada": dias,
        "status": status,
        "nivel_risco": NIVEL_RISCO[status],
        "alerta": status == "ALERTA",
    }
    gravar_csv(linha)
    total = len(ler_csv())
    log.info("ACEITO ip=%s dispositivo=%s dias=%s temp=%s umid=%s status=%s",
             ip, dados["dispositivo_id"], dias, temperatura, umidade, status)

    return jsonify({
        "id": total,
        "dispositivo_id": dados["dispositivo_id"],
        "metrica": "dias_agua_parada",
        "valor": dias,
        "status": status,
        "nivel_risco": NIVEL_RISCO[status],
        "alerta": status == "ALERTA",
    }), 201


@app.get("/leituras")
def listar_leituras():
    if not token_valido():
        log.warning("RECUSADO consulta sem token ip=%s", ip_do_cliente())
        return jsonify({"erro": "token ausente ou invalido"}), 401
    linhas = ler_csv()
    dispositivo = request.args.get("dispositivo")
    if dispositivo:
        linhas = [l for l in linhas if l["dispositivo_id"] == dispositivo]
    limite = request.args.get("limite", default=50, type=int)
    return jsonify({"total": len(linhas), "leituras": linhas[-limite:]})


@app.get("/indicadores")
def indicadores():
    if not token_valido():
        log.warning("RECUSADO consulta sem token ip=%s", ip_do_cliente())
        return jsonify({"erro": "token ausente ou invalido"}), 401
    linhas = ler_csv()
    if not linhas:
        return jsonify({"total_leituras": 0, "mensagem": "ainda nao ha leituras"})

    contagem = {"OK": 0, "ATENCAO": 0, "ALERTA": 0}
    for linha in linhas:
        contagem[linha["status"]] += 1

    temperaturas = [float(l["temperatura_c"]) for l in linhas if l["temperatura_c"]]
    umidades = [float(l["umidade_pct"]) for l in linhas if l["umidade_pct"]]
    maior_sequencia = max(int(l["dias_agua_parada"]) for l in linhas)
    total = len(linhas)

    return jsonify({
        "total_leituras": total,
        "total_alertas": contagem["ALERTA"],
        "leituras_por_status": contagem,
        "percentual_em_alerta": round(100 * contagem["ALERTA"] / total, 1),
        "maior_numero_de_dias_com_agua": maior_sequencia,
        "temperatura_media": round(sum(temperaturas) / len(temperaturas), 1) if temperaturas else None,
        "umidade_media": round(sum(umidades) / len(umidades), 1) if umidades else None,
        "ultimo_status": linhas[-1]["status"],
        "ultima_leitura_em": linhas[-1]["data_hora"],
    })


@app.get("/previsao")
def previsao():
    if not token_valido():
        log.warning("RECUSADO consulta sem token ip=%s", ip_do_cliente())
        return jsonify({"erro": "token ausente ou invalido"}), 401
    # status do quintal = última leitura gravada do aparelho
    linhas = ler_csv()
    dispositivo = request.args.get("dispositivo")
    if dispositivo:
        linhas = [l for l in linhas if l["dispositivo_id"] == dispositivo]
    status_quintal = linhas[-1]["status"] if linhas else None

    from previsao import gerar_previsao   # carrega as IAs só quando precisa
    try:
        resultado = gerar_previsao(status_quintal)
    except Exception as erro:
        log.warning("PREVISAO indisponivel: %s", erro)
        return jsonify({"erro": "previsao indisponivel no momento", "status_quintal": status_quintal}), 503
    log.info("PREVISAO risco=%s tendencia=%s quintal=%s",
             resultado["risco_proxima_semana"]["probabilidade_risco_alto"],
             resultado["casos_proximas_semanas"]["tendencia"], status_quintal)
    return jsonify(resultado)


if __name__ == "__main__":
    if not TOKEN_DISPOSITIVO:
        print("Defina a variavel TOKEN_DISPOSITIVO antes de rodar a API")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORTA", "5000")))
