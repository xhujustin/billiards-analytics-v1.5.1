.PHONY: help install install-dev test lint format clean docs examples

help:
	@echo "AI Coach - Development Tasks"
	@echo ""
	@echo "Available targets:"
	@echo "  install         Install package in production mode"
	@echo "  install-dev     Install package with dev dependencies"
	@echo "  install-train   Install package with training dependencies"
	@echo "  test            Run unit tests"
	@echo "  test-cov        Run tests with coverage report"
	@echo "  lint            Run code linting (flake8, mypy)"
	@echo "  format          Format code with black"
	@echo "  clean           Remove build artifacts and cache"
	@echo "  docs            Build documentation"
	@echo "  examples        Run example scripts"
	@echo ""

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

install-train:
	pip install -e ".[training]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=ai_coach --cov-report=html
	@echo "Coverage report generated: htmlcov/index.html"

lint:
	flake8 ai_coach/
	mypy ai_coach/
	@echo "✅ Linting completed"

format:
	black ai_coach/ tests/ examples/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ *.egg-info
	rm -rf .mypy_cache/ .pytest_cache/ htmlcov/
	@echo "✅ Cleaned up"

docs:
	@echo "Documentation is in docs/ directory"

examples:
	@echo "Running examples..."
	python examples/example_basic.py
	python examples/example_realtime.py
