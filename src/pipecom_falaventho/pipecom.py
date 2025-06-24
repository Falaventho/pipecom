import platform

os_name = platform.system().lower()

if os_name == 'windows':
    import _pipecom_win as pc
elif os_name == 'linux' or os_name == 'darwin':
    import _pipecom_posix as pc


def listen(pipe_name: str, callback: callable, timeout=0, max_messages=0, die_code: str = "PIPECOM_DIE"):
    """Start listening on a named pipe.
    Args:
        pipe_name (str): The name of the pipe to listen on.
        callback (callable): Function that runs  when a message is received. Will pass the message as an argument.
        timeout (int): Time in seconds to wait for a message before giving up. If set to 0, it will wait indefinitely.
        max_messages (int): Maximum number of messages to process before stopping. If set to 0, it will process messages indefinitely.
        die_code (str): A special code that will stop the listener when received. Defaults to "PIPECOM_DIE".
    Raises:
        PipeError: If there is an error starting the listener or processing messages.
    """
    try:
        pc.listen(pipe_name, callback)
    except:
        raise


def send(pipe_name: str, message: callable, timeout=0, max_attempts=0):
    """Send a message through a named pipe.
    Args:
        pipe_name (str): The name of the pipe to send the message through.
        message (callable): The message to send.
        timeout (int): Time in seconds to wait for the send to complete. If set to 0, it will wait indefinitely.
        max_attempts (int): Maximum number of attempts to send the message. If set to 0, it will attempt to send indefinitely.
    Returns:
        bool: True if the message was sent successfully, False otherwise.
    Raises:
        PipeError: If there is an error sending the message.
    """
    try:
        return pc.send(pipe_name, message)
    except:
        raise
