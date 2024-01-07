import sys
import os
import argparse
import socket
import subprocess
import time
import hashlib
import zlib
import json
from pathlib import Path
from shutil import which, rmtree
from urllib.parse import urlparse
from mitmproxy.io import FlowReader

def main():

    parser = argparse.ArgumentParser(
        description=
        "Mockasite: Record and serve back a mock version of a website")
    parser.add_argument('--capture',
                        action='store_true',
                        help='Record web interactions for later use.')

    parser.add_argument('--review-capture',
                        action='store_true',
                        help='Review the last capture.')

    parser.add_argument('--delete-capture',
                        action='store_true',
                        help='Delete the last capture.')

    parser.add_argument(
        '--process',
        action='store_true',
        help='Process the last capture.' +
        ' This will extract and dump HTTP request and response data into a' +
        ' structured directory format.')

    parser.add_argument('--review-processed',
                        action='store_true',
                        help='Review processed files.')

    parser.add_argument('--delete-processed',
                        action='store_true',
                        help='Delete processed files.')

    parser.add_argument('--delete-all',
                        action='store_true',
                        help='Delete the last capture and processed files.')

    parser.add_argument(
        '--playback',
        action='store_true',
        help=
        'Replay processed data as a functioning interactive mock of the original site.'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export a standalone server that serves the mock website.')

    args = parser.parse_args()

    if args.capture:
        capture()
    elif args.review_capture:
        review_capture()
    elif args.delete_capture:
        delete_last_capture()
    elif args.process:
        process_capture()
    elif args.review_processed:
        review_processed()
    elif args.delete_processed:
        delete_processed_files()
    elif args.delete_all:
        delete_last_capture()
        delete_processed_files()
    elif args.playback:
        playback()
    elif args.export:
        export()
    else:
        parser.print_help()

    return 0

def delete_last_capture():
    last_capture_file = get_last_capture_file()

    if os.path.exists(last_capture_file):
        try:
            os.remove(last_capture_file)
            print(f"Delete '{last_capture_file}'")
        except OSError as e:
            print(f"Error: {e.strerror}")

def delete_processed_files():
    playback_storage_path = get_playback_storage_path()
    is_directory_empty = len(os.listdir(playback_storage_path)) == 0
    if not is_directory_empty:
        try:
            rmtree(playback_storage_path)
            print(f"Delete '{playback_storage_path}'")
        except OSError as e:
            print(f"Error: {e.strerror}")

def is_port_open(host, port):
    """Check if a port is open on a given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)  # Timeout for the socket operation
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False

def capture():
    port = find_free_port()
    proc = launch_mitmdump(port)
    while not is_port_open("localhost", port):
        time.sleep(1)
    launch_chrome_with_proxy(port)
    proc.terminate()

def review_capture():
    last_capture_file = get_last_capture_file()
    if not os.path.exists(last_capture_file):
        print("Run a capture first.")
        return

    mitm_cmd = ['mitmproxy', '-n', '-r', last_capture_file]
    subprocess.call(mitm_cmd)

def print_tree(directory, prefix=''):
    """ Recursively prints a tree view of the directory """
    files = sorted(os.listdir(directory))
    for i, file in enumerate(files):
        path = os.path.join(directory, file)
        is_last = i == (len(files) - 1)
        print(prefix + ('└── ' if is_last else '├── ') + file)

        if os.path.isdir(path):
            extension = '    ' if is_last else '│   '
            print_tree(path, prefix=prefix + extension)

def review_processed():
    playback_storage_path = get_playback_storage_path()
    tree_output = subprocess.check_output(
        f'cd {playback_storage_path} && tree', shell=True, text=True)
    pager = os.environ.get('PAGER', 'less')
    try:
        subprocess.run([pager], input=tree_output, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"{e}")
        return

def playback():
    print("TODO: Implement playback functionality")

def export():
    print("TODO: Implement export functionality")

def find_free_port(starting_from: int = 8080):
    for port in range(starting_from, 65535):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise Exception("No free ports available.")

def find_chrome_executable() -> str:
    common_names = ['google-chrome-stable', 'google-chrome', 'chrome']
    for name in common_names:
        if which(name):
            return name
    raise FileNotFoundError("Google Chrome not found on system.")

def launch_mitmdump(port) -> subprocess.Popen:
    mitm_cmd = ['mitmdump', '-p', str(port), '-w', get_last_capture_file()]
    return subprocess.Popen(mitm_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

def launch_chrome_with_proxy(port):
    chrome_cmd = [
        find_chrome_executable(), f"--proxy-server=http://127.0.0.1:{port}"
    ]
    with subprocess.Popen(chrome_cmd,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as proc:
        proc.wait()

def get_last_capture_file() -> Path:
    return get_capture_storage_path() / "traffic_capture"

def get_capture_storage_path() -> Path:
    home_dir = Path.home()
    mockasite_dir = home_dir / ".mockasite"
    captures_dir = mockasite_dir / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    return captures_dir

def get_playback_storage_path() -> Path:
    home_dir = Path.home()
    mockasite_dir = home_dir / ".mockasite"
    playback_dir = mockasite_dir / "playback" / "www"
    playback_dir.mkdir(parents=True, exist_ok=True)
    return playback_dir

def convert_keys_to_string(dictionary):
    """Converts dictionary keys from tuples to strings."""
    return {
        '|'.join(map(str, key)): value
        for key, value in dictionary.items()
    }

def insert_sequence_number_in_path(path, sequence_number, query_param_hash):
    parts = path.split(f"{query_param_hash}.")
    modified_path = f"{parts[0]}{query_param_hash}.seq{sequence_number}.{parts[1]}"
    return modified_path

def get_next_sequence_number(mapKey, url_to_folder_map):
    sequence_number = 1

    while mapKey + (sequence_number, ) in url_to_folder_map:
        sequence_number += 1

    return sequence_number

def normalize_meta(meta):
    headers = meta.get('headers', {})
    headers.pop('Date', None)
    normalized_meta = {
        "status_code": meta.get('status_code'),
        "headers": headers
    }
    return json.dumps(normalized_meta, indent=4, sort_keys=True)

def format_js_file(file_path):
    try:
        subprocess.run(["prettier", "--write", file_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error formatting file {file_path}: {e}")

def hash_path(path):
    return hashlib.md5(path.encode()).hexdigest()

def process_capture():
    last_capture_file = get_last_capture_file()
    if not os.path.exists(last_capture_file):
        print("Run a capture first.")
        return

    base_dir = get_playback_storage_path()
    max_path_length = 255

    url_to_folder_map_file = base_dir / "url_to_folder_map.json"
    url_to_folder_map = {}

    with open(last_capture_file, 'rb') as f:
        reader = FlowReader(f)
        for flow in reader.stream():
            flow_type = str(type(flow))

            if "HTTPFlow" not in flow_type: continue
            http_method = flow.request.method.upper()
            parsed_url = urlparse(flow.request.pretty_url)
            query_param_hash = format(
                zlib.crc32('&'.join(flow.request.query.keys()).encode())
                & 0xffffffff, '08x')

            directory_path = os.path.join(
                base_dir, parsed_url.netloc,
                os.path.dirname(parsed_url.path.lstrip("/")))

            if len(directory_path) > max_path_length:
                hashed_path = hash_path(parsed_url.path.lstrip("/"))
                directory_path = os.path.join(base_dir, parsed_url.netloc,
                                              hashed_path)

            os.makedirs(directory_path, exist_ok=True)

            file_name = os.path.basename(parsed_url.path)

            meta_path = os.path.join(
                directory_path,
                f"{http_method}.META.{query_param_hash}.{file_name}.json")

            if len(meta_path) > max_path_length:
                meta_path = os.path.join(
                    directory_path,
                    f"{http_method}.META.{query_param_hash}.{hash_path(file_name)}.json"
                )

            body_path = os.path.join(
                directory_path,
                f"{http_method}.BODY.{query_param_hash}.{file_name}")

            if len(body_path) > max_path_length:
                body_path = os.path.join(
                    directory_path,
                    f"{http_method}.BODY.{query_param_hash}.{hash_path(file_name)}.json"
                )

            mapKey = (http_method, parsed_url.path, query_param_hash)
            if mapKey in url_to_folder_map:
                meta_path, body_path = url_to_folder_map[mapKey]

                existing_meta = None
                with open(meta_path, 'r', encoding='utf-8') as meta_file:
                    existing_meta = json.load(meta_file)
                    existing_meta_hash = hashlib.sha256(
                        normalize_meta(existing_meta).encode()).hexdigest()

                with open(body_path, 'rb') as body_file:
                    existing_body_hash = hashlib.sha256(
                        body_file.read()).hexdigest()

                hasResponse = flow.response is not None

                if hasResponse:
                    current_meta = {
                        "status_code": flow.response.status_code,
                        "headers": dict(flow.response.headers)
                    }
                    normalized_current_meta = normalize_meta(current_meta)
                    current_meta_hash = hashlib.sha256(
                        normalized_current_meta.encode()).hexdigest()
                    current_body_hash = hashlib.sha256(
                        flow.response.content).hexdigest()

                    if existing_meta_hash == current_meta_hash and existing_body_hash == current_body_hash:
                        # The response is a duplicate, so skip further processing
                        continue

                sequence_number = get_next_sequence_number(
                    mapKey, url_to_folder_map)
                mapKey = mapKey + (sequence_number, )

                if not hasResponse:
                    url_to_folder_map[mapKey] = None
                    continue

                meta_path = insert_sequence_number_in_path(
                    meta_path, sequence_number, query_param_hash)
                body_path = insert_sequence_number_in_path(
                    body_path, sequence_number, query_param_hash)

            if flow.response:
                response_data = {
                    "status_code": flow.response.status_code,
                    "headers": dict(flow.response.headers)
                }
                with open(meta_path, 'w', encoding='utf-8') as meta_file:
                    json.dump(response_data, meta_file, indent=4)

                with open(body_path, 'wb') as body_file:
                    body_file.write(flow.response.content)

                url_to_folder_map[mapKey] = [meta_path, body_path]

    string_keyed_dict = convert_keys_to_string(url_to_folder_map)

    with open(url_to_folder_map_file, 'w', encoding='utf-8') as map_file:
        json.dump(string_keyed_dict, map_file, indent=4)

if __name__ == '__main__':
    sys.exit(main())
