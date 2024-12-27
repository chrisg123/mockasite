import os
import sys
import pwd
import subprocess
import zlib
import time
from typing import Iterable, Tuple, Optional, List
from pathlib import Path

def is_root() -> bool:
    return os.geteuid() == 0

def get_effective_user() -> str:
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return sudo_user
    return os.getlogin()

def mkdir_p(path: Path, chown: Optional[str] = None):
    uid, gid = None, None
    if chown:
        try:
            user_info = pwd.getpwnam(chown)
            uid, gid = user_info.pw_uid, user_info.pw_gid
        except KeyError as e:
            raise ValueError(f"User '{chown}' does not exist.") from e

    current_path = path
    dirs_to_create = []
    while not current_path.exists():
        dirs_to_create.append(current_path)
        current_path = current_path.parent

    for d in reversed(dirs_to_create):
        d.mkdir(parents=False, exist_ok=True)
        if uid is not None and gid is not None:
            try:
                os.chown(d, uid, gid)
            except PermissionError:
                print(f"Could not change ownership of '{d}'.")
                raise

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

    if not get_user_confirmation("This command requires root privileges." +
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
                     query_params: Iterable[str],
                     origin_header: str,
                     sequence_number: int = None) -> str:
    if not (origin_header.startswith(
        ("http://", "https://")) or origin_header == "no_origin"):
        raise ValueError(
            "origin_header must start with 'http://' or 'https://'," +
            f" or be 'no_origin'. Value was {origin_header}")

    query_params_str = [str(param) for param in query_params]
    query_param_hash = hash_crc32('&'.join(query_params_str))
    origin_hash = hash_crc32(origin_header)
    base_key = f"{http_method}|{path}|{query_param_hash}|{origin_hash}"
    return f"{base_key}|{sequence_number}" if sequence_number is not None else base_key

def split_map_key(map_key: str,
                  delimiter: str = '|') -> Tuple[str, str, str, str]:
    components = map_key.split(delimiter)
    if len(components) == 5:
        return (components[0], components[1], components[2], components[3],
                components[4])

    return (components[0], components[1], components[2], components[3], None)

def get_next_available_map_key(mapKey: str, url_to_folder_map: dict,
                               query_params: Iterable,
                               origin_header: str) -> str:
    """Returns the next available map key with an incremented sequence number."""
    http_method, path, _, _, sequence_number = split_map_key(mapKey)

    sequence_number = sequence_number or 1

    while True:
        new_map_key = generate_map_key(http_method, path, query_params,
                                       origin_header, sequence_number)
        if new_map_key not in url_to_folder_map:
            break
        sequence_number += 1

    return new_map_key
def ensure_chrome_not_running():

    def is_chrome_running() -> bool:
        try:
            subprocess.run(['pgrep', 'chrome'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError:
            return False

    def kill_chrome_instances():
        subprocess.run(['pkill', 'chrome'], check=True)

    still_msg = ""
    while is_chrome_running():

        if get_user_confirmation(
                f"\nChrome browser is {still_msg}running. It must be closed to proceed.\n" +
                "Choose 'Y' to kill all instances of Chrome, or manually close" +
                " then proceed with 'N'.",
                default_to_yes=False):
            print("Attempting to close all Chrome instances...")
            kill_chrome_instances()
            break
        still_msg = "STILL "

    time.sleep(1)

    if is_chrome_running():
        raise SystemExit("Process aborted due to running Chrome instances.")

    print("No running Chrome instances detected. Proceeding...")
