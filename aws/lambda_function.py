"""
Alerta Criadouro - API serverless de ingestão (AWS Lambda + RDS PostgreSQL + IA)
Global Solution 2026.2 - Plataformas, Serviços Cognitivos & Cloud Computing - FIAP 1TIAPZ
Matheus Rebelo (RM 570260), Felipe Olmos (RM 570946), Luiz Guilherme (RM 573486)

Baseado no material de apoio da disciplina, adaptado ao nosso cenário:
o aparelho no quintal mede há quantos dias o potinho sentinela está com água
parada (metrica dias_agua_parada), junto com temperatura e umidade.

Rotas (Function URL):
  GET  /health       -> status da função
  POST /ocorrencias  -> recebe a leitura, classifica, analisa o relato e grava no RDS
  GET  /ocorrencias  -> lista as últimas ocorrências gravadas

Variáveis de ambiente:
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD   (RDS PostgreSQL)
  HF_TOKEN      token gratuito do tipo Read da Hugging Face (usado para baixar o modelo)
  HF_MODEL      padrão: onnx-community/twitter-xlm-roberta-base-sentiment-ONNX
  TOKEN_DISPOSITIVO (opcional) se definido, o POST exige o cabeçalho X-Token-Dispositivo

IA (caminho A - Hugging Face): o modelo de sentimento é baixado do Hub da Hugging Face
na primeira chamada e roda dentro da própria Lambda com onnxruntime. Desde outubro de 2026
a API de inferência gratuita da Hugging Face passou a cobrar crédito (erro 402), então
trazer o modelo para dentro da função foi o jeito de manter a IA funcionando sem custo.
"""

import json
import logging
import os
import re
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone

import numpy as np
import onnxruntime as ort
import pg8000 as driver   # Python puro: pip install pg8000 -t pacote/
from tokenizers import Tokenizer

logger = logging.getLogger()
logger.setLevel(logging.INFO)

HF_MODEL = os.environ.get("HF_MODEL", "onnx-community/twitter-xlm-roberta-base-sentiment-ONNX")
HF_TOKEN = os.environ.get("HF_TOKEN")
PASTA_MODELO = "/tmp/modelo"
ARQUIVOS_MODELO = {               # arquivo no Hub -> nome local
    "config.json": "config.json",
    "tokenizer.json": "tokenizer.json",
    "onnx/model_quantized.onnx": "model.onnx",
}
_modelo = None                    # fica na memória entre as chamadas da mesma instância
TOKEN_DISPOSITIVO = os.environ.get("TOKEN_DISPOSITIVO")

# Limiares do Alerta Criadouro (os mesmos do ESP32 e da API Flask)
DIAS_ATENCAO = 1          # qualquer água parada já pede atenção
DIAS_CRITICO_CLIMA = 3    # 3 dias com calor e umidade altos
DIAS_CRITICO_SEMPRE = 5   # 5 dias em qualquer clima
TEMP_ALERTA = 25.0
UMIDADE_ALERTA = 70.0
PADRAO_ID = re.compile(r"^[a-z0-9-]{3,40}$")   # evita fórmula maliciosa e lixo no banco


# ---------------------------------------------------------------- banco
def conectar():
    return driver.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 5432)),
        database=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        timeout=10,
    )


def gravar_ocorrencia(dados):
    sql = """
        INSERT INTO ocorrencias
            (dispositivo_id, tipo_dispositivo, latitude, longitude, metrica, valor,
             temperatura_c, umidade_pct, nivel_agua_cm, relato, sentimento, confianca,
             nivel_risco, alerta, medido_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, criado_em
    """
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute(sql, (
            dados["dispositivo_id"], dados["tipo_dispositivo"], dados["latitude"], dados["longitude"],
            dados["metrica"], dados["valor"], dados["temperatura_c"], dados["umidade_pct"],
            dados["nivel_agua_cm"], dados["relato"], dados["sentimento"], dados["confianca"],
            dados["nivel_risco"], dados["alerta"], dados["medido_em"],
        ))
        novo_id, criado_em = cur.fetchone()
        conn.commit()
        return novo_id, criado_em
    finally:
        conn.close()


def listar_ocorrencias(limite=20):
    conn = conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, dispositivo_id, tipo_dispositivo, valor, temperatura_c, umidade_pct,
                   nivel_risco, alerta, sentimento, confianca, relato, criado_em
              FROM ocorrencias ORDER BY id DESC LIMIT %s
        """, (limite,))
        colunas = ["id", "dispositivo_id", "tipo_dispositivo", "dias_agua_parada", "temperatura_c",
                   "umidade_pct", "nivel_risco", "alerta", "sentimento", "confianca", "relato", "criado_em"]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]
    finally:
        conn.close()


# ------------------------------------------------------- classificações
def classificar_risco(dias, temperatura=None, umidade=None):
    """Regra de limiar local: não depende de rede nem de token. Sempre executa."""
    if dias < DIAS_ATENCAO:
        return "normal"
    if dias >= DIAS_CRITICO_SEMPRE:
        return "critico"
    if temperatura is not None and umidade is not None:
        if dias >= DIAS_CRITICO_CLIMA and temperatura >= TEMP_ALERTA and umidade >= UMIDADE_ALERTA:
            return "critico"
    return "atencao"


def baixar_do_hub(arquivo, destino):
    url = f"https://huggingface.co/{HF_MODEL}/resolve/main/{arquivo}"
    cabecalhos = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
    requisicao = urllib.request.Request(url, headers=cabecalhos)
    with urllib.request.urlopen(requisicao, timeout=25) as resp, open(destino + ".parte", "wb") as saida:
        shutil.copyfileobj(resp, saida, 1024 * 1024)
    os.replace(destino + ".parte", destino)


def carregar_modelo():
    """Baixa o modelo da Hugging Face uma vez por instância e deixa pronto na memória."""
    global _modelo
    if _modelo is not None:
        return _modelo
    os.makedirs(PASTA_MODELO, exist_ok=True)
    for arquivo, nome_local in ARQUIVOS_MODELO.items():
        destino = os.path.join(PASTA_MODELO, nome_local)
        if not os.path.exists(destino):
            baixar_do_hub(arquivo, destino)
    tokenizador = Tokenizer.from_file(os.path.join(PASTA_MODELO, "tokenizer.json"))
    tokenizador.enable_truncation(max_length=128)
    sessao = ort.InferenceSession(os.path.join(PASTA_MODELO, "model.onnx"), providers=["CPUExecutionProvider"])
    with open(os.path.join(PASTA_MODELO, "config.json"), encoding="utf-8") as arq:
        rotulos = {int(k): v for k, v in json.load(arq)["id2label"].items()}
    entradas = {e.name for e in sessao.get_inputs()}
    _modelo = (tokenizador, sessao, rotulos, entradas)
    logger.info("MODELO CARREGADO %s", HF_MODEL)
    return _modelo


def analisar_relato(texto):
    """
    Caminho A - Hugging Face. Classifica o sentimento do relato da família.
    Se a IA falhar, devolve (None, None) e a ingestão continua normalmente.
    """
    if not texto:
        return None, None
    try:
        tokenizador, sessao, rotulos, entradas = carregar_modelo()
        codificado = tokenizador.encode(texto)
        dados = {
            "input_ids": np.array([codificado.ids], dtype=np.int64),
            "attention_mask": np.array([codificado.attention_mask], dtype=np.int64),
        }
        logits = sessao.run(None, {k: v for k, v in dados.items() if k in entradas})[0][0]
        probabilidades = np.exp(logits - logits.max())
        probabilidades = probabilidades / probabilidades.sum()
        melhor = int(probabilidades.argmax())
        return rotulos[melhor], round(float(probabilidades[melhor]), 4)
    except urllib.error.HTTPError as erro:
        logger.warning("IA INDISPONIVEL - Hugging Face respondeu %s ao baixar o modelo", erro.code)
    except Exception as erro:  # timeout, falta de espaço, arquivo corrompido
        logger.warning("IA INDISPONIVEL - falha ao usar o modelo: %s", erro)
    return None, None


def numero_ou_none(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------- rotas
def rota_ingestao(evento):
    cabecalhos = {k.lower(): v for k, v in (evento.get("headers") or {}).items()}
    bruto = evento.get("body") or "{}"
    logger.info("PAYLOAD RECEBIDO: %s", bruto)

    if TOKEN_DISPOSITIVO and cabecalhos.get("x-token-dispositivo") != TOKEN_DISPOSITIVO:
        logger.warning("LEITURA DESCARTADA - token do dispositivo ausente ou invalido")
        return resposta(401, {"erro": "token do dispositivo ausente ou invalido"})

    try:
        payload = json.loads(bruto)
    except json.JSONDecodeError:
        logger.warning("LEITURA DESCARTADA - corpo nao e JSON valido")
        return resposta(400, {"erro": "corpo nao e um JSON valido"})
    if not isinstance(payload, dict):
        logger.warning("LEITURA DESCARTADA - corpo nao e um objeto JSON")
        return resposta(400, {"erro": "o corpo precisa ser um objeto JSON"})

    faltando = [c for c in ("dispositivo_id", "metrica", "valor") if payload.get(c) is None]
    if faltando:
        logger.warning("LEITURA DESCARTADA - campos ausentes: %s", faltando)
        return resposta(400, {"erro": "campos obrigatorios ausentes", "campos": faltando})

    erros = []
    if not isinstance(payload["dispositivo_id"], str) or not PADRAO_ID.match(payload["dispositivo_id"]):
        erros.append("dispositivo_id invalido")
    if payload["metrica"] != "dias_agua_parada":
        erros.append("metrica precisa ser dias_agua_parada")
    valor = numero_ou_none(payload["valor"])
    if valor is None or not 0 <= valor <= 365:
        erros.append("valor precisa ser um numero de 0 a 365")
    if erros:
        logger.warning("LEITURA DESCARTADA - %s", erros)
        return resposta(400, {"erro": "leitura invalida", "detalhes": erros})

    leituras = payload.get("leituras") if isinstance(payload.get("leituras"), dict) else {}
    dados = {
        "dispositivo_id": payload["dispositivo_id"],
        "tipo_dispositivo": payload.get("tipo_dispositivo", "desconhecido"),
        "latitude": numero_ou_none(payload.get("latitude")),
        "longitude": numero_ou_none(payload.get("longitude")),
        "metrica": payload["metrica"],
        "valor": valor,
        "temperatura_c": numero_ou_none(leituras.get("temperatura_c")),
        "umidade_pct": numero_ou_none(leituras.get("umidade_pct")),
        "nivel_agua_cm": numero_ou_none(leituras.get("nivel_agua_cm")),
        "relato": payload.get("relato"),
        "medido_em": payload.get("medido_em") or datetime.now(timezone.utc).isoformat(),
    }
    logger.info("DISPOSITIVO=%s TIPO=%s GPS=(%s, %s) %s=%s TEMP=%s UMID=%s",
                dados["dispositivo_id"], dados["tipo_dispositivo"], dados["latitude"], dados["longitude"],
                dados["metrica"], dados["valor"], dados["temperatura_c"], dados["umidade_pct"])

    dados["nivel_risco"] = classificar_risco(dados["valor"], dados["temperatura_c"], dados["umidade_pct"])
    dados["sentimento"], dados["confianca"] = analisar_relato(dados["relato"])
    # relato muito negativo da família reforça o aviso quando já há água parada
    relato_preocupante = dados["sentimento"] == "negative" and (dados["confianca"] or 0) >= 0.8
    dados["alerta"] = dados["nivel_risco"] == "critico" or (dados["nivel_risco"] == "atencao" and relato_preocupante)

    logger.info("CLASSIFICACAO risco=%s sentimento=%s confianca=%s alerta=%s",
                dados["nivel_risco"], dados["sentimento"], dados["confianca"], dados["alerta"])
    if dados["nivel_risco"] == "critico":
        logger.warning("ALERTA CIDADAO: potinho de %s com agua ha %s dias (critico) - esvaziar recipientes do quintal",
                       dados["dispositivo_id"], int(dados["valor"]))

    novo_id, criado_em = gravar_ocorrencia(dados)
    logger.info("GRAVADO NO RDS id=%s em %s", novo_id, criado_em)

    return resposta(201, {
        "id": novo_id,
        "dispositivo_id": dados["dispositivo_id"],
        "metrica": dados["metrica"],
        "valor": dados["valor"],
        "nivel_risco": dados["nivel_risco"],
        "sentimento": dados["sentimento"],
        "confianca": dados["confianca"],
        "alerta": dados["alerta"],
    })


def resposta(status, corpo):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(corpo, default=str, ensure_ascii=False)}


def lambda_handler(evento, contexto):
    metodo = evento.get("requestContext", {}).get("http", {}).get("method", "GET").upper()
    caminho = evento.get("rawPath", "/")
    logger.info("REQUISICAO %s %s", metodo, caminho)
    try:
        if caminho == "/health":
            return resposta(200, {"status": "ok", "projeto": "alerta-criadouro", "modelo": HF_MODEL,
                                  "token_hf_configurado": bool(HF_TOKEN),
                                  "modelo_na_memoria": _modelo is not None})
        if caminho == "/ocorrencias" and metodo == "POST":
            return rota_ingestao(evento)
        if caminho == "/ocorrencias" and metodo == "GET":
            return resposta(200, {"ocorrencias": listar_ocorrencias()})
        return resposta(404, {"erro": "rota nao encontrada", "caminho": caminho})
    except Exception as erro:
        logger.exception("ERRO NAO TRATADO")
        return resposta(500, {"erro": str(erro)})
