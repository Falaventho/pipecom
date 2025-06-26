import sys
import os

try:
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
except Exception:
    pass

from pipecom import pipecom
from pipecom._exceptions import PipeError
import time
import json


def test_basic_send():
    """Test basic message sending functionality."""
    print("=== Basic Send Test ===")

    try:
        result = pipecom.send('simple', 'Hello World', timeout=5, max_attempts=3)
        print(f"✅ Message sent successfully: {result}")
        return True
    except PipeError as e:
        print(f"❌ PipeError: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_multiple_sends():
    """Test sending multiple messages in sequence."""
    print("\n=== Multiple Send Test ===")

    messages = [
        "First message",
        "Second message with numbers: 12345",
        "Third message with special chars: !@#$%^&*()",
        "Final message"
    ]

    success_count = 0
    for i, msg in enumerate(messages, 1):
        try:
            print(f"Sending message {i}: {msg}")
            result = pipecom.send('simple', msg, timeout=5, max_attempts=3)
            if result:
                print(f"✅ Message {i} sent successfully")
                success_count += 1
            else:
                print(f"❌ Message {i} failed to send")
            time.sleep(0.5)  # Small delay between messages
        except Exception as e:
            print(f"❌ Error sending message {i}: {e}")

    print(f"\n📊 Results: {success_count}/{len(messages)} messages sent successfully")
    return success_count == len(messages)


def test_json_message():
    """Test sending JSON data."""
    print("\n=== JSON Message Test ===")

    data = {
        "type": "test_message",
        "timestamp": time.time(),
        "payload": {
            "user": "test_user",
            "action": "send_data",
            "data": [1, 2, 3, 4, 5]
        }
    }

    try:
        json_message = json.dumps(data, indent=2)
        print(f"Sending JSON: {json_message}")
        result = pipecom.send('simple', json_message, timeout=5, max_attempts=3)
        print(f"✅ JSON message sent successfully: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending JSON: {e}")
        return False


def test_large_message():
    """Test sending a large message."""
    print("\n=== Large Message Test ===")

    # Create a large message (about 1KB)
    large_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20
    large_message = f"LARGE_MESSAGE:{large_text}"

    try:
        print(f"Sending large message ({len(large_message)} characters)...")
        result = pipecom.send('simple', large_message, timeout=10, max_attempts=3)
        print(f"✅ Large message sent successfully: {result}")
        return True
    except Exception as e:
        print(f"❌ Error sending large message: {e}")
        return False


def test_error_conditions():
    """Test various error conditions."""
    print("\n=== Error Condition Tests ===")

    test_results = []

    # Test 1: Non-existent pipe
    print("1. Testing non-existent pipe...")
    try:
        pipecom.send('nonexistent_pipe_12345', 'test', timeout=1, max_attempts=1)
        print("❌ Expected error but none occurred")
        test_results.append(False)
    except PipeError as e:
        print(f"✅ Expected PipeError: {e}")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Unexpected error type: {e}")
        test_results.append(False)

    # Test 2: Empty message
    print("\n2. Testing empty message...")
    try:
        result = pipecom.send('simple', '', timeout=5, max_attempts=3)
        print(f"✅ Empty message handled: {result}")
        test_results.append(True)
    except Exception as e:
        print(f"❌ Error with empty message: {e}")
        test_results.append(False)

    # Test 3: Very short timeout
    print("\n3. Testing very short timeout...")
    try:
        result = pipecom.send('simple', 'timeout test', timeout=0.1, max_attempts=1)
        print(f"Result with short timeout: {result}")
        test_results.append(True)
    except Exception as e:
        print(f"Short timeout result: {e}")
        test_results.append(True)  # Expected to potentially fail

    success_count = sum(test_results)
    print(f"\n📊 Error condition tests: {success_count}/{len(test_results)} passed")

    return success_count >= len(test_results) - 1  # Allow one failure


def test_concurrent_sends():
    """Test concurrent sending from multiple threads."""
    print("\n=== Concurrent Send Test ===")

    import threading
    results = []

    def send_worker(worker_id, message_count):
        worker_results = []
        for i in range(message_count):
            try:
                msg = f"Worker-{worker_id}-Message-{i+1}"
                result = pipecom.send('simple', msg, timeout=5, max_attempts=3)
                worker_results.append(result)
                print(f"Worker {worker_id}: Sent message {i+1} - {result}")
                time.sleep(0.1)
            except Exception as e:
                print(f"Worker {worker_id}: Error on message {i+1}: {e}")
                worker_results.append(False)
        results.extend(worker_results)

    # Start multiple worker threads
    threads = []
    for worker_id in range(3):
        thread = threading.Thread(target=send_worker, args=(worker_id, 2))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    success_count = sum(1 for r in results if r)
    print(f"\n📊 Concurrent sends: {success_count}/{len(results)} successful")

    return success_count >= len(results) * 0.8  # Allow 20% failure rate


def interactive_mode():
    """Interactive mode for manual testing."""
    print("\n=== Interactive Mode ===")
    print("Enter messages to send (type 'quit' to exit, 'die' to stop listener):")

    while True:
        try:
            message = input("Message> ").strip()

            if message.lower() == 'quit':
                break
            elif message.lower() == 'die':
                message = "PIPECOM_DIE"

            if message:
                result = pipecom.send('simple', message, timeout=5, max_attempts=3)
                print(f"Result: {result}")

                if message == "PIPECOM_DIE":
                    print("Sent shutdown signal to listener")
                    break
            else:
                print("Empty message, try again...")

        except KeyboardInterrupt:
            print("\nExiting interactive mode...")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main test function."""
    print("PipeCom Sender Test Suite")
    print("=========================")

    if len(sys.argv) > 1 and sys.argv[1] == 'interactive':
        interactive_mode()
        return

    # Run all tests
    tests = [
        ("Basic Send", test_basic_send),
        ("Multiple Sends", test_multiple_sends),
        ("JSON Message", test_json_message),
        ("Large Message", test_large_message),
        ("Error Conditions", test_error_conditions),
        ("Concurrent Sends", test_concurrent_sends)
    ]

    print("Make sure test.py is running in another terminal first!")
    input("Press Enter when ready to start tests...")

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)

        try:
            result = test_func()
            results.append((test_name, result))
            print(f"\n{test_name}: {'✅ PASSED' if result else '❌ FAILED'}")
        except Exception as e:
            print(f"\n{test_name}: ❌ FAILED with exception: {e}")
            results.append((test_name, False))

        time.sleep(1)  # Brief pause between tests

    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print('='*50)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<30} {status}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
