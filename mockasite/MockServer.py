import json
import os
from collections import defaultdict
from flask import Flask, request, Response
from pathlib import Path
from flask_cors import CORS
from queue import Queue
import logging
from logging.handlers import QueueHandler
from .utils import (get_pkg_name, generate_map_key, split_map_key, find_free_port)

class MockServer:
    RED = '\033[91m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

    def __init__(self, url_to_folder_map_file: Path, port: int):
        self.app = Flask(__name__)
        self.port = port
        CORS(self.app)

        self.request_count = defaultdict(int)
        self.url_to_folder_map_file = url_to_folder_map_file
        with open(self.url_to_folder_map_file, 'r', encoding='utf-8') as f:
            self.url_to_folder_map = json.load(f)

        self.ignore_headers = {'content-encoding', 'content-length'}

        self.app.route('/', defaults={'path': ''})(self.mock_server)
        self.app.route('/<path:path>',
                       methods=['GET', 'POST', 'PUT', 'DELETE',
                                'OPTIONS'])(self.mock_server)

    def mock_server(self, path):
        http_method = request.method
        origin_header = request.headers.get("Origin", "no_origin")
        query_params = request.args.keys()
        map_key = generate_map_key(http_method, '/' + path, query_params, origin_header)
        map_key_seq = map_key
        _, _, query_param_hash, _, _ = split_map_key(map_key)

        if self.request_count[map_key] > 0:
            map_key_seq = generate_map_key(http_method, '/' + path,
                                           query_params,
                                           origin_header,
                                           self.request_count[map_key])

        self.request_count[map_key] += 1

        if map_key_seq in self.url_to_folder_map:
            map_key = map_key_seq
        else:
            self.request_count[map_key] = 0

        if map_key in self.url_to_folder_map and self.url_to_folder_map[
                map_key] is not None:

            meta_path, body_path = self.url_to_folder_map[map_key]

            meta = {"status_code": 200, "headers": {}}
            body = b''

            if os.path.isfile(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)

            if os.path.isfile(body_path):
                with open(body_path, 'rb') as f:
                    body = f.read()

            status_code = meta["status_code"]

            response = Response(body, status=status_code)

            for key, value in meta["headers"].items():
                if key in self.ignore_headers: continue
                response.headers[key] = value


            print(f"DEBUG: body_path: {body_path}", flush=True)
            return response

        # Debug information if map_key was not found
        debug_info = {
            "source": f"{get_pkg_name()}",
            "message": "No recorded response found for request.",
            "http_method": http_method,
            "path": path,
            "origin_header": origin_header,
            "query_params": list(query_params),
            "generated_map_key": map_key,
            "map_key_sequence": map_key_seq,
            "available_keys": list(self.url_to_folder_map.keys())
        }

        # Return debug info as a JSON response
        response = Response(json.dumps(debug_info, indent=4), status=404, mimetype="application/json")
        response.headers['Access-Control-Allow-Origin'] = '*'
        if origin_header:
            response.headers['Access-Control-Allow-Origin'] = origin_header
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
        return response

    def run(self):
        self.app.run(port=self.port, debug=True, use_reloader=False)
