# Alerta Criadouro - previsões da IA usadas pela API (rota GET /previsao)
# Global Solution 2026.2 - FIAP - 1TIAPZ
# Matheus Rebelo - RM 570260
# Felipe Olmos - RM 570946
# Luiz Guilherme - RM 573486
#
# Junta as duas IAs do projeto:
#   - Machine Learning (Random Forest): risco alto de dengue na próxima semana?
#   - Rede neural LSTM: casos previstos para as próximas 4 semanas
# Os dois usam os dados reais do InfoDengue da cidade de São Paulo.
# Na primeira chamada os modelos são treinados com os mesmos dados e
# hiperparâmetros escolhidos nos notebooks e ficam salvos na pasta modelos/.

import hashlib
import os
import urllib.request

import numpy as np
import pandas as pd

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_MODELOS = os.path.join(PASTA, "modelos")
ARQUIVO_DADOS = os.path.join(PASTA, "..", "dados", "infodengue_sp_2015_2025.csv")
URL_DADOS = ("https://raw.githubusercontent.com/matheusrebelo04-maker/alerta-criadouro/main/"
             "dados/infodengue_sp_2015_2025.csv")
HASH_ESPERADO = "741ccfb2a01cf5d98614fcffd4ddfaf41a748b4b0549211435879c1bec97a03b"

JANELA, HORIZONTE = 12, 4
ATRIBUTOS_LSTM = ["variacao_log", "Rt", "tempmed", "tempmin", "umidmed", "umidmax", "semana_sin", "semana_cos"]

_cache = {}


# ------------------------------------------------------------------ dados
def carregar_dados():
    if "dados" in _cache:
        return _cache["dados"]
    caminho = ARQUIVO_DADOS
    if not os.path.exists(caminho):
        caminho = os.path.join(PASTA, "infodengue_sp_2015_2025.csv")
        if not os.path.exists(caminho):
            urllib.request.urlretrieve(URL_DADOS, caminho)
    # proteção do modelo: só treina com a base original
    if hashlib.sha256(open(caminho, "rb").read()).hexdigest() != HASH_ESPERADO:
        raise ValueError("base do InfoDengue alterada, previsão cancelada")
    dados = pd.read_csv(caminho)
    dados["data"] = pd.to_datetime(dados["data_iniSE"])
    dados = dados.sort_values("data").reset_index(drop=True)
    _cache["dados"] = dados
    return dados


# ------------------------------------------------- Machine Learning (risco)
def atributos_ml(base):
    f = pd.DataFrame({"data": base["data"]})
    log_casos = np.log1p(base["casos"])
    f["log_casos"] = log_casos
    f["log_casos_1"] = log_casos.shift(1)
    f["log_casos_2"] = log_casos.shift(2)
    f["variacao_casos"] = f["log_casos"] - f["log_casos_1"]
    f["rt"] = base["Rt"]
    f["rt_1"] = base["Rt"].shift(1)
    f["incidencia"] = base["p_inc100k"]
    f["nivel_atual"] = base["nivel"]
    for c in ["tempmed", "tempmin", "umidmed", "umidmax"]:
        f[c] = base[c]
        f[c + "_media4"] = base[c].rolling(4, min_periods=1).mean()
    semana = base["SE"] % 100
    f["semana_sin"] = np.sin(2 * np.pi * semana / 52)
    f["semana_cos"] = np.cos(2 * np.pi * semana / 52)
    return f


def modelo_risco():
    if "risco" in _cache:
        return _cache["risco"]
    import joblib
    arquivo = os.path.join(PASTA_MODELOS, "modelo_risco_dengue.joblib")
    if os.path.exists(arquivo):
        pacote = joblib.load(arquivo)
    else:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        dados = carregar_dados()
        f = atributos_ml(dados)
        f["alvo"] = (dados["nivel"].shift(-1) >= 3).astype(float)
        f.loc[dados["nivel"].shift(-1).isna(), "alvo"] = np.nan
        f = f.dropna(subset=["alvo", "log_casos_2"])
        colunas = [c for c in f.columns if c not in ("data", "alvo")]
        treino = f[f["data"] < "2023-01-01"]
        # mesmos hiperparâmetros escolhidos pelo GridSearchCV no notebook de ML
        modelo = Pipeline([
            ("faltantes", SimpleImputer(strategy="median")),
            ("padronizacao", StandardScaler()),
            ("modelo", RandomForestClassifier(n_estimators=200, max_depth=5, max_features=0.5,
                                              min_samples_leaf=3, class_weight="balanced", random_state=42)),
        ]).fit(treino[colunas], treino["alvo"].astype(int))
        pacote = {"modelo": modelo, "colunas": colunas}
        os.makedirs(PASTA_MODELOS, exist_ok=True)
        joblib.dump(pacote, arquivo)
    _cache["risco"] = pacote
    return pacote


def prever_risco():
    dados = carregar_dados()
    pacote = modelo_risco()
    ultima = atributos_ml(dados).iloc[[-1]]
    prob = float(pacote["modelo"].predict_proba(ultima[pacote["colunas"]])[0, 1])
    return round(prob, 3)


