import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from upload import create_ssh_client, check_sudo_privileges, create_remote_directory, upload_file

class TestUploadScript(unittest.TestCase):

    @patch('upload.paramiko.SSHClient', autospec=True)
    def test_create_ssh_client(self, MockSSHClient):
        mock_client = MockSSHClient.return_value

        hostname = 'test_host'
        port = 22
        username = 'test_user'
        password = 'test_pass'

        client = create_ssh_client(hostname, port, username, password)
        MockSSHClient.assert_called_once()
        mock_client.connect.assert_called_once_with(hostname, port, username, password)
        self.assertEqual(client, mock_client)

    @patch('upload.logger')
    def test_check_sudo_privileges(self, mock_logger):
        mock_ssh_client = MagicMock()
        mock_ssh_client.exec_command.return_value = (None, MagicMock(), MagicMock())
        mock_ssh_client.exec_command.return_value[1].channel.recv_exit_status.return_value = 0

        result = check_sudo_privileges(mock_ssh_client)
        self.assertTrue(result)
        mock_logger.info.assert_called_with("User has sudo privileges")

    @patch('upload.logger')
    def test_create_remote_directory(self, mock_logger):
        mock_ssh_client = MagicMock()
        mock_ssh_client.exec_command.return_value = (None, MagicMock(), MagicMock())
        mock_ssh_client.exec_command.return_value[1].channel.recv_exit_status.return_value = 1

        remote_dir = '/test/dir'
        password = 'test_pass'

        create_remote_directory(mock_ssh_client, remote_dir, password)
        mock_logger.info.assert_any_call("Creating remote directory: %s", remote_dir)

if __name__ == '__main__':
    unittest.main()
