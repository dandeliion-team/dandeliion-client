import nox


@nox.session
def tests(session):
    session.install('pytest', '.')
    session.run('pytest')
    # Here we queue up the test coverage session to run next
    session.notify("coverage")

@nox.session
def lint(session):
    session.install('flake8')
    session.run('flake8',
                '--max-line-length', '120',
                'src/python')

@nox.session
def coverage(session):
    session.install("coverage")
    session.run("coverage")
#   session.run("coverage", "report")
