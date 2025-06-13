# Working with Byte Size Parameters in CockroachDB

CockroachDB has many parameters that use byte size units (KiB, MiB, GiB, etc.). The `cockroachdb_parameter` Ansible module provides built-in support for handling these units consistently, ensuring idempotent operations even when CockroachDB formats them differently.

## Supported Formats

The module supports various byte size formats:

- Basic units: `KiB`, `MiB`, `GiB`, `TiB`
- Units with spaces: `64 MiB`, `1 GiB`
- Units with decimal points: `1.0 GiB`, `2.5 MiB`

## Common Byte Size Parameters

Some commonly used byte size parameters in CockroachDB include:

- `kv.snapshot_rebalance.max_rate`: Maximum rate for range rebalancing operations
- `kv.snapshot_recovery.max_rate`: Maximum rate for recovery operations
- `kv.bulk_io_write.max_rate`: Maximum rate for bulk IO write operations
- `sql.distsql.temp_storage.workmem`: Memory allocation for temporary storage during distributed SQL operations

## Handling Different Formats

CockroachDB sometimes formats byte size values differently than how they're input. For example:

- Setting `sql.distsql.temp_storage.workmem` to `1GiB` may result in CockroachDB reporting it as `1.0 GiB`
- Setting `kv.snapshot_rebalance.max_rate` to `64MiB` may result in CockroachDB reporting it as `64 MiB`

The `cockroachdb_parameter` module normalizes these variations to ensure idempotent operations. This means that if you set a parameter to `1GiB` and CockroachDB formats it as `1.0 GiB`, the module will recognize that they are equivalent and won't try to change the value again.

## Examples

```yaml
# Set byte size parameters
- name: Configure memory-related parameters
  cockroachdb_parameter:
    parameters:
      kv.snapshot_rebalance.max_rate: "64MiB"
      sql.distsql.temp_storage.workmem: "1GiB"
    host: localhost
    port: 26257
    user: root
```

## Troubleshooting

If you experience issues with byte size parameter idempotency, you can enable debug output by setting the `ANSIBLE_DEBUG` environment variable, which will show normalized values and comparison results.
