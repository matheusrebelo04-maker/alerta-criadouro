# =============================================================================
# Global Solution 2026.2 - Statistical Computing with R & Python
# Projeto: Alerta Criadouro (CitizenTech) - FIAP - Tecnólogo em IA - 1TIAPZ
#
# Integrantes:
#   Matheus Rebelo da Silva de Jesus - RM 570260
#   Felipe Olmos - RM 570946
#   Luiz Guilherme - RM 573486
#
# Base: InfoDengue (Fiocruz/FGV) - dengue e clima da cidade de São Paulo,
# semanas de 2015 a 2025 (dados reais). Arquivo: base_infodengue_sp.csv
#
# Pergunta do cliente: o clima (calor e umidade) ajuda a explicar quando a
# dengue se espalha em São Paulo? Isso justifica o Alerta Criadouro medir
# temperatura e umidade no quintal das famílias.
#
# Como rodar: pip install pandas numpy scipy statsmodels matplotlib seaborn
#             python analise_estatistica.py
# =============================================================================

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from scipy import stats
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_GRAFICOS = os.path.join(PASTA, "graficos")
os.makedirs(PASTA_GRAFICOS, exist_ok=True)
sns.set_theme(style="whitegrid")


def salvar(nome):
    plt.tight_layout()
    plt.savefig(os.path.join(PASTA_GRAFICOS, nome), dpi=150)
    plt.close()


def classificar_probabilidade(p):
    if p == 0:
        return "evento impossível"
    if p < 0.5:
        return "evento improvável (pouco provável)"
    if np.isclose(p, 0.5):
        return "evento equiprovável (mesma chance de acontecer ou não)"
    if p < 1:
        return "evento provável"
    return "evento certo"


# -----------------------------------------------------------------------------
# 1) Base de dados
# -----------------------------------------------------------------------------
base = pd.read_csv(os.path.join(PASTA, "base_infodengue_sp.csv"))
print("=" * 70)
print("BASE DE DADOS")
print("=" * 70)
print(f"Semanas: {len(base)} | de {base['data_inicio_semana'].min()} a {base['data_inicio_semana'].max()}")
print(base.describe().round(2).T)

# -----------------------------------------------------------------------------
# 2) Probabilidades com a Distribuição Normal - temperatura média semanal
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 2 - DISTRIBUIÇÃO NORMAL (temperatura média semanal, °C)")
print("=" * 70)
temp = base["temp_media"]
media = temp.mean()
mediana = temp.median()
desvio = temp.std()
print(f"Média = {media:.4f} °C | Mediana = {mediana:.4f} °C | Desvio padrão = {desvio:.4f} °C")

p_menor_media = stats.norm.cdf(media, loc=media, scale=desvio)
print(f"a) P(X < {media:.2f}) = {p_menor_media:.4f} ({p_menor_media*100:.2f}%) -> {classificar_probabilidade(p_menor_media)}")

p_maior_mediana = 1 - stats.norm.cdf(mediana, loc=media, scale=desvio)
z_mediana = (mediana - media) / desvio
print(f"b) P(X > {mediana:.2f}) = {p_maior_mediana:.4f} ({p_maior_mediana*100:.2f}%) | z = {z_mediana:.4f} "
      f"-> {classificar_probabilidade(p_maior_mediana)}")

plt.figure(figsize=(8, 4.5))
x = np.linspace(temp.min() - 1, temp.max() + 1, 300)
plt.hist(temp, bins=25, density=True, alpha=0.45, color="#4C72B0", label="Semanas reais")
plt.plot(x, stats.norm.pdf(x, media, desvio), color="#C44E52", lw=2, label="Curva Normal")
plt.axvline(media, color="black", ls="--", label=f"Média {media:.2f} °C")
plt.axvline(mediana, color="green", ls=":", lw=2, label=f"Mediana {mediana:.2f} °C")
plt.title("Temperatura média semanal em São Paulo (2015-2025)")
plt.xlabel("Temperatura média da semana (°C)")
plt.ylabel("Densidade")
plt.legend()
salvar("item2_normal_temperatura.png")

# -----------------------------------------------------------------------------
# 3) Teste de hipótese para a média - temperatura média semanal
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 3 - TESTE DE HIPÓTESE PARA A MÉDIA (temperatura média semanal)")
print("=" * 70)
mu_ref = temp.mean()               # média populacional de referência
sigma_ref = temp.std(ddof=0)       # desvio padrão populacional dos dados
print(f"Média populacional de referência = {mu_ref:.4f} °C | Desvio padrão populacional = {sigma_ref:.4f} °C")


