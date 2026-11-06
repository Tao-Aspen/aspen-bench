# Frontend Conventions

We use ReactRouterV6 and we use Toasty in our own Alert Context.

We use ShadCN + Tailwind for UI components and styling.
We use .env.local-development for our local development settings.
In order to mock to tell the frontend code to use the mocked axios configuratio you must set VITE_MOCKAXIOS="true" in
the .env.local-development file. Do the opposite for when you want to frontend to actually hit the backend apis. You
must make sure you run the backend portal.api. Inorder for the backend to successfully run you need to make sure docker
is running with mssql server and azurite are running as well.

## Folder Structure for new features/pages

Each page is a folder:

```
/pages
    /[pageName]
        /client
         - [pageName]Client.ts
         - [pageName]Endpoints.ts
         - mockData.ts
        /components
         - Component1.tsx
         - Component2.tsx
        - Index.tsx       // Main page
        - types.ts        // Types/interfaces
        - constants.ts   // Constants/enums
        - utils.ts        // Utility functions
        -[PageName]Context.tsx     // Optional (complex state)
```

⸻

## File naming convention:

We use the standard React convention for file naming.

Constants and other .ts and react hook files should be camelCase(i.e. useForm.tsx) and react components (.tsx files)
should be PascalCase.

⸻

## Layouts

We have 4 different types of layouts files:

- Layout files that only have styling (ApplicationTopNavBarLayout)
- Layout files that only hold a context’s provider (i.e. RegistrationProviderWrapper)
- Layout files that guard and potentially boot users with insufficient permissions (i.e. MfaAuthGuard)
- Layout files that hold dialog/modal components (i.e. LoginDialogWrapper)

⸻

## API Client Pattern

All backend access is built on Axios + useBaseHttpClient.

### Client file

```tsx
export const useAuthClient = () => {
  return useBaseHttpClient({ endpoints: authEndpoints });
};
```

### Endpoints file

```tsx
const LOGIN = "/auth/login" as const;
const AUTH_USER = "/auth/user" as const;

export const authEndpoints = {
  login: defineEndpoint<Post, typeof LOGIN, ICredentials, ILoginResponse>(POST, LOGIN),
  authUser: defineEndpoint<Get, typeof AUTH_USER, undefined, IApplicationUser>(GET, AUTH_USER),
};
```

### Usage of client in a component with AlertContext

```tsx
 const { showError, showSuccess } = useAlertContext();
 const authClient = useAuthClient();

  const changePasswordAsync = useCallback(async () => {
    
  const result = await authClient.changePassword.postAsync({
    pathParams: { userId: authUser.id },
    data: passwordSubmission,
  });
  // handle result
    if (!result.isValid) {
      showError("Unable to reset password");
    } else {
      showSuccess("Password has been updated");
    }
  },[authUser, authClient]);
```

## Playwright E2E Test Architecture

Playwright tests must follow the same architectural discipline as the rest of the frontend. The test file should tell the user-flow story, not contain backend setup, auth plumbing, repeated browser mechanics, or fragile synchronization logic.

### Goals

- Keep tests readable and deterministic.
- Move new files into their appropriate directories.
- Use fixtures and helpers so tests stay focused on the behavior under test.

### Playwright file placement and naming

- Place E2E tests under `src/tests/test-e2e/test`.
- Create feature folders in camelCase with a `Tests` suffix, for example:
  - `authTests`
  - `phoneTests`

### Test file naming

- Create test files in camelCase and end them with `.e2e.tsx`, for example:
  - `phoneManagementShouldCreateUpdateAndDelete.e2e.tsx`
- Name test files after the feature and expected behavior. Prefer:
  - `[feature][ExpectedBehavior].e2e.tsx`
  
### Test naming

- Name each Playwright test with the pattern:
  - `should [expected result] when [condition]`

Example:

```tsx
test("should load the phone page when the organization is fresh", async () => {
  // test body
});
```

## Playwright coding conventions

These conventions are required for new Playwright tests and helpers.

### 1. Wait for meaningful signals

Prefer waiting for:
- API responses
- URL changes
- load states
- visible UI elements
- final user-facing outcomes

Do not introduce arbitrary sleep-style waits unless there is no better option.

### 2. Tests should read like a sequence of actions and outcomes:

- create the promise
- perform the action
- await the result
- assert the outcome

This is especially useful when a user action causes a side-effect and the test needs to wait for that side-effect before asserting the outcome.

In practice, set up the wait before the action, then perform the action, then wait for the side-effect to finish, and only then assert the final result. This makes the test less flaky when actions trigger things like requests, navigation, toasts, or refreshed UI state.

### 3. Do not use `Promise.all()` as the default synchronization pattern

`Promise.all()` is allowed, but default to explicit sequencing when an action triggers a request or state change:

- create the wait first
- perform the UI action second
- await the result third

### 4. Store intermediate results in descriptive variables

Prefer descriptive variables such as:

- `loginResultPromise`
- `setup2FaResultPromise`

### 5. Wait for page readiness, not just navigation

Do not assume `page.goto()` means the page is ready for interaction.

Preferred readiness pattern:

- navigate
- wait for the correct URL
- wait for the load state
- wait for important UI elements to be visible
- only then interact

Use existing helpers such as `waitForUrlAsync` and `gotoPathAsync` when appropriate.

### 6. Assert the behavior that actually matters

Assert the real user-visible or domain-relevant outcome.

### 7. Choose the fixture based on the behavior being tested

Use the starting fixture that matches the scenario.

- When testing login, 2FA, or remember-me behavior, start from a fresh unauthenticated account.
- When testing authenticated feature behavior, start from a fresh authenticated account.

### 8. Keep test files thin

A good test file should mainly:

- choose the right fixture
- use helpers to prepare the scenario
- perform the action being tested
- assert the user-visible outcome


## Creating a new Playwright frontend test

Use this checklist when adding a test:

1. Define one clear behavior to verify.
2. Decide what backend data must exist before the test starts.
3. Put the file in the correct `src/tests/test-e2e/test/[feature]Tests` folder and name it after the feature + expected behavior.
4. Choose the correct starting fixture:
  - fresh unauthenticated account for login / 2FA / remember-me flows
  - fresh authenticated account for in-app feature flows
5. Reuse existing shared helpers and feature helpers before adding browser steps directly.
6. Add a new helper, seeding method, or fixture only if it has one clear responsibility.
7. Write the flow in explicit steps:
  - create the promise
  - perform the action
  - await the result
  - assert the outcome
8. Wait for meaningful readiness/completion signals, not arbitrary delays.
9. Keep the test file thin and assert the final behavior that matters.

