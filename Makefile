.PHONY: install test dev api proto clean lint agent telegram

install:
	pip install -e ".[dev]"
	pip install -e ".[agent]"
	npm install

dev:
	uvicorn api.main:app --reload --port 8000

da:
	docker-compose up -d

da-stop:
	docker-compose down

test:
	pytest tests/ -q

test-v:
	pytest tests/ -v

proto:
	bash scripts/generate_proto.sh

demo:
	python examples/legal_assistant.py

demo-live:
	export $$(grep -v "^\#" .env | grep -v "^$$" | xargs) && \
	python examples/legal_assistant.py --live

deploy:
	npx hardhat run contracts/scripts/deploy.js --network 0g-testnet

telegram:
	python scripts/run_telegram.py

agent:
	@echo "Agent module ready. Import from 'agent' package."
	@echo "  from agent import AgentLoop, ToolRegistry"

lint:
	ruff check ogmem/ api/ tests/ agent/ protocol.py

format:
	ruff format ogmem/ api/ tests/ agent/ protocol.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache dist *.egg-info
	rm -f .ogmem_index_*.json audit_report.json
