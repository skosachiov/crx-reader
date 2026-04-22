# crx_reader.py

Extract Chrome extension ID, name, version, and XML update manifest from CRX3 files. Standalone Python script with optional `--id`, `--version`, `--name`, `--xml`, `--json` flags for pipeline use. Uses protobuf parsing for accurate header extraction.

## Requirements

- Python 3.6+
