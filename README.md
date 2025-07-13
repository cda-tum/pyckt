# pyckt: Python Analog Circuit Synthesis Tool (ACST)

This library provides tools for analog circuit topology generation, structural recognition, and partitioning, inspired by the C++ ACST project.

## Structure
- `pyckt/topology/`: Topology generation
- `pyckt/recognition/`: Structural recognition
- `pyckt/partitioning/`: Partitioning
- `pyckt/utils.py`: Utilities
- `tests/`: Unit tests

## Installation
```bash
pip install .
```

## Testing
```bash
python -m unittest discover tests
```

## Author
Your Name

## Acknowledgements
This project is inspired by the original implementation:
- acst - Analog Circuit Synthesis Tool: https://github.com/inga000/acst/
- Abel, Inga, and Helmut Graeb. "FUBOCO: Structure synthesis of basic op-amps by FUnctional BlOck COmposition." ACM Transactions on Design Automation of Electronic Systems (TODAES) 27.6 (2022): 1-27.
