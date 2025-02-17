import sys
import io
import os
import argparse
import socket
import subprocess
import time
import hashlib
import json
import asyncio
from signal import signal, SIGINT
from pathlib import Path
from shutil import which, rmtree, copy
from urllib.parse import urlparse
from multiprocessing import Queue
from queue import Empty
from mitmproxy.io import FlowReader
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster
from .MockServer import MockServer
from .ProcessTracker import ProcessTracker
from .utils import (get_pkg_name, generate_map_key, split_map_key,
                    get_next_available_map_key, re_run_as_sudo,
                    get_user_confirmation, is_root, docker_image_remove,
                    docker_image_exists, get_effective_user, mkdir_p,
                    ensure_chrome_not_running, find_free_port)

class OutputFilter(io.TextIOWrapper):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        start_color = "\033[1;35m"
        reset_color = "\033[0m"
        self.prefix = f"{start_color}:: {reset_color} "

    def write(self, text):
        if isinstance(text, bytes):
            text = text.decode('utf-8')

        modified_text = ''.join(f'{self.prefix}{line}\n'
                                for line in text.splitlines()
                                if line.strip() != '')
        super().write(modified_text)
        self.flush()

# sys.stdout = OutputFilter(sys.stdout.buffer, encoding='utf-8')
# sys.stderr = OutputFilter(sys.stderr.buffer, encoding='utf-8')

def sigx(signum, _stackframe, main_pid: int, ptracker: ProcessTracker):
    current_pid = os.getpid()

    if current_pid == main_pid:
        if signum == SIGINT:
            ptracker.terminate_all()
            sys.stdout.write("\nexit\n")
            sys.exit(0)

def main():
    main_pid = os.getpid()
    ptracker = ProcessTracker()
    signal(SIGINT, lambda s, f: sigx(s, f, main_pid, ptracker))
    pkg_name = get_pkg_name()
    parser = argparse.ArgumentParser(
        description=
        f"{pkg_name.title()}: Record and serve back a mock version of a website"
    )
    parser.add_argument('--capture',
                        action='store_true',
                        help='Record web interactions for later use.')

    parser.add_argument('--url',
                        type=str,
                        metavar='URL',
                        help='The url to pass to the browser.')

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
        ensure_chrome_not_running()
        capture(url=args.url)
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
        delete_docker_export()
    elif args.playback:
        ensure_chrome_not_running()
        playback(ptracker)
    elif args.export:
        export()
    else:
        parser.print_help()

    return 0

def delete_last_capture():
    last_capture_file = get_last_capture_file()
    playback_metadata_path = get_capture_storage_path(
    ) / "playback_metadata.json"

    if os.path.exists(last_capture_file):
        try:
            os.remove(last_capture_file)
            print(f"Delete '{last_capture_file}'")
        except OSError as e:
            print(f"Error: {e.strerror}")

    if os.path.exists(playback_metadata_path):
        try:
            os.remove(playback_metadata_path)
            print(f"Delete '{playback_metadata_path}'")
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

def delete_docker_export():
    image_name = f"{get_pkg_name()}_export"
    tar_file = f"{image_name}.tar"

    if os.path.isfile(tar_file):
        try:
            os.remove(tar_file)
            print(f"Delete '{tar_file}'")
        except Exception as e:
            print(f"Error: {e}")

    if not which("docker"): return

    def do_docker_remove(default_to_yes=False, msg_prefix="") -> bool:
        return get_user_confirmation(
            f"{msg_prefix}Remove any docker images named '{image_name}'?",
            default_to_yes)

    if is_root():
        if not docker_image_exists(image_name):
            print(
                f"Nothing to do, no docker image named '{image_name}' found.")
            return
        if not do_docker_remove(default_to_yes=True, msg_prefix="*root* "):
            return
        docker_image_remove(image_name)
    else:
        if do_docker_remove(): re_run_as_sudo()
        return