def teste_z(n, alfa, lado, semente):
    amostra = temp.sample(n=n, random_state=semente)
    media_amostra = amostra.mean()
    erro_padrao = sigma_ref / np.sqrt(n)
    z = (media_amostra - mu_ref) / erro_padrao
    if lado == "esquerda":
        z_critico = stats.norm.ppf(alfa)
        p_valor = stats.norm.cdf(z)
        rejeita = z < z_critico
        h1 = "mu < mu0"
    else:
        z_critico = stats.norm.ppf(1 - alfa)
        p_valor = 1 - stats.norm.cdf(z)
        rejeita = z > z_critico
        h1 = "mu > mu0"
    print(f"n = {n} | alfa = {alfa:.0%} | H0: mu = {mu_ref:.2f} | H1: {h1}")
    print(f"   Média da amostra = {media_amostra:.4f} °C | Erro padrão = {erro_padrao:.4f}")
    print(f"   Z calculado = {z:.4f} | Z crítico = {z_critico:.4f} | p-valor = {p_valor:.4f}")
    print("   Decisão:", "REJEITA H0" if rejeita else "NÃO REJEITA H0")
    return amostra, media_amostra, z, z_critico, p_valor, rejeita


print("a) Teste unilateral à esquerda")
amostra_a, *res_a = teste_z(20, 0.06, "esquerda", semente=7)
print("b) Teste unilateral à direita")
amostra_b, *res_b = teste_z(25, 0.09, "direita", semente=2025)

fig, eixos = plt.subplots(1, 2, figsize=(11, 4))
zz = np.linspace(-4, 4, 400)
for eixo, (titulo, res, lado) in zip(eixos, [("a) n=20, alfa=6%, cauda à esquerda", res_a, "esquerda"),
                                           ("b) n=25, alfa=9%, cauda à direita", res_b, "direita")]):
    _, z, z_crit, _, _ = res
    eixo.plot(zz, stats.norm.pdf(zz), color="#333")
    regiao = zz <= z_crit if lado == "esquerda" else zz >= z_crit
    eixo.fill_between(zz[regiao], stats.norm.pdf(zz[regiao]), color="#C44E52", alpha=0.5, label="Região de rejeição")
    eixo.axvline(z, color="#4C72B0", lw=2, label=f"Z calculado = {z:.2f}")
    eixo.set_title(titulo)
    eixo.set_xlabel("Z")
    eixo.set_ylabel("Densidade")
    eixo.legend(fontsize=8)
salvar("item3_teste_hipotese.png")

# -----------------------------------------------------------------------------
# 4) Análise bivariada: temperatura média x Rt
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 4 - ANÁLISE BIVARIADA: temperatura média (X) x Rt (Y)")
print("=" * 70)
X = base["temp_media"]
Y = base["rt"]

covariancia = np.cov(X, Y, ddof=1)[0, 1]
pearson, p_pearson = stats.pearsonr(X, Y)
print(f"b) Covariância = {covariancia:.4f} | Correlação de Pearson r = {pearson:.4f} (p-valor = {p_pearson:.2e})")

modelo_simples = sm.OLS(Y, sm.add_constant(X)).fit()
b0, b1 = modelo_simples.params
print(f"d) Equação: Rt = {b0:.4f} {b1:+.4f} x temp_media")
print(f"e) R² = {modelo_simples.rsquared:.4f} | F = {modelo_simples.fvalue:.2f} | p-valor do F = {modelo_simples.f_pvalue:.2e}")
temp_prevista = 25.0
rt_previsto = b0 + b1 * temp_prevista
print(f"f) Previsão: semana com temperatura média de {temp_prevista} °C -> Rt = {rt_previsto:.3f}")
print(modelo_simples.summary())

plt.figure(figsize=(8, 5))
plt.scatter(X, Y, alpha=0.45, color="#4C72B0", edgecolor="white", s=35)
plt.title("Temperatura média da semana x Rt da dengue em São Paulo (2015-2025)")
plt.xlabel("Temperatura média da semana (°C)")
plt.ylabel("Rt (pessoas que cada doente infecta)")
plt.axhline(1, color="gray", ls=":", lw=1)
salvar("item4a_dispersao.png")

plt.figure(figsize=(4.8, 4))
sns.heatmap(base[["temp_media", "rt"]].corr(), annot=True, fmt=".3f", cmap="RdBu_r", vmin=-1, vmax=1, square=True)
plt.title("Correlação de Pearson")
salvar("item4c_correlacao.png")

plt.figure(figsize=(8, 5))
plt.scatter(X, Y, alpha=0.45, color="#4C72B0", edgecolor="white", s=35, label="Semanas")
xs = np.linspace(X.min(), X.max(), 100)
plt.plot(xs, b0 + b1 * xs, color="#C44E52", lw=2.5, label=f"Rt = {b0:.3f} + {b1:.4f}·temp")
plt.scatter([temp_prevista], [rt_previsto], color="black", s=90, marker="X", zorder=5,
            label=f"Previsão: 25 °C -> Rt {rt_previsto:.2f}")
plt.title("Regressão linear simples: temperatura média x Rt")
plt.xlabel("Temperatura média da semana (°C)")
plt.ylabel("Rt (pessoas que cada doente infecta)")
plt.legend()
salvar("item4d_regressao_simples.png")

