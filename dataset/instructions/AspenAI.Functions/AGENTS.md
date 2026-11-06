# Azure Functions Conventions

- Every Timed function must have a Timed version and an HTTP version.

- Each function has an entry in appsettings.Development.json, appsettings.Local.json, appsettings.Staging.json, and
  appsettings.Production.json.

- Camel case for all file names

- Example AppSetting

  ```json
  "RejectEmailsFunctionSettings": {
    "Enable": true,
    "EnableTimedFunction": false
  }
  ```

- Example Function Implementation

```csharp
[Function($"Timed_{nameof(ProcessRejectEmailsFunction)}")]
public async Task Timed_ProcessRejectEmailsFunction(
[TimerTrigger("0 */10 * * * *", RunOnStartup = false)] TimerInfo myTimer)
{
    try
    {
        if (!_settings.EnableTimedFunction || myTimer.IsPastDue) return;

        var result = await ProcessRejectsAsync();
        if (result.Success)
        {
            _appMonitor.LogMessage("Timed_ProcessRejectEmailsFunction ran successfully");
        }
    }
    catch (Exception ex)
    {
        _appMonitor.LogAndEmailException(ex,"Unexpected error occurred in ProcessRejectEmailsFunction");
    }
}

[Function($"Http_{nameof(ProcessRejectEmailsFunction)}")]
public async Task<IActionResult> Http_ProcessRejectEmailsFunction(
[HttpTrigger(AuthorizationLevel.Function, "post", Route = $"Http_{nameof(ProcessRejectEmailsFunction)}")]
FunctionContext executionContext)
{
    try
    {
        _appMonitor.LogMessage("ProcessRejectEmailsFunction endpoint has been hit");
        if (!_settings.Enable) return new OkObjectResult("Not Enabled");

        var result = await ProcessRejectsAsync();
        if (!result.Success) return new BadRequestObjectResult(result.Errors);

        return new OkObjectResult("Success");
    }
    catch (Exception ex)
    {
        _appMonitor.LogAndEmailException(ex,"Unexpected error occurred in ProcessRejectEmailsFunction");
        return new BadRequestObjectResult("Unexpected error occurred");
    }
}
```
