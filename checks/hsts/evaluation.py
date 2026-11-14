from dataclasses import dataclass, field, InitVar
from celery.exceptions import SoftTimeLimitExceeded
from collections.abc import Iterable

from checks import scoring
from checks.hsts.parser import parse_hsts_header, HSTSParseError
from checks.tasks.mail import dmarc_find_organizational_domain, dmarc_get_public_suffix_list
from checks.tasks.shared import TranslatableTechTableItem

HSTS_MIN_MAX_AGE = 31536000  # 1 year in seconds


# this should move to shared code
def get_apex(domain: str) -> bool:
    public_suffix_list = dmarc_get_public_suffix_list()
    if not public_suffix_list:
        # We don't have the public suffix list.
        # Raise SoftTimeLimitExceeded to easily fail the test.
        raise SoftTimeLimitExceeded

    return dmarc_find_organizational_domain(domain, public_suffix_list)


@dataclass
class HSTSEvaluation:
    """
    The evaluation of a set of HSTS headers.
    """

    errors: list[TranslatableTechTableItem] = field(default_factory=list)
    recommendations: list[TranslatableTechTableItem] = field(default_factory=list)
    directives: dict[str, int | bool | str] = field(default_factory=dict)
    max_age: int | None = None
    hsts_enabled: bool = field(init=False, default=False)
    domain: InitVar[str | None] = None
    hsts_policies: list[str] = field(default_factory=list)

    def __post_init__(self, domain: str | None):
        if len(self.hsts_policies) > 1:
            self.recommendations.append(TranslatableTechTableItem("multiple-headers", {}))

        # RFC 6797 Section 8.1: UAs process the first valid HSTS header field
        for header in self.hsts_policies:
            try:
                parsed_directives, parser_recs = parse_hsts_header(header)
            except HSTSParseError as hpe:
                self.errors.append(hpe.to_translatable_tech_table_item())
                continue

            # Clear errors from any preceding invalid headers once a valid header is found
            self.errors.clear()
            self.directives = parsed_directives
            self.max_age = int(parsed_directives["max-age"])
            self.hsts_enabled = True
            self.recommendations.extend(rec.to_translatable_tech_table_item() for rec in parser_recs)

            if self.max_age < HSTS_MIN_MAX_AGE:
                self.recommendations.append(
                    TranslatableTechTableItem(
                        "invalid-max-age-too-short",
                        {"max_age": self.max_age, "min_max_age": HSTS_MIN_MAX_AGE},
                    )
                )

            if self.directives.get("preload") is True:
                if not self.directives.get("includesubdomains"):
                    self.recommendations.append(
                        TranslatableTechTableItem("ineffective-preload-no-includesubdomains", {})
                    )
                if domain:
                    normalized = domain.strip().rstrip(".").lower()
                    apex = get_apex(normalized)
                    if normalized != apex:
                        self.recommendations.append(
                            TranslatableTechTableItem(
                                "ineffective-preload-no-apex",
                                {"domain": normalized, "apex": apex},
                            )
                        )
            break

    @property
    def score(self) -> int:
        if self.hsts_enabled and not self.errors:
            if self.max_age >= HSTS_MIN_MAX_AGE:
                return scoring.WEB_TLS_HSTS_GOOD
            return scoring.WEB_TLS_HSTS_PARTIAL
        return scoring.WEB_TLS_HSTS_BAD
