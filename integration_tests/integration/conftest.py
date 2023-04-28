import pytest
import subprocess


@pytest.fixture(autouse=True, scope="session")
def validate_environment(pytestconfig):
    command = f'docker compose --ansi=never --env-file "test.env" --project-name "internetnl-test" exec worker ping --count=1 --timeout=1 1.1.1.1'
    try:
        subprocess.check_output(command, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError:
        # we expect you to die mister bond
        pass
    else:
        pytest.fail("Precondition failed: test environment not properly isolated, worker can connect to internet.")

    command = f'docker compose --ansi=never --env-file "test.env" --project-name "internetnl-test" exec worker dig example.com +tries=1 +time=3'
    try:
        subprocess.check_output(command, shell=True, universal_newlines=True)
    except subprocess.CalledProcessError:
        # we expect you to die mister bond
        pass
    else:
        pytest.fail("Precondition failed: test environment not properly isolated, worker can resolve external DNS records.")
