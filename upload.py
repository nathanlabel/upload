import json
import os
import logging
import paramiko
import argparse
from scp import SCPClient, SCPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SSHConfig:
    def __init__(self, hostname: str, port: int, username: str, password: str) -> None:
        self._hostname = hostname
        self._port: int = port
        self._username: str = username
        self._password: str = password
        self._ssh_client: SCPClient = None

        if self._valid_details():
            self.connect()
            if self.is_connected():
                logger.info("Successfully connected to %s", self._hostname)
            else:
                logger.error("Failed to connect to %s", self._hostname)
        else:
            logger.error("Invalid SSH configuration details")

    def connect(self):
        if self._valid_details():
            self._ssh_client = self._create_ssh_client()
            if self._ssh_client is None:
                logger.error("Failed to create SSH client")
                return
            else:
                logger.info("Successfully created SSH client")

    def is_connected(self) -> bool:
        if self._ssh_client is None:
            return False
        return self._ssh_client.get_transport().is_active() and \
            self._ssh_client.get_transport().is_active() and \
            self._ssh_client.get_transport().is_authenticated()

    def _valid_details(self) -> bool:
        return self._hostname and \
            self._port and \
                self._username and \
                    self._password

    def _create_ssh_client(self):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self._hostname, self._port, self._username, self._password)
        return client

    def close(self):
        if self._ssh_client:
            self._ssh_client.close()
            logger.info("SSH session closed")

# Function to check sudo privileges
def check_sudo_privileges(ssh_client):
    stdin, stdout, stderr = ssh_client.exec_command('sudo -l')
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("User has sudo privileges")
        return True
    else:
        logger.error("User does not have sudo privileges: %s", stderr.read().decode())
        return False

# Function to create remote directory if it does not exist
def create_remote_directory(ssh_client, remote_dir, password):
    logger.info("Creating remote directory: %s", remote_dir)  # Add logging
    # Check if the directory already exists
    command_check = f'sudo -S ls {remote_dir}'
    stdin, stdout, stderr = ssh_client.exec_command(command_check)
    exit_status = stdout.channel.recv_exit_status()
    stdout_str = stdout.read().decode()
    stderr_str = stderr.read().decode()

    logger.info("Check directory command: %s", command_check)
    logger.info("Check directory stdout: %s", stdout_str)
    logger.info("Check directory stderr: %s", stderr_str)
    logger.info("Check directory exit status: %s", exit_status)

    if exit_status == 0:
        logger.info("Remote directory %s already exists", remote_dir)
        return  # Directory already exists, no need to create it
    else:
        logger.warning("Remote directory %s does not exist or cannot be accessed", remote_dir)

    command = f'echo {password} | sudo -S mkdir -p {remote_dir}'
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    stdout_str = stdout.read().decode()
    stderr_str = stderr.read().decode()

    logger.info("Create directory command: %s", command)
    logger.info("Create directory stdout: %s", stdout_str)
    logger.info("Create directory stderr: %s", stderr_str)
    logger.info("Create directory exit status: %s", exit_status)

    if exit_status == 0:
        logger.info("Successfully created remote directory %s", remote_dir)
    else:
        logger.error("Failed to create remote directory %s: %s", remote_dir, stderr_str)

# Function to upload file
def upload_file(ssh_client, local_file_path, remote_file_path, password):
    if not os.path.exists(local_file_path):
        logger.error("Local file %s does not exist", local_file_path)
        return

    temp_remote_path = f"/tmp/{os.path.basename(local_file_path)}"
    try:
        with SCPClient(ssh_client.get_transport()) as scp:
            scp.put(local_file_path, temp_remote_path)
    except SCPException as e:
        logger.error("SCP transfer failed for %s: %s", local_file_path, str(e))
        return

    command = f'echo {password} | sudo -S mv {temp_remote_path} {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("Successfully uploaded %s to %s", local_file_path, remote_file_path) # Modified logging
    else:
        logger.error("Failed to move %s to %s: %s", temp_remote_path, remote_file_path, stderr.read().decode())
        return

    # Convert line endings from CRLF to LF
    convert_line_endings_command = f'echo {password} | sudo -S sed -i "s/\\r$//" {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(convert_line_endings_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("Successfully converted line endings of %s to LF", remote_file_path)
    else:
        logger.error("Failed to convert line endings of %s to LF: %s", remote_file_path, stderr.read().decode())
        return

    # Change ownership to mysite:mysite
    chown_command = f'echo {password} | sudo -S chown mysite:mysite {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(chown_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        pass
    else:
        logger.error("Failed to change ownership of %s to mysite:mysite: %s", remote_file_path, stderr.read().decode())
        return

    # Make the file executable
    chmod_command = f'echo {password} | sudo -S chmod +x {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(chmod_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        pass
    else:
        logger.error("Failed to make %s executable: %s", remote_file_path, stderr.read().decode())
        return

# Function to list directory contents
def list_directory(ssh_client, remote_dir):
    command = f'ls -lh {remote_dir}'
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("Directory contents of %s:\n%s", remote_dir, stdout.read().decode())
    else:
        logger.error("Failed to list directory %s: %s", remote_dir, stderr.read().decode())

