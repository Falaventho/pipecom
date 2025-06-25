import signal
import os
from ._exceptions import PipeError
from threading import Thread
import time
import base64

ACK = "ACK"


def listen(pipe_name: str, callback: callable, timeout: int, max_messages: int, die_code: str, daemon: bool, response_pipe_name: str, buffer_size: int):
    pipe_thread = Thread(target=_handler, args=(pipe_name, callback, max_messages,
                         die_code, response_pipe_name), daemon=daemon)
    pipe_thread.start()
    if timeout > 0:
        kill_thread = Thread(target=_kill_pipe, args=(pipe_name, timeout, die_code, pipe_thread), daemon=True)
        kill_thread.start()


def send(pipe_name: str, message: str, timeout: int, max_attempts: int = 0) -> bool:
    ack_pipe_name = pipe_name + "_ack"
    fifo_in = None
    fifo_out = None
    try:
        _make_fifos(pipe_name, ack_pipe_name)
    except Exception:
        raise

    def alarm_handler(signum, frame):
        raise PipeError(f"Timeout while waiting for response from pipe '{pipe_name}'", PipeError.TIMEOUT)

    # Only set signal handler if we're in the main thread
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, alarm_handler)
        signal.alarm(timeout)
        use_signal = True
    except ValueError:
        # Not in main thread, can't use signals
        use_signal = False

    try:
        fifo_out = open(pipe_name, 'w', 1)

        encoded_message = base64.b64encode(message.encode('utf-8')).decode('utf-8')
        fifo_out.write(encoded_message + '\n')
        fifo_out.close()
        fifo_out = None

        fifo_in = open(ack_pipe_name, 'r')

        # Manual timeout check for non-main threads
        if not use_signal:
            # Use select or polling for timeout in threads
            import select
            ready, _, _ = select.select([fifo_in], [], [], timeout)
            if not ready:
                raise PipeError(
                    f"Timeout while waiting for response from pipe '{pipe_name}'", PipeError.TIMEOUT)

        res = fifo_in.readline().strip()
        res = base64.b64decode(res.encode('utf-8'))
        if res != ACK.encode('utf-8'):
            raise PipeError(f"Invalid response from pipe '{pipe_name}': {res}", PipeError.UNKNOWN)
        fifo_in.close()
        fifo_in = None

        return True  # Success

    except PipeError:
        raise

    except Exception as e:
        raise PipeError(f"Failed to open pipe '{pipe_name}': {e}", PipeError.UNKNOWN)

    finally:
        if use_signal:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)

        if fifo_in is not None:
            fifo_in.close()
        if fifo_out is not None:
            fifo_out.close()


def _make_fifos(pipe_name, ack_pipe_name):
    try:
        os.mkfifo(pipe_name, 0o666)
    except FileExistsError:
        pass
    except PermissionError:
        raise PipeError(f"Permission denied for pipe '{pipe_name}'", PipeError.PERMISSION_DENIED)
    except Exception:
        raise PipeError(f"Failed to create pipe '{pipe_name}'", PipeError.UNKNOWN)
    try:
        os.mkfifo(ack_pipe_name, 0o666)
    except FileExistsError:
        pass
    except PermissionError:
        raise PipeError(f"Permission denied for pipe '{pipe_name}'", PipeError.PERMISSION_DENIED)
    except Exception:
        raise PipeError(f"Failed to create pipe '{pipe_name}'", PipeError.UNKNOWN)


