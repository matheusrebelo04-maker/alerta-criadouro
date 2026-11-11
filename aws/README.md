# Alerta Criadouro - API serverless na AWS

Global Solution 2026.2 - Plataformas, Serviços Cognitivos & Cloud Computing - turma 1TIAPZ

- Matheus Rebelo - RM 570260
- Felipe Olmos - RM 570946
- Luiz Guilherme - RM 573486

## O cenário

O problema é a dengue dentro de casa. Cerca de 75% dos focos do mosquito ficam nas residências, e em 2024 o Brasil teve 6,48 milhões de casos prováveis, o pior ano da história. A larva vira mosquito em uns 10 dias, e a família quase sempre só percebe quando alguém já ficou doente.

**Quem é beneficiado:** famílias que moram em casas com quintal na cidade de São Paulo.

**O que o dispositivo mede:** o aparelho com ESP32 fica na área de serviço e observa um "potinho sentinela" deixado no quintal. O sensor HC-SR04 mede o nível de água do potinho e o DHT22 mede temperatura e umidade. A métrica enviada para a nuvem é `dias_agua_parada`: há quantos dias o potinho está com água.

**Limiares adotados** (os mesmos do ESP32 e da API em Flask do projeto):

| Nível | Regra |
|---|---|
| `normal` | potinho seco (0 dias com água) |
| `atencao` | tem água parada há 1 dia ou mais |
| `critico` | água há 3 dias ou mais com temperatura de 25 °C ou mais e umidade de 70% ou mais, ou água há 5 dias em qualquer clima |

O ciclo do mosquito acelera com calor e umidade, por isso o crítico chega antes quando o tempo está quente e úmido. A leitura crítica gera `alerta = true`, que é o aviso para a família esvaziar os recipientes do quintal.

## Arquitetura

```
ESP32 no quintal ou simulador          (mesmo JSON nos dois casos)
        |  HTTPS POST /ocorrencias
        v
AWS Lambda alerta-criadouro-api (Function URL, fora de VPC)
        |-- log  -> CloudWatch Logs (payload, dados lidos, classificação, id gravado)
        |-- IA   -> modelo da Hugging Face rodando na Lambda (sentimento do relato)
        v
Amazon RDS PostgreSQL alerta-criadouro-db   tabela ocorrencias
        |
        v
GET /ocorrencias  (lista o que foi gravado, para painel ou aviso)
```

**Function URL:** https://3i6enawj4hage4fgq2i3sewkyu0ypber.lambda-url.us-east-1.on.aws

**Endpoint do RDS:** alerta-criadouro-db.c9m6ue40i2ou.us-east-1.rds.amazonaws.com (porta 5432, banco `alertacriadouro`, usuário `postgres`; a senha não vai no repositório)

## Rotas

| Rota | O que faz |
|---|---|
| `GET /health` | mostra se a função está no ar, qual modelo usa e se o token da Hugging Face está configurado |
| `POST /ocorrencias` | valida a leitura, classifica o risco, manda o relato para a IA e grava no RDS. Devolve `201` com o id, ou `400` quando falta campo ou o valor é inválido |
| `GET /ocorrencias` | lista as últimas leituras gravadas |

Exemplo do JSON enviado pelo aparelho:

```json
{
  "dispositivo_id": "esp32-quintal-001",
  "tipo_dispositivo": "esp32",
  "latitude": -23.632,
  "longitude": -46.736,
  "metrica": "dias_agua_parada",
  "valor": 3,
  "leituras": {"temperatura_c": 29.5, "umidade_pct": 83.0, "nivel_agua_cm": 3.9},
  "relato": "Achei larvas no pratinho do vaso, estou com medo da dengue",
  "medido_em": "2026-11-06T15:20:00+00:00"
}
```

A localização vai só com 3 casas decimais. Isso mostra o bairro, não a casa da família.

## Camada de IA: caminho A, Hugging Face

O modelo é o `twitter-xlm-roberta-base-sentiment`, o mesmo indicado no enunciado, na versão ONNX publicada no Hub (`onnx-community/twitter-xlm-roberta-base-sentiment-ONNX`). Ele lê o relato que a família escreve e devolve `positive`, `neutral` ou `negative`, com a confiança.

