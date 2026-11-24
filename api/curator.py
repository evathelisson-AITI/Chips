"""Vercel function behind /api/curator: the password-protected curator page.
All logic lives in curator_web.py (repo root, bundled via vercel.json includeFiles)."""
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__))), os.getcwd()]

import curator_web  # noqa: E402


class handler(curator_web.Handler):
    pass
