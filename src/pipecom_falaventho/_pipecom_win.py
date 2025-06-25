from ._exceptions import PipeError
from threading import Thread
import time
import win32file
import pywintypes
import win32pipe
import win32con
import base64

import win32security as ws
import ntsecuritycon as ntc

ACK = "ACK".encode('utf-8')


def listen(pipe_name: str, callback: callable, timeout: int, max_messages: int, die_code: str, daemon: bool, response_pipe_name: str, buffer_size: int):
    pipe_string = f'\\\\.\\pipe\\{pipe_name}'
    pipe_thread = Thread(target=_handler, args=(pipe_string, callback,
                         max_messages, die_code, response_pipe_name, buffer_size), daemon=daemon)
    pipe_thread.start()
    if timeout > 0:
        kill_thread = Thread(target=_kill_pipe, args=(pipe_string, timeout, die_code, pipe_thread), daemon=True)
        kill_thread.start()


def send(pipe_name: str, message: str, timeout: int, max_attempts: int) -> bool:
    try:
        pipe_string = f'\\\\.\\pipe\\{pipe_name}'
        pipe = win32file.CreateFile(
            pipe_string,
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            0,
            None,
            win32con.OPEN_EXISTING,
            0,
            None
        )

        win32pipe.SetNamedPipeHandleState(pipe, win32pipe.PIPE_READMODE_MESSAGE, None, None)
        encoded_message = base64.b64encode(message.encode('utf-8'))

        attempt = 0
        start_time = time.time()
        while attempt < max_attempts or max_attempts == 0:
            try:
                win32file.WriteFile(pipe, encoded_message)
                # Wait for ACK with timeout
                if timeout > 0:
                    ready = win32file.ReadFile(pipe, 1024)
                    hr, response = ready
                else:
                    hr, response = win32file.ReadFile(pipe, 1024)
                if response == ACK:
                    return True
                else:
                    raise PipeError(
                        message=f"Expected ACK but received {response}",
                        error_code=PipeError.UNKNOWN,
                        context={
                            "pipe_name": pipe_string,
                            "expected": ACK,
                            "received": response
                        }
                    )
            except pywintypes.error:
                # If timeout is set, check if we've exceeded it
                if timeout > 0 and (time.time() - start_time) >= timeout:
                    raise PipeError(
                        message="Timeout waiting for ACK",
                        error_code=PipeError.TIMEOUT,
                        context={
                            "pipe_name": pipe_string,
                            "timeout": timeout,                        "attempts": attempt + 1
                        }
                    )
                attempt += 1
                time.sleep(0.1)
            except Exception as e:
                raise PipeError(
                    message=f"Error sending message: {e}",
                    error_code=PipeError.UNKNOWN,
                    context={
                        "pipe_name": pipe_string,
                        "attempts": attempt + 1
                    }
                )
    except pywintypes.error as e:
        if hasattr(win32con, 'ERROR_PIPE_BUSY') and e.winerror == win32con.ERROR_PIPE_BUSY:
            raise PipeError(
                message="Pipe is busy",
                error_code=PipeError.PERMISSION_DENIED,
                context={
                    "pipe_name": pipe_string,
                    "error": str(e)
                }
            )
        else:
            raise PipeError(
                message=f"Failed to connect to pipe: {e}",
                error_code=PipeError.CONNECTION_FAILED,
                context={
                    "pipe_name": pipe_string,
                    "error": str(e)
                }
            )

    except Exception:
        raise

    finally:
        if 'pipe' in locals():
            win32file.CloseHandle(pipe)

    return False


def _handler(pipe_string, callback, max_messages, die_code, response_pipe_name, buffer_size):
    """Handles incoming connections on a named pipe and processes messages.

    Args:
        pipe_string (str): The name of the pipe to listen on.
        callback (callable): Function that runs when a message is received. Will pass the message as an argument.
        max_messages (int): Maximum number of messages to process before stopping. If set to 0, it will process messages indefinitely.
        die_code (str): A special code that will stop the listener when received.
        response_pipe_name (str): Name of a response pipe over which to send the return value.
        buffer_size (int): Size of the buffer for reading messages.
    Raises:
        PipeError: If there is an error starting the listener or processing messages.

    """
    keep_alive = True

    def handle_connection(pipe):
        nonlocal keep_alive
        try:
            hr, message = win32file.ReadFile(pipe, buffer_size)
            if message == die_code.encode('utf-8'):
                win32file.WriteFile(pipe, ACK)
                keep_alive = False
                return
            decoded_message = base64.b64decode(message).decode('utf-8')
            result = callback(decoded_message)
            win32file.WriteFile(pipe, ACK)
        except Exception:
            raise PipeError(
                message="Error in listen handler",
                error_code=PipeError.UNKNOWN,
                context={
                    "pipe_name": pipe_string,
                    "callback":  callback.__name__,
                    "response_pipe_name": response_pipe_name,
                    "buffer_size": buffer_size
                }
            )
        finally:
            win32file.CloseHandle(pipe)

        return result

    sa = _generate_sa()
    message_count = 0

    while keep_alive:
        try:
            pipe = win32pipe.CreateNamedPipe(
                pipe_string,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                win32pipe.PIPE_UNLIMITED_INSTANCES,
                65536,
                65536,
                0,
                sa
            )            # blocking, awaits a connection
            win32pipe.ConnectNamedPipe(pipe, None)

            # connection made
            Thread(target=handle_connection, args=(pipe,)).start()

            if max_messages > 0:
                message_count += 1
                if message_count >= max_messages:
                    keep_alive = False

        except PipeError:
            raise
        except Exception:
            raise


def _generate_sa():

    sidEveryone = pywintypes.SID()
    sidEveryone.Initialize(ntc.SECURITY_WORLD_SID_AUTHORITY, 1)
    sidEveryone.SetSubAuthority(0, ntc.SECURITY_WORLD_RID)

    sidNetwork = pywintypes.SID()
    sidNetwork.Initialize(ntc.SECURITY_NT_AUTHORITY, 1)
    sidNetwork.SetSubAuthority(0, ntc.SECURITY_NETWORK_RID)

    sidCreator = pywintypes.SID()
    sidCreator.Initialize(ntc.SECURITY_CREATOR_SID_AUTHORITY, 1)
    sidCreator.SetSubAuthority(0, ntc.SECURITY_CREATOR_OWNER_RID)

    acl = pywintypes.ACL()
    acl.AddAccessAllowedAce(ws.ACL_REVISION, ntc.FILE_GENERIC_READ | ntc.FILE_GENERIC_WRITE, sidEveryone)
    acl.AddAccessAllowedAce(ws.ACL_REVISION, ntc.FILE_ALL_ACCESS, sidCreator)
    acl.AddAccessDeniedAce(ws.ACL_REVISION, ntc.FILE_ALL_ACCESS, sidNetwork)

    sa = pywintypes.SECURITY_ATTRIBUTES()
    sa.SetSecurityDescriptorDacl(1, acl, 0)

    return sa


def _kill_pipe(pipe_name, timeout, die_code, pipe_thread: Thread):
    start_time = time.time()
    end_time = start_time + timeout
    while time.time() < end_time:
        time.sleep(0.1)
    while pipe_thread is not None and pipe_thread.is_alive():
        # send(pipe_name, die_code, timeout=0, max_attempts=0)
        pipe_thread.join(timeout=0.1)
