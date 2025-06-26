#!/usr/bin/env python3
"""
Utility script to clean up leftover FIFO pipes from testing.
Run this if pipes are not being cleaned up properly.
"""
import os
import glob


def cleanup_test_pipes():
    """Clean up any leftover test pipes."""
    patterns = [
        "test_pipe_*",
        "test_pipe_*_ack",
        "test_pipe_*_custom",
        "test_pipe_*_custom_ack",
        "task_processor*",
        "task_results*",
        "simple_chat_server*",
        "interactive_test*",
        "slow_pipe*"
    ]

    cleaned = 0
    for pattern in patterns:
        for pipe_file in glob.glob(pattern):
            try:
                if os.path.exists(pipe_file):
                    os.unlink(pipe_file)
                    print(f"Cleaned up: {pipe_file}")
                    cleaned += 1
            except Exception as e:
                print(f"Failed to clean {pipe_file}: {e}")

    if cleaned == 0:
        print("No test pipes found to clean up.")
    else:
        print(f"Cleaned up {cleaned} pipe(s).")


if __name__ == "__main__":
    cleanup_test_pipes()
