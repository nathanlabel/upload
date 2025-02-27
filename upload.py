"""
SSH file upload and management tool.

This script connects to an SSH server, then supports commands such as
checking sudo privileges, creating directories, uploading files, and
listing directory contents – either via a non-interactive mode through
command-line arguments or via an interactive prompt.
"""

import json
import os
import logging
import paramiko
import argparse
from scp import SCPClient, SCPException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SSHConfig:
    """
    Manages SSH connection using provided server details.
    
    Attributes:
        _hostname (str): SSH server hostname.
        _port (int): Port number.
        _username (str): Username for SSH.
        _password (str): Password for SSH.
        _ssh_client (SCPClient): The SSH client instance.
    """
    
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
        """Establishes an SSH connection using the provided credentials."""
        if self._valid_details():
            self._ssh_client = self._create_ssh_client()
            if self._ssh_client is None:
                logger.error("Failed to create SSH client")
                return
            else:
                logger.info("Successfully created SSH client")

    def is_connected(self) -> bool:
        """
        Checks if the SSH client is connected and authenticated.
        
        Returns:
            bool: True if connected; False otherwise.
        """
        if self._ssh_client is None:
            return False
        return self._ssh_client.get_transport().is_active() and \
            self._ssh_client.get_transport().is_active() and \
            self._ssh_client.get_transport().is_authenticated()

    def _valid_details(self) -> bool:
        """
        Validates that all required SSH credentials are provided.
        
        Returns:
            bool: True if details are valid; False otherwise.
        """
        return self._hostname and self._port and self._username and self._password

    def _create_ssh_client(self):
        """Creates and returns a new SSH client connected to the server."""
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self._hostname, self._port, self._username, self._password)
        return client

    def close(self):
        """Closes the SSH session if it is active."""
        if self._ssh_client:
            self._ssh_client.close()
            logger.info("SSH session closed")

# Function to check sudo privileges
def check_sudo_privileges(ssh_client):
    """
    Checks if the connected user has sudo privileges.
    
    Args:
        ssh_client: The active SSH client.
    
    Returns:
        bool: True if sudo privileges are available; else False.
    """
    stdin, stdout, stderr = ssh_client.exec_command('sudo -l')
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("User has sudo privileges")
        return True
    else:
        logger.error("User does not have sudo privileges: %s", stderr.read().decode())
        return False

# Function to create a remote directory if it does not exist
def create_remote_directory(ssh_client, remote_dir, password):
    """
    Creates a remote directory on the server if it does not exist.
    
    Args:
        ssh_client: The SSH client.
        remote_dir (str): Remote directory path.
        password (str): Sudo password.
    """
    logger.info("Creating remote directory: %s", remote_dir)
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
        return
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