# Function to display help information
def display_help():
    help_text = """
Available Commands:
  check_sudo      - Check if the user has sudo privileges on the remote server
  create_dir PATH - Create a directory at PATH on the remote server
  upload LOCAL REMOTE - Upload a file from LOCAL path to REMOTE path
  dir PATH        - List contents of directory at PATH on the remote server
  help (or h)     - Show this help message
  exit            - Exit the application
"""
    print(help_text)

def get_args():
    parser = argparse.ArgumentParser(prog='UPLOAD', description='SSH file upload and management tool')
    parser.add_argument('-n', '--name', type=str, help="Hostname of the SSH Server", default=os.getenv('SCP_HOSTNAME'))
    parser.add_argument('-p', '--port', type=int, help="Port of the SSH Server", default=int(os.getenv('SCP_PORT', 22)))
    parser.add_argument('-u', '--username', type=str, help="Username of the SSH Server", default=os.getenv('SCP_USERNAME'))
    parser.add_argument('-P', '--password', type=str, help="Password of the SSH Server", default=os.getenv('SCP_PASSWORD'))
    parser.add_argument('-i', '--interactive', action='store_true', help="Run in interactive mode")
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Check sudo command
    check_sudo_parser = subparsers.add_parser('check_sudo', help='Check sudo privileges')
    
    # Create directory command
    create_dir_parser = subparsers.add_parser('create_dir', help='Create remote directory')
    create_dir_parser.add_argument('dir_path', nargs='?', help='Remote directory path')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload file to remote server')
    upload_parser.add_argument('local_path', nargs='?', help='Local file path')
    upload_parser.add_argument('remote_path', nargs='?', help='Remote file path')
    
    # Directory listing command
    dir_parser = subparsers.add_parser('dir', help='List directory contents')
    dir_parser.add_argument('dir_path', nargs='?', help='Remote directory path')
    
    # Exit command
    exit_parser = subparsers.add_parser('exit', help='Exit the application')

    # Help command for interactive mode is handled separately
    
    return parser.parse_args()

def execute_command(ssh, args):
    if args.command == 'check_sudo':
        check_sudo_privileges(ssh._ssh_client)
    elif args.command == 'create_dir':
        remote_dir = args.dir_path if hasattr(args, 'dir_path') and args.dir_path else input("Enter remote directory path: ").strip()
        create_remote_directory(ssh._ssh_client, remote_dir, args.password)
    elif args.command == 'upload':
        local_file_path = args.local_path if hasattr(args, 'local_path') and args.local_path else input("Enter local file path: ").strip()
        remote_file_path = args.remote_path if hasattr(args, 'remote_path') and args.remote_path else input("Enter remote file path: ").strip()
        upload_file(ssh._ssh_client, local_file_path, remote_file_path, args.password)
    elif args.command == 'dir':
        remote_dir = args.dir_path if hasattr(args, 'dir_path') and args.dir_path else input("Enter remote directory path: ").strip()
        list_directory(ssh._ssh_client, remote_dir)
    elif args.command == 'help' or args.command == 'h':
        display_help()
    elif args.command == 'exit':
        return False
    else:
        print("Unknown command. Type 'help' for available commands.")
    return True

def interactive_mode(ssh, password):
    print("Interactive mode. Type 'help' for commands or 'exit' to quit.")
    while True:
        try:
            cmd_input = input("upload> ").strip()
            if not cmd_input:
                continue
                
            if cmd_input == 'exit':
                break
            elif cmd_input in ['help', 'h', '-h', '--help']:
                display_help()
                continue
            
            # Parse the interactive command
            cmd_parts = cmd_input.split()
            if not cmd_parts:
                continue
                
            cmd = cmd_parts[0]
            params = cmd_parts[1:] if len(cmd_parts) > 1 else []
            
            # Create a simple namespace to hold the args
            class Args:
                pass
                
            args = Args()
            args.command = cmd
            args.password = password
            
            if cmd == 'dir' and params:
                args.dir_path = params[0]
            elif cmd == 'create_dir' and params:
                args.dir_path = params[0]
            elif cmd == 'upload' and params:
                args.local_path = params[0] if params else None
                args.remote_path = params[1] if len(params) > 1 else None
            elif cmd in ['help', 'h', '-h', '--help']:
                display_help()
                continue
                
            if not execute_command(ssh, args):
                break
                
        except KeyboardInterrupt:
            print("\nKeyboard Interrupt. Type 'exit' to quit.")
        except Exception as e:
            print(f"Error: {e}")

def main():
    args = get_args()
    
    # If no command provided and not in interactive mode, show help
    if not args.command and not args.interactive:
        display_help()
        return
        
    ssh = SSHConfig(args.name, args.port, args.username, args.password)
    ssh.connect()

    if args.interactive:
        interactive_mode(ssh, args.password)
    else:
        execute_command(ssh, args)
    
    ssh.close()

if __name__ == '__main__':
    main()