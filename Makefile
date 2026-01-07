.PHONY: build test run clean help

IMAGE_NAME := kiro-register
CONTAINER_NAME := kiro-register

help:
	@echo "Kiro Auto Register - Docker Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build    - Build Docker image"
	@echo "  test     - Test Docker environment"
	@echo "  run      - Run registration process"
	@echo "  shell    - Open interactive shell in container"
	@echo "  clean    - Remove Docker image and containers"
	@echo "  logs     - Show container logs"
	@echo ""

build:
	@echo "Building Docker image..."
	docker-compose build

test:
	@echo "Testing Docker environment..."
	docker run --rm $(IMAGE_NAME):latest python test_docker.py

run:
	@if [ ! -f config.json ]; then \
		echo "Error: config.json not found!"; \
		echo "Copy config.example.json to config.json and fill in your settings."; \
		exit 1; \
	fi
	@echo "Running registration process..."
	docker-compose up

shell:
	@echo "Opening interactive shell..."
	docker run --rm -it \
		-v $(PWD)/config.json:/app/config.json:ro \
		$(IMAGE_NAME):latest \
		/bin/bash

clean:
	@echo "Cleaning up..."
	docker-compose down -v
	docker rmi $(IMAGE_NAME):latest 2>/dev/null || true

logs:
	docker-compose logs -f
