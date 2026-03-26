# ✅ Setup & Getting Started Checklist

## 🎯 Installation (5 minutes)

- [ ] **Read QUICKSTART.md** (2 min)
  - Explains 3 visualization options
  - Shows what to expect

- [ ] **Install Python dependencies**
  ```bash
  pip install -r requirements.txt
  ```
  - [ ] Command completed without errors
  - [ ] All packages installed (websockets, plotly, pyqtgraph, PyQt5, numpy, scikit-learn)

- [ ] **Verify Python files**
  ```bash
  python -m py_compile *.py
  ```
  - [ ] No syntax errors

---

## 🚀 First Run (2 minutes)

### Option A: Recommended (PyQtGraph)
- [ ] Start: `python btc_hft_pyqtgraph.py`
- [ ] Verify:
  - [ ] GUI window opens
  - [ ] Chart visible with green line
  - [ ] Current price shown in large display
  - [ ] Real-time updates visible

### Option B: Interactive Menu
- [ ] Start: `python main.py`
- [ ] Verify:
  - [ ] Menu displays 5 options
  - [ ] Can navigate with number keys
  - [ ] Select option 1 (PyQtGraph)

### Option C: Web Server
- [ ] Start: `python btc_hft_standalone.py`
- [ ] Verify:
  - [ ] Browser opens automatically
  - [ ] Dark Plotly interface shows
  - [ ] Chart updates every 50ms

---

## 📊 Data Collection (5+ minutes)

- [ ] **Let visualizer run for 5+ minutes**
  - [ ] Accumulating data points
  - [ ] Chart shows 20+ price points
  - [ ] Price stable or moving naturally

- [ ] **Verify btc_data_log.csv created**
  ```bash
  ls -la btc_data_log.csv
  head -5 btc_data_log.csv
  ```
  - [ ] File exists
  - [ ] Has timestamp and price columns
  - [ ] Multiple rows present

---

## 🧪 Run Tests (2 minutes)

- [ ] **Execute test suite**
  ```bash
  python test_suite.py
  ```
  - [ ] 35 tests show in output
  - [ ] Most tests PASS (success count > 30)
  - [ ] No critical errors

---

## 📈 Analysis & ML (Optional, 5 minutes)

- [ ] **Analyze collected data**
  ```bash
  python btc_data_loader.py
  ```
  - [ ] Shows statistics
  - [ ] "Total points" > 5 (means data collected)
  - [ ] Price range shows variation

- [ ] **Train ML model**
  ```bash
  python btc_ml_model.py
  ```
  - [ ] Model trains successfully
  - [ ] Shows RMSE, MAE, R² metrics
  - [ ] Feature importance displayed

---

## 🎓 Exploration (10 minutes)

- [ ] **Run examples**
  ```bash
  python example.py
  ```
  - [ ] Menu shows 6 examples
  - [ ] Can select and run each
  - [ ] Outputs look reasonable

- [ ] **Run benchmark** (30 sec)
  ```bash
  python btc_benchmark.py
  ```
  - [ ] Shows latency stats
  - [ ] FPS estimate displayed
  - [ ] Creates benchmark_results.csv

---

## 📚 Documentation Review (15 minutes)

Essential:
- [ ] Read [QUICKSTART.md](QUICKSTART.md)
- [ ] Read [README.md](README.md)

Recommended:
- [ ] Skim [ARCHITECTURE.md](ARCHITECTURE.md)
- [ ] Skim [ROADMAP.md](ROADMAP.md)

Advanced:
- [ ] Review [INDEX.md](INDEX.md)
- [ ] Review code comments in btc_hft_pyqtgraph.py
- [ ] Study [ARCHITECTURE.md](ARCHITECTURE.md) technical section

---

## 🔧 Configuration (Optional)

- [ ] **Edit config.ini** (if changing parameters)
  - [ ] MAX_POINTS: keep 100 for 60 FPS
  - [ ] TARGET_FPS: set to 60
  - [ ] Understand other parameters

- [ ] **Edit requirements.txt** (if compatibility issues)
  - [ ] Only change versions if needed
  - [ ] Re-run: `pip install -r requirements.txt`

---

## 🐳 Docker Setup (Optional)

- [ ] **Build Docker image**
  ```bash
  docker build -t btc-hft .
  ```
  - [ ] Build completes without errors

- [ ] **Run Docker container**
  ```bash
  docker run -e DISPLAY btc-hft
  ```
  - [ ] Container starts successfully

