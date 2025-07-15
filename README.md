# GTFS-Dense (.gtfsd)

[![License: MIT](https.img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Spec Version](https://img.shields.io/badge/spec-v1.0.0-blue.svg)](spec/SPECIFICATION.md)

**GTFS-Dense** is a fast, binary serialization format for static public transit data (GTFS).

The goal of GTFS-Dense is to enable quick, offline loading of an entire GTFS network on an memory-constrained devices like mobile phones and web browsers- so it doesn't need to parse large files.

GTFS-Dense uses **Protocol Buffers (PBF)** as its underlying encoding format. A converter tool reads a standard GTFS feed, resolves all relational links (e.g., connecting a trip to its stop times and shape), and writes the data into a nested, graph-like structure.
