import platform

os_name = platform.system().lower()

if os_name == 'windows':
    from . import _pipecom_win as pc
elif os_name == 'linux' or os_name == 'darwin':
    from . import _pipecom_posix as pc


class Pipe():

    def __init__(self, pipe_name: str, callback: callable, timeout=0, max_messages=0, die_code: str = "PIPECOM_DIE", daemon: bool = True, response_pipe_name: str = None, buffer_size: int = 4096):
        """Initialize a Pipe object.
        Args:
            pipe_name (str): The name of the pipe to listen on.
            callback (callable): Function that runs  when a message is received. Will pass the message as an argument.
            timeout (int): Time in seconds to wait for a message before giving up. If set to 0, it will wait indefinitely.
            max_messages (int): Maximum number of messages to process before stopping. If set to 0, it will process messages indefinitely.
            die_code (str): A special code that will stop the listener when received. Defaults to "PIPECOM_DIE".
            daemon (bool): If True, the listener will run as a daemon thread and be terminated when the main.
            response_pipe_name (str): The name of the response pipe to send messages back through. If None, no response will be sent.
            buffer_size (int): (WINDOWS ONLY) Size of the buffer for reading messages from the pipe. Defaults to 4096 bytes.

        """
        self.pipe_name = pipe_name
        self.callback = callback
        self.timeout = timeout
        self.max_messages = max_messages
        self.die_code = die_code
        self.daemon = daemon
        self.response_pipe_name = response_pipe_name
        self.pipe = None
        self.message_count = 0 if max_messages > 0 else None
        self.buffer_size = buffer_size

    def listen(self):
        """Start listening on a named pipe.
        Raises:
            PipeError: If there is an error starting the listener or processing messages.
        """
        try:
            pc.listen(self.pipe_name, self.callback, self.timeout, self.max_messages,
                      self.die_code, self.daemon, self.response_pipe_name, self.buffer_size)
        except Exception:
            raise


def send(pipe: str | Pipe, message: str, timeout: int = 0, max_attempts: int = 0) -> bool:
    """Send a message through a named pipe.
    Args:
        pipe (str|Pipe): The name of the pipe or a Pipe object to send the message through.
        message (str): The message to send.
        timeout (int): Time in seconds to wait for the message to be sent. If set to 0, it will wait indefinitely.
        max_attempts (int): Maximum number of attempts to send the message. If set to 0, it will attempt indefinitely.
    Returns:
        bool: True if the message was sent successfully, False otherwise.
    Raises:
        PipeError: If there is an error sending the message.
    """
    try:
        return pc.send(pipe, message, timeout, max_attempts)
    except:
        raise
