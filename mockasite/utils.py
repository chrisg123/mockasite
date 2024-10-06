import os
import sys
import subprocess
import zlib
from typing import Iterable, Tuple

def re_run_as_sudo():
    if os.geteuid() == 0: return

    while True:
        try:
            response = input("This command requires root privileges." +
                             " Do you want to re-launch with sudo? [Y/n]: "
                             ).strip().lower()
        except EOFError:
            print("\nNo input detected. Aborting.")
            sys.exit(1)

        if response in ['', 'y', 'yes']: break

        if response in ['n', 'no']:
            print("Aborting.")
            sys.exit(1)

        print("Please respond with 'Y' or 'N'.")

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

def get_query_param_hash(query_params: Iterable[str]) -> str:
    return hash_crc32('&'.join(query_params))

def generate_map_key(http_method: str,
                     path: str,
                     query_param_hash: str,
                     sequence_number: int = None) -> str:
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
