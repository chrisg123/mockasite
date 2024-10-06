import os
import sys
import subprocess
import zlib
from typing import Iterable, Tuple

def is_root() -> bool:
    return os.geteuid() == 0

def get_user_confirmation(message: str, default_to_yes: bool = False) -> bool:
    while True:
        default_prompt = "[Y/n]" if default_to_yes else "[y/N]"
        response = input(f"{message} {default_prompt}:").strip().lower()
        if response in ['y', 'yes']: return True
        if response in ['n', 'no']: return False
        if response == '': return default_to_yes
        print("Invalid response. Please enter 'Y' or 'N'.")

def docker_image_remove(image_name):
    try:
        subprocess.run(["docker", "rmi", "-f", image_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error removing Docker image '{image_name}': {e.stderr}")

def docker_image_exists(image_name: str) -> bool:
    try:
        result = subprocess.run(["docker", "images", "-q", image_name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                check=True)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def re_run_as_sudo():
    if is_root(): return

    if not get_user_confirmation(
            "This command requires root privileges." +
            " Do you want to re-launch with sudo?"):
        print("Aborting.")
        sys.exit(0)

    print("Re-launching with sudo...")

    if __package__:
        command = ["sudo", "-E", sys.executable, "-m", __package__
                   ] + sys.argv[1:]
    else:
        command = ["sudo", "-E", sys.argv[0]] + sys.argv[1:]
    try:
        #print(command)
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to re-run as sudo: {e}")
        sys.exit(e.returncode)
    sys.exit(0)

def hash_crc32(value: str) -> str:
    return format(zlib.crc32(value.encode()) & 0xffffffff, '08x')

def generate_map_key(http_method: str,
                     path: str,
                     query_params: Iterable,
                     sequence_number: int = None) -> str:
    query_params_str = [str(param) for param in query_params]
    query_param_hash = hash_crc32('&'.join(query_params_str))
    base_key = f"{http_method}|{path}|{query_param_hash}"
    return f"{base_key}|{sequence_number}" if sequence_number is not None else base_key

def split_map_key(map_key: str,
                  delimiter: str = '|') -> Tuple[str, str, str, str]:
    components = map_key.split(delimiter)
    if len(components) == 4:
        return (components[0], components[1], components[2], components[3])

    return (components[0], components[1], components[2], None)

def get_next_available_map_key(mapKey: str, url_to_folder_map: dict) -> str:
    """Returns the next available map key with an incremented sequence number."""
    http_method, path, query_param_hash, sequence_number = split_map_key(
        mapKey)

    sequence_number = sequence_number or 1

    while True:
        new_map_key = generate_map_key(http_method, path, query_param_hash,
                                       sequence_number)
        if new_map_key not in url_to_folder_map:
            break
        sequence_number += 1

    return new_map_key
