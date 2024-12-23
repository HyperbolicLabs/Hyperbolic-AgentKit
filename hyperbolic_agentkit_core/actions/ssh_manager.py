import os
from typing import Callable, Optional, Union

import paramiko


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
            except Exception:
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
            # Close existing connection if any
            self.disconnect()

            # Initialize new client
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Get default key path from environment
            default_key_path = os.getenv("SSH_PRIVATE_KEY_PATH", "~/.ssh/id_rsa")
            default_key_path = os.path.expanduser(default_key_path)

            if password:
                self._ssh_client.connect(
                    host, port=port, username=username, password=password
                )
            else:
                key_path = private_key_path if private_key_path else default_key_path
                if not os.path.exists(key_path):
                    return f"SSH Key Error: Key file not found at {key_path}"

                # Try loading the key based on its type
                try:
                    if "ed25519" in key_path.lower():
                        private_key = paramiko.Ed25519Key.from_private_key_file(
                            key_path
                        )
                    else:
                        private_key = paramiko.RSAKey.from_private_key_file(key_path)

                    self._ssh_client.connect(
                        host, port=port, username=username, pkey=private_key
                    )
                except Exception as key_error:
                    return f"SSH Key Error: Failed to load key from {key_path}: {str(key_error)}"

            self._connected = True
            self._host = host
            self._username = username
            return f"Successfully connected to {host} as {username}"

        except Exception as e:
            self._connected = False
            return f"SSH Connection Error: {str(e)}"

    def execute(self, command: str) -> str:
        """Execute command on connected server."""
        if not self.is_connected:
            return "Error: No active SSH connection. Please connect first."

        try:
            output = ""
            stdin, stdout, stderr = self._ssh_client.exec_command(command, get_pty=True)
            for line in iter(stdout.readline, ""):
                output += line
                print(line, end="")

            error = stderr.read().decode()

            if error:
                return f"Error: {error}\nOutput: {output}"
            return output

        except Exception as e:
            self._connected = False
            return f"SSH Command Error: {str(e)}"

    def disconnect(self):
        """Close SSH connection."""
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except Exception:
                pass
        self._connected = False
        self._host = None
        self._username = None

    def get_connection_info(self) -> str:
        """Get current connection information."""
        if self.is_connected:
            return f"Connected to {self._host} as {self._username}"
        return "Not connected"

    def execute_interactive(
        self, command: str, prompts: dict[str, Union[str, Callable]]
    ) -> str:
        """
        Execute a command that requires interactive responses.

        Args:
            command: The command to execute
            prompts: Dictionary mapping prompt strings to either:
                    - Static response strings
                    - Callable that takes current output and returns response

        Returns:
            The complete output from the command
        """
        if not self._ssh_client:
            return "Error: No SSH connection established"

        # Get interactive shell with pseudo-terminal
        shell = self._ssh_client.invoke_shell(get_pty=True)
        output = ""

        # Send the command
        shell.send(f"{command}\n")

        # Read output and handle prompts
        while True:
            if shell.recv_ready():
                chunk = shell.recv(1024).decode("utf-8")
                output += chunk
                print(chunk, end="")

                # Check for any matching prompts
                for prompt_text, response in prompts.items():
                    if prompt_text in output:
                        if callable(response):
                            resp = response(output)
                        else:
                            resp = response
                        shell.send(f"{resp}\n")

            # Break if channel is closed
            if shell.exit_status_ready():
                break

        # Close the channel
        shell.close()
        return output


# Global instance
ssh_manager = SSHManager()
