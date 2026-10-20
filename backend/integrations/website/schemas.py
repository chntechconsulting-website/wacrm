from pydantic import BaseModel, Field
from typing import Optional

class WebsiteLeadRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=150, example="Arun Kumar")
    firstName: Optional[str] = Field(None, max_length=100)
    lastName: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)

    phone: Optional[str] = Field(None, max_length=50, example="9876543210")
    countryCode: Optional[str] = Field(None, max_length=10)
    country_code: Optional[str] = Field(None, max_length=10)
    whatsapp: Optional[str] = Field(None, max_length=50)
    whatsapp_number: Optional[str] = Field(None, max_length=50)
    whatsappNumber: Optional[str] = Field(None, max_length=50)

    email: Optional[str] = Field(None, max_length=100, example="arun@gmail.com")
    company: Optional[str] = Field(None, max_length=150, example="ABC")
    message: Optional[str] = Field(None, example="Interested in your service")

    designation: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, max_length=100)
    jobTitle: Optional[str] = Field(None, max_length=100)
    job_title: Optional[str] = Field(None, max_length=100)
    functionalArea: Optional[str] = Field(None, max_length=100)
    functional_area: Optional[str] = Field(None, max_length=100)

    companySize: Optional[str] = Field(None, max_length=50)
    company_size: Optional[str] = Field(None, max_length=50)
    teamSize: Optional[str] = Field(None, max_length=50)
    team_size: Optional[str] = Field(None, max_length=50)

    industry: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    location: Optional[str] = Field(None, max_length=150)

    # Multi-Website Attribution Fields
    website_id: Optional[str] = Field(None, max_length=50, example="wapluscrm")
    website_name: Optional[str] = Field(None, max_length=100, example="WA Plus CRM")
    landing_page: Optional[str] = Field(None, max_length=255, example="http://www.wapluscrm.in/solutions/demo")
    campaign: Optional[str] = Field(None, max_length=100, example="Solutions Demo")

    source: Optional[str] = Field(None, description="Ignored by backend - source is forced to WEBSITE")

class WebsiteLeadResponse(BaseModel):
    success: bool = True
    message: str = "Website lead created successfully"
    lead_id: Optional[int] = None
