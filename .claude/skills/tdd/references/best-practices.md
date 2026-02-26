# TDD Best Practices

## Test Structure: Arrange-Act-Assert

Every test follows three phases:

```python
def test_user_can_update_email():
    # Arrange — set up preconditions
    user = User(email="old@example.com")

    # Act — perform the action under test
    user.update_email("new@example.com")

    # Assert — verify the outcome
    assert user.email == "new@example.com"
```

Keep each phase short. Long arrange blocks signal the unit is too complex or the test needs fixtures/helpers.

## Naming Tests

Test names describe the behavior, not the implementation:

**Good:**
```
test_returns_empty_list_when_no_items_match
test_raises_error_for_negative_quantity
test_sends_welcome_email_on_signup
```

**Bad:**
```
test_function          # what behavior?
test_edge_case         # which one?
test_it_works          # meaningless
test_parse_method      # describes implementation, not behavior
```

## What Makes a Good Test

1. **Tests one behavior** — a single logical assertion (multiple `assert` statements are fine if they verify one behavior)
2. **Independent** — does not depend on other tests or execution order
3. **Deterministic** — same result every time, no flakiness
4. **Fast** — unit tests should run in milliseconds
5. **Readable** — a new developer can understand the intent without reading the implementation

## Common Pitfalls

### Testing implementation, not behavior

**Wrong — tied to implementation:**
```python
def test_sort_uses_quicksort():
    sorter = Sorter()
    sorter.sort([3, 1, 2])
    assert sorter._algorithm_used == "quicksort"
```

**Right — tests observable behavior:**
```python
def test_sort_returns_elements_in_ascending_order():
    assert Sorter().sort([3, 1, 2]) == [1, 2, 3]
```

### Over-mocking

**Wrong — mocks everything, tests nothing:**
```python
def test_process_order():
    order = Mock()
    order.total = Mock(return_value=100)
    processor = OrderProcessor()
    processor.db = Mock()
    processor.emailer = Mock()
    processor.process(order)
    processor.db.save.assert_called_once()  # only tests wiring
```

**Right — mock boundaries, test logic:**
```python
def test_process_order_applies_discount():
    order = Order(items=[Item(price=100)], discount_code="SAVE10")
    processor = OrderProcessor(db=FakeDB(), emailer=FakeEmailer())
    result = processor.process(order)
    assert result.total == 90
```

Mock at system boundaries (databases, APIs, file systems). Don't mock the code you're testing.

### Writing too many tests at once

TDD means one test at a time. Writing three failing tests before implementing any of them:
- Obscures which behavior is being developed
- Makes the green step harder (tempting to write more code than needed)
- Breaks the feedback loop

### Testing trivial code

Don't test getters/setters, framework behavior, or language features. Test YOUR logic.

### Giant test functions

If a test needs 30 lines of setup, the design needs work, not more tests. Extract helpers or simplify the unit under test.

## Mocking Guidelines

**Do mock:**
- External services (HTTP APIs, databases, message queues)
- File system operations in unit tests
- Time/dates when testing time-sensitive logic
- Third-party libraries with side effects

**Don't mock:**
- The class/function under test
- Simple value objects or data structures
- Pure functions with no side effects
- Internal implementation details

## Test Isolation Checklist

- No shared mutable state between tests
- No dependency on test execution order
- No dependency on external services (in unit tests)
- Each test can run independently and produce the same result
- Setup/teardown properly cleans up resources

## Red-Green-Refactor Anti-Patterns

| Anti-Pattern | Problem | Fix |
|---|---|---|
| Writing code before the test | Violates TDD; no red step | Always start with a failing test |
| Making the test pass with hardcoded values | Green step is fake | Triangulate: add a second example to force real logic |
| Skipping refactor | Technical debt accumulates | At least evaluate if refactoring is needed each cycle |
| Giant leaps | Tests cover too much at once | Break into smaller behavioral increments |
| Gold plating in green | Adding unrequested features | Write only what the test demands |
