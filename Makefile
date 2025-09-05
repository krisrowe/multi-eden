# Multi-Eden SDK Makefile

.PHONY: install test test-unit test-ai clean help

# Default target
help:
	@echo "Multi-Eden SDK Commands:"
	@echo "  make install   - Set up virtual environment and install package"
	@echo "  make test      - Run all tests"
	@echo "  make test-unit - Run unit tests"
	@echo "  make test-ai   - Run AI tests"
	@echo "  make clean     - Clean virtual environment"

# Set up virtual environment and install package
install:
	@chmod +x setup-venv.sh
	@./setup-venv.sh
	@echo "✅ Setup complete! Run 'pytest' to run tests"

# Run all tests
test: install
	@. venv/bin/activate && pytest

# Run unit tests
test-unit: install
	@. venv/bin/activate && pytest tests/unit/

# Run AI tests  
test-ai: install
	@. venv/bin/activate && pytest tests/ai/

# Clean virtual environment
clean:
	@rm -rf venv/
	@echo "✅ Virtual environment cleaned"
