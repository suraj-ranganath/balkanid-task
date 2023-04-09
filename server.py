import http.server
import socketserver
import importlib
import logging_config

PORT = 8080
MODULE_NAME = "main"

logger = logging_config.get_logger(__name__, "/var/lib/postgresql/data/server.log")

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        module = importlib.import_module(MODULE_NAME)
        module.main()

try:
    with socketserver.TCPServer(("", PORT), RequestHandler) as httpd:
        print("Serving at port", PORT)
        logger.info("Serving at port %s", PORT)
        httpd.serve_forever()
except KeyboardInterrupt:
    logger.info("KeyboardInterrupt: ending server.py")