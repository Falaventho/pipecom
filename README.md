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
message_sent = pipecom.send("my_pipe", "Hello, World!")
if message_sent:
    print("Message sent successfully!")
else:
    print("Failed to send message")
```

### Advanced Usage with Response Pipe

```python
import sys
import os
import threading

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom as pipecom
import time

# Track responses received
responses_received = []


def task_processor(message):
    """Main pipe callback that processes tasks and returns results."""
    print(f"Processing task: {message}")
    # Simulate some processing time
    time.sleep(0.1)

    # Return a result that will be sent to the response pipe
    if "error" in message.lower():
        return f"ERROR: Failed to process {message}"
    else:
        return f"SUCCESS: Completed {message}"


def response_handler(message):
    """Response pipe callback that receives processing results."""
    decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
    responses_received.append(decoded_msg)
    print(f"📋 Result received: {decoded_msg}")
    return f"Result acknowledged: {decoded_msg}"


# Set up bidirectional communication
main_pipe_name = "task_processor"
response_pipe_name = "task_results"

# Start the response pipe listener first
response_pipe = pipecom.Pipe(response_pipe_name, response_handler)
response_pipe.listen()

time.sleep(0.2)  # Allow response pipe to start

# Create main pipe with custom configuration and response pipe
main_pipe = pipecom.Pipe(
    pipe_name=main_pipe_name,
    callback=task_processor,
    timeout=30,                      # Auto-shutdown after 30 seconds of inactivity
    max_messages=10,                 # Stop after processing 10 messages
    die_code="SHUTDOWN",             # Custom shutdown command
    daemon=False,                    # Non-daemon thread
    response_pipe_name=response_pipe_name  # Send results to response pipe
)

main_pipe.listen()

time.sleep(0.2)  # Allow main pipe to start

# Send multiple tasks
tasks = [
    "Generate report",
    "Process data",
    "Send email",
    "Handle error case",  # This will trigger an error response
    "Final task"
]

for task in tasks:
    try:
        success = pipecom.send(main_pipe_name, task, timeout=5, max_attempts=3)
        print(f"Task '{task}': {'Submitted' if success else 'Failed'}")
        time.sleep(0.3)  # Allow processing time
    except pipecom.PipeError as e:
        print(f"Error sending '{task}': {e}")

# Wait for all processing to complete
time.sleep(2)

print("\n📊 Summary:")
print(f"Tasks sent: {len(tasks)}")
print(f"Results received: {len(responses_received)}")
print("Results:")
for response in responses_received:
    print(f"  - {response}")

# Shutdown both pipes - main pipe first to avoid response pipe issues
try:
    pipecom.send(main_pipe_name, "SHUTDOWN", timeout=5)
    print("✅ Main pipe shutdown successfully")
except Exception as e:
    print(f"❌ Error shutting down main pipe: {e}")

# Wait a moment for main pipe to fully shutdown
time.sleep(0.5)

try:
    pipecom.send(response_pipe_name, "PIPECOM_DIE", timeout=5)
    print("✅ Response pipe shutdown successfully")
except Exception as e:
    print(f"❌ Error shutting down response pipe: {e}")

print("\n🎉 Demo completed!")
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
- `callback` (callable): Function called when a message is received - message is passed as param
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

### Simple Chat Application

```python
import sys
import os

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom as pipecom
import threading


def simple_chat_handler(message):
    print(f"📨 Received message: {message}")
    return f"ACK: {message}"


server_pipe = pipecom.Pipe(
    pipe_name="simple_chat_server",
    callback=simple_chat_handler,
    timeout=30,  # Auto-shutdown after 30 seconds of inactivity
    max_messages=10,  # Stop after processing 10 messages
    die_code="SHUTDOWN",  # Custom shutdown command
)

# Start the server pipe listener
server_pipe.listen()


# Client-side example
client_pipe_name = "simple_chat_server"


def send_message(message, max_retries=5):
    """Send a message with retry logic for busy pipe instances."""
    for attempt in range(max_retries):
        try:
            result = pipecom.send(client_pipe_name, message, timeout=5, max_attempts=3)
            if result:
                print(f"✅ Message sent successfully: {message}")
                return True
            else:
                print(f"❌ Failed to send message: {message}")
                return False
        except pipecom.PipeError as e:
            if "busy" in str(e).lower() and attempt < max_retries - 1:
                # Exponential backoff for busy pipe instances
                wait_time = (2 ** attempt) * 0.1  # 0.1, 0.2, 0.4, 0.8, 1.6 seconds
                print(f"🔄 Pipe busy, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})")
                threading.Event().wait(wait_time)
            else:
                print(f"❌ Error sending message after {attempt + 1} attempts: {e}")
                return False
        except Exception as e:
            print(f"❌ Unexpected error sending message: {e}")
            return False
    return False


def example_client(client_id):
    """Example client that sends messages with proper spacing."""
    print(f"🚀 Starting client {client_id}")

    for i in range(3):  # Reduced to 3 messages to avoid overwhelming the pipe
        message = f"Client {client_id} - Message {i + 1}"
        send_message(message)
        # Add some random jitter to spread out the requests
        import random
        wait_time = 0.5 + random.uniform(0.1, 0.5)  # 0.6-1.0 second wait
        threading.Event().wait(wait_time)

    print(f"✅ Client {client_id} finished")


# Example usage - start clients with staggered timing
print("🎬 Starting Simple Chat Demo")
print("=" * 40)

for i in range(3):  # Reduced number of clients
    # Stagger client start times to reduce initial congestion
    threading.Timer(i * 0.2, lambda client_id=i +
                    1: threading.Thread(target=example_client, args=(client_id,)).start()).start()

# Add a shutdown mechanism


def shutdown_after_delay():
    threading.Event().wait(15)  # Wait 15 seconds
    try:
        print("\n🛑 Sending shutdown signal...")
        pipecom.send(client_pipe_name, "SHUTDOWN", timeout=5, max_attempts=3)
        print("✅ Shutdown signal sent")
    except Exception as e:
        print(f"❌ Error sending shutdown: {e}")


# Start shutdown timer
threading.Thread(target=shutdown_after_delay, daemon=True).start()

print("💬 Chat server is running... (will auto-shutdown in 15 seconds)")
print("🔊 Listening for messages...")
```

### Task Queue System

```python
import pipecom as pipecom
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
import pipecom as pipecom

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
- Functional test suite

## Support

- **GitHub Issues**: [https://github.com/falaventho/pipecom/issues](https://github.com/falaventho/pipecom/issues)
- **Documentation**: This README and inline code documentation
- **Examples**: See `tests/` directory for usage examples

---

Made by [Falaventho](https://github.com/falaventho)
