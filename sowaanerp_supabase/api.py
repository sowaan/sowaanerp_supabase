import requests
import frappe

from supabase import create_client, Client
from datetime import datetime
from frappe.desk.form.assign_to import add as add_assignment




# https://api.supabase.com/platform/auth/iigqdtaityrwtrilkbbg/users
# authorization Bearer token
def get_settings():
    try:
        return frappe.get_single("Supabase Settings")
    except Exception as e:
        frappe.throw(f"Failed to retrieve Supabase Settings: {str(e)}")


def get_headers():
    settings = get_settings()
    if not settings.supabase_service_api_key:
        raise frappe.ValidationError("Supabase API Key is not set in Caller Settings.")
    actual_api_key = settings.get_password("supabase_service_api_key")

    return {
        "Authorization": f"Bearer {actual_api_key}",
        "apikey": actual_api_key,
        "Content-Type": "application/json"
    }


def create_user(email):
    settings = get_settings()
    url = f"{settings.supabase_url}/auth/v1/admin/users"
    headers = get_headers()
    data = {
        "email": email,
        "password": "SowaanERP1234",  # Default password
        "email_confirm": True
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Network error while creating user: {str(e)}")

    try:
        return response.json()
    except ValueError:
        frappe.throw(f"Invalid JSON response from Supabase when creating user: {response.text}")


def create_user_profile(user_id, full_name, company_name=None):
    settings = get_settings()
    headers = get_headers()
    data = {
        "id": user_id,
        "full_name": full_name,
        "created_at": frappe.utils.now(),
        "company_id": company_name,
    }
    print(f"Creating user profile with data: {data}")
    url = f"{settings.supabase_url}/rest/v1/Profiles"
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Network error while creating user profile: {str(e)}")

def create_company(company_name):
    """
    Create a company in Supabase.
    
    :param company_name: Name of the company to create
    :return: Response from Supabase API
    """
    settings = get_settings()
    headers = get_headers()
    data = {
        "id": company_name,
        "created_at": frappe.utils.now(),
    }

    url = f"{settings.supabase_url}/rest/v1/Companies"
    

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        frappe.throw(f"Network error while creating company: {str(e)}")


def get_user_email(user_id):
    settings = get_settings()
    SUPABASE_URL = settings.supabase_url
    headers = get_headers()

    url = f"{SUPABASE_URL}/auth/v1/admin/users/{user_id}"

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("email")
    return ""


@frappe.whitelist()
def create_user_and_profile(email, full_name):
    """
    Create a user and their profile in Supabase.
    
    :param email: User's email address
    :param full_name: User's full name
    :return: Response from Supabase API
    """
    user_response = create_user(email)
    user_id = user_response.get("id")

    if not user_id:
        frappe.throw(f"User creation failed: 'id' not found in response: {user_response}")

    # company_name is host url, which is not provided in the function parameters
    company_name = frappe.get_site_config().host_name if frappe.get_site_config().host_name else None
    # Create user profile
    if company_name:
        create_company(company_name)

    try:
        create_user_profile(user_id, full_name, company_name)
    except Exception as e:
        frappe.throw(f"Failed to create user profile: {str(e)}")
    
    return "User and profile created successfully."



# supabase client
@frappe.whitelist()
def sync_calls_to_leads():
    # 1. Get settings from Caller Settings doctype
    settings = get_settings()
    SUPABASE_URL = settings.supabase_url
    SUPABASE_KEY = settings.supabase_api_key

    site_config = frappe.get_site_config()
    company_name = None
    # Check if 'domains' key exists and has at least one value
    if "domains" in site_config and site_config["domains"]:
        company_name = site_config["domains"][0]
        


    print(f"Using company name: {company_name}")
    # 2. Connect to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # 3. Fetch call records
    contacts_response = supabase.table("Contacts").select("*").eq("company_id", company_name).execute()
    contacts = contacts_response.data

    lead_doc = {
        "notes": [],
    }
    for contact in contacts:
        contact_id = contact.get("id", None)
        phone = contact.get("phone")
        name = contact.get("name", str(phone))
        assign_uid = contact.get("assign")
        print(f"Processing contact: {contact_id} with phone: {phone}")

        assign_email = get_user_email(assign_uid) if assign_uid else None   
        
        lead = frappe.db.exists("Lead", {"phone": phone})
        if lead:
            call_notes_response = supabase.table("Calls").select("*").eq("contact_id", contact_id).eq("company_id", company_name).execute()
            call_notes = call_notes_response.data

            if assign_email:
                try:
                    add_assignment({
                        "assign_to": [assign_email],
                        "doctype": "Lead",
                        "name": lead,
                        "description": f"Lead assigned from contact {contact_id}"
                    })
                except Exception as e:
                    frappe.log_error(f"Failed to assign Lead {lead} to {assign_email}: {str(e)}")
            if call_notes:
                lead_doc = frappe.get_doc("Lead", lead)
                lead_doc.notes = []
                for note in call_notes:
                    added_by_email = get_user_email(note.get("created_by"))
                    created_at = None
                    iso_string = note.get("created_at")
                    if iso_string:
                        try:
                            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00")).replace(tzinfo=None)
                            created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass  # skip bad formats
                    lead_doc.append("notes", {
                        "note": note.get("notes"),
                        "added_by": added_by_email,
                        "added_on": created_at,
                    })
                lead_doc.save()
                frappe.db.commit()
        else:
            lead_doc = frappe.new_doc("Lead")
            lead_doc.first_name = name if name else str(phone)
            lead_doc.phone = phone
            call_notes_response = supabase.table("Calls").select("*").eq("contact_id", contact_id).execute()
            call_notes = call_notes_response.data

            for field in settings.lead_fields:
                erp_field = field.erp_field
                supabase_field = field.supabase_field
                default_value = field.default

                # Determine the value to set on lead_doc
                if not supabase_field:
                    value = default_value
                else:
                    value = contact.get(supabase_field)

                # Only set if erp_field is valid and value is not None
                if erp_field and value is not None:
                    lead_doc.set(erp_field, value)

            lead_doc.save()

            if assign_email:
                try:
                    add_assignment({
                        "assign_to": [assign_email],
                        "doctype": "Lead",
                        "name": lead_doc.name,
                        "description": f"Lead assigned from contact {contact_id}"
                    })
                except Exception as e:
                    frappe.log_error(f"Failed to assign Lead {lead_doc.name} to {assign_email}: {str(e)}")
            
            if call_notes:
                for note in call_notes:
                    added_by_email = get_user_email(note.get("created_by"))
                    created_at = None
                    iso_string = note.get("created_at")
                    if iso_string:
                        try:
                            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00")).replace(tzinfo=None)
                            created_at = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass  # skip bad formats
                    lead_doc.append("notes", {
                        "note": note.get("notes"),
                        "added_by": added_by_email,
                        "added_on": created_at,
                    })
            
            lead_doc.save()
            frappe.db.commit()

    return lead_doc
                

