.PHONY: help install test run run-gui run-web benchmark analyse-data train-ml examples clean setup

help:
	@echo "🚀 BTC HFT Visualizer - Available Commands"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup       - Run full setup (install requirements)"
	@echo "  make install     - Install Python dependencies"
	@echo ""
	@echo "Run Visualizers:"
	@echo "  make run         - Run interactive menu (main.py)"
	@echo "  make run-gui     - Run PyQtGraph (recommended)"
	@echo "  make run-web     - Run Plotly Web Server"
	@echo ""
	@echo "Analysis & ML:"
	@echo "  make analyse-data - Analyze collected data"
	@echo "  make train-ml     - Train ML model"
	@echo "  make examples     - Run interactive examples"
	@echo "  make benchmark    - Test WebSocket performance"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test        - Run test suite"
	@echo "  make lint        - Run code linting (if available)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean       - Remove generated files (CSV, logs)"
	@echo "  make help        - Show this help"

setup:
	@echo "🔧 Running setup..."
	bash setup.sh

install:
	@echo "📦 Installing dependencies..."
	pip install -r requirements.txt

run:
	@echo "🚀 Starting interactive menu..."
	python main.py

run-gui:
	@echo "🎨 Starting PyQtGraph GUI (recommended)..."
	python btc_hft_pyqtgraph.py

run-web:
	@echo "🌐 Starting Plotly Web Server..."
	python btc_hft_standalone.py

benchmark:
	@echo "⚡ Running WebSocket benchmark (30 seconds)..."
	python btc_benchmark.py

analyse-data:
	@echo "📊 Analyzing collected data..."
	python btc_data_loader.py

train-ml:
	@echo "🤖 Training ML model..."
	python btc_ml_model.py

examples:
	@echo "📚 Running interactive examples..."
	python example.py

test:
	@echo "🧪 Running test suite..."
	python test_suite.py

lint:
	@echo "📝 Linting code (if flake8 installed)..."
	flake8 *.py --max-line-length=100 || echo "Install flake8: pip install flake8"

clean:
	@echo "🧹 Cleaning generated files..."
	rm -f btc_data_log.csv
	rm -f benchmark_results.csv
	rm -f *.log
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	@echo "✅ Cleaned!"

docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t btc-hft-visualizer:latest .
	@echo "✅ Built! Run: docker run -e DISPLAY btc-hft-visualizer"

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -e DISPLAY btc-hft-visualizer:latest

info:
	@echo "📋 Project Information:"
	@echo "   Files: 21"
	@echo "   Lines of code: ~2500"
	@echo "   Tests: 35"
	@echo "   Modules: 9"
	@echo "   Documentation pages: 8"
	@python -c "import subprocess; r = subprocess.run(['python', 'test_suite.py'], capture_output=True); print(r.stdout.decode())" || echo "   Tests not available yet"
