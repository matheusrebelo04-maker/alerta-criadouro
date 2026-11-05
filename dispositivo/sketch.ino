// Alerta Criadouro - dispositivo do quintal (ESP32)
// Global Solution 2026.2 - FIAP - 1TIAPZ
// Matheus Rebelo - RM 570260
// Felipe Olmos - RM 570946
// Luiz Guilherme - RM 573486
//
// DHT22 mede temperatura e umidade. O HC-SR04 aponta para dentro do
// potinho sentinela e mede a distância até a água. LEDs e buzzer avisam
// a família. A cada leitura o ESP32 manda um JSON para a nossa API.

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "DHTesp.h"

// ---------- rede e API ----------
const char* WIFI_NOME = "Wokwi-GUEST";
const char* WIFI_SENHA = "";
// endereço da API: túnel aberto pelo notebook api/rodar_api_colab.ipynb
// (a cada vez que o notebook roda, o Colab gera um endereço novo; trocar aqui)
// No Wokwi usamos http porque a conexão segura estoura o tempo no simulador.
// No aparelho de verdade o envio seria por https.
const char* URL_API = "http://vsnet-adequate-spaces-era.trycloudflare.com/leituras";
const char* TOKEN_DISPOSITIVO = "ac-quintal-001-demo";
const char* ID_DISPOSITIVO = "esp32-quintal-001";

// ---------- pinos ----------
const int PINO_DHT = 15;
const int PINO_TRIG = 5;
const int PINO_ECHO = 18;
const int LED_VERDE = 25;
const int LED_AMARELO = 26;
const int LED_VERMELHO = 27;
const int PINO_BUZZER = 13;

// ---------- limiares (iguais aos da API) ----------
const float ALTURA_POTINHO_CM = 12.0;  // sensor até o fundo vazio
const float AGUA_MINIMA_CM = 1.0;
const float TEMP_ALERTA = 25.0;
const float UMIDADE_ALERTA = 70.0;
const int DIAS_ALERTA_CLIMA = 3;
const int DIAS_ALERTA_SEMPRE = 5;

// no Wokwi 1 dia vale 10 segundos, para dar para ver acontecer
const unsigned long MS_POR_DIA = 10000;
const unsigned long INTERVALO_ENVIO = 5000;

DHTesp dht;
unsigned long inicioAgua = 0;   // quando o potinho começou a ter água
bool temAgua = false;
unsigned long ultimoEnvio = 0;
String estadoAnterior = "";

float medirDistancia() {
  digitalWrite(PINO_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PINO_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PINO_TRIG, LOW);
  long duracao = pulseIn(PINO_ECHO, HIGH, 30000);
  if (duracao == 0) return -1;
  return duracao * 0.0343 / 2.0;
}

String classificar(int dias, float temp, float umid) {
  if (dias <= 0) return "OK";
  if (dias >= DIAS_ALERTA_SEMPRE) return "ALERTA";
  bool climaFavoravel = temp >= TEMP_ALERTA && umid >= UMIDADE_ALERTA;
  if (dias >= DIAS_ALERTA_CLIMA && climaFavoravel) return "ALERTA";
  return "ATENCAO";
}

void mostrarEstado(String estado) {
  digitalWrite(LED_VERDE, estado == "OK");
  digitalWrite(LED_AMARELO, estado == "ATENCAO");
  digitalWrite(LED_VERMELHO, estado == "ALERTA");

  if (estado == "ALERTA") {
    // bipes repetidos enquanto estiver em alerta
    for (int i = 0; i < 3; i++) {
      tone(PINO_BUZZER, 2000, 150);
      delay(250);
    }
  } else if (estado == "ATENCAO" && estadoAnterior != "ATENCAO") {
    tone(PINO_BUZZER, 1000, 200);  // um bipe só quando entra em atenção
  }
}

void enviarJson(String corpo) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Sem Wi-Fi, leitura nao enviada");
    return;
  }
  WiFiClient cliente;
  HTTPClient http;
  http.setConnectTimeout(15000);  // o simulador às vezes demora para conectar
  http.setTimeout(15000);
  http.begin(cliente, URL_API);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Token-Dispositivo", TOKEN_DISPOSITIVO);
  int codigo = http.POST(corpo);
  Serial.print("API respondeu HTTP ");
  Serial.println(codigo);
  if (codigo > 0) Serial.println(http.getString());
  http.end();
}

void setup() {
  Serial.begin(115200);
  dht.setup(PINO_DHT, DHTesp::DHT22);
  pinMode(PINO_TRIG, OUTPUT);
  pinMode(PINO_ECHO, INPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);

  Serial.print("Conectando no Wi-Fi");
  WiFi.begin(WIFI_NOME, WIFI_SENHA);
  int tentativas = 0;
  while (WiFi.status() != WL_CONNECTED && tentativas < 40) {
    delay(250);
    Serial.print(".");
    tentativas++;
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " conectado!" : " sem Wi-Fi, segue so no alerta local");
}

void loop() {
  TempAndHumidity clima = dht.getTempAndHumidity();
  float distancia = medirDistancia();
  if (isnan(clima.temperature) || distancia < 0) {
    Serial.println("Leitura invalida, tentando de novo");
    delay(1000);
    return;
  }

  float nivel = ALTURA_POTINHO_CM - distancia;
  if (nivel < 0) nivel = 0;

  // conta há quantos dias tem água no potinho
  if (nivel >= AGUA_MINIMA_CM) {
    if (!temAgua) {
      temAgua = true;
      inicioAgua = millis();
    }
  } else {
    temAgua = false;
  }
  int dias = temAgua ? (millis() - inicioAgua) / MS_POR_DIA + 1 : 0;

  String estado = classificar(dias, clima.temperature, clima.humidity);
  mostrarEstado(estado);

  if (millis() - ultimoEnvio >= INTERVALO_ENVIO || estado != estadoAnterior) {
    JsonDocument doc;
    doc["dispositivo_id"] = ID_DISPOSITIVO;
    doc["tipo_dispositivo"] = "esp32";
    doc["latitude"] = -23.541;
    doc["longitude"] = -46.471;
    doc["metrica"] = "dias_agua_parada";
    doc["valor"] = dias;
    JsonObject leituras = doc["leituras"].to<JsonObject>();
    leituras["temperatura_c"] = round(clima.temperature * 10) / 10.0;
    leituras["umidade_pct"] = round(clima.humidity * 10) / 10.0;
    leituras["distancia_cm"] = round(distancia * 10) / 10.0;
    leituras["nivel_agua_cm"] = round(nivel * 10) / 10.0;
    JsonObject sensores = doc["status_sensores"].to<JsonObject>();
    sensores["temperatura"] = clima.temperature >= TEMP_ALERTA ? "ALERTA" : "OK";
    sensores["umidade"] = clima.humidity >= UMIDADE_ALERTA ? "ALERTA" : "OK";
    sensores["agua"] = nivel >= AGUA_MINIMA_CM ? "ALERTA" : "OK";
    doc["status_local"] = estado;

    String corpo;
    serializeJson(doc, corpo);
    Serial.println("----------------------------------------");
    Serial.print("Estado: ");
    Serial.println(estado);
    Serial.print("JSON enviado: ");
    Serial.println(corpo);
    enviarJson(corpo);
    ultimoEnvio = millis();
  }

  estadoAnterior = estado;
  delay(1000);
}
