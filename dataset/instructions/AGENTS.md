# Aspen AI Architecture & Conventions

This document defines the solution-wide architecture, conventions, and format for the entire monorepo. This file is the single source of truth for global rules and patterns.

⸻

# Architecture Overview

## We have a monolithic repo with all projects and apps:

- AspenAI.Portal.API – Main portal API

- AspenAI.Bot.API – Bot API

- AspenAI.Functions – Azure Functions (all timed/scheduled jobs)

- AspenAI.Portal.Frontend – TypeScript/React frontend on Vite

- AspenAI.Services & AspenAI.Portal.Services – Business logic

- AspenAI.Infrastructure – Logging, emailing, extension methods

- Test projects – One per project using XUnit with Moq

## System Context Diagram (high-level)

- AspenAI.Portal.Frontend ⇄ AspenAI.Portal.API ⇄ AspenAI.Services ⇄ AspenAI.Dal ⇄ Azure SQL
- AspenAI.Bot.Api ⇄ AspenAI.Services ⇄ AspenAI.Dal ⇄ Azure SQL
- AspenAI.Functions ⇄ AspenAI.Services ⇄ AspenAI.Dal ⇄ Azure SQL
- All may use AspenAI.Infrastructure (logging/email/extensions) and Azure Blob/Table (via Dal)
- Prompts used by AspenAI.Bot.Api from AspenAI.Bot.Prompts

⸻

## Aspen AI Repository Contents

### Main Projects

- AspenAI.Services - This project holds the shared services between all applications (Portal.Api, Bot.Api, Functions)
- AspenAI.Portal.Services - Services only used by the portal
- AspenAI.Portal.Frontend - Holds our react typescript shadcn tailwind vite application
- AspenAI.Portal.Api - Api endpoints for the Portal.Frontend to consume and use
- AspenAI.Models - Holds the enums, EF entities, settings, and Dtos that our whole solution uses.
- AspenAI.Infrastructure - Holds the logging and emailing logic, extension method logic.
- AspenAI.Functions - holds our timed serverless azure functions
- AspenAI.Dal - Has our ef migration files modelsnapshot file, repo methods, ApplicationDbContext, Our AzureTableStorage accessors and Context.
- AspenAI.Bot.Prompts - Holds all of the prompts that the bot uses
- AspenAI.Bot.Api - Defines the endpoints that twilio and livekit can communicate with our bot
- AgentPublisher - Console app only for manual use

### Test Projects

- AspenAI.Tests.Base - This holds the appsettings file for the all tests and base test files for Database, Blob, Controller, and default test setups. Also has testhelpers for each test setup.
- AspenAI.Services.Tests - Combination of unit tests and integration tests for service logic
- AspenAI.Portal.Services.Tests - Combination of unit tests and integration tests for portal service logic
- AspenAI.Portal.Api.Tests - Controller action method tests
- AspenAI.Infrastructure.Tests - Primarily unit tests for infrastructure logic
- AspenAI.Functions.Tests - Integration test to ensure function are working properly
- AspenAI.Dal.Tests - Unit tests to ensure each repo call or any sql raw queries are working as expected.
- AspenAI.Bot.Prompts.Tests - Has the tests and shared logic to allow us to evaluate whether our prompts are successfully working for specific scenarios
- AspenAI.Bot.Api.Tests - Controller action method tests

### The relationship between all projects is as follows:

- AspenAI.Models are at the root(Doesn’t have any relationships)
- AspenAI.Infrastructure(references models)
- AspenAI.Dal(References Models and Infrastructure)
- AspenAI.Services(References Models, Infrastructure, Dal)
- AspenAI.Bot.Api(References Models, Infrastructure, Dal, Services)
- AspenAI.Functions(References Models, Infrastructure, Dal, Services)
- AspenAI.Portal.Services(References Models, Infrastructure, Dal, Services)
- AspenAI.Portal.Api(References Models, Infrastructure, Dal, Services, Portal.Services)
- Test projects have the same references as the project they are testing. I.e. Portal.Services.Tests references Models, Infrastructure, Dal, Services, and AspenAI.Portal.Services
- AspenAI.Portal.Frontend doesn’t reference any other projects.

### Other Files/Folders

- global.json - .NET SDK version configuration
- Sql - folder contains common sql query we run to manually analyze data
- Solution Items - folder container common setup guides
- Pipelines - folder that container our azure devops yml files
- Kubernetes - folder that container our Azure Kubernetes Service files for our bot.api
- AudioConverter - Console app only for manual use when we need to convert audio files.
- Docker - folder for our docker files
- AspenAI.sln.DotSettings - Shared solution-wide IDE settings
- AspenAI.sln - Main Visual Studio solution file
- .agent/DOD.md - Definition of done documentation that must be followed when done with a feature or change

⸻

### Environments & Configuration

- Config files per environment: AppSettings.{Environment}.json for APIs and Functions(Local is appsettings.Local.json) and .env.\* for Frontend(Local is .env.local-development).

# Tech Stack

- Backend: .NET 8 with C#

- Data Access: EF Core with Azure SQL Server

- Storage: Azure Blob Storage + Azure Table Storage (for caching/redundancy if DB goes down)

- Frontend: React, TypeScript, Vite, ShadCN, Tailwind CSS

- Scheduled Jobs: Azure Functions (all jobs must live in AspenAI.Functions)

### Local Tooling

- Docker Desktop (for MSSQL & Azurite)
- Node LTS for Frontend (Vite build)
- Azure Functions Core Tools (for local Functions dev)
- .NET 10 SDK (as pinned in global.json)
- .NET EF Core CLI Tools (for migrations). Install with: `dotnet tool install --global dotnet-ef`

### Static Analysis & Style

- Backend: dotnet format, analyzers.
- Frontend: ESLint + TypeScript strict mode; Prettier for formatting.
  ⸻

# How to Run the application

- Ensure mssql is running locally and is reachable (connection string: `Server=localhost,1433;Database=AspenAIData;User Id=sa;Password=P@ssw0rd;`
- Ensure azurite is running locally and is reachable (connstring: `AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;DefaultEndpointsProtocol=http;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;`
- In most cases these will be running in a docker container so you would need to ensure that docker is up and running with these containers started and running. Additional note: The application will run the migrations and seed the db and tableStorage when running the application automatically each time the application is run.

  - This is the code that does it:

  ```csharp
  if (app.Environment.IsLocal())
  {
      using var scope = serviceProvider.CreateScope();
      var dbContext = scope.ServiceProvider.GetRequiredService();
      var tablesContext = scope.ServiceProvider.GetRequiredService();

      SampleDataInitializer.RunMigrations(dbContext);
      await SampleDataInitializer.ClearAndReseedDatabaseAsync(dbContext, scope, true).ConfigureAwait(false);
      SampleDataInitializer.ClearAndReseedTableStorage(tablesContext);
  }
  ```

## Docker Quickstart

- Start containers:
  - MSSQL: `docker run -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=P@ssw0rd;" -p 1433:1433 --name aspen-sql -d mcr.microsoft.com/mssql/server:2022-latest`
  - AZURITE: `docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 --name aspen-azurite -d mcr.microsoft.com/azure-storage/azurite`

## Setting up Https
### Backend:
`dotnet dev-certs https --trust`
### Frontend:
1. Install mkcert

2. Install the Local CA
```
mkcert -install
```

3. Generate SSL Certificates
   Navigate to the root directory(AspenAI.Portal.Frontend) of the React project and run:
```
mkcert -key-file key.pem -cert-file cert.pem localhost 127.0.0.1 ::1
```
4. Copy the `cert.pem` and the `key.pem` files to a `certs` folder in the root dir of AspenAI.portal.frontend i.e. ~/AspenAI.Portal.Frontend/certs

## Running Projects

- Backend (from repo root): dotnet build then run AspenAI.Portal.Api / AspenAI.Bot.Api / AspenAI.Functions as needed.
- Frontend: cd AspenAI.Portal.Frontend && npm i && npm start

## Local URLs

- Portal.Frontend: http://localhost:3000
- Portal.API: https://localhost:59981
- Bot.API: https://localhost:7236
- Functions (HTTP): http://localhost:7071

---

# How to test the application

Ensure the MSSQL and Azurite are running. If using docker make sure the docker instance is running and that ms sql server is running and so is azurite.
You can then run the tests with dotnet test {projectname} e.g. dotnet test AspenAI.Dal.Tests.csproj

### Common test commands
- Run tests for a single project: `dotnet test ./AspenAI.Dal.Tests/AspenAI.Dal.Tests.csproj -l "trx;LogFileName=TestResults.trx"`
- NEVER run AspenAI.Bot.Prompt.Tests those take a long time and hit our Ai resources. We mainly want to test repo, service, infrastructure, and controller tests when we make changes in those projects.

---

# Backend Conventions

## Deployment & Database Migrations

Our deployment process is designed for **zero downtime**. To achieve this, the pipeline deploys database schema changes *before* it deploys the new application code. This creates a short period where the new database schema must work with the old, existing code, and vice-versa.

Therefore, all database changes **must be backward-compatible**.

### Core Rules for Schema Changes

-   **NEVER Rename or Remove:** Any data schema element—including **SQL columns**, **Azure Table Storage properties**, or **enum values**—defined in code that has been merged into the `main` branch must **never be renamed or removed** directly.

-   **GRACEFULLY Handle New Fields:** When adding a new column or property, all existing data entries will not have a value for it. The new application code **must** be written to handle cases where this new field is `null` or missing. New database columns should be **nullable**, and the corresponding code must perform null-checks before using the property's value.

-   **How to "Rename" or "Remove" (The Additive Method):**
    1.  **Add the New:** Add the new property, table, or enum value. Ensure the application works correctly if this new field is `null`.
    2.  **Depricate the Old:** Mark the old element with the `[Obsolete("Use NewProperty instead.")]` attribute.
    3.  **Update the Code:** Modify the application logic to use the new element and migrate data over time if necessary.
    4.  The actual removal of the obsolete element is a separate, future task after the new code has been deployed and stabilized.

**This is the most critical rule for maintaining production stability.** Any plan involving database modifications must strictly adhere to this backward-compatible, additive approach.

## Repository Pattern
- We use the Repository pattern.
- Each DB table has a Repo class inheriting from `RepoBase`, which implements boilerplate CRUD methods.
- Engineers may add custom queries and ExecuteAsync logic inside specific repo classes.
- Repo methods should only contain DB related logic, agnostic of business decisions

⸻

## Service Classes

We use service classes to house the higher level implementation that requires state/methods from either repositories or other service classes

- Keep class names short, descriptive, and concise

 - When generating a constructor for any service class, parameters MUST be ordered as follows:
   1.  Repository interfaces (e.g., `IRepo`)
   2.  Service interfaces (e.g., `IService`)
   3.  Settings classes (e.g., `IOptions<MySettings>`)
   4.  Logging/Monitoring (`IAppMonitor<T>`)

- We pretty much exclusively use scoped services. Scoped services, clients, and options/settings should be registered in the file `AspenAI.Services.Configuration.ServicesConfiguration` or `AspenAI.Portal.Services.Configuration.ServicesConfiguration` depending on whether the service is used by all projects or just the portal project. The pattern for registering a scoped service is as follows:

  ```csharp
  services.AddScoped<IBot, BotServices.Bot>();
  ```

- We register http clients using the typed client pattern. The pattern for registering a typed http client is as follows:
  ```csharp
  services.AddHttpClient<ISideCarClient, SideCarClient>();
  ```
- We register appsettings using the options pattern. The pattern for registering appsettings is as follows:
  ```csharp
  services.ConfigureAspenAIOptions<AzureSettings>(nameof(AzureSettings));
  ```

⸻

## Infrastructure

### ScopedProperties

Lightweight per-request context (RequestId + Org info) used by logging (`IAppMonitor`) and `ApplicationDbContext` query filters.

**Purpose:** Correlate logs and apply tenant scoping.

**Usage:**

- Portal (`AspenAI.Portal.Api`): Set automatically from user claims
- Bot/Functions: Call `SetScopedProperties(orgId)` manually in controllers/functions. Example:

```csharp
[HttpPost("{orgId:int}")]
public async Task<IActionResult> DoSomething([FromRoute] int orgId)
{
try
{
    _scopedProperties.SetScopedProperties(orgId);
    // implementation
```

An orgId should always be passed in if the action is tenant bound without a user claim(login user).

### Extension Classes

We use extension classes to house basic utility logic that revolved around a single object without the need to inject any repo/service class logic

Extension classes and methods are always static

Ex: `StringExtensions.cs`

```csharp
public static int CountWords(this string value)
```

```csharp
var s = “example phrase”
var numWords = s.CountWords() // Result: 2
```

If the extension method needs to be Tried then we can pass in a generic appMonitor. Ex:

```csharp

public static int TryCountingWords<T>(this string value, IAppMonitor<T> appMonitor)
{
    try
    {
        //logic to count words
    }
    catch(Exception ex){
        appMonitor.LogAndEmailException(ex, “Error occurred when counting words”)
    }
}
```

⸻

## Method Naming Conventions

Keep methods simple, descriptive, and consistent.

### Prefixes

- Try – Method has try/catch and cannot throw (except for CancellationToken). Ex:

```csharp
   public async Task<bool> TryAddItemAsync(Item item, CancellationToken token)
```

### Suffixes (combine in this order)

- `_IncludeX` – Adds the Navigation/Inverse Navigation from a fetched EF entity. EX:
- `_AsQueryable` – Returns IQueryable (query not executed yet).
- `_NoTracking` – Doesn’t add fetched entities to the change tracker
- `_IgnoreQueryFilters` – Ignores EF query filters.
- `Async` – Async methods (always last).

### Examples

- `TryGetAllUsers_IncludeTeams_AsQueryable_NoTracking_IgnoreQueryFiltersAsync`
- `TryGetAllUsers_IncludeTeamsAsync`
- `GetUsers_IgnoreQueryFilters`
- `GetUsers_AsQueryable`
- `DoThisAsync`
- `TryAddingItem`

⸻

## Coding Conventions

We like to use is false instead of !. e.g. `if(someProp is false){ }`.

We only use single line ifs for continue or returns. e.g. `forEach(item in items){ if(item.isTrue) continue;}`

We don’t like long if conditions/nested ternary conditions. We prefer to break it up into separate steps with descriptive variables.

⸻

## Models Project
This `AspenAI.Models` project has its own `AGENTS.md` file that defines detailed conventions for the Models project. Below is a summary of the key architectural points that affect the entire solution.

- This project contains all the Entity Framework Core entities, enums, settings classes, and shared DTOs.
- Use DTOs for data transfer between repos, services, and controllers.
- Entities are reserved for database tables and live in the `AspenAI.Models.Entities` namespace.

### Base Entity Hierarchy & Usage

**RULE:** When creating a new entity, you **MUST** inherit from the narrowest base class that provides the required behavior. This ensures automatic tenancy, soft-delete, and audit filtering.

1.  **EntityRoot**
    -   **Adds:** Audit fields (`CreatedBy`, `ModifiedBy`, etc.).
    -   **Use When:** You need audit tracking but require a custom primary key shape (not a standard `int Id`).

2.  **EntityBase** (inherits `EntityRoot`)
    -   **Adds:** `int Id` (Standard Identity PK).
    -   **Use When:** For simple, non-tenant-specific entities that do not need to be archived or soft-deleted.

3.  **OrganizationEntityBase** (inherits `EntityBase`)
    -   **Adds:** Mandatory `int OrganizationId`.
    -   **Use When:** The entity **must** belong to a single organization. It will be automatically filtered by tenant.

4.  **NullableOrganizationEntityBase** (inherits `EntityBase`)
    -   **Adds:** Optional `int? OrganizationId`.
    -   **Use When:** The entity can be global (`OrganizationId` is `null`) or can be overridden by a specific tenant.

5.  **ArchivableEntityBase** (inherits `EntityBase`)
    -   **Adds:** `bool IsArchived`.
    -   **Use When:** For items that users can "archive" or hide but that should remain accessible for restoration or historical reporting.

6.  **ArchivableOrganizationEntityBase** (inherits `OrganizationEntityBase`)
    -   **Adds:** `bool IsArchived`.
    -   **Use When:** For a tenant-scoped entity that also needs archive functionality.

7.  **DeletableEntityBase** (inherits `EntityBase`)
    -   **Adds:** `bool IsDeleted` (soft-delete flag).
    -   **Use When:** For items that are semantically "deleted" but must be retained internally for compliance or history. Prefer `Archivable` if the user-facing term is "archive."

8.  **DeletableOrganizationEntityBase** (inherits `OrganizationEntityBase`)
    -   **Adds:** `bool IsDeleted`.
    -   **Use When:** For a tenant-scoped entity that needs soft-delete functionality.

### EF Core Relationships

**RULE:** When defining a one-to-many relationship, you **MUST** use the `[InverseProperty]` attribute on the collection navigation property to explicitly link the two sides of the relationship.

-   **The "One" Side (Principal Entity):**
    ```csharp
    [InverseProperty(nameof(AgentScript.AiAgentNavigation))]
    public IEnumerable<AgentScript> AgentScripts { get; set; }
    ```

-   **The "Many" Side (Dependent Entity):**
    ```csharp
    public int? AgentVoiceId { get; set; }

    [ForeignKey(nameof(AgentVoiceId))]
    public AgentVoice AgentVoiceNavigation { get; set; }
    ```

⸻
## Cancellation Token Handling

If a method accepts a CancellationToken, always:
First line: token.ThrowIfCancellationRequested();

In Try methods: catch OperationCanceledException, log with `_appMonitor.LogMessage()`, then rethrow. Example:

```csharp
public void TryDoingTask(CancellationToken cancellationToken)
{
    token.ThrowIfCancellationRequested();
    try{
    //some logic
    }
    catch(OperationTaskCancelled){
        _appMonitor.LogMessage(“Token was canceled”)
        throw;
    }
    catch(Exception ex){
        _appMonitor.LogAndEmailException(ex)
    }
}
```

This is the only case where a Try method may throw. Only when it takes in a CancelationToken as a parameter.
If a Tried method instantiates CancellationTokenSource or uses a CancelationToken without it getting passed into the method as a parameter then it should never rethrow when catching the OperationTaskCanceled Exception. Example:

```csharp
public async Task TryDoingTaskAsync(){
    try{
        var cancellationToken = _cancellationTokenSource.Token;
        await HandleTaskAsync(cancellationToken);
    }
    catch(OperationTaskCancelled){
        _appMonitor.LogMessage(“Token was canceled”);
        //We catch the OperationTaskCancelled Exception but we do not rethrow.
    }
    catch(Exception ex){
        _appMonitor.LogAndEmailException(ex)
    }
}
```

### CancelationtokenSource naming convention

Tokens named for the scenario that cancels them. So if there is a token that only gets canceled when the bot is interrupted then the CancelationtokenSource is called the interruptionCts or botInterruptionCts.
If we have a task that is running and needs to get canceled anytime the callers speech gets transcribed then we will call the cts callerSpokeCts. And the token will be the callerSpokeToken.

⸻

## Error Handling

### Controller Action Methods – wrap every method in try/catch:

```csharp

[MFAAuthorize] // Use for any Controller requiring authentication
public async Task<IActionResult> GetSomething()
{
    try
    {
        // implementation
    }
    catch (CustomException ex)
    {
        return new BadRequestObjectResult(ex.Message);
    }
    catch (Exception ex)
    {
        _appMonitor.LogAndEmailException(ex);
        return StatusCode(500);
    }
}
```

### Service Methods

If a service-level exception should prevent continuation, and display an error to the frontend then throw new CustomException(). Controllers catch CustomException and return BadRequestObjectResult.

### Logging (IAppMonitor)

We use a custom IAppMonitor for logging + email notifications.
`_appMonitor.LogAndEmailException(ex, “message”)` – Always in default catch blocks and used anytime an unexpected exception occurs that should be investigated.

`_appMonitor.TryLogAndEmailWarningAsync()` - For scenarios that should be investigated but do not cause the code to fail or cause an outage.

`_appMonitor.LogWarning()` – For non-error scenarios that should be logged but do not need action taken.

`_appMonitor.LogMessage()` - For expected flow (e.g., function started, completed successfully).

`_appMonitor.LogDebug()` – For verbose debugging info (e.g., method entry/exit, variable values).

⸻

## Security & Auth

- `AspenAI.Portal.Api` Controllers requiring auth should use `[MFAAuthorize]`.
- `AspenAI.Bot.Api` uses two patterns:
  - an Api-key header for action methods with `[Authorize(AuthenticationSchemes = ApplicationConstants.AuthSchemeBasicAuth)]`
  - action methods for twilio should have `[ValidateTwilioRequest]`.
- Never log sensitive info (PII, secrets).

---

# Frontend Conventions
We have a separate `AGENTS.md` file in the `AspenAI.Portal.Frontend` project that defines the architecture and conventions for the frontend. Below is a summary of the key points.

- The project is a single-page application built with **React, TypeScript, Vite, ShadCN, and Tailwind CSS**.
- New features and pages follow a **standardized folder structure** containing components, types, and client logic.
- All backend communication is handled through a **defined API client pattern**. This pattern uses Axios, a custom `useBaseHttpClient` hook, and a `defineEndpoint` helper function to create strongly-typed endpoint definitions.
- **File naming conventions** are strictly enforced: `camelCase.ts` for standard TypeScript files and `PascalCase.tsx` for React components.
- Local development and API mocking are controlled via environment variables in the `.env.local-development` file, specifically the `VITE_MOCKAXIOS` flag.
---

# Testing Conventions

## Test Base Classes

### DatabaseTestsBase – For DB or Azure Table Storage tests.

- Seeds database with initial data.

- Exposes ExecuteInATransactionAsync and ExecuteInAzureTableStorageTransactionAsync.

### ControllerTestBase – For controller tests.

### DefaultTestSetup – For tests not mutating DB/Storage (assume mocks).

### BaseTest (in Test.Base) holds shared logic:

- Logging + print utilities

- GetAppMonitorInstance()

- GetHttpClientFactory()

- CreateFeatureFlagService()

⸻

## Test Utilities

### TestHelpers provides:

- GetMockedApiSettings()

- GetConfiguration()

- GetContext() (returns ApplicationDbContext)

- GetScope()

- GetAppMonitorInstance()

⸻

## Naming Conventions

- Pattern: `Test_{MethodBeingTested}{InitialCondition}{ExpectedOutcome}`

- Example: Test_GetScript_ScriptDoesNotExist_ShouldReturnNotFound

⸻

## Repo Tests Requirement

- Anytime you add a Repo method, you must add corresponding tests in the AspenAI.Dal.Tests project, inside the RepoTests folder.

- Repo tests should validate all query logic and conditions.

- All repo tests should be wrapped in a ExecuteInATransactionAsync to not affect the database state

  - Example – ActivityLogRepoTests

    ```csharp
    public class ActivityLogRepoTests : DatabaseTestsBase
    {
    private readonly IActivityLogRepo _activityLogRepo;

        public ActivityLogRepoTests(ITestOutputHelper outputHelper) : base(outputHelper)
        {
            var realRepo = new ActivityLogRepo(ApplicationDbContext, GetAppMonitorInstance<ActivityLogRepo>().Object);
            _activityLogRepo = ProfilingProxy<IActivityLogRepo>.Create(realRepo);
        }

        [Fact]
        public async Task Test_GetNotificationActivityLogs_ShouldOnlyReturnNotificationActivityLogAsync()
        {
            await ExecuteInATransactionAsync(RunTheTestAsync);

            async Task RunTheTestAsync()
            {
               // test implementation
            }
        }
    }
    ```
### Notes
 - We wrap repository instances in a ProfilingProxy during testing to log the execution time of each database call, helping us identify performance issues.

⸻

## Service Tests

Unit tests in service tests should mock all dependencies. Integration tests in service tests can use the DatabaseTestsBase to seed the database and test the service logic with a real database. External dependencies like HttpClients should be mocked in both unit and integration tests.

Follow the existing patterns established in the service tests projects and other projects when adding new tests.

IMPORTANT: When adding new functionality ensure existing tests pass. Add new unit and integration tests are adding to address new scenarios. Try to avoid modifying existing tests unless absolutely necessary. Always provide a good reason in the PR description if existing tests are modified.

---

# Azure Functions Conventions
We have a separate `AGENTS.md` file in the `AspenAI.Functions` project that defines the architecture and conventions for Azure Functions. Below is a summary of the key points.

- The project follows a strict architectural pattern where every function **must** be implemented with two entry points: a `TimerTrigger` for scheduled execution and an `HttpTrigger` for manual, on-demand execution unless an orchestrator function. i.e. Durable Functions.
- The operation of each function is controlled by specific settings in the environment-specific `AppSettings.{Environment}.json` files, which allow the timed and HTTP triggers to be enabled or disabled independently.

---
