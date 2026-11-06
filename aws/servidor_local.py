"""
Alerta Criadouro - sobe a Lambda em http://127.0.0.1:8099 para testar o simulador sem AWS.
Uso: python3 servidor_local.py   (e em outro terminal o simulador com FUNCTION_URL=http://127.0.0.1:8099)
"""
from http.server import BaseHTTPRequestHandler, HTTPServer

import teste_local  # reaproveita o banco e a IA falsos

fn = teste_local.fn


class Tratador(BaseHTTPRequestHandler):
    def rodar(self, metodo):
        tamanho = int(self.headers.get("Content-Length") or 0)
        corpo = self.rfile.read(tamanho).decode() if tamanho else None
        evento = {"rawPath": self.path, "requestContext": {"http": {"method": metodo}},
                  "headers": dict(self.headers), "body": corpo}
        r = fn.lambda_handler(evento, None)
        saida = r["body"].encode()
        self.send_response(r["statusCode"])
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(saida)))
        self.end_headers()
        self.wfile.write(saida)

    def do_POST(self):
        self.rodar("POST")

    def do_GET(self):
        self.rodar("GET")

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", 8099), Tratador).serve_forever()
