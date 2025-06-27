import sys
import os

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom
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
