from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="btc-hft-visualizer",
    version="1.0.0",
    author="HFT Developer",
    description="Real-time Bitcoin price visualizer using Binance WebSocket",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/btc-hft-visualizer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial :: Point-Of-Sale",
        "Topic :: Scientific/Engineering :: Visualization",
    ],
    python_requires=">=3.9",
    install_requires=[
        "websockets>=12.0",
        "plotly>=5.18.0",
        "pyqtgraph>=0.13.7",
        "PyQt5>=5.15.9",
        "numpy>=1.24.3",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "black>=23.0",
            "flake8>=6.0",
        ],
        "jupyter": [
            "ipython>=8.18.1",
            "jupyter>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "btc-hft-gui=btc_hft_pyqtgraph:main",
            "btc-hft-web=btc_hft_standalone:main",
        ],
    },
)
