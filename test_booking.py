
from datetime import date, timedelta

from appointment_store import (
    initialize_database,
    get_available_slots,
    book_appointment,
)

initialize_database()

# Find the next date with an available slot.
selected_date = date.today() + timedelta(days=1)

while True:
    date_text = selected_date.isoformat()
    slots = get_available_slots(date_text)

    if slots:
        break

    selected_date += timedelta(days=1)

selected_time = slots[0]

print("Testing date:", date_text)
print("Testing time:", selected_time)

appointment_id = book_appointment(
    customer_name="Demo Customer",
    contact="demo@example.com",
    appointment_date=date_text,
    appointment_time=selected_time,
    reason="Routine check-up",
)

print("Booking saved successfully!")
print("Appointment ID:", appointment_id)

# Verify that the same slot is no longer available.
remaining_slots = get_available_slots(date_text)

print("Slot still available:", selected_time in remaining_slots)
