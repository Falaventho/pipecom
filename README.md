# PipeCom

An OS-agnostic Python library for inter-process communication (IPC) via named pipes. PipeCom provides a simple, unified interface for creating pipe-based communication channels between processes on both Windows and Unix-like systems (Linux, macOS).

## Features

- **Cross-platform**: Works on Windows, Linux, and macOS
- **Simple API**: Easy-to-use interface for creating pipe listeners and sending messages
- **Asynchronous**: Non-blocking message handling with callback functions
- **Robust**: Built-in error handling, timeouts, and acknowledgment system
- **Flexible**: Configurable timeouts, message limits, and callbacks
- **Thread-safe**: Handles concurrent client connections

### Dependencies

- **Windows**: `pywin32`
- **Unix-like systems**: No additional dependencies required

## Quick Start

### Basic Usage

**Server (Listener):**

```python
import pipecom

def message_handler(message):
    print(f"Received: {message}")
    return f"Processed: {message}"

# Create and start a pipe listener
pipe = pipecom.Pipe("my_pipe", message_handler)
pipe.listen()

# Keep the main thread alive
input("Press Enter to stop...")
```

**Client (Sender):**

```python
import pipecom

# Send a message
result = pipecom.send("my_pipe", "Hello, World!", timeout=5)
if result:
    print("Message sent successfully!")
else:
    print("Failed to send message")
```

### Advanced Usage

```python
import pipecom
import time

def advanced_handler(message):
    print(f"Processing: {message}")
    # Simulate some processing time
    time.sleep(0.1)
    return f"ACK: {message}"



# Create pipe with custom configuration
pipe = pipecom.Pipe(
    pipe_name="advanced_pipe",
    callback=advanced_handler,
    timeout=30,              # Auto-shutdown after 30 seconds of inactivity
    max_messages=100,        # Stop after processing 100 messages
    die_code="SHUTDOWN",     # Custom shutdown command
    daemon=False             # Non-daemon thread
)

pipe.listen()

# Send multiple messages
messages = ["Task 1", "Task 2", "Task 3"]
for msg in messages:
    try:
        success = pipecom.send("advanced_pipe", msg, timeout=5, max_attempts=3)
        print(f"Message '{msg}': {'Success' if success else 'Failed'}")
    except pipecom.PipeError as e:
        print(f"Error sending '{msg}': {e}")

# Shutdown the pipe
pipecom.send("advanced_pipe", "SHUTDOWN", timeout=5)
```

## API Reference

### Pipe Class

#### Constructor

```python
Pipe(pipe_name, callback, timeout=0, max_messages=0, die_code="PIPECOM_DIE",
     daemon=True, response_pipe_name=None, buffer_size=4096)
```

**Parameters:**

- `pipe_name` (str): Name of the pipe to listen on
- `callback` (callable): Function called when a message is received
- `timeout` (int): Seconds to wait before auto-shutdown (0 = indefinite)
- `max_messages` (int): Maximum messages to process before stopping (0 = unlimited)
- `die_code` (str): Special message that triggers shutdown
- `daemon` (bool): Whether to run as daemon thread
- `response_pipe_name` (str): Name of response pipe (unused in current implementation)
- `buffer_size` (int): Buffer size for Windows pipes

#### Methods

##### `listen()`

Starts the pipe listener in a separate thread.

**Raises:**

- `PipeError`: If there's an error starting the listener

### Send Function

```python
send(pipe, message, timeout=0, max_attempts=0) -> bool
```

**Parameters:**

- `pipe` (str|Pipe): Pipe name or Pipe object
- `message` (str): Message to send
- `timeout` (int): Seconds to wait for response (0 = indefinite)
- `max_attempts` (int): Maximum send attempts (0 = unlimited)

**Returns:**

- `bool`: True if message was sent and acknowledged

**Raises:**

- `PipeError`: If there's an error sending the message

### Exception Classes

#### PipeError