Começamos pelo endpoint `router.huggingface.co/hf-inference`, como no material da disciplina. Na hora do teste ele respondeu **402**: desde outubro de 2026 a Hugging Face só libera essa API com crédito pago. A mensagem ficou registrada no CloudWatch:

```
IA INDISPONIVEL - Hugging Face respondeu 402: "Purchase pre-paid credits to continue using Inference Providers..."
```

Mesmo assim a leitura foi classificada pelo limiar e gravada no banco, que é o que o enunciado pede quando a IA falha. Para a IA voltar a funcionar sem custo, a Lambda passou a baixar o modelo do Hub da Hugging Face na primeira chamada e rodar ele ali dentro, com `onnxruntime`. O download usa o token Read guardado na variável `HF_TOKEN`, que não aparece no código. O modelo fica em `/tmp` e na memória, então só a primeira chamada de cada instância demora alguns segundos.

Por que esse caminho:

- o modelo é multilíngue e entende o português da família;
- não precisa mexer em IAM, o que o Learner Lab não deixa (o Amazon Comprehend, caminho B, voltou `AccessDenied`);
- não tem custo por chamada e não depende de a API de terceiro estar no ar.

Se o modelo não carregar, a função registra um `WARNING` de IA indisponível e segue normalmente: classifica pelo limiar, grava no RDS e responde 201. A IA também reforça o aviso: quando já existe água parada (atenção) e o relato vem muito negativo (confiança de 0,8 ou mais), a API marca `alerta = true`.

## Arquivos

| Arquivo | O que é |
|---|---|
| `lambda_function.py` | função Lambda com as rotas, a validação, o log, a classificação, o modelo de sentimento e a gravação no RDS |
| `tabela_ocorrencias.sql` | criação da tabela `ocorrencias` e as consultas usadas nos prints |
| `simulador_dispositivo.py` | simula o ESP32 do quintal, um envio por dia, com cenário normal e de risco |
| `teste_local.py` | roda a Lambda no computador com banco e modelo falsos |
| `servidor_local.py` | sobe a Lambda local em `http://127.0.0.1:8099` para testar o simulador sem AWS |
| `evidencias/` | os prints da entrega |
| `AWS_Alerta_Criadouro.pdf` | relatório da entrega, com o cenário, a arquitetura, a IA e as evidências |

## Passo a passo para reproduzir

Tudo foi feito pelo AWS CloudShell, na região us-east-1, com a conta do AWS Academy (Learner Lab).

**1. Baixar o projeto**

```
git clone https://github.com/matheusrebelo04-maker/alerta-criadouro.git
cd alerta-criadouro/aws
```

**2. Criar o banco RDS PostgreSQL** (db.t3.micro, 20 GB, acesso público liberado na porta 5432 para a Lambda fora de VPC)

```
VPC=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)
SG=$(aws ec2 create-security-group --group-name alerta-criadouro-rds --description 'PostgreSQL do Alerta Criadouro' --vpc-id $VPC --query GroupId --output text)
aws ec2 authorize-security-group-ingress --group-id $SG --protocol tcp --port 5432 --cidr 0.0.0.0/0
umask 077; openssl rand -base64 30 | tr -dc 'A-Za-z0-9' | head -c 20 > ~/.dbsenha; umask 022
aws rds create-db-instance --db-instance-identifier alerta-criadouro-db --db-instance-class db.t3.micro \
  --engine postgres --allocated-storage 20 --storage-type gp2 --master-username postgres \
  --master-user-password "$(cat ~/.dbsenha)" --db-name alertacriadouro --vpc-security-group-ids $SG \
  --publicly-accessible --backup-retention-period 0 --no-multi-az
aws rds wait db-instance-available --db-instance-identifier alerta-criadouro-db
```

A senha é gerada aleatória e fica só no arquivo `~/.dbsenha` do CloudShell.

**3. Criar a tabela**

