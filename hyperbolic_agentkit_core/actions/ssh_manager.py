from collections.abc import Callable
import select
import socket
import sys
import termios
import time
import tty
import paramiko
import os
from typing import List, Optional, Tuple


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
            # Close existing connection if any
            self.disconnect()

            # Initialize new client
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())


            # Initialize new client
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Get default key path from environment
            default_key_path = os.getenv('SSH_PRIVATE_KEY_PATH', '~/.ssh/id_rsa')
            default_key_path = os.path.expanduser(default_key_path)

            if password:
                self._ssh_client.connect(host, port=port, username=username, password=password)
            else:
                key_path = private_key_path if private_key_path else default_key_path
                if not os.path.exists(key_path):
                    return f"SSH Key Error: Key file not found at {key_path}"
                private_key = paramiko.RSAKey.from_private_key_file(key_path)
                self._ssh_client.connect(host, port=port, username=username, pkey=private_key)

            self._connected = True
            self._host = host
            self._username = username
            return f"Successfully connected to {host} as {username}"

        except Exception as e:
            self._connected = False
            return f"SSH Connection Error: {str(e)}"

    def interactive_command(
        self, command: str = "", send_str: str = "", timeout: int = 30
    ) -> Tuple[str, str]:
        """
        Executes a command or sends input in interactive mode and returns the output.

        This method maintains an interactive SSH session that can be used for multiple
        interactions. It either starts a new command or continues an existing session
        by sending new input. All output processing and decision making is left to
        the calling function.

        Args:
            command: Initial command to execute (if starting a new interaction)
            send_str: String to send to the session (for continuing interactions)
            timeout: Maximum time to wait for output

        Returns:
            Tuple[str, str]: (command_output, error_message)
            - command_output contains all output received during this interaction
            - error_message contains any error that occurred, empty string if successful
        """
        if not self.is_connected:
            return "", "Error: No active SSH connection. Please connect first."

        try:
            # Create the interactive channel if it doesn't exist
            if (
                not hasattr(self, "_interactive_channel")
                or self._interactive_channel is None
            ):
                self._interactive_channel = self._ssh_client.invoke_shell()
                self._interactive_channel.settimeout(timeout)
                self._interactive_channel.set_combine_stderr(True)

            # Initialize output collection
            output_buffer = []

            # Send the command or input if provided
            if command:
                self._interactive_channel.send((command + "\n").encode("utf-8"))
            elif send_str:
                self._interactive_channel.send((send_str + "\n").encode("utf-8"))

            # Wait for and collect output
            # We'll implement a small delay to allow output to accumulate
            time.sleep(0.5)  # Give the command some time to generate output

            while True:
                if self._interactive_channel.recv_ready():
                    chunk = self._interactive_channel.recv(1024).decode(
                        "utf-8", "ignore"
                    )
                    output_buffer.append(chunk)
                    # Small sleep to allow more output to arrive
                    time.sleep(0.1)
                else:
                    # If no more output is ready, break the loop
                    if output_buffer:  # Only break if we've received some output
                        break
                    time.sleep(0.1)  # Wait a bit more if no output yet

            return "".join(output_buffer).strip(), ""

        except Exception as e:
            # Close the channel on error
            self.close_interactive_session()
            error_msg = f"Interactive command failed: {str(e)}"
            return "", error_msg

    def close_interactive_session(self):
        """
        Cleanly closes the interactive SSH session if one exists.
        Should be called when done with a series of interactions.
        """
        if (
            hasattr(self, "_interactive_channel")
            and self._interactive_channel is not None
        ):
            self._interactive_channel.close()
            self._interactive_channel = None

    def execute(
        self,
        command: str,
        interactive: bool = False,
        questions_and_responses: dict = None,
    ) -> str:
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
                        stdin.write(f"{response}\n")
                        stdin.flush()
                        output.append(
                            f"[Automated Response] Found question: {question}, sent: {response}\n"
                        )

            # For interactive mode, there's no stderr

            return "".join(output)

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
