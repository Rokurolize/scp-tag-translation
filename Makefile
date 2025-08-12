.PHONY: all test lint format check clean run

# Default target
all: check

# Run the main CLI
run:
	python cli.py

# Run tests
test:
	PYTHONPATH=. uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Run linter
lint:
	uv run ruff check src/ tests/ cli.py cli_improved.py --fix

# Format code
format:
	uv run ruff format src/ tests/ cli.py cli_improved.py

# Run all checks
check: format lint test

# Clean up generated files
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage .pytest_cache
	rm -f mapping_audit.csv mapping_audit_v2.csv

# Generate dictionary
generate:
	PYTHONPATH=. python -c "from src.generator import generate_dictionary; generate_dictionary()"

# Validate dictionary
validate:
	PYTHONPATH=. python -c "import json; from src.validator import validate_business_rules; \
		with open('dictionaries/en_to_jp.json') as f: d = json.load(f); \
		c, w = validate_business_rules(d); \
		print(f'Critical: {len(c)}, Warnings: {len(w)}')"

# Help
help:
	@echo "Available targets:"
	@echo "  make run      - Run the main CLI"
	@echo "  make test     - Run tests with coverage"
	@echo "  make lint     - Check code style"
	@echo "  make format   - Format code"
	@echo "  make check    - Run all checks (format, lint, test)"
	@echo "  make clean    - Clean generated files"
	@echo "  make generate - Generate dictionary only"
	@echo "  make validate - Validate dictionary only"