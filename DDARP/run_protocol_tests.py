#!/usr/bin/env python3
"""
DDARP Protocol Test Runner

Runs all protocol tests and generates a comprehensive report.
"""

import sys
import os
import unittest
import time
from io import StringIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def run_tests():
    """Run all protocol tests and return results."""

    # Discover tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests', 'protocol')

    if not os.path.exists(start_dir):
        print(f"❌ Test directory not found: {start_dir}")
        return False

    suite = loader.discover(start_dir, pattern='test_*.py')

    # Run tests with detailed output
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    print("🧪 Running DDARP Protocol Tests...")
    print("=" * 60)

    start_time = time.time()
    result = runner.run(suite)
    end_time = time.time()

    # Print results
    print(stream.getvalue())

    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"Execution time: {end_time - start_time:.2f}s")

    # Print failure details
    if result.failures:
        print(f"\n❌ FAILURES ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  • {test}: {traceback.split('AssertionError:')[-1].strip()}")

    if result.errors:
        print(f"\n💥 ERRORS ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  • {test}: {traceback.split('Exception:')[-1].strip()}")

    success = len(result.failures) == 0 and len(result.errors) == 0

    if success:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {len(result.failures) + len(result.errors)} test(s) failed")

    return success

def main():
    """Main test runner function."""
    print("DDARP Protocol Test Suite")
    print("=" * 60)

    try:
        success = run_tests()

        if success:
            print("\n🎉 Protocol implementation is ready!")
            print("\nNext steps:")
            print("1. Run examples: python3 examples/protocol_usage.py")
            print("2. Integrate with DDARP node implementation")
            print("3. Add to networking layer")
            return 0
        else:
            print("\n🔧 Please fix failing tests before proceeding")
            return 1

    except Exception as e:
        print(f"\n💥 Error running tests: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())