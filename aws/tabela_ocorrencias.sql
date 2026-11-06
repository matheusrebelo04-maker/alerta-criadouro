-- Global Solution 2026.2 - CitizenTech - Alerta Criadouro
-- Plataformas, Serviços Cognitivos & Cloud Computing - FIAP 1TIAPZ
-- Matheus Rebelo (RM 570260), Felipe Olmos (RM 570946), Luiz Guilherme (RM 573486)
--
-- Tabela que recebe as leituras do Alerta Criadouro (ESP32 no quintal, simulador ou app da família).

CREATE TABLE IF NOT EXISTS ocorrencias (
    id                SERIAL PRIMARY KEY,
    dispositivo_id    TEXT        NOT NULL,              -- ex.: esp32-quintal-001
    tipo_dispositivo  TEXT        NOT NULL,              -- esp32 | simulador | app
    latitude          DOUBLE PRECISION,                  -- só 3 casas decimais (bairro, não a casa)
    longitude         DOUBLE PRECISION,
    metrica           TEXT        NOT NULL,              -- dias_agua_parada
    valor             DOUBLE PRECISION NOT NULL,         -- dias com água no potinho sentinela
    temperatura_c     DOUBLE PRECISION,                  -- DHT22
    umidade_pct       DOUBLE PRECISION,                  -- DHT22
    nivel_agua_cm     DOUBLE PRECISION,                  -- HC-SR04
    relato            TEXT,                              -- texto da família (vai para a IA)
    sentimento        TEXT,                              -- rótulo do modelo da Hugging Face
    confianca         NUMERIC(5,4),                      -- score do rótulo
    nivel_risco       TEXT        NOT NULL,              -- normal | atencao | critico
    alerta            BOOLEAN     NOT NULL DEFAULT FALSE,-- dispara aviso à família
    medido_em         TIMESTAMPTZ,                       -- hora no dispositivo
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW() -- hora da gravação na nuvem
);

CREATE INDEX IF NOT EXISTS idx_ocorrencias_dispositivo ON ocorrencias (dispositivo_id);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_risco       ON ocorrencias (nivel_risco);
CREATE INDEX IF NOT EXISTS idx_ocorrencias_criado      ON ocorrencias (criado_em DESC);

-- Consultas para os prints da entrega ------------------------------------------

-- 1) últimas leituras que chegaram na nuvem
SELECT id, dispositivo_id, tipo_dispositivo, valor AS dias_agua, temperatura_c, umidade_pct,
       nivel_risco, alerta, sentimento, confianca, criado_em
  FROM ocorrencias
 ORDER BY id DESC
 LIMIT 15;

-- 2) quintais em situação crítica (as leituras que geram alerta à família)
SELECT dispositivo_id, valor AS dias_agua, temperatura_c, umidade_pct, relato, sentimento, criado_em
  FROM ocorrencias
 WHERE nivel_risco = 'critico'
 ORDER BY criado_em DESC;

-- 3) resumo por aparelho
SELECT dispositivo_id,
       COUNT(*)                              AS leituras,
       MAX(valor)                            AS maior_numero_de_dias_com_agua,
       ROUND(AVG(temperatura_c)::numeric, 1) AS temperatura_media,
       SUM((nivel_risco = 'critico')::int)   AS criticas
  FROM ocorrencias
 GROUP BY dispositivo_id
 ORDER BY criticas DESC;