---

## ✨ Advanced Usage (After basics work)

- [ ] **Review example.py** for:
  - [ ] Data analysis patterns
  - [ ] ML training workflows
  - [ ] Backtesting strategies
  - [ ] WebSocket callbacks

- [ ] **Study ROADMAP.md** for:
  - [ ] Multi-symbol support
  - [ ] Custom indicators
  - [ ] Trading bot features
  - [ ] Production deployment

- [ ] **Deep dive ARCHITECTURE.md**:
  - [ ] Understand asyncio patterns
  - [ ] Learn threading model
  - [ ] Review performance metrics
  - [ ] Study thread safety

---

## 🎯 Common Tasks

### Task: Run visualizer
```bash
python btc_hft_pyqtgraph.py
# or
python main.py
```
- [ ] Completed successfully

### Task: Collect 1 hour data
```bash
python btc_hft_pyqtgraph.py
# Let run for 60 minutes
# Then Ctrl+C to stop
```
- [ ] btc_data_log.csv has 50+ points

### Task: Analyze prices
```bash
python btc_data_loader.py
```
- [ ] Statistics displayed correctly

### Task: Train predictor
```bash
python btc_ml_model.py
```
- [ ] Model trained with R² > 0.4

### Task: Predict next price
```python
from btc_ml_model import BTCPricePredictorRF
model = BTCPricePredictorRF()
model.train()
pred = model.predict([42500, 42450, 125, 50, 65, 42550])
print(f"${pred:.2f}")
```
- [ ] Prediction returns reasonable value

---

## 🐛 Troubleshooting Checklist

If something doesn't work:

- [ ] **ImportError**: 
  - Run `pip install -r requirements.txt` again
  - Check Python version (3.9+)

- [ ] **GUI lag/freezes**:
  - Use PyQtGraph instead of Plotly
  - Reduce MAX_POINTS in config.ini

- [ ] **WebSocket disconnects**:
  - Check internet connection
  - Run `python btc_benchmark.py` for diagnostics
  - Reconnection is automatic (expected)

- [ ] **CSV file not created**:
  - Visualizer needs to run >1 second
  - Check file permissions in directory

- [ ] **ML training fails**:
  - Need >30 data points (run visualizer 5+ min first)
  - Run `python btc_data_loader.py` to verify

- [ ] **Tests fail**:
  - Check CSV exists: `python btc_data_loader.py`
  - Run individual test: `python -m unittest test_suite.TestBTCML`

---

## 📊 Validation Checklist

Final validation that everything works:

- [ ] **Syntax validation**
  ```bash
  python -m py_compile btc_*.py main.py example.py test_suite.py
  ```

- [ ] **Import validation**
  ```python
  python -c "import websockets, plotly, pyqtgraph, sklearn"
  ```

- [ ] **Data pipeline**
  ```bash
  # 1. Collect
  python btc_hft_pyqtgraph.py &
  sleep 60
  pkill -f btc_hft
  
  # 2. Verify data
  wc -l btc_data_log.csv  # Should be > 1
  
  # 3. Analyze
  python btc_data_loader.py
  
  # 4. Train
  python btc_ml_model.py
  ```

- [ ] **All features tested**:
  - [ ] Visualization: Running with updates
  - [ ] Data collection: CSV file created
  - [ ] ML: Model training works
  - [ ] Analysis: Statistics display
  - [ ] Benchmark: Latency measured

---

## 🎉 Completion!

When all checkboxes are complete:

✅ **You have successfully:**
- Installed all dependencies
- Verified core functionality
- Collected real Bitcoin data
- Trained ML model
- Reviewed documentation
- Understood architecture
- Are ready to extend/customize

**Next steps:**
- Review [ROADMAP.md](ROADMAP.md) for extensions
- Customize visualizer parameters
- Build upon ML model
- Deploy to production (careful!)

---

## 📈 Performance Validation

Check these metrics to validate good setup:

| Metric | Expected | Check |
|--------|----------|-------|
| WebSocket latency | 50-150ms | Run btc_benchmark.py |
| GUI FPS | 60+ | Watch chart smoothness |
| Memory | <10MB | System monitor |
| CPU | 5-10% | Top / Activity Monitor |
| CSV write latency | <5ms | test_suite.py |

---

**Happy hacking! 🚀📈**

When you have questions, check [INDEX.md](INDEX.md) for links to relevant docs.
