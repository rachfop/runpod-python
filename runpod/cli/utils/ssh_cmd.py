'''
RunPod | CLI | Utils | SSH Command

Connect and run commands over SSH.
'''
import os
import logging
import subprocess
import colorama
import paramiko

from .rp_info import get_pod_ssh_ip_port
from .rp_userspace import find_ssh_key_file
from .rp_runpodignore import get_ignore_list

logging.basicConfig()
logging.getLogger("paramiko").setLevel(logging.WARNING)


class SSHConnection:
    ''' Connect and run commands over SSH. '''

    def __init__(self, pod_id):
        self.pod_id = pod_id

        self.pod_ip, self.pod_port = get_pod_ssh_ip_port(pod_id)
        assert None not in [self.pod_ip, self.pod_port]

        self.key_file = find_ssh_key_file(self.pod_ip, self.pod_port)
        assert self.key_file is not None

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(self.pod_ip, port=self.pod_port,
                         username='root', key_filename=self.key_file)

        colorama.init(autoreset=True) # Initialize colorama

    def run_commands(self, commands):
        ''' Runs a list of bash commands over SSH. '''
        for command in commands:
            command = f'source /root/.bashrc && {command}'
            command = f'source /etc/rp_environment && {command}'
            _, stdout, stderr = self.ssh.exec_command(command)
            for line in stdout:
                print(colorama.Fore.GREEN + f"[{self.pod_id}]", line.strip())
            for line in stderr:
                print(colorama.Fore.RED + f"[{self.pod_id} ERROR]", line.strip())

    def put_file(self, local_path, remote_path):
        ''' Copy local file to remote machine over SSH. '''
        with self.ssh.open_sftp() as sftp:
            sftp.put(local_path, remote_path)

    def get_file(self, remote_path, local_path):
        ''' Fetch a remote file to local machine over SSH. '''
        with self.ssh.open_sftp() as sftp:
            sftp.get(remote_path, local_path)

    def launch_terminal(self):
        ''' Launch an interactive terminal over SSH. '''
        cmd = [
            "ssh" , "-p", str(self.pod_port),
            "-o", "StrictHostKeyChecking=no",
            "-i", self.key_file,
            f"root@{self.pod_ip}"
        ]

        subprocess.run(cmd, check=True)

    def rsync(self, local_path, remote_path, quiet=False):
        """ Sync a local directory to a remote directory over SSH.

        A .runpodignore file can be used to ignore files and directories.
        This file should be placed in the root of the local directory to sync.

        Args:
            local_path (str): The local directory to sync.
            remote_path (str): The remote directory to sync.
        """
        ssh_options = [
            "-o", "StrictHostKeyChecking=no",
            "-p", str(self.pod_port),
            "-i", self.key_file
        ]

        rsync_cmd = ["rsync", "-avz", "--no-owner", "--no-group"]

        for pattern in get_ignore_list():
            rsync_cmd.extend(["--exclude", pattern])

        if quiet:
            rsync_cmd.append("--quiet")

        rsync_cmd.extend([
            "-e", f"ssh {' '.join(ssh_options)}",
            local_path,
            f"root@{self.pod_ip}:{remote_path}"
        ])

        return subprocess.run(rsync_cmd, check=True)

    def close(self):
        ''' Close the SSH connection. '''
        self.ssh.close()
