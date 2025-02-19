import nox


@nox.session
def tests(session):
    session.install('pytest', '.')
    session.run('pytest')

@nox.session
def lint(session):
    session.install('flake8')
    session.run('flake8',
                '--max-line-length', '120',
                'src/python')
