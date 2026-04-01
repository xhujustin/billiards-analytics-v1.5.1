#!/usr/bin/env python
"""
Setup script for AI Coach package.
"""

from setuptools import setup, find_packages

setup(
    name="ai-coach",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.5.0",
        "pillow>=8.3.0",
        "requests>=2.26.0",
        "numpy>=1.19.0",
    ],
    extras_require={
        "training": [
            "torch>=2.0.0",
            "datasets>=2.14.0",
            "transformers>=4.36.0",
            "peft>=0.7.0",
            "trl>=0.7.0",
            "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "black>=22.0",
            "flake8>=4.0",
        ],
    },
    author="Billiards Analytics Team",
    author_email="team@example.com",
    description="AI Coach System for Billiards Analytics",
    long_description=open("README.md").read() if __name__ != "__main__" else "",
    long_description_content_type="text/markdown",
    url="https://github.com/xhujustin/billiards-analytics-v1.5.1",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
