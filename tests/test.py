import os
import sys

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

import pipecom_falaventho as pipecom
from pipecom_falaventho import PipeError
import time
import threading
import unittest


class TestPipecom(unittest.TestCase):
    """Comprehensive test suite for pipecom library."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_pipe_name = f"test_pipe_{int(time.time() * 1000) % 10000}"  # Unique pipe name
        self.messages_received = []
        self.callbacks_executed = []

    def tearDown(self):
        """Clean up after each test method."""
        # Send die code to stop any listening pipes
        try:
            pipecom.send(self.test_pipe_name, "PIPECOM_DIE", timeout=1, max_attempts=1)
        except Exception:
            pass
        time.sleep(0.1)  # Give time for cleanup

    def message_callback(self, message):
        """Callback function that records received messages."""
        decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
        self.messages_received.append(decoded_msg)
        self.callbacks_executed.append(time.time())
        print(f"Received: {decoded_msg}")
        return f"ACK: {decoded_msg}"

    def test_basic_send_receive(self):
        """Test basic message sending and receiving."""
        print("\n=== Testing Basic Send/Receive ===")

        # Start listener
        pipe = pipecom.Pipe(self.test_pipe_name, self.message_callback)
        pipe.listen()

        time.sleep(0.2)  # Allow listener to start

        # Send message
        test_message = "Hello, World!"
        result = pipecom.send(self.test_pipe_name, test_message, timeout=5, max_attempts=3)

        time.sleep(0.1)  # Allow processing

        self.assertTrue(result, "Message should be sent successfully")
        self.assertIn(test_message, str(self.messages_received), "Message should be received by callback")

    def test_multiple_messages(self):
        """Test sending multiple messages."""
        print("\n=== Testing Multiple Messages ===")

        pipe = pipecom.Pipe(self.test_pipe_name, self.message_callback)
        pipe.listen()

        time.sleep(0.2)

        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            result = pipecom.send(self.test_pipe_name, msg, timeout=5, max_attempts=3)
            self.assertTrue(result, f"Message '{msg}' should be sent successfully")
            time.sleep(0.1)

        time.sleep(0.2)  # Allow all messages to be processed

        for msg in messages:
            self.assertIn(msg, str(self.messages_received), f"Message '{msg}' should be received")

    def test_timeout_handling(self):
        """Test timeout scenarios."""
        print("\n=== Testing Timeout Handling ===")

        def slow_callback(message):
            """Callback that simulates a slow response."""
            time.sleep(3)

        # Start listener
        pipe = pipecom.Pipe("slow_pipe", slow_callback)
        pipe.listen()

        # Try to send to unresponsive pipe with short timeout
        with self.assertRaises(PipeError) as context:
            pipecom.send("slow_pipe", "test", timeout=1, max_attempts=1)

        print(f"Expected timeout error: {context.exception}")

    def test_pipe_configuration(self):
        """Test different pipe configurations."""
        print("\n=== Testing Pipe Configuration ===")

        # Test with custom die code and max_messages=3 (2 messages + 1 die code)
        custom_die_code = "CUSTOM_DIE"
        pipe = pipecom.Pipe(
            self.test_pipe_name + "_custom",
            self.message_callback,
            die_code=custom_die_code,
            max_messages=3  # Allow for 2 messages + die code
        )
        pipe.listen()

        time.sleep(0.2)

        # Send messages
        result1 = pipecom.send(pipe.pipe_name, "Message 1", timeout=5, max_attempts=3)
        result2 = pipecom.send(pipe.pipe_name, "Message 2", timeout=5, max_attempts=3)

        time.sleep(0.2)

        # Send custom die code
        result3 = pipecom.send(pipe.pipe_name, custom_die_code, timeout=5, max_attempts=3)

        # Verify all sends succeeded
        self.assertTrue(result1, "Message 1 should be sent successfully")
        self.assertTrue(result2, "Message 2 should be sent successfully")
        self.assertTrue(result3, "Custom die code should be sent successfully")

    def test_error_handling(self):
        """Test error conditions and exception handling."""
        print("\n=== Testing Error Handling ===")

        # Test invalid pipe name scenarios
        invalid_names = ["", " ", "pipe/with/slashes"]

        for name in invalid_names:
            try:
                pipecom.send(name, "test", timeout=1, max_attempts=1)
            except Exception as e:
                print(f"Expected error for invalid pipe name '{name}': {e}")

    def test_concurrent_clients(self):
        """Test multiple clients sending to the same pipe."""
        print("\n=== Testing Concurrent Clients ===")

        pipe = pipecom.Pipe(self.test_pipe_name, self.message_callback)
        pipe.listen()

        time.sleep(0.2)

        def send_messages(client_id, count):
            for i in range(count):
                msg = f"Client {client_id} - Message {i+1}"
                try:
                    result = pipecom.send(self.test_pipe_name, msg, timeout=5, max_attempts=3)
                    print(f"Client {client_id} sent: {msg} - Success: {result}")
                    time.sleep(0.05)
                except Exception as e:
                    print(f"Client {client_id} error: {e}")

        # Start multiple client threads
        threads = []
        for client_id in range(3):
            thread = threading.Thread(target=send_messages, args=(client_id, 2))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        time.sleep(0.3)  # Allow all messages to be processed

        print(f"Total messages received: {len(self.messages_received)}")

    def test_response_pipe_functionality(self):
        """Test response pipe functionality for bidirectional communication."""
        print("\n=== Testing Response Pipe Functionality ===")

        # Track messages received on both pipes
        main_messages = []
        response_messages = []

        def main_callback(message):
            """Main pipe callback that processes requests and returns responses."""
            decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
            main_messages.append(decoded_msg)
            print(f"Main pipe received: {decoded_msg}")
            
            # Return a response that will be sent to the response pipe
            return f"Processed: {decoded_msg}"

        def response_callback(message):
            """Response pipe callback that receives the processed results."""
            decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
            response_messages.append(decoded_msg)
            print(f"Response pipe received: {decoded_msg}")
            return f"Response ACK: {decoded_msg}"

        # Create main pipe (without response_pipe_name for now)
        main_pipe_name = f"{self.test_pipe_name}_main"
        response_pipe_name = f"{self.test_pipe_name}_response"
        
        # Start the response pipe listener first
        response_pipe = pipecom.Pipe(response_pipe_name, response_callback)
        response_pipe.listen()
        
        time.sleep(0.2)  # Allow response pipe to start

        # Start the main pipe listener with response_pipe_name configured
        main_pipe = pipecom.Pipe(main_pipe_name, main_callback, response_pipe_name=response_pipe_name)
        main_pipe.listen()

        time.sleep(0.2)  # Allow main pipe to start

        # Send test messages to the main pipe
        test_messages = ["Request 1", "Request 2", "Request 3"]
        
        for msg in test_messages:
            print(f"Sending to main pipe: {msg}")
            result = pipecom.send(main_pipe_name, msg, timeout=5, max_attempts=3)
            self.assertTrue(result, f"Message '{msg}' should be sent successfully to main pipe")
            time.sleep(0.2)  # Allow processing time

        time.sleep(0.5)  # Allow all messages to be processed

        # Verify messages were received on both pipes
        print(f"Main pipe received {len(main_messages)} messages: {main_messages}")
        print(f"Response pipe received {len(response_messages)} messages: {response_messages}")

        # Check that all messages were received on the main pipe
        for msg in test_messages:
            self.assertIn(msg, main_messages, f"Message '{msg}' should be received on main pipe")

        # Check that responses were sent to the response pipe
        for msg in test_messages:
            expected_response = f"Processed: {msg}"
            self.assertIn(expected_response, response_messages, 
                         f"Response '{expected_response}' should be received on response pipe")

        # Clean up both pipes
        try:
            pipecom.send(main_pipe_name, "PIPECOM_DIE", timeout=1, max_attempts=1)
        except Exception:
            pass
        
        try:
            pipecom.send(response_pipe_name, "PIPECOM_DIE", timeout=1, max_attempts=1)
        except Exception:
            pass

    def test_response_pipe_error_handling(self):
        """Test response pipe error handling when response pipe is unavailable."""
        print("\n=== Testing Response Pipe Error Handling ===")

        main_messages = []

        def error_prone_callback(message):
            """Callback that tries to send to non-existent response pipe."""
            decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
            main_messages.append(decoded_msg)
            print(f"Main pipe received: {decoded_msg}")
            return f"Response: {decoded_msg}"

        # Create main pipe with non-existent response pipe
        main_pipe_name = f"{self.test_pipe_name}_error_main"
        nonexistent_response_pipe = f"{self.test_pipe_name}_nonexistent"
        
        # Start main pipe with reference to non-existent response pipe
        main_pipe = pipecom.Pipe(
            main_pipe_name, 
            error_prone_callback, 
            response_pipe_name=nonexistent_response_pipe
        )
        main_pipe.listen()

        time.sleep(0.2)

        # Send a message - this should still work even if response pipe fails
        test_message = "Test message for error handling"
        
        try:
            result = pipecom.send(main_pipe_name, test_message, timeout=5, max_attempts=3)
            # The main message should still be processed successfully
            # even if the response pipe send fails
            print(f"Send result: {result}")
        except Exception as e:
            print(f"Expected error when response pipe is unavailable: {e}")

        time.sleep(0.2)

        # Verify the main message was still received
        self.assertIn(test_message, main_messages, 
                     "Main message should be received even if response pipe fails")

        # Clean up
        try:
            pipecom.send(main_pipe_name, "PIPECOM_DIE", timeout=1, max_attempts=1)
        except Exception:
            pass


def run_interactive_test():
    """Run an interactive test for manual verification."""
    print("\n" + "="*50)
    print("INTERACTIVE TEST - Manual Verification")
    print("="*50)

    messages_received = []

    def interactive_callback(message):
        decoded_msg = message.decode('utf-8') if isinstance(message, bytes) else str(message)
        messages_received.append(decoded_msg)
        print(f"📨 Received: {decoded_msg}")
        return f"ACK: {decoded_msg}"

    # Start listener
    print("🚀 Starting pipe listener...")
    pipe = pipecom.Pipe("interactive_test", interactive_callback)
    pipe.listen()

    time.sleep(0.2)

    print("✅ Listener started. You can now run test2.py in another terminal")
    print("💡 Or send messages programmatically...")

    # Send a few test messages
    test_messages = [
        "Hello from automated test!",
        "Testing special characters: !@#$%^&*()",
        "Testing numbers: 123456789",
        "Final test message"
    ]

    for i, msg in enumerate(test_messages, 1):
        print(f"📤 Sending message {i}: {msg}")
        try:
            result = pipecom.send("interactive_test", msg, timeout=5, max_attempts=3)
            print(f"✅ Send result: {result}")
        except Exception as e:
            print(f"❌ Send error: {e}")
        time.sleep(1)

    print(f"\n📊 Summary: Sent {len(test_messages)} messages, Received {len(messages_received)} messages")

    # Clean up
    try:
        pipecom.send("interactive_test", "PIPECOM_DIE", timeout=1, max_attempts=1)
        print("🛑 Sent shutdown signal")
    except Exception:
        pass


if __name__ == "__main__":
    print("PipeCom Test Suite")
    print("==================")

    choice = input("Run (a)utomated tests or (i)nteractive test? [a/i]: ").lower().strip()

    if choice == 'i':
        run_interactive_test()
    else:
        # Run automated tests
        unittest.main(verbosity=2)
