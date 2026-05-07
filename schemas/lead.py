from pydantic import BaseModel
from typing import Optional


class LeadWebhookPayload(BaseModel):
    """
    Shape of data arriving from the Facebook/Instagram lead ad form webhook.
    Field names match the form field names in your ad.
    """
    first_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    state: Optional[str] = None
    company_name: Optional[str] = None
    # "agent" | "broker" | "imf" | "posp_advisor" etc.
    types_of_business: Optional[str] = None
    # "yes" | "no"
    are_you_open_to_adopting_a_new_technology_platform: Optional[str] = None
    do_you_currently_use_any_software: Optional[str] = None
    would_you_be_willing_to_evaluate_a_new_tech_solution: Optional[str] = None
    # "fb" | "ig"
    platform: Optional[str] = None


class LeadResponse(BaseModel):
    id: int
    first_name: Optional[str]
    email: Optional[str]
    lead_quality: str
    lead_score: int
    status: str

    class Config:
        from_attributes = True
