"""
Coded tool for the Meeting Prep Briefing agent network.

Looks up a mock internal account record for a given company and returns
ONLY a safe, bucketed summary to the calling LLM agent. The full record
(raw deal value, CSM notes, the primary contact's direct phone number)
is written to `sly_data` -- neuro-san's protected channel that coded
tools can read and write, but that is never inserted into an LLM
prompt and never leaves the agent network unless explicitly allowed
in the .hocon "allow" block.

In a production build, `_MOCK_ACCOUNTS` would be replaced by a real
CRM/ERP lookup (e.g. Salesforce, Dynamics). The mock data here exists
only to demonstrate the sly_data pattern for the hackathon demo.
"""

from logging import Logger
from logging import getLogger
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool


# Mock CRM records, keyed by lower-cased company name.
# raw_deal_value and primary_contact_phone are examples of data that
# should never be echoed back into an LLM prompt.
_MOCK_ACCOUNTS: Dict[str, Dict[str, Any]] = {
    "acme corp": {
        "raw_deal_value": 87400,
        "relationship_health": "Stable",
        "primary_contact_phone": "+1-555-0142",
        "csm_notes": "Renewed last quarter; sensitive to pricing changes.",
    },
    "globex industries": {
        "raw_deal_value": 212000,
        "relationship_health": "At risk",
        "primary_contact_phone": "+1-555-0198",
        "csm_notes": "Escalation last month over delivery timelines.",
    },
    "zoho": {
        "raw_deal_value": 340000,
        "relationship_health": "Strong",
        "primary_contact_phone": "+91-44-5555-0199",
        "csm_notes": "Long-standing partner; renewal cycle begins next quarter.",
    },
}


def _bucket_deal_value(raw_value: float) -> str:
    """
    Converts a raw dollar figure into a coarse band, so the exact
    figure never needs to be shared with an LLM agent.

    :param raw_value: the raw deal value in dollars.
    :return: a human-readable band label.
    """
    if raw_value < 50_000:
        return "Entry-tier (< $50K)"
    if raw_value < 150_000:
        return "Mid-tier ($50K-$150K)"
    return "Strategic-tier (> $150K)"


class AccountContextTool(CodedTool):
    """
    Looks up internal account context for a company and returns a
    safe, bucketed summary. Raw sensitive fields are written to
    sly_data for other coded tools to use, but are never included
    in the value returned to the calling LLM agent.
    """

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        :param args: A dictionary with the key:
                "company_name": the company to look up.

        :param sly_data: The protected, LLM-invisible data channel.
                This tool writes the raw account record here so other
                coded tools could use it, but nothing here is returned
                to the calling agent's prompt.

        :return: A dictionary containing only safe, bucketed fields:
                 "deal_value_band", "relationship_health".
                 If no record is found, returns an "Unknown" result.
        """
        tool_name = self.__class__.__name__
        logger: Logger = getLogger(self.__class__.__name__)

        company_name = str(args.get("company_name", "")).strip()
        logger.debug("========== Calling %s for '%s' ==========", tool_name, company_name)

        record = _MOCK_ACCOUNTS.get(company_name.lower())

        if record is None:
            tool_response = {
                "deal_value_band": "Unknown",
                "relationship_health": "No internal record found",
            }
            logger.debug("%s response: %s", tool_name, tool_response)
            return tool_response

        # Store the FULL record in sly_data -- visible to coded tools only,
        # never inserted into an LLM prompt, and never sent back to the
        # client unless explicitly allowed in the .hocon "allow" block.
        sly_data["account_record"] = record

        deal_value_band = _bucket_deal_value(record["raw_deal_value"])
        # Also stash the bucketed (safe) value under its own sly_data key,
        # since the front-man's "allow.to_upstream" only exposes this key.
        sly_data["deal_value_band"] = deal_value_band

        tool_response = {
            "deal_value_band": deal_value_band,
            "relationship_health": record["relationship_health"],
        }

        logger.debug("%s response (safe fields only): %s", tool_name, tool_response)
        logger.debug("========== Done with %s ==========", tool_name)
        return tool_response