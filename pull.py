import argparse
import functools
import logging
import sys
import os

import paramiko.client

log = logging.getLogger(__name__)


def short_hostname(hostname):
    return hostname.split('.')[0]

class ShellCommand:
    def __init__(self, command):
        self.command = command

    def exec(self, hostname, client):
        stdin, stdout, stderr = client.exec_command(self.command)
        if stdout.channel.recv_exit_status():
            for line in stdout.readlines():
                logging.info("%s:%s" % (short_hostname(hostname), line))
            for line in stderr.readlines():
                logging.error("%s:%s" % (short_hostname(hostname), line))
        logging.info("%s:%s" % (short_hostname(hostname), "SUCCESS"))

class FilePutCommand:
    def __init__(self, local, remote):
        self.local = local
        self.remote = remote

    def exec(self, hostname, client):
        ftp_client = client.open_sftp()
        ftp_client.put(self.local, self.remote)
        ftp_client.close()

class FileGetCommand:
    def __init__(self, remote, local):
        self.local = local
        self.remote = remote

    def exec(self, hostname, client):
        ftp_client = client.open_sftp()
        ftp_client.get(self.remote, self.local)
        ftp_client.close()

def ssh_public_key(source):
    with open(source) as f:
        return f.readline()

def short_hostname(hostname):
    return hostname.split('.')[0]

def exec_command(command, admin, hostname):
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)
    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    for key in agent_keys:
        try:
            client.connect(hostname, username=admin, pkey=key)
            channel = client.get_transport().open_session()
            stdin, stdout, stderr = client.exec_command(command)
            if stdout.channel.recv_exit_status():
                for line in stderr.readlines():
                    logging.error("%s:%s" % (short_hostname(hostname), line))
            logging.info("%s:%s" % (short_hostname(hostname), "SUCCESS"))
            break
        except Exception as e:
            logging.error(e)

def exec_chain(command_chain, username, hostname):
    """Executes a chain of commands on a remote host"""
    client = paramiko.client.SSHClient()
    client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy)

    # setup connection to remote host
    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    for key in agent_keys:
        try:
            client.connect(hostname, username=username, pkey=key)
            break
        except Exception as e:
            logging.error(e)
            return

    # execute commands on remote host
    for command in command_chain:
        command.exec(hostname, client)

def main(argv):
  logging.getLogger('').setLevel(logging.INFO)
  hostname = argv[0]
  data_dir = argv[1]
  #remove_tar_cmd = ShellCommand('rm data.tgz')
  create_tar_cmd = ShellCommand('tar -cf data.tgz {}'.format(data_dir))
  scp_tar_cmd = FileGetCommand('/users/hvolos01/data.tgz', '/tmp/data.tgz')
  exec_chain([create_tar_cmd, scp_tar_cmd], 'hvolos01', hostname)
  os.system('tar -xf /tmp/data.tgz')

if __name__ == "__main__":
  main(sys.argv[1:])
