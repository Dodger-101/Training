# Not a Scale

`not_a_scale_v2.py` monitors smart-shelf weight events received from a NATS
server. It can also retrieve the latest shelf and bay metadata from the Shekel
API and associate incoming shelf IDs with readable shelf information.

## Requirements

- Python 3.9 or newer
- Network access to the configured NATS server on TCP port `4222`
- Network access to the Shekel API when refreshing shelf metadata
- The Python `requests` package

Install the dependency with:

```bash
python3 -m pip install requests
```

## Files

- `not_a_scale_v2.py`: Main application
- `config.json`: Runtime settings and Shekel API credentials
- `shelves_config.json`: Shelf metadata retrieved from the Shekel API
- `all_messages.log`: Optional log of received NATS protocol messages

The application resolves these files relative to its own directory. It can
therefore be started from any working directory.

## Configuration

`config.json` contains the following fields:

| Field | Type | Description |
| --- | --- | --- |
| `nats_ip` | string | IP address or hostname of the NATS server |
| `dump_log` | boolean | Writes all received NATS lines to `all_messages.log` when enabled |
| `full_output` | boolean | Displays additional shelf and bay details when enabled |
| `min_weight_g` | number | Ignores weight events below this absolute value in grams |
| `shekel_email` | string | Shekel API login email |
| `shekel_password` | string | Shekel API login password |

The built-in config editor does not display or prompt for `shekel_email` and
`shekel_password`. Their existing values are preserved when other settings are
changed.

Because `config.json` contains credentials, restrict access to it and do not
commit it to a public repository. On Unix-like systems, suitable permissions
can be set with:

```bash
chmod 600 config.json
```

## Running the application

From the application directory:

```bash
python3 not_a_scale_v2.py
```

Or with an absolute path:

```bash
python3 /Volumes/gunther/nas/v3/not_a_scale_v2.py
```

At startup, the application asks:

```text
Do you want to edit the config? (y = yes, n = no) [n]:
Do you want to retrieve a new shelf config? (y = yes, n = no) [n]:
```

Pressing Enter accepts the displayed default. Both uppercase and lowercase
`y` and `n` are accepted.

Boolean values in the config editor use a separate input format:

```text
1 = true
2 = false
```

Pressing Enter keeps the current value.

## Shelf metadata refresh

If the shelf refresh prompt is answered with `y`, the application:

1. Logs in to the Shekel API using the credentials from `config.json`.
2. Retrieves all available pages of bay and shelf data.
3. Removes duplicate entries by ID.
4. Writes the combined result to `shelves_config.json`.

If the refresh fails, the monitor does not start. If no refresh is requested,
the existing `shelves_config.json` is used.

## NATS monitoring

The application connects to the configured server on port `4222`, subscribes
to all subjects using `>`, and waits for JSON weight or location events.

For each qualifying event, it can display:

- Timestamp
- Weight in grams
- Location in centimeters
- Shelf ID
- Shelf name and position
- Optional shelf ordinal, bay ID, and enabled status

The NATS connection attempt times out after 30 seconds. Once connected, the
monitor waits continuously until the connection closes or the process is
stopped with `Ctrl+C`.

## Troubleshooting

- **NATS connection fails:** Verify `nats_ip`, routing, firewall rules, and TCP
  port `4222`.
- **Shelf names are missing:** Refresh the shelf configuration and verify that
  `shelves_config.json` contains the incoming shelf ID.
- **Shekel login fails:** Verify the credentials in `config.json` and confirm
  that the API is reachable.
- **No events are displayed:** Check `min_weight_g`; events below this absolute
  threshold are ignored.
- **`requests` cannot be imported:** Install it with the command shown under
  Requirements.