def _handler(pipe_name, callback, max_messages, die_code, response_pipe_name):
    keep_alive = True
    ack_pipe_name = pipe_name + "_ack"

    def handle_connection(fifo_in):
        nonlocal keep_alive
        nonlocal ack_pipe_name
        nonlocal pipe_name

        fifo_out = None
        try:
            message = fifo_in.readline().strip()
            fifo_in.close()
            if message == '':  # Process has disconnected from other end of pipe
                return
            decoded_message = base64.b64decode(message).decode('utf-8')
            if decoded_message == die_code:
                keep_alive = False
                # Still send acknowledgment for die code
                fifo_out = open(ack_pipe_name, 'w', 1)
                encoded_ack = base64.b64encode(ACK.encode('utf-8')).decode('utf-8')
                fifo_out.write(encoded_ack + '\n')
                fifo_out.close()
                return  # Don't cleanup here - let the main handler do it
            result = callback(decoded_message)
            fifo_out = open(ack_pipe_name, 'w', 1)
            encoded_ack = base64.b64encode(ACK.encode('utf-8')).decode('utf-8')
            fifo_out.write(encoded_ack + '\n')
            fifo_out.close()

            # Send result to response pipe if configured
            if response_pipe_name is not None:
                try:
                    send(response_pipe_name, result, timeout=5, max_attempts=3)
                except Exception as e:
                    print(f"Warning: Failed to send to response pipe '{response_pipe_name}': {e}")
        except Exception:
            raise PipeError(
                message="Error in listen handler",
                error_code=PipeError.UNKNOWN,
                context={
                    "pipe_name": pipe_name,
                    "callback":  callback.__name__,
                    "response_pipe_name": response_pipe_name,
                }
            )
        finally:
            if fifo_in is not None:
                fifo_in.close()
            if fifo_out is not None:
                fifo_out.close()
            # Don't cleanup fifos here - they should persist for multiple connections

        return result

    try:
        _make_fifos(pipe_name, ack_pipe_name)
    except Exception:
        pipe_open, ack_open, exceptions = _cleanup_fifos(pipe_name, ack_pipe_name)
        if not pipe_open and not ack_open:
            raise PipeError(f"Failed to create pipes '{pipe_name}' or '{ack_pipe_name}'", PipeError.UNKNOWN)
        exception_msg = 'Failed to clean up pipe(s): '
        if pipe_open:
            exception_msg += f"\nPipe '{pipe_name}' is still open. "
        if ack_open:
            exception_msg += f"\nAcknowledgment pipe '{ack_pipe_name}' is still open. "
        if exceptions:
            exception_msg += "\nExceptions encountered:"
            for e in exceptions:
                exception_msg += f"\n- {e}"
        raise PipeError(exception_msg, PipeError.UNKNOWN)

    message_count = 0
    try:
        while keep_alive:
            try:
                # blocking, awaits a connection
                fifo_in = open(pipe_name, 'r')

                # connection made
                Thread(target=handle_connection, args=(fifo_in,), daemon=True).start()

                if max_messages > 0:
                    message_count += 1
                    if message_count >= max_messages:
                        keep_alive = False
            except Exception:
                raise
    finally:
        # Clean up fifos when the handler exits
        _cleanup_fifos(pipe_name, ack_pipe_name)


def _cleanup_fifos(pipe_name,  ack_pipe_name):
    """
    Clean up named pipes by unlinking them.

    Returns:
        tuple: (pipe_open, ack_pipe_open, exceptions)
            - pipe_open: True if the pipe was open and could not be unlinked
            - ack_pipe_open: True if the acknowledgment pipe was open and could not be unlinked
            - exceptions: List of exceptions encountered during unlinking
    """
    pipe_open = False
    ack_pipe_open = False
    exceptions = []
    try:
        os.unlink(pipe_name)
    except FileNotFoundError:
        pass
    except Exception as e:
        pipe_open = True
        exceptions.append(e)

    try:
        os.unlink(ack_pipe_name)
    except FileNotFoundError:
        pass
    except Exception as e:
        ack_pipe_open = True
        exceptions.append(e)

    return (pipe_open, ack_pipe_open, exceptions)


def _kill_pipe(pipe_name, timeout, die_code, pipe_thread: Thread):
    start_time = time.time()
    end_time = start_time + timeout
    while time.time() < end_time:
        time.sleep(0.1)
    while pipe_thread is not None and pipe_thread.is_alive():
        send(pipe_name, die_code, timeout=5, max_attempts=5)
        pipe_thread.join(timeout=0.1)
