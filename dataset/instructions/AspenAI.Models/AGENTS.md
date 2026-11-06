## Models Project Conventions

When adding a new database entity you must add the entity as DbSet in ApplicationDbContext in AspenAI.Dal.

### Enums and lookup tables

- Lookup data should have a corresponding enum in `AspenAI.Models.Enums`.
- To ensure the enum values in code are perfectly aligned with the Ids in the DB you must also add seeding data in the
  AspenAI.Dal.Initialization namespace in SeedingData.cs. For example:

```csharp
  public static List<ConversationBlockType> ConversationBlockTypes =>
        EnumExtensions.ToEntityList<ConversationBlockTypeEnum, ConversationBlockType>();
```

You then must add the entity to the SampleDataInitializer in AspenAI.Dal `SeedData` and `ClearData` lists. You must
ensure proper ORDERING. We can't insert data into the DB if its parent isn't already in the DB. The opposite it true
when Clearing data. Lookups typically always come first when seeding and last when clearing since they don't hold
foreign key relationships.

Example of seeding data:

```csharp
 private static void SeedData(ApplicationDbContext context, bool seedSampleData = false)
    {
        try
        {
            TryProcessInsertLookupData(context, context.ConversationBlockTypes, SeedingData.ConversationBlockTypes);
            //other seeding data 
            ProcessInsert(context, context.Orgs, SeedingData.SampleOrgs);

        }
        catch (Exception ex)
        {
            //logging
        }
    }
```