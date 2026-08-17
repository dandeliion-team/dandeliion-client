# SPDX-License-Identifier: BSD-3-Clause

import nox

nox.options.sessions = ["tests", "lint", "typecheck", "build"]


@nox.session(python=["3.10", "3.11", "3.12", "3.13"])
def tests(session):
    """Run the core suite without optional PyBaMM."""
    session.install("-e", ".[dev]")
    session.run(
        "pytest",
        "--ignore=tests/python/dandeliion/client/pybamm_test.py",
        "--cov=dandeliion.client",
        "--cov-branch",
        "--cov-report=term-missing",
    )


@nox.session(python=["3.10", "3.11", "3.12", "3.13"])
def pybamm(session):
    """Validate the optional PyBaMM integration."""
    session.install("-e", ".[dev,pybamm]")
    session.run("pytest", "tests/python/dandeliion/client/pybamm_test.py")


@nox.session
def lint(session):
    """Run formatting and lint checks."""
    session.install("ruff")
    session.run("ruff", "format", "--check", ".")
    session.run("ruff", "check", ".")
    session.run(
        "ruff",
        "check",
        "--select",
        "D",
        "src/python/dandeliion/client",
        "scripts/production_smoke.py",
    )


@nox.session
def typecheck(session):
    """Type-check the public package."""
    session.install("-e", ".[dev]")
    session.run("mypy", "src/python/dandeliion/client")


@nox.session
def build(session):
    """Build and validate wheel and source distributions."""
    session.install("build", "twine")
    session.run("python", "-m", "build")
    session.run("twine", "check", "dist/*")


@nox.session
def docs(session):
    """Build documentation with warnings treated as errors."""
    session.install("-e", ".[docs]")
    session.run("sphinx-build", "-W", "--keep-going", "docs", "docs/_build/html")


@nox.session
def audit(session):
    """Audit the base runtime dependency graph."""
    session.run("python", "-m", "pip", "install", "--upgrade", "pip")
    session.install("-e", ".")
    session.install("pip-audit")
    session.run("pip-audit", "--skip-editable")
