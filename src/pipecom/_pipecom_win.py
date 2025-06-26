from threading import Thread
import time
import base64

import win32file
import win32pipe
import win32con
import win32event
import winerror
import pywintypes

import win32security as ws
import ntsecuritycon as ntc

from ._exceptions import PipeError

ACK = "ACK".encode('utf-8')


def _validate_pipe_name(pipe_name: str):
    """Validate pipe name to prevent problematic names."""
    if not pipe_name or not pipe_name.strip():
        raise PipeError("Pipe name cannot be empty or only whitespace", PipeError.INVALID_PIPE_NAME)

    if '/' in pipe_name or '\\' in pipe_name:
        raise PipeError("Pipe name cannot contain path separators", PipeError.INVALID_PIPE_NAME)

    # Additional validation for problematic names
    if pipe_name.isspace():
        raise PipeError("Pipe name cannot be only whitespace", PipeError.INVALID_PIPE_NAME)


def listen(pipe_name: str, callback: callable, timeout: int, max_messages: int, die_code: str, daemon: bool, response_pipe_name: str, buffer_size: int):
    # Validate pipe name first
    _validate_pipe_name(pipe_name)

    pipe_string = f'\\\\.\\pipe\\{pipe_name}'
    pipe_thread = Thread(target=_handler, args=(pipe_string, callback,
                         max_messages, die_code, response_pipe_name, buffer_size), daemon=daemon)
    pipe_thread.start()
    if timeout > 0:
        kill_thread = Thread(target=_kill_pipe, args=(pipe_name, timeout, die_code, pipe_thread), daemon=True)
        kill_thread.start()


def send(pipe_name: str, message: str, timeout: int, max_attempts: int) -> bool:
    # Validate pipe name first
    _validate_pipe_name(pipe_name)

    try:
        pipe_string = f'\\\\.\\pipe\\{pipe_name}'
        if timeout > 0:
            pipe = win32file.CreateFile(
                pipe_string,
                win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                0,
                None,
                win32con.OPEN_EXISTING,
                win32con.FILE_FLAG_OVERLAPPED,
                None
            )
        else:
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
                    overlapped = pywintypes.OVERLAPPED()
                    overlapped.Offset = 0  # Starting offset for the read operation
                    overlapped.hEvent = win32event.CreateEvent(None, 1, 0, None)  # Create an event
                    buffer = win32file.AllocateReadBuffer(3)
                    ready = win32file.ReadFile(pipe, buffer, overlapped)
                    hr, response = ready
                    if hr == winerror.ERROR_IO_PENDING:
                        remaining_time = int((start_time + timeout - time.time()) * 1000)
                        if remaining_time < 0:
                            raise PipeError(
                                message="Timeout waiting for ACK",
                                error_code=PipeError.TIMEOUT,
                                context={
                                    "pipe_name": pipe_string,
                                    "timeout": timeout,
                                    "attempts": attempt + 1
                                }
                            )
                        wait_result = win32event.WaitForSingleObject(overlapped.hEvent, remaining_time)
                        if wait_result == win32con.WAIT_TIMEOUT:
                            # Cancel the pending operation
                            try:
                                win32file.CancelIo(pipe)
                            except Exception:
                                pass
                            raise PipeError(
                                message="Timeout waiting for ACK",
                                error_code=PipeError.TIMEOUT,
                                context={
                                    "pipe_name": pipe_string,
                                    "timeout": timeout,
                                    "attempts": attempt + 1
                                }
                            )
                        elif wait_result == win32con.WAIT_OBJECT_0:
                            # Operation completed successfully, continue with GetOverlappedResult
                            bytes_read = win32file.GetOverlappedResult(pipe, overlapped, True)
                            data = buffer[:bytes_read]
                        else:
                            # Wait failed for some other reason
                            raise PipeError(
                                message="Wait operation failed",
                                error_code=PipeError.UNKNOWN,
                                context={
                                    "pipe_name": pipe_string,
                                    "wait_result": wait_result,
                                    "attempts": attempt + 1
                                }
                            )
                    else:
                        # Operation completed synchronously
                        data = response  # Use the response data directly
                else:
                    hr, data = win32file.ReadFile(pipe, 3)

                if data == ACK:
                    return True
                else:
                    raise PipeError(
                        message=f"Expected ACK but received {data}",
                        error_code=PipeError.UNKNOWN,
                        context={
                            "pipe_name": pipe_string,
                            "expected": ACK,
                            "received": data
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
                            "timeout": timeout,
                            "attempts": attempt + 1
                        }
                    )
                attempt += 1
                time.sleep(0.1)

            except PipeError:
                raise

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
    keep_alive = True

    def handle_connection(pipe):
        nonlocal keep_alive
        try:
            hr, message = win32file.ReadFile(pipe, buffer_size)
            decoded_message = base64.b64decode(message).decode('utf-8')
            if decoded_message == die_code:
                win32file.WriteFile(pipe, ACK)
                keep_alive = False
                return
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

        if response_pipe_name is not None:
            try:
                send(response_pipe_name, result, timeout=5, max_attempts=3)
            except Exception as e:
                print(f"Warning: Failed to send to response pipe '{response_pipe_name}': {e}")
        return

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
            )

            # Check if we should still be alive before blocking on connect
            if not keep_alive:
                win32file.CloseHandle(pipe)
                break

            # blocking, awaits a connection
            win32pipe.ConnectNamedPipe(pipe, None)

            # connection made
            Thread(target=handle_connection, args=(pipe,), daemon=True).start()

            if max_messages > 0:
                message_count += 1
                if message_count >= max_messages:
                    keep_alive = False

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

    # Wait for the timeout period
    while time.time() < end_time:
        time.sleep(0.1)
        # If the thread dies naturally during the timeout, we're done
        if not pipe_thread.is_alive():
            return

    # After timeout, try to send die code a few times then give up
    max_kill_attempts = 3
    kill_attempt = 0

    while pipe_thread.is_alive() and kill_attempt < max_kill_attempts:
        try:
            send(pipe_name, die_code, timeout=1, max_attempts=1)  # Short timeout
            pipe_thread.join(timeout=0.5)  # Give it a moment to process
            kill_attempt += 1
        except Exception:
            # If we can't send the die code, break out
            break

    # If thread is still alive after attempts, just return and let it be cleaned up
    # as a daemon thread