Custom exception for pipe-related errors.

**Error Codes:**

- `INVALID_PIPE`: Invalid pipe name or configuration
- `CONNECTION_FAILED`: Failed to connect to pipe
- `PERMISSION_DENIED`: Insufficient permissions
- `TIMEOUT`: Operation timed out
- `UNKNOWN`: Unknown error

**Properties:**

- `error_code`: Error code string
- `context`: Additional error context (dict)

## Examples

### Simple Chat System

```python
import pipecom_falaventho as pipecom
import threading
import time

def chat_handler(message):
    print(f"[CHAT] {message}")
    return "Message received"

# Start chat server
chat_pipe = pipecom.Pipe("chat_room", chat_handler)
chat_pipe.listen()

# Simulate multiple clients
def client_thread(client_id):
    for i in range(3):
        msg = f"Client {client_id}: Hello {i+1}"
        pipecom.send("chat_room", msg, timeout=5)
        time.sleep(1)

# Start multiple clients
threads = []
for i in range(3):
    t = threading.Thread(target=client_thread, args=(i,))
    t.start()
    threads.append(t)

# Wait for clients to finish
for t in threads:
    t.join()

# Shutdown chat server
pipecom.send("chat_room", "PIPECOM_DIE", timeout=5)
```

### Task Queue System

```python
import pipecom_falaventho as pipecom
import json
import time

def task_processor(message):
    try:
        task = json.loads(message)
        print(f"Processing task: {task['name']}")

        # Simulate task processing
        time.sleep(task.get('duration', 1))

        return json.dumps({"status": "completed", "task_id": task['id']})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})

# Start task processor
processor = pipecom.Pipe("task_queue", task_processor, max_messages=10)
processor.listen()

# Submit tasks
tasks = [
    {"id": 1, "name": "Process data", "duration": 2},
    {"id": 2, "name": "Generate report", "duration": 1},
    {"id": 3, "name": "Send email", "duration": 0.5}
]

for task in tasks:
    result = pipecom.send("task_queue", json.dumps(task), timeout=10)
    print(f"Task {task['id']} submitted: {'Success' if result else 'Failed'}")

# Wait for processing to complete
time.sleep(5)
```

## Error Handling

```python
import pipecom_falaventho as pipecom

try:
    result = pipecom.send("nonexistent_pipe", "test", timeout=5)
except pipecom.PipeError as e:
    print(f"Error: {e}")
    print(f"Error code: {e.error_code}")
    if e.context:
        print(f"Context: {e.context}")
```

## Testing

The library includes comprehensive tests:

```bash
# Run all tests
python tests/test.py

# Run interactive test
python tests/test.py
# Then choose 'i' for interactive mode
```

## Platform-Specific Notes

### Windows

- Uses Windows Named Pipes API via `pywin32`
- Pipe names are automatically prefixed with `\\\\.\\pipe\\`
- Supports overlapped I/O for timeouts

### Unix-like Systems (Linux, macOS)

- Uses POSIX named pipes (FIFOs)
- Pipe files are created in the current directory
- Uses signal-based timeouts (main thread) or `select()` (other threads)

## Performance Considerations

- **Message Size**: No built-in limit, but very large messages may impact performance
- **Concurrent Clients**: Handles multiple concurrent connections efficiently
- **Memory Usage**: Minimal memory footprint with automatic cleanup
- **Encoding**: All messages are base64-encoded for safe transmission

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Changelog

### Version 0.0.1

- Initial release
- Cross-platform named pipe support
- Basic send/receive functionality
- Error handling and timeouts
- Comprehensive test suite

## Support

- **GitHub Issues**: [https://github.com/falaventho/pipecom/issues](https://github.com/falaventho/pipecom/issues)
- **Documentation**: This README and inline code documentation
- **Examples**: See `tests/` directory for usage examples

---

Made with ❤️ by [Falaventho](https://github.com/falaventho)
