import json
import zlib
import os
from collections import defaultdict
from flask import Flask, request, Response
from pathlib import Path
from flask_cors import CORS
from queue import Queue
import logging
from logging.handlers import QueueHandler

class MockServer:
    RED = '\033[91m'
    GREEN = '\033[92m'
    RESET = '\033[0m'

    def __init__(self, playback_storage_path: Path):
        self.app = Flask(__name__)
        CORS(self.app)

        self.request_count = defaultdict(int)
        self.url_to_folder_map_file = playback_storage_path / "url_to_folder_map.json"
        with open(self.url_to_folder_map_file, 'r', encoding='utf-8') as f:
            self.url_to_folder_map = json.load(f)

        self.ignore_headers = {'content-encoding', 'content-length'}

        self.app.route('/', defaults={'path': ''})(self.mock_server)
        self.app.route('/<path:path>',
                       methods=['GET', 'POST', 'PUT', 'DELETE',
                                'OPTIONS'])(self.mock_server)

    def mock_server(self, path):
        http_method = request.method

        query_param_hash = format(
            zlib.crc32('&'.join(request.args.keys()).encode())
            & 0xffffffff, '08x')

        map_key = f"{http_method}|{'/' + path}|{query_param_hash}"
        map_key_seq = map_key

        if self.request_count[map_key] > 0:
            map_key_seq += f"|{self.request_count[map_key]}"

        self.request_count[map_key] += 1

        if map_key_seq in self.url_to_folder_map:
            map_key = map_key_seq
        else:
            self.request_count[map_key] = 0

        if map_key in self.url_to_folder_map and self.url_to_folder_map[
                map_key] is not None:

            meta_path, body_path = self.url_to_folder_map[map_key]

            meta = {"status_code": 200, "headers": {}}
            body = ''

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

            return response

        return "No Content", 204

    def run(self):
        self.app.run(debug=True, use_reloader=False)
