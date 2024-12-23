import paramiko
import os
from typing import Optional


class SSHManager:
    _instance = None
    _ssh_client = None
    _connected = False
    _host = None
    _username = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SSHManager, cls).__new__(cls)
        return cls._instance

    @property
    def is_connected(self) -> bool:
        """Check if there's an active SSH connection."""
        if self._ssh_client and self._connected:
            try:
                self._ssh_client.exec_command("echo 1", timeout=5)
                return True
            except:
                self._connected = False
        return False

    def connect(
        self,
        host: str,
        username: str,
        password: Optional[str] = None,
        private_key_path: Optional[str] = None,
        port: int = 22,
    ) -> str:
        """Establish SSH connection."""
        try:
            print(
                f"Connecting to {host} as {username}... Port {port} Password {password} Key {private_key_path}"
            )
            # Close existing connection if any
            self.disconnect()

            # Initialize new client
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Get default key path from environment
            default_key_path = os.getenv("SSH_PRIVATE_KEY_PATH", "~/.ssh/id_rsa")
            default_key_path = os.path.expanduser(default_key_path)

            print(f"Default key path: {default_key_path} - Password: {password}")
            if password:
                self._ssh_client.connect(
                    host, port=port, username=username, password=password
                )
            else:
                key_path = private_key_path if private_key_path else default_key_path
                print(f"Private key path: {key_path} - using key")
                if not os.path.exists(key_path):
                    return f"SSH Key Error: Key file not found at {key_path}"

                try:
                    try:
                        private_key = paramiko.RSAKey.from_private_key_file(key_path)
                    except paramiko.ssh_exception.SSHException:
                        try:
                            private_key = paramiko.Ed25519Key.from_private_key_file(
                                key_path, password=None
                            )
                        except paramiko.ssh_exception.SSHException:
                            try:
                                private_key = paramiko.ECDSAKey.from_private_key_file(
                                    key_path, password=None
                                )
                            except paramiko.ssh_exception.SSHException:
                                private_key = paramiko.PKey.from_private_key_file(
                                    key_path, password=None
                                )

                    self._ssh_client.connect(
                        host, port=port, username=username, pkey=private_key
                    )
                except Exception as e:
                    return f"SSH Key Error: Failed to load private key: {str(e)}"

            self._connected = True
            self._host = host
            self._username = username
            return f"Successfully connected to {host} as {username}"

        except Exception as e:
            self._connected = False
            return f"SSH Connection Error: {str(e)}"

    def execute(self, command: str, interactive: bool = False, questions_and_responses: dict = None) -> str:
        """Execute command on connected server.
        
        Args:
            command: The command to execute
            interactive: Whether to handle interactive prompts
            questions_and_responses: Dictionary of expected questions and their responses
        """
        if not self.is_connected:
            return "Error: No active SSH connection. Please connect first."

        try:
            if interactive:
                return self.execute_interactive(command, questions_and_responses)
            else:
                return self.execute_noninteractive(command)

        except Exception as e:
            self._connected = False
            return f"SSH Command Error: {str(e)}"

    def execute_noninteractive(self, command: str) -> str:
        """Execute a non-interactive command on the connected server.
        
        Args:
            command: The command to execute
        """
        stdin, stdout, stderr = self._ssh_client.exec_command(command)
        output = stdout.read().decode()
        error = stderr.read().decode()

        if error:
            return f"Error: {error}\nOutput: {output}"
        return output

    def execute_interactive(self, command: str, questions_and_responses: dict) -> str:
        """Execute an interactive command with predefined responses to questions.
        
        Args:
            command: The command to execute
            questions_and_responses: Dictionary mapping expected questions to their responses
        """
        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(command, get_pty=True)
            output = []

            while True:
                line = stdout.readline()
                if not line:
                    break
                
                output.append(line)
                
                # Check if line contains any of our expected questions
                for question, response in questions_and_responses.items():
                    if question in line:
                        stdin.write(f'{response}\n')
                        stdin.flush()
                        output.append(f"[Automated Response] Found question: {question}, sent: {response}\n")

            # For interactive mode, there's no stderr

            return ''.join(output)

        except Exception as e:
            self._connected = False
            return f"SSH Interactive Command Error: {str(e)}"

    def disconnect(self):
        """Close SSH connection."""
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except:
                pass
        self._connected = False
        self._host = None
        self._username = None

    def get_connection_info(self) -> str:
        """Get current connection information."""
        if self.is_connected:
            return f"Connected to {self._host} as {self._username}"
        return "Not connected"


# Global instance
ssh_manager = SSHManager()
