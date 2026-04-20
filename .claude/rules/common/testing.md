# Testing Standards

## Coverage Target
- Minimum 80% code coverage for new code
- All critical paths must have tests
- Edge cases and error paths must be tested

## Test-Driven Development
- Write tests FIRST, then implement
- Tests define the expected behavior
- Red -> Green -> Refactor cycle

## Test Organization
- One test file per model/feature
- Descriptive test method names: `test_<scenario>_<expected_result>`
- Group related tests in the same class
- Use setUp() for shared test data

## Test Quality
- Each test should test ONE thing
- Tests must be independent (no order dependency)
- Tests must be deterministic (no random data without seeds)
- Clean up test data in tearDown when necessary
