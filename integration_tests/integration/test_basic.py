"""Basis functionality that should always be present."""
from datetime import timedelta
import pytest
import re
from playwright.sync_api import Page, expect
from pytest_playwright import pytest_playwright

TEST_DOMAIN = "test-target.internet.nl"
ALL_PROBES = {"ipv6", "dnssec", "tls", "appsecpriv", "rpki"}
TEST_DOMAIN_EXPECTED_SCORE = 100
TEST_DOMAIN_EXPECTED_SCORE = 48

TEST_EMAIL = "test-target.internet.nl"
ALL_EMAIL_PROBES = {"ipv6", "dnssec", "tls", "auth", "rpki"}
TEST_EMAIL_EXPECTED_SCORE = 100
TEST_EMAIL_EXPECTED_SCORE = 0

ALL_CONNECTION_PROBES = {"ipv6", "resolver"}
TEST_CONNECTION_EXPECTED_SCORE = 0.0

FOOTER_TEXT = "Internet.nl is an initiative of the Internet community and the Dutch"

DEFAULT_TIMEOUT = timedelta(seconds=120)

@pytest.fixture
def context(context):
    context.set_default_timeout(timedelta(seconds=120).microseconds)
    yield context

def test_index_http_ok(page):
    assert page.goto("http://internet.nl/")


def test_index_footer_text_present(page):
    page.goto("http://internet.nl/")
    footer = page.locator("#footer")

    expect(footer).to_have_text(re.compile(FOOTER_TEXT))

def test_reject_invalid_domain(page):
    domain = "invalid-domain.example.com"

    page.goto("http://internet.nl/")

    page.locator('#web-url').fill(domain)
    page.locator('section.websitetest button').click()

    assert page.url == "http://internet.nl/test-site/?invalid"


@pytest.fixture(scope="module")
def site_test(browser, test_domain=TEST_DOMAIN):
    """Runs the 'Test your website' test against the test target."""
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://internet.nl/")

    page.locator('#web-url').fill(test_domain)
    page.locator('section.websitetest button').click()

    assert page.url == f"http://internet.nl/site/{test_domain}/"

    page.wait_for_url(f"http://internet.nl/site/{test_domain}/*/", timeout=DEFAULT_TIMEOUT.microseconds)

    yield page

def test_your_website_score(site_test):
    """Validate score from site_test."""

    score = site_test.locator('div.testresults-percentage')
    expect(score).to_have_attribute('data-resultscore', str(TEST_DOMAIN_EXPECTED_SCORE))

@pytest.mark.xfail()
@pytest.mark.parametrize("probe", ALL_PROBES)
def test_your_website_probe_success(site_test, probe, test_domain=TEST_DOMAIN):

    probe_result = site_test.locator(f'#site{probe}-results')
    expect(probe_result).to_have_class('passed')

@pytest.fixture(scope="module")
def email_test(browser, test_email=TEST_EMAIL):
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://internet.nl/")

    page.locator('#mail-url').fill(test_email)
    page.locator('section.emailtest button').click()

    assert page.url == f"http://internet.nl/mail/{test_email}/"

    page.wait_for_url(f"http://internet.nl/mail/{test_email}/*/", timeout=DEFAULT_TIMEOUT.microseconds)

    yield page

def test_your_email_score(email_test, test_email=TEST_EMAIL):
    """Runs the 'Test your email' and expects a decent result."""

    score = email_test.locator('div.testresults-percentage')
    expect(score).to_have_attribute('data-resultscore', str(TEST_EMAIL_EXPECTED_SCORE))

@pytest.mark.xfail()
@pytest.mark.parametrize("probe", ALL_EMAIL_PROBES)
def test_your_email_probe_success(email_test, probe, test_email=TEST_EMAIL):

    probe_result = email_test.locator(f'#mail{probe}-results')
    expect(probe_result).to_have_class('passed')

@pytest.fixture(scope="module")
def connection_test(browser):
    context = browser.new_context()
    page = context.new_page()

    page.goto("http://internet.nl/")

    page.locator('section.connectiontest button').click()

    assert page.url == f"http://internet.nl/connection/"

    page.wait_for_url(f"http://internet.nl/connection/*/results", timeout=DEFAULT_TIMEOUT.microseconds)

    yield page

def test_your_connection_score(connection_test):
    """Runs the 'Test your email' and expects a decent result."""

    score = connection_test.locator('div.testresults-percentage')
    expect(score).to_have_attribute('data-resultscore', str(TEST_CONNECTION_EXPECTED_SCORE))

@pytest.mark.xfail()
@pytest.mark.parametrize("probe", ALL_CONNECTION_PROBES)
def test_your_connection_probe_success(connection_test, probe):

    probe_result = connection_test.locator(f'#conn{probe}-results')
    expect(probe_result).to_have_class('passed')
