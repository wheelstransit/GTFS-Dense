PYTHON_PROTO_DIR = src/gtfsdense

.PHONY: proto

proto:
	protoc --python_out=$(PYTHON_PROTO_DIR) --proto_path=proto proto/gtfs-dense.proto