def is_port_open(host, port):
    """Check if a port is open on a given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1) # Timeout for the socket operation
        try:
            s.connect((host, port))
            return True
        except (socket.timeout, ConnectionRefusedError):
            return False

def capture(url: str):
    port = find_free_port()
    proc = launch_mitmdump(port)

    playback_metadata_path = get_capture_storage_path(
    ) / "playback_metadata.json"

    with open(playback_metadata_path, 'w', encoding='utf-8') as f:
        json.dump({"url": url}, f)

    while not is_port_open("localhost", port):
        time.sleep(1)

    launch_chrome_with_proxy(port, url)

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

def run_playback_server(output: Queue, url_to_folder_map_file: Path, port: int):
    server = MockServer(url_to_folder_map_file, port)
    try:
        server.run()
    except Exception as e:
        output.put(f"Error: {str(e)}")
    finally:
        output.put('Server stopped')

def is_docker() -> bool:
    return os.getenv(f"{get_pkg_name().upper()}_ENV") == "DOCKER"

def playback(ptracker: ProcessTracker):
    playback_storage_path = get_playback_storage_path()
    is_directory_empty = len(os.listdir(playback_storage_path)) == 0
    if is_directory_empty:
        print(f"Playback storage path '{playback_storage_path}' is empty.")
        return

    url_to_folder_map_file = get_url_to_folder_map_file(playback_storage_path)

    if not url_to_folder_map_file.exists():
        print(f"Playback map file '{url_to_folder_map_file}' does not exist." +
              " Try running --process first.")
        return

    proxy_port = 8080 if is_docker() else find_free_port()
    playback_port = find_free_port(starting_from=5000)

    binding = '0.0.0.0' # Any
    output = Queue()

    ptracker.start(run_playback_server, output, url_to_folder_map_file, playback_port)
    ptracker.start(start_proxy_server, output, binding, proxy_port, playback_port)

    playback_metadata_path = get_playback_storage_path(
    ) / "playback_metadata.json"
    try:
        with open(playback_metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            url = metadata["url"]
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading playback metadata: {e}")
        return

    while not is_port_open("localhost", proxy_port):
        time.sleep(1)

    if not is_docker():
        ptracker.start(get_chrome_cmd(proxy_port, url), output)

    try:
        while True:
            if not output.empty():
                try:
                    results = output.get(timeout=1)
                    print(f"{results}")
                    if results == 'Server stopped':
                        break
                except Empty:
                    print("Unexpected empty queue after non-empty check.")
            else:
                time.sleep(1)

    finally:
        ptracker.terminate_all()

class Addon:
    def __init__(self, port):
        self.port = port

    def request(self, flow):
        flow.request.host = "localhost"
        flow.request.port = self.port
        flow.request.scheme = "http"

def start_proxy_server(output: Queue, binding: str, proxy_port: int, playback_port: int):

    async def run_proxy():
        options = Options(listen_host=binding, listen_port=proxy_port)
        m = DumpMaster(options, with_termlog=False, with_dumper=False)
        m.addons.add(Addon(playback_port))

        try:
            await m.run()
        except KeyboardInterrupt:
            m.shutdown()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    output.put(
        f"Starting proxy server binding={binding}, port={proxy_port}. [{os.getpid()}]"
    )
    loop.run_until_complete(run_proxy())
    loop.close()

def export():
    re_run_as_sudo()

    playback_storage_path = get_playback_storage_path()
    playback_tar = "playback.tar.gz"
    image_name = f"{get_pkg_name()}_export"
    image_tar = f"{image_name}.tar"
    try:
        subprocess.run(["rm", "-f", playback_tar], check=True)
        subprocess.run([
            "tar", "czvf", playback_tar, "-C", playback_storage_path / "..",
            "www"
        ],
                       check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error durring export: {e}")

    pkg_name = get_pkg_name()
    dockerfile_content = f"""
    FROM python:3.12-slim

    ENV {pkg_name.upper()}_ENV=DOCKER

    WORKDIR app

    RUN mkdir -p /app/playback

    RUN apt-get update && apt-get install -y git

    COPY {playback_tar} /app/playback/{playback_tar}

    RUN tar -xzvf /app/playback/{playback_tar} -C /app/playback

    RUN pip install git+https://github.com/chrisg123/{pkg_name}.git

    EXPOSE 8080

    CMD ["python", "-m", "{pkg_name}", "--playback"]
    """
    with open("Dockerfile", "w", encoding='utf-8') as f:
        f.write(dockerfile_content)

    # Check if Docker is installed
    if not which("docker"):
        print(
            "Docker is not installed. Please install Docker to use the export functionality."
        )
        return

    try:
        subprocess.run(
            ["docker", "build", "--no-cache", "-t", image_name, "."],
            check=True)
        subprocess.run(["docker", "save", "-o", image_tar, image_name],
                       check=True)

        print(f"Docker image saved to {image_tar}.")
    except subprocess.CalledProcessError as e:
        print(f"Error durring export: {e}")

    docker_image_remove(image_name)

def find_chrome_executable() -> str:
    common_names = ['google-chrome-stable', 'google-chrome', 'chrome']
    for name in common_names:
        if which(name):
            return name
    raise FileNotFoundError("Google Chrome not found on system.")

def launch_mitmdump(port) -> subprocess.Popen:
    # pkg_name = get_pkg_name()
    # cert_path = Path.home(
    # ) / f".{pkg_name}" / "certificates" / f"{pkg_name}CA.pem"
    mitm_cmd = ['mitmdump', '-p', str(port), '-w', get_last_capture_file()]
    return subprocess.Popen(mitm_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

def launch_chrome_with_proxy(port: int, url: str):
    chrome_cmd = get_chrome_cmd(port, url)

    with subprocess.Popen(chrome_cmd,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL) as proc:
        proc.wait()

def get_chrome_cmd(port: int, url: str) -> [str]:
    chrome_cmd = [
        find_chrome_executable(), "--incognito",
        f"--proxy-server=http://127.0.0.1:{port}"
    ]
    if url:
        chrome_cmd.extend([url])
    return chrome_cmd

def get_last_capture_file() -> Path:
    return get_capture_storage_path() / "traffic_capture"

def get_capture_storage_path() -> Path:
    home_dir = Path.home()
    pkg_dir = home_dir / f".{get_pkg_name()}"
    captures_dir = pkg_dir / "captures"
    captures_dir.mkdir(parents=True, exist_ok=True)
    return captures_dir

def get_playback_storage_path() -> Path:
    if is_docker():
        return Path("/") / "app" / "playback" / "www"

    home_dir = Path.home()
    pkg_dir = home_dir / f".{get_pkg_name()}"
    playback_dir = pkg_dir / "playback" / "www"
    mkdir_p(playback_dir, get_effective_user())
    return playback_dir

def get_url_to_folder_map_file(playback_storage_path: Path) -> Path:
    return playback_storage_path / "url_to_folder_map.json"

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

    playback_metadata_path = get_capture_storage_path(
    ) / "playback_metadata.json"

    copy(playback_metadata_path, base_dir)

    url_to_folder_map_file = base_dir / "url_to_folder_map.json"
    url_to_folder_map = {}

    with open(last_capture_file, 'rb') as f:
        reader = FlowReader(f)
        for flow in reader.stream():
            flow_type = str(type(flow))

            if "HTTPFlow" not in flow_type: continue

            origin_header = flow.request.headers.get("Origin", "no_origin")
            http_method = flow.request.method.upper()
            parsed_url = urlparse(flow.request.pretty_url)
            query_params = flow.request.query.keys()

            mapKey = generate_map_key(http_method, parsed_url.path,
                                      query_params, origin_header)

            _, _, query_param_hash, origin_hash, _ = split_map_key(mapKey)

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
                f"{http_method}.META.{origin_hash}.{query_param_hash}.{file_name}.json"
            )

            if len(meta_path) > max_path_length:
                meta_path = os.path.join(
                    directory_path,
                    f"{http_method}.META.{origin_hash}.{query_param_hash}.{hash_path(file_name)}.json"
                )

            body_path = os.path.join(
                directory_path,
                f"{http_method}.BODY.{origin_hash}.{query_param_hash}.{file_name}"
            )

            if len(body_path) > max_path_length:
                body_path = os.path.join(
                    directory_path,
                    f"{http_method}.BODY.{origin_hash}.{query_param_hash}.{hash_path(file_name)}.json"
                )

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

                mapKey = get_next_available_map_key(mapKey, url_to_folder_map,
                                                    query_params,
                                                    origin_header)
                _, _, _, _, sequence_number = split_map_key(mapKey)

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

                if flow.response.content is not None:
                    with open(body_path, 'wb') as body_file:
                        body_file.write(flow.response.content)
                else:
                    with open(body_path, 'wb') as body_file:
                        pass # Creates empty file

                url_to_folder_map[mapKey] = [meta_path, body_path]

    with open(url_to_folder_map_file, 'w', encoding='utf-8') as map_file:
        json.dump(url_to_folder_map, map_file, indent=4)
