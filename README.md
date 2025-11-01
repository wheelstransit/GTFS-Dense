# GTFS-Dense (.gtfsd)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Spec Version](https://img.shields.io/badge/spec-v1.6.0-blue.svg)](proto/gtfs-dense.proto)

**GTFS-Dense** is a fast, binary serialization format for static public transit data (GTFS).

The goal of GTFS-Dense is to enable quick, offline loading of an entire GTFS network on memory-constrained devices like mobile phones and web browsers, eliminating the need to parse large text files.

GTFS-Dense uses **Protocol Buffers (PBF)** as its underlying encoding format. A converter tool reads a standard GTFS feed, resolves all relational links (e.g., connecting a trip to its stop times and shape), and writes the data into a nested, graph-like structure.

## Structure

- `proto/` - The Protocol Buffers schema.
- `src/gtfsdense/` - The main Python package.
  - `converter.py` - The script to convert GTFS to GTFS-Dense.
  - `gtfs_dense_pb2.py` - The generated Python code from the schema.
- `gtfs-dense-rust/` - The Rust library for parsing GTFS-Dense.
- `pyproject.toml` - The Python project definition file.

## Usage

To convert a GTFS `.zip` file to a `.gtfsd` file, use the converter script:

```bash
python -m src.gtfsdense.converter --input /path/to/your/gtfs.zip --output /path/to/your/output.gtfsd
```

## Development

This project uses `setuptools` for packaging and `protoc` for generating the protobuf code.

### Python

1.  **Install dependencies:**

    ```bash
    pip install -e .
    ```

2.  **Modify the schema:**

    Edit `proto/gtfs-dense.proto`.

3.  **Regenerate the protobuf code:**

    ```bash
    protoc --python_out=src --proto_path=proto proto/gtfs-dense.proto
    ```

### Rust

1.  **Build the library:**

    ```bash
    cd gtfs-dense-rust
    cargo build
    ```

2.  **Run the example:**

    ```bash
    cargo run --example print_feed -- <path/to/your.gtfsd>
    ```