# Function to upload a file to the remote server
def upload_file(ssh_client, local_file_path, remote_file_path, password):
    """
    Uploads a file from the local system to the remote server.
    
    Args:
        ssh_client: The SSH client.
        local_file_path (str): Local file path.
        remote_file_path (str): Desired remote file path.
        password (str): Sudo password.
    """
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
        logger.info("Successfully uploaded %s to %s", local_file_path, remote_file_path)
    else:
        logger.error("Failed to move %s to %s: %s", temp_remote_path, remote_file_path, stderr.read().decode())
        return

    # Convert line endings
    convert_line_endings_command = f'echo {password} | sudo -S sed -i "s/\\r$//" {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(convert_line_endings_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("Successfully converted line endings of %s to LF", remote_file_path)
    else:
        logger.error("Failed to convert line endings of %s to LF: %s", remote_file_path, stderr.read().decode())
        return

    # Change ownership and make executable
    chown_command = f'echo {password} | sudo -S chown mysite:mysite {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(chown_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        logger.error("Failed to change ownership of %s to mysite:mysite: %s", remote_file_path, stderr.read().decode())
        return

    chmod_command = f'echo {password} | sudo -S chmod +x {remote_file_path}'
    stdin, stdout, stderr = ssh_client.exec_command(chmod_command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        logger.error("Failed to make %s executable: %s", remote_file_path, stderr.read().decode())
        return

# Function to list directory contents on the remote server
def list_directory(ssh_client, remote_dir):
    """
    Lists the contents of a directory on the remote server.
    
    Args:
        ssh_client: The SSH client.
        remote_dir (str): Remote directory path.
    """
    command = f'ls -lh {remote_dir}'
    stdin, stdout, stderr = ssh_client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status == 0:
        logger.info("Directory contents of %s:\n%s", remote_dir, stdout.read().decode())
    else:
        logger.error("Failed to list directory %s: %s", remote_dir, stderr.read().decode())

# Function to display help information for interactive mode
def display_help():
    """
    Prints available commands.
    """
    help_text = """
Available Commands:
  check_sudo           - Check sudo privileges on the remote server
  create_dir PATH      - Create a remote directory at PATH
  upload LOCAL REMOTE  - Upload a file from LOCAL path to REMOTE path
  dir PATH             - List contents of directory at PATH
  help (or h)          - Show this help message
  exit                 - Exit the application
"""
    print(help_text)

def get_args():
    """
    Parses command-line arguments.
    
    Returns:
        Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(prog='UPLOAD', description='SSH file upload and management tool')
    parser.add_argument('-n', '--name', type=str, help="Hostname of the SSH Server", default=os.getenv('SCP_HOSTNAME'))
    parser.add_argument('-p', '--port', type=int, help="Port of the SSH Server", default=int(os.getenv('SCP_PORT', 22)))
    parser.add_argument('-u', '--username', type=str, help="Username of the SSH Server", default=os.getenv('SCP_USERNAME'))
    parser.add_argument('-P', '--password', type=str, help="Password of the SSH Server", default=os.getenv('SCP_PASSWORD'))
    parser.add_argument('-i', '--interactive', action='store_true', help="Run in interactive mode")
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Check sudo command
    subparsers.add_parser('check_sudo', help='Check sudo privileges')
    
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
    subparsers.add_parser('exit', help='Exit the application')
    
    return parser.parse_args()

def execute_command(ssh, args):
    """
    Executes the specified command using the given SSH client.
    
    Args:
        ssh (SSHConfig): SSH configuration instance.
        args (Namespace): Command-line arguments.
    
    Returns:
        bool: True if command executed and should continue; False to exit.
    """
    if args.command == 'check_sudo':
        check_sudo_privileges(ssh._ssh_client)
    elif args.command == 'create_dir':
        remote_dir = getattr(args, 'dir_path', None) or input("Enter remote directory path: ").strip()
        create_remote_directory(ssh._ssh_client, remote_dir, args.password)
    elif args.command == 'upload':
        local_file_path = getattr(args, 'local_path', None) or input("Enter local file path: ").strip()
        remote_file_path = getattr(args, 'remote_path', None) or input("Enter remote file path: ").strip()
        upload_file(ssh._ssh_client, local_file_path, remote_file_path, args.password)
    elif args.command == 'dir':
        remote_dir = getattr(args, 'dir_path', None) or input("Enter remote directory path: ").strip()
        list_directory(ssh._ssh_client, remote_dir)
    elif args.command in ['help', 'h', '-h', '--help']:
        display_help()
    elif args.command == 'exit':
        return False
    else:
        print("Unknown command. Type 'help' for available commands.")
    return True

def cli_file_selector(start_dir="."):
    current_dir = os.path.abspath(start_dir)
    while True:
        items = []
        # Add parent directory option
        if current_dir != os.path.abspath(start_dir):
            items.append(".. (Parent Directory)")
        # Add subdirectories
        subdirs = [d for d in os.listdir(current_dir) if os.path.isdir(os.path.join(current_dir, d))]
        items.extend(subdirs)
        # Add files
        files = [f for f in os.listdir(current_dir) if os.path.isfile(os.path.join(current_dir, f))]
        items.extend(files)

        if not items:
            print("No files or directories found in", current_dir)
            return None

        for idx, item in enumerate(items, 1):
            if item == ".. (Parent Directory)":
                print(f"{idx}. {item}/")
            elif os.path.isdir(os.path.join(current_dir, item)):
                print(f"{idx}. {item}/")
            else:
                print(f"{idx}. {item}")

        choice = input("Select a file/directory by number (or 'q' to quit): ").strip()

        if choice.lower() == 'q':
            return None

        try:
            index = int(choice) - 1
            if index < 0 or index >= len(items):
                print("Invalid selection.")
                continue

            selected_item = items[index]

            if selected_item == ".. (Parent Directory)":
                current_dir = os.path.abspath(os.path.join(current_dir, ".."))
                print("Navigating to:", current_dir)
            elif os.path.isdir(os.path.join(current_dir, selected_item)):
                current_dir = os.path.join(current_dir, selected_item)
                print("Navigating to:", current_dir)
            else:
                return os.path.join(current_dir, selected_item)

        except ValueError:
            print("Invalid input.")

def interactive_mode(ssh, password):
    """
    Runs the interactive command loop.
    
    Args:
        ssh (SSHConfig): SSH configuration instance.
        password (str): SSH password.
    """
    print("Interactive mode. Type 'help' for commands or 'exit' to quit.")
    while True:
        try:
            cmd_input = input("upload> ").strip()
            if not cmd_input:
                continue
                
            if cmd_input in ['exit']:
                break
            if cmd_input in ['help', 'h', '-h', '--help']:
                display_help()
                continue
            
            # Parse the interactive command
            cmd_parts = cmd_input.split()
            if not cmd_parts:
                continue
                
            cmd = cmd_parts[0]
            params = cmd_parts[1:]
            
            # Create a simple namespace to simulate parsed arguments
            class SimpleArgs:
                pass
            
            args = SimpleArgs()
            args.command = cmd
            args.password = password
            
            if cmd == 'dir' and params:
                args.dir_path = params[0]
            elif cmd == 'create_dir' and params:
                args.dir_path = params[0]
            elif cmd == 'upload':
                if params:
                    args.local_path = params[0]
                else:
                    # Use CLI file selector instead of tkinter
                    selected_file = cli_file_selector()
                    if not selected_file:
                        args.local_path = None
                    else:
                        args.local_path = selected_file
                if len(params) >= 2:
                    args.remote_path = params[1]
                else:
                    args.remote_path = input("Enter remote file path: ").strip()

                # Ensure local_path and remote_path attributes always exist
                if not hasattr(args, 'local_path'):
                    args.local_path = None
                if not hasattr(args, 'remote_path'):
                    args.remote_path = None

            execute_command(ssh, args)
                
        except KeyboardInterrupt:
            print("\nKeyboard Interrupt. Type 'exit' to quit.")
        except Exception as e:
            print(f"Error: {e}")

def main():
    """
    Main entry point. Determines mode, executes commands, and manages SSH session.
    """
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