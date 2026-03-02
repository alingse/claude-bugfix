"""Example buggy code for testing claude-bugfix."""


def divide_numbers(a, b):
    """Divide two numbers."""
    return a / b


def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    total = sum(numbers)
    return total / len(numbers)


def get_user_age(user_data):
    """Get user age from user data dictionary."""
    return user_data["age"]


def process_items(items):
    """Process a list of items."""
    results = []
    for i in range(len(items) + 1):  # Bug: off-by-one error
        results.append(items[i].upper())
    return results


if __name__ == "__main__":
    # Test cases that will trigger bugs
    print(divide_numbers(10, 0))  # Division by zero
    print(calculate_average([]))  # Empty list
    print(get_user_age({}))  # Missing key
    print(process_items(["hello", "world"]))  # Index out of range
