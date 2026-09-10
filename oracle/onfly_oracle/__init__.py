# -*- coding: utf-8 -*-
"""ONFLY reference oracle (SRS section 8.2, oracle O-1).

Plain Python only: no NumPy, no sum(), explicit left-to-right loops.  Since
Python 3.12 sum() uses compensated summation, which would make the oracle
disagree with a straightforward left-to-right accumulation in C.
"""