# --------------------------------------------------------- LSTM (casos)
def preparar_lstm(dados):
    d = dados.copy()
    for coluna in ["tempmed", "umidmed", "umidmax"]:
        d[coluna] = d[coluna].interpolate(limit_direction="both")
    d["log_casos"] = np.log1p(d["casos"])
    d["variacao_log"] = d["log_casos"].diff().fillna(0)
    semana = d["SE"] % 100
    d["semana_sin"] = np.sin(2 * np.pi * semana / 52)
    d["semana_cos"] = np.cos(2 * np.pi * semana / 52)
    fim_treino = d.index[d["data"] < "2022-01-01"].max()
    media = d.loc[:fim_treino, ATRIBUTOS_LSTM].mean()
    desvio = d.loc[:fim_treino, ATRIBUTOS_LSTM].std(ddof=0)
    Z = ((d[ATRIBUTOS_LSTM] - media) / desvio).values.astype("float32")
    return d, Z, fim_treino


def modelo_lstm():
    if "lstm" in _cache:
        return _cache["lstm"]
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    import tensorflow as tf
    arquivo = os.path.join(PASTA_MODELOS, "lstm_casos_dengue.keras")
    if os.path.exists(arquivo):
        rede = tf.keras.models.load_model(arquivo)
    else:
        d, Z, fim_treino = preparar_lstm(carregar_dados())
        fim_validacao = d.index[d["data"] < "2023-01-01"].max()
        log_casos = d["log_casos"].values
        X, Y, inicio = [], [], []
        for t in range(JANELA, len(d) - HORIZONTE + 1):
            X.append(Z[t - JANELA:t])
            Y.append(log_casos[t:t + HORIZONTE] - log_casos[t - 1])
            inicio.append(t)
        X, Y, inicio = np.array(X), np.array(Y, dtype="float32"), np.array(inicio)
        em_treino = inicio + HORIZONTE - 1 <= fim_treino
        em_validacao = (inicio > fim_treino) & (inicio + HORIZONTE - 1 <= fim_validacao)
        # configuração C, a escolhida no notebook de Redes Neurais
        tf.keras.utils.set_random_seed(42)
        rede = tf.keras.Sequential([
            tf.keras.Input(shape=(JANELA, len(ATRIBUTOS_LSTM))),
            tf.keras.layers.LSTM(64),
            tf.keras.layers.Dropout(0.3),
            tf.keras.layers.Dense(HORIZONTE),
        ])
        rede.compile(optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3), loss="mse")
        rede.fit(X[em_treino], Y[em_treino], validation_data=(X[em_validacao], Y[em_validacao]),
                 epochs=300, batch_size=16, verbose=0,
                 callbacks=[tf.keras.callbacks.EarlyStopping(patience=25, restore_best_weights=True)])
        os.makedirs(PASTA_MODELOS, exist_ok=True)
        rede.save(arquivo)
    _cache["lstm"] = rede
    return rede


def prever_casos():
    d, Z, _ = preparar_lstm(carregar_dados())
    rede = modelo_lstm()
    janela = Z[-JANELA:][None, :, :]
    variacao = rede.predict(janela, verbose=0)[0]
    previstos = np.expm1(d["log_casos"].iloc[-1] + variacao)
    ultima_data = d["data"].iloc[-1]
    semanas = [(ultima_data + pd.Timedelta(weeks=k + 1)).strftime("%Y-%m-%d") for k in range(HORIZONTE)]
    return {
        "semana_base": ultima_data.strftime("%Y-%m-%d"),
        "casos_na_semana_base": int(d["casos"].iloc[-1]),
        "semanas": semanas,
        "casos_previstos": [int(round(v)) for v in previstos],
    }


# --------------------------------------------------------- mensagem final
def montar_mensagem(prob_risco, casos, status_quintal):
    risco_alto = prob_risco >= 0.5
    base = max(casos["casos_na_semana_base"], 1)
    mudanca = (casos["casos_previstos"][-1] / base - 1) * 100
    tendencia = "subindo" if mudanca > 25 else "caindo" if mudanca < -25 else "estável"

    if status_quintal == "ALERTA":
        acao = "Seu potinho está com água há dias: esvazie os vasos, baldes e pratinhos do quintal hoje."
    elif status_quintal == "ATENCAO" and (risco_alto or tendencia == "subindo"):
        acao = "Choveu no seu quintal e a dengue está forte na cidade: faça a vistoria hoje, não espere."
    elif status_quintal == "ATENCAO":
        acao = "Tem água parada no potinho. Dê uma olhada nos recipientes do quintal nos próximos dias."
    elif risco_alto or tendencia == "subindo":
        acao = "Quintal seco, ótimo. A dengue está alta na cidade: mantenha a vistoria toda semana."
    else:
        acao = "Tudo certo no quintal. Mantenha a vistoria semanal."
    cidade = f"Risco de dengue em São Paulo na próxima semana: {'ALTO' if risco_alto else 'baixo'}. " \
             f"Casos nas próximas 4 semanas: tendência {tendencia}."
    return round(mudanca, 1), tendencia, f"{cidade} {acao}"


def gerar_previsao(status_quintal=None):
    prob = prever_risco()
    casos = prever_casos()
    mudanca, tendencia, mensagem = montar_mensagem(prob, casos, status_quintal)
    return {
        "risco_proxima_semana": {"probabilidade_risco_alto": prob, "risco_alto": prob >= 0.5,
                                 "modelo": "Random Forest (Machine Learning)"},
        "casos_proximas_semanas": {**casos, "mudanca_em_4_semanas_pct": mudanca, "tendencia": tendencia,
                                   "modelo": "LSTM (Redes Neurais)"},
        "status_quintal": status_quintal or "sem leitura",
        "mensagem_para_familia": mensagem,
    }