# -----------------------------------------------------------------------------
# 5) Análise multivariada: Rt x temperatura média, umidade média e umidade máxima
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 5 - ANÁLISE MULTIVARIADA: Rt ~ temp_media + umid_media + umid_maxima")
print("=" * 70)
variaveis = ["rt", "temp_media", "umid_media", "umid_maxima"]
print("b) Matriz de covariância:")
print(base[variaveis].cov().round(4))
print("b) Matriz de correlação de Pearson:")
print(base[variaveis].corr().round(4))

explicativas = ["temp_media", "umid_media", "umid_maxima"]
modelo_multiplo = sm.OLS(base["rt"], sm.add_constant(base[explicativas])).fit()
c = modelo_multiplo.params
print(f"d) Equação: Rt = {c['const']:.4f} {c['temp_media']:+.4f} x temp_media "
      f"{c['umid_media']:+.4f} x umid_media {c['umid_maxima']:+.4f} x umid_maxima")
print(f"e) R² = {modelo_multiplo.rsquared:.4f} | R² ajustado = {modelo_multiplo.rsquared_adj:.4f} | "
      f"F = {modelo_multiplo.fvalue:.2f} | p-valor do F = {modelo_multiplo.f_pvalue:.2e}")
print(modelo_multiplo.summary())
nova_semana = pd.DataFrame({"const": [1.0], "temp_media": [25.0], "umid_media": [80.0], "umid_maxima": [95.0]})
rt_multiplo = float(modelo_multiplo.predict(nova_semana)[0])
print(f"f) Previsão: temp_media 25 °C, umid_media 80%, umid_maxima 95% -> Rt = {rt_multiplo:.3f}")

grade = sns.pairplot(base[variaveis], corner=True, plot_kws={"alpha": 0.35, "s": 18})
grade.figure.suptitle("Dispersão entre Rt, temperatura média, umidade média e umidade máxima", y=1.02)
grade.figure.savefig(os.path.join(PASTA_GRAFICOS, "item5a_dispersao_multipla.png"), dpi=130, bbox_inches="tight")
plt.close("all")

plt.figure(figsize=(6.2, 5))
sns.heatmap(base[variaveis].corr(), annot=True, fmt=".3f", cmap="RdBu_r", vmin=-1, vmax=1, square=True)
plt.title("Matriz de correlação de Pearson")
salvar("item5c_correlacao_multipla.png")

# -----------------------------------------------------------------------------
# 6) Regressão logística binária: a dengue está se espalhando (Rt > 1)?
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ITEM 6 - REGRESSÃO LOGÍSTICA: espalhando = 1 se Rt > 1")
print("=" * 70)
base["espalhando"] = (base["rt"] > 1).astype(int)
print("Semanas com Rt > 1:", base["espalhando"].sum(), "de", len(base))
X_log = base[explicativas]
y_log = base["espalhando"]
X_treino, X_teste, y_treino, y_teste = train_test_split(X_log, y_log, test_size=0.3, random_state=42, stratify=y_log)
modelo_log = sm.Logit(y_treino, sm.add_constant(X_treino)).fit(disp=0)
g = modelo_log.params
print(f"a) Equação: P(Rt>1) = 1 / (1 + e^-({g['const']:.4f} {g['temp_media']:+.4f} x temp_media "
      f"{g['umid_media']:+.4f} x umid_media {g['umid_maxima']:+.4f} x umid_maxima))")
print(modelo_log.summary())
prob_teste = modelo_log.predict(sm.add_constant(X_teste))
prev_teste = (prob_teste >= 0.5).astype(int)
matriz = confusion_matrix(y_teste, prev_teste)
acuracia = accuracy_score(y_teste, prev_teste)
print("b) Matriz de confusão (teste, 30% das semanas) [linhas = real, colunas = previsto]:")
print(matriz)
print(f"b) Acurácia no teste = {acuracia:.4f} ({acuracia*100:.1f}%)")
print(f"   Proporção da classe mais comum no teste = {max(y_teste.mean(), 1 - y_teste.mean()):.4f}")

semanas_novas = pd.DataFrame({
    "temp_media": [25.0, 16.0],
    "umid_media": [80.0, 70.0],
    "umid_maxima": [95.0, 85.0],
})
prob_novas = modelo_log.predict(sm.add_constant(semanas_novas, has_constant="add"))
for i, linha in semanas_novas.iterrows():
    p = float(prob_novas.iloc[i])
    print(f"c) Semana com {linha['temp_media']} °C, umid. média {linha['umid_media']}% e máxima "
          f"{linha['umid_maxima']}% -> P(Rt>1) = {p:.3f} -> {'ESPALHANDO (Rt > 1)' if p >= 0.5 else 'NÃO espalhando'}")

plt.figure(figsize=(5, 4.2))
sns.heatmap(matriz, annot=True, fmt="d", cmap="Blues", cbar=False,
            xticklabels=["Previsto: não", "Previsto: sim"], yticklabels=["Real: não", "Real: sim"])
plt.title(f"Matriz de confusão (acurácia {acuracia*100:.1f}%)")
salvar("item6_matriz_confusao.png")

print("\nGráficos salvos em:", PASTA_GRAFICOS)
