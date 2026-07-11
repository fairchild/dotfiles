## References

`canonical-agent-schema.duckdb.sql` is the canonical normalized storage schema for
cross-harness agent data.

Conventions:

- every table has an `id` primary key
- foreign keys are named `{table}_id`
- provider-native identifiers use `external_*`
- every table includes `created_at` and `updated_at`

The analyzer loads this schema idempotently during database bootstrap so new
and upgraded databases have the canonical tables available before harness-
specific tables and views are populated.
