
from appointment_store import (
    initialize_database,
    create_appointment_request,
)

initialize_database()

request_id = create_appointment_request(
    customer_name="Demo Customer",
    contact="demo@example.com",
    preferred_date="2026-11-15",
    preferred_time="10:30 AM",
    reason="Routine dental check-up",
)

print("Test request saved successfully!")
print(f"Request ID: {request_id}")
print("Status: pending (awaiting clinic confirmation)")
