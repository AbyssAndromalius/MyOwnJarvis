.PHONY: build test run clean install help

# Variables
BINARY_NAME=assistant
BUILD_DIR=build
CMD_DIR=./cmd/assistant

# Default target
.DEFAULT_GOAL := help

## help: Display this help message
help:
	@echo "Available targets:"
	@echo "  build      - Build the application"
	@echo "  test       - Run all tests"
	@echo "  run        - Run the application"
	@echo "  clean      - Remove build artifacts"
	@echo "  install    - Install dependencies"
	@echo "  coverage   - Run tests with coverage"
	@echo "  lint       - Run linter (requires golangci-lint)"

## install: Download dependencies
install:
	go mod download
	go mod verify

## build: Build the application
build:
	@echo "Building $(BINARY_NAME)..."
	@mkdir -p $(BUILD_DIR)
	go build -o $(BUILD_DIR)/$(BINARY_NAME) $(CMD_DIR)
	@echo "Build complete: $(BUILD_DIR)/$(BINARY_NAME)"

## test: Run all tests
test:
	@echo "Running tests..."
	go test -v ./...

## coverage: Run tests with coverage
coverage:
	@echo "Running tests with coverage..."
	go test -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report: coverage.html"

## run: Run the application
run:
	@echo "Starting $(BINARY_NAME)..."
	go run $(CMD_DIR)

## clean: Remove build artifacts
clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR)
	@rm -f coverage.out coverage.html
	@echo "Clean complete"

## lint: Run golangci-lint
lint:
	golangci-lint run ./...

## fmt: Format code
fmt:
	go fmt ./...

## vet: Run go vet
vet:
	go vet ./...

## check: Run fmt, vet and test
check: fmt vet test
	@echo "All checks passed!"
