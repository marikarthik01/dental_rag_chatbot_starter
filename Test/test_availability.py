
from datetime import date, timedelta

from appointment_store import (
    initialize_database,
    get_available_slots,
    book_appointment,
)

initialize_database()

# Use tomorrow so the test does not depend on today's remaining hours.
tomorrow = (date.today() + timedelta(days=1)).isoformat()

slots = get_available_slots(tomorrow)

print("Test date:", tomorrow)
print("Available slots:", slots)

if slots:
    print("First available slot:", slots[0])
else:
    print("No slots available on this date.")
