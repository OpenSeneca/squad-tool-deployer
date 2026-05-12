from setuptools import setup

setup(
    name="squad-tool-deployer",
    version="1.0.0",
    description="Squad Tool Deployer - Manage and deploy tools across all squad agents",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="OpenSeneca",
    url="https://github.com/OpenSeneca/squad-tool-deployer",
    py_modules=["main"],
    install_requires=[
        # No external dependencies - uses only Python stdlib
    ],
    entry_points={
        "console_scripts": [
            "squad-tool-deployer=main:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
    ],
    keywords="squad deployment tools openseneca agents",
)
