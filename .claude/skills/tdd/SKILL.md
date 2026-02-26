---
name: tdd
description: "Test-Driven Development (TDD) workflow enforcing the red-green-refactor cycle with mandatory human approval gates. Use this skill whenever the user asks to develop using TDD, write tests first, do test-driven development, use red-green-refactor, or any development task where TDD methodology is requested. Also trigger when the user says things like 'let's TDD this', 'test first approach', 'write the test before the code', or mentions wanting failing tests before implementation. Enforces that every test must be shown failing (red) and approved by the user before any implementation code is written."
---

# Test-Driven Development (TDD)

## Critical Rule: Human Approval Gate

**NEVER write implementation code without explicit user approval of the failing test.**

For every unit of work:
1. Write the test → show it to the user → run it to prove it fails (red)
2. **STOP. Ask the user to approve the failing test before proceeding.**
3. Only after approval: write the minimum code to make it pass (green)
4. Only after green: refactor if needed

If the user rejects the test, revise it based on their feedback and repeat from step 1.

## TDD Workflow

### Step 1: RED — Write a Failing Test

1. Identify the smallest behavior to test next
2. Write ONE test that asserts that behavior
3. Run the test suite — confirm the new test FAILS
4. Present the failing test and its output to the user
5. **Ask for approval using AskUserQuestion** before proceeding

Present the test like this:

```
Here's the failing test for [behavior]:

[test code]

Test output (RED):
[failure output]

Do you approve this test? I'll implement the code to make it pass once approved.
```

### Step 2: GREEN — Write Minimal Implementation

Only after user approves the red test:

1. Write the **minimum** code to make the failing test pass
2. Run the full test suite — all tests must pass
3. Show the implementation and passing output to the user

Do NOT:
- Add code beyond what the test requires
- Optimize or generalize prematurely
- Add error handling the test doesn't demand

### Step 3: REFACTOR — Clean Up

With all tests green:

1. Look for duplication, unclear naming, structural issues
2. Refactor in small steps, running tests after each change
3. If refactoring is trivial or unnecessary, skip this step — don't force it

## Test Writing Best Practices

See [references/best-practices.md](references/best-practices.md) for detailed guidance on:
- Test structure (Arrange-Act-Assert)
- What makes a good vs bad test
- Common pitfalls and anti-patterns
- Naming conventions
- Examples of right and wrong approaches

## Deciding What to Test Next

Work in small increments. Prioritize:

1. **Happy path** — the simplest valid case
2. **Edge cases** — boundaries, empty inputs, single elements
3. **Error cases** — invalid inputs, failures, exceptions
4. **Complex behavior** — build on simpler tests

Each test should add exactly one new behavioral assertion. If a test requires more than a few lines of setup, the unit under test may be doing too much.

## Multi-Test Sessions

When building a feature through multiple red-green-refactor cycles:

1. Keep a mental list of remaining behaviors to test
2. After each cycle completes, state what you plan to test next
3. Get approval for each red test individually — never batch
4. Run the full suite after each green step to catch regressions
