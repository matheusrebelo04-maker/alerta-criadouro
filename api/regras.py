# Alerta Criadouro - regras de classificação das leituras
# Global Solution 2026.2 - FIAP - 1TIAPZ
# Matheus Rebelo da Silva de Jesus - RM 570260
# Felipe Olmos - RM 570946
# Luiz Guilherme - RM 573486
#
# As mesmas regras do ESP32. Usadas na API Flask e na Lambda da AWS.

ALTURA_POTINHO_CM = 12.0    # distância do sensor até o fundo do potinho vazio
AGUA_MINIMA_CM = 1.0        # a partir disso conta como água parada
TEMP_ALERTA = 25.0          # °C
UMIDADE_ALERTA = 70.0       # %
DIAS_ALERTA_CLIMA = 3       # com calor e umidade altos
DIAS_ALERTA_SEMPRE = 5      # em qualquer clima

# como cada estado aparece na API da AWS
NIVEL_RISCO = {"OK": "normal", "ATENCAO": "atencao", "ALERTA": "critico"}


def nivel_agua(distancia_cm):
    nivel = ALTURA_POTINHO_CM - distancia_cm
    return round(max(nivel, 0.0), 1)


def status_dos_sensores(temperatura, umidade, nivel):
    return {
        "temperatura": "ALERTA" if temperatura >= TEMP_ALERTA else "OK",
        "umidade": "ALERTA" if umidade >= UMIDADE_ALERTA else "OK",
        "agua": "ALERTA" if nivel >= AGUA_MINIMA_CM else "OK",
    }


def classificar(dias_agua, temperatura=None, umidade=None):
    """Devolve OK, ATENCAO ou ALERTA."""
    if dias_agua <= 0:
        return "OK"
    if dias_agua >= DIAS_ALERTA_SEMPRE:
        return "ALERTA"
    # sem dados de clima, fica só na regra dos dias
    if temperatura is not None and umidade is not None:
        clima_favoravel = temperatura >= TEMP_ALERTA and umidade >= UMIDADE_ALERTA
        if dias_agua >= DIAS_ALERTA_CLIMA and clima_favoravel:
            return "ALERTA"
    return "ATENCAO"


if __name__ == "__main__":
    # teste rápido dos três estados
    testes = [
        (0, 30, 80),    # potinho seco
        (1, 30, 80),    # água recente
        (3, 29, 78),    # 3 dias, calor e umidade
        (3, 20, 60),    # 3 dias, clima frio
        (5, 18, 50),    # 5 dias, qualquer clima
        (2, None, None),
    ]
    for dias, temp, umid in testes:
        estado = classificar(dias, temp, umid)
        print(f"dias={dias} temp={temp} umid={umid} -> {estado} ({NIVEL_RISCO[estado]})")
    print("nivel com distancia 7.5 cm:", nivel_agua(7.5), "cm")
    print(status_dos_sensores(29.4, 78, nivel_agua(7.5)))