```
sudo dnf install -y postgresql15
export DB_HOST=$(aws rds describe-db-instances --db-instance-identifier alerta-criadouro-db --query 'DBInstances[0].Endpoint.Address' --output text)
export PGPASSWORD=$(cat ~/.dbsenha)
psql -h $DB_HOST -U postgres -d alertacriadouro -f tabela_ocorrencias.sql
```

**4. Publicar a Lambda** (com o driver `pg8000` e as bibliotecas do modelo, `onnxruntime`, `tokenizers` e `numpy`, baixadas para o Linux da Lambda)

```
P="--platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 --implementation cp --python-version 3.13 --only-binary=:all: -t pacote"
pip3 install $P pg8000 numpy
pip3 install $P --no-deps tokenizers onnxruntime
cp lambda_function.py pacote/
(cd pacote && zip -qr9 ../funcao.zip . -x '*__pycache__*')
aws lambda create-function --function-name alerta-criadouro-api --runtime python3.13 \
  --role $(aws iam get-role --role-name LabRole --query Role.Arn --output text) \
  --handler lambda_function.lambda_handler --zip-file fileb://funcao.zip --timeout 30 --memory-size 1024
aws lambda create-function-url-config --function-name alerta-criadouro-api --auth-type NONE
aws lambda add-permission --function-name alerta-criadouro-api --statement-id url-publica \
  --action lambda:InvokeFunctionUrl --principal '*' --function-url-auth-type NONE
aws lambda add-permission --function-name alerta-criadouro-api --statement-id url-publica-invoke \
  --action lambda:InvokeFunction --principal '*' --invoked-via-function-url
aws lambda update-function-configuration --function-name alerta-criadouro-api \
  --environment "Variables={DB_HOST=$DB_HOST,DB_PORT=5432,DB_NAME=alertacriadouro,DB_USER=postgres,DB_PASSWORD=$PGPASSWORD}"
```

Depois, no console da Lambda, em Configuração > Variáveis de ambiente, adicionar `HF_TOKEN` com o token Read da Hugging Face. A função fica com 1024 MB de memória (o modelo ocupa uns 300 MB), timeout de 30 segundos e fora de VPC.

**5. Rodar o simulador**

```
export FUNCTION_URL=$(aws lambda get-function-url-config --function-name alerta-criadouro-api --query FunctionUrl --output text)
python3 simulador_dispositivo.py --cenario normal --dias 3
python3 simulador_dispositivo.py --cenario risco --dias 7
python3 simulador_dispositivo.py --invalida
```

**6. Conferir**

- CloudWatch Logs, grupo `/aws/lambda/alerta-criadouro-api`: aparecem as linhas `PAYLOAD RECEBIDO`, `DISPOSITIVO=...`, `CLASSIFICACAO`, `GRAVADO NO RDS` e os `WARNING` de leitura descartada e de alerta crítico.
- Banco: `psql -h $DB_HOST -U postgres -d alertacriadouro` e as consultas do fim do `tabela_ocorrencias.sql`.

**Teste sem AWS:** `python3 teste_local.py`, ou `python3 servidor_local.py` em um terminal e o simulador com `FUNCTION_URL=http://127.0.0.1:8099` em outro.

## Evidências

| Print | Arquivo |
|---|---|
| Variável de ambiente cadastrada na Lambda | `evidencias/01_variaveis_ambiente.png` |
| Simulador enviando as leituras | `evidencias/02_simulador.png` |
| CloudWatch Logs com o payload e a classificação | `evidencias/03_cloudwatch.png` |
| Consulta no banco com as ocorrências gravadas | `evidencias/04_consulta_banco.png` |

## ODS

- **ODS 3 - Saúde e bem-estar:** avisa a família antes de a larva virar mosquito, o que reduz os casos de dengue dentro de casa.
- **ODS 10 - Redução das desigualdades:** o aparelho é barato e a nuvem não depende de estrutura na casa, então o monitoramento chega também a bairros da periferia, onde a dengue costuma pesar mais.
- **ODS 11 - Cidades e comunidades sustentáveis:** as leituras ficam gravadas por bairro e podem ajudar os agentes de saúde e a prefeitura a ver onde a água parada está se repetindo.
