"""
Coded tool for the Meeting Prep Briefing agent network.

This is the enforcement layer behind source citation. Researcher agents
are INSTRUCTED (in their prompts) to attach a source URL to every claim,
but an instruction is not a guarantee -- an LLM can still cite a URL
that was never actually in its search results. This tool closes that
gap in code: it checks each claim's cited URL against the real list of
URLs the agent actually got back from `ddgs_search`, and mechanically
discards any claim whose URL doesn't match. Only claims that pass this
check are meant to be used in the final briefing.

This is a membership/grounding check on the URL, not a full semantic
fact-check of the claim text against the page content -- it verifies
"this URL was really in your search results", not "this URL really
says what you claim it says". That stronger check would require
fetching and reading the full page (see notes in the project write-up).
"""

from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import List
from typing import Union
from urllib.parse import urlparse

from neuro_san.interfaces.coded_tool import CodedTool


def _normalize_url(url: str) -> str:
    """
    Normalizes a URL for comparison: lower-cases the host, strips a
    trailing slash, and ignores query strings / fragments, so minor
    LLM reformatting (e.g. dropping "https://" or a trailing "/")
    doesn't cause a false rejection.

    :param url: the URL string to normalize.
    :return: a normalized string suitable for equality comparison.
    """
    if not url:
        return ""
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    parsed = urlparse(candidate)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return f"{netloc}{path}"


class CitationFilter(CodedTool):
    """
    Verifies that each claim's cited source URL genuinely appears in
    the set of URLs the calling agent's search actually returned.
    Claims whose URL cannot be verified are discarded, not passed
    through -- so an unverifiable claim never reaches the final
    briefing, no matter how confidently the LLM stated it.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: A dictionary with the keys:
                "claims": a list of {"claim": str, "source_url": str} objects.
                "known_urls": a list of URL strings -- the "href" values
                    the agent actually received back from its ddgs_search
                    calls for this research task.

        :param sly_data: Not used by this tool.

        :return: A dictionary with:
                 "validated_claims": the claims whose source_url matched
                     one of "known_urls" (list of {"claim", "source_url"}).
                 "discarded_count": how many claims were rejected.
                 "discarded_reasons": a short list of why each rejected
                     claim was dropped, for transparency/debugging --
                     the discarded claim TEXT is intentionally omitted
                     here so an unverifiable claim can't sneak back into
                     the conversation through this side channel.
        """
        tool_name = self.__class__.__name__
        logger: Logger = getLogger(self.__class__.__name__)

        claims: List[Dict[str, str]] = args.get("claims") or []
        known_urls: List[str] = args.get("known_urls") or []
        known_normalized = {_normalize_url(u) for u in known_urls if u}

        logger.debug(
            "========== Calling %s: %d claim(s) against %d known URL(s) ==========",
            tool_name,
            len(claims),
            len(known_normalized),
        )

        validated_claims: List[Dict[str, str]] = []
        discarded_reasons: List[str] = []

        for claim in claims:
            claim_text = str(claim.get("claim", "")).strip()
            source_url = str(claim.get("source_url", "")).strip()

            if not claim_text:
                discarded_reasons.append("Empty claim text.")
                continue
            if not source_url:
                discarded_reasons.append("Claim had no source_url attached.")
                continue
            if _normalize_url(source_url) not in known_normalized:
                discarded_reasons.append(
                    f"Cited URL not found among this task's actual search results: {source_url}"
                )
                continue

            validated_claims.append({"claim": claim_text, "source_url": source_url})

        tool_response = {
            "validated_claims": validated_claims,
            "discarded_count": len(discarded_reasons),
            "discarded_reasons": discarded_reasons,
        }

        logger.debug(
            "%s result: %d validated, %d discarded",
            tool_name,
            len(validated_claims),
            len(discarded_reasons),
        )
        logger.debug("========== Done with %s ==========", tool_name)
        return tool_response