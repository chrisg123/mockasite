from subprocess import Popen, DEVNULL
from typing import Callable, Any, Union, Dict
from multiprocessing import Process, Queue

class ProcessTracker:

    def __init__(self):
        self.python_processes: Dict[int, Process] = {}
        self.subprocesses: Dict[int, Popen] = {}

    def start(self, target: Union[Callable[[Queue, Any], None], list],
              output: Queue, *args: Any) -> int:
        """Starts a new process and keeps track of it"""
        pid = None
        if isinstance(target, list):
            # We will manage the lifecycle of the process manually
            # pylint: disable=consider-using-with
            proc = Popen(target, stdout=DEVNULL, stderr=DEVNULL)
            self.subprocesses[proc.pid] = proc
            pid = proc.pid
        else:
            proc = Process(target=target, args=(output, ) + args)
            proc.start()
            self.python_processes[proc.pid] = proc
            pid = proc.pid

        return pid

    def wait(self, pid=None):
        """Waits for specific process or all processes."""
        if pid:
            if pid in self.python_processes:
                self.python_processes[pid].join()
            elif pid in self.subprocesses:
                self.subprocesses[pid].wait()
        else:
            for proc in self.python_processes.values():
                proc.join()
            for proc in self.subprocesses.values():
                proc.wait()

    def terminate(self, pid):
        """Terminates a process by PID"""

        if pid in self.python_processes:
            proc = self.python_processes[pid]
            try:
                proc.terminate()
                proc.join()
            except Exception as e:
                print(f"Failed to terminate process {pid}: {e}")

        elif pid in self.subprocesses:
            proc = self.subprocesses[pid]
            try:
                proc.terminate()
                proc.wait()
            except Exception as e:
                print(f"Failed to terminate process {pid}: {e}")

    def terminate_all(self):
        """Stops all tracked processes"""
        for pid in list(self.python_processes.keys()):
            self.terminate(pid)

        for pid in list(self.subprocesses.keys()):
            self.terminate(pid)
