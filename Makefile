# ============================================================================
# NYC Crime Pipeline — Makefile
# ============================================================================

.PHONY: build pipeline reference transform dashboard dashboard-bg test logs stop clean all

build:
	docker-compose build

pipeline: build
	docker-compose run --rm pipeline

reference: build
	docker-compose run --rm pipeline python -m src.pipeline --skip-complaints

transform: build
	docker-compose run --rm pipeline python -m src.pipeline --skip-extract

dashboard: build
	docker-compose up dashboard

dashboard-bg: build
	docker-compose up dashboard -d
	@echo "Dashboard running at http://localhost:8501"

test: build
	docker-compose run --rm test

logs:
	docker-compose logs -f dashboard

stop:
	docker-compose down

clean:
	docker-compose down -v --rmi local

all: build pipeline dashboard
