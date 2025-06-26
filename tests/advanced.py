import sys
import os

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom_falaventho as pipecom
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
