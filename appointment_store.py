
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from datetime import date, datetime, timedelta


DB_PATH = Path(__file__).parent / "appointments.db"


def initialize_database():
    """Create the appointment requests table if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        contact TEXT NOT NULL,
        appointment_date TEXT NOT NULL,
        appointment_time TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL DEFAULT 30,
        reason TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'confirmed',
        created_at TEXT NOT NULL,
        UNIQUE (appointment_date, appointment_time)
    )
    
""")
        # ADD THE NEW CODE DIRECTLY HERE
        connection.execute(
            """
            INSERT OR IGNORE INTO sqlite_sequence (name, seq)
            VALUES ('appointments', 999)
            """
        )

        connection.execute(
            """
            UPDATE sqlite_sequence
            SET seq = 999
            WHERE name = 'appointments'
              AND seq < 999
            """
        )



def create_appointment_request(
    customer_name,
    contact,
    preferred_date,
    preferred_time,
    reason=""
):
    """Save a request, not a confirmed appointment."""

    # Basic validation
    customer_name = customer_name.strip()
    contact = contact.strip()
    preferred_date = preferred_date.strip()
    preferred_time = preferred_time.strip()
    reason = reason.strip()

    if not customer_name or not contact:
        raise ValueError("Customer name and contact are required.")

    if not preferred_date or not preferred_time:
        raise ValueError("Preferred date and time are required.")

    # Generate a unique request reference
    request_id = "REQ-" + uuid.uuid4().hex[:8].upper()

    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            INSERT INTO appointment_requests (
                request_id,
                customer_name,
                contact,
                preferred_date,
                preferred_time,
                reason,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (
            request_id,
            customer_name,
            contact,
            preferred_date,
            preferred_time,
            reason,
            created_at
        ))

    return request_id


if __name__ == "__main__":
    initialize_database()
    print("Appointment database initialized successfully.")
    print(f"Database location: {DB_PATH}")



from datetime import date, datetime, timedelta


# DEMO SCHEDULE — adjust to match your clinic's actual hours.
# Weekday: Monday=0, Tuesday=1, ..., Sunday=6.
CLINIC_HOURS = {
    0: ("09:00", "19:00"),  # Monday
    1: ("09:00", "19:00"),
    2: ("09:00", "19:00"),
    3: ("09:00", "19:00"),
    4: ("09:00", "19:00"),
    5: ("09:00", "17:00"),  # Saturday
    6: None,                # Sunday closed
}


def get_available_slots(appointment_date):
    """Return available 30-minute slots for a YYYY-MM-DD date."""

    try:
        selected_date = date.fromisoformat(appointment_date)
    except ValueError:
        raise ValueError("Date must use YYYY-MM-DD format.")

    if selected_date < date.today():
        return []

    hours = CLINIC_HOURS.get(selected_date.weekday())

    if hours is None:
        return []

    opening = datetime.strptime(hours[0], "%H:%M")
    closing = datetime.strptime(hours[1], "%H:%M")

    slots = []
    current = opening

    while current + timedelta(minutes=30) <= closing:
        slot = current.strftime("%H:%M")

        # Do not offer slots that have already started today.
        if selected_date == date.today():
            slot_datetime = datetime.combine(
                selected_date, current.time()
            )
            if slot_datetime <= datetime.now():
                current += timedelta(minutes=30)
                continue

        slots.append(slot)
        current += timedelta(minutes=30)

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT appointment_time
            FROM appointments
            WHERE appointment_date = ?
              AND status = 'confirmed'
        """, (appointment_date,)).fetchall()

    booked_slots = {row[0] for row in rows}

    return [
        slot for slot in slots
        if slot not in booked_slots
    ]



def book_appointment(
    customer_name,
    contact,
    appointment_date,
    appointment_time,
    reason="",
):
    """Reserve one available 30-minute appointment slot."""

    customer_name = customer_name.strip()
    contact = contact.strip()
    appointment_date = appointment_date.strip()
    appointment_time = appointment_time.strip()

    if not customer_name or not contact:
        raise ValueError("Name and contact are required.")

    # Validate the requested date.
    try:
        selected_date = date.fromisoformat(appointment_date)
    except ValueError:
        raise ValueError("Date must use YYYY-MM-DD format.")

    # Validate the time format.
    try:
        selected_time = datetime.strptime(
            appointment_time, "%H:%M"
        )
    except ValueError:
        raise ValueError("Time must use HH:MM format.")

    # Check that the slot is within the configured clinic schedule.
    hours = CLINIC_HOURS.get(selected_date.weekday())

    if hours is None:
        raise ValueError("The clinic is closed on this date.")

    opening = datetime.strptime(hours[0], "%H:%M")
    closing = datetime.strptime(hours[1], "%H:%M")

    if not (
        opening <= selected_time
        and selected_time + timedelta(minutes=30) <= closing
    ):
        raise ValueError("This time is outside clinic working hours.")

    if selected_time.minute not in (0, 30):
        raise ValueError("Appointments must start every 30 minutes.")

    now = datetime.now()
    slot_datetime = datetime.combine(
        selected_date, selected_time.time()
    )

    if slot_datetime <= now:
        raise ValueError("Please choose a future appointment time.")

    # Begin the transaction before checking for an existing booking.
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as connection:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute("""
                SELECT 1
                FROM appointments
                WHERE appointment_date = ?
                  AND appointment_time = ?
                  AND status = 'confirmed'
            """, (appointment_date, appointment_time)).fetchone()

            if existing:
                raise ValueError(
                    "This slot is already booked. Please choose another."
                )

            cursor = connection.execute("""
                INSERT INTO appointments (
                    customer_name,
                    contact,
                    appointment_date,
                    appointment_time,
                    duration_minutes,
                    reason,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 30, ?, 'confirmed', ?)
            """, (
                customer_name,
                contact,
                appointment_date,
                appointment_time,
                reason.strip(),
                datetime.now().isoformat(),
            ))

            appointment_id = cursor.lastrowid

        return appointment_id

    except sqlite3.IntegrityError:
        raise ValueError(
            "This slot is already booked. Please choose another."
        )




# DEMO SCHEDULE — adjust to match your clinic's actual hours.
# Weekday: Monday=0, Tuesday=1, ..., Sunday=6.
CLINIC_HOURS = {
    0: ("09:00", "19:00"),  # Monday
    1: ("09:00", "19:00"),
    2: ("09:00", "19:00"),
    3: ("09:00", "19:00"),
    4: ("09:00", "19:00"),
    5: ("09:00", "17:00"),  # Saturday
    6: None,                # Sunday closed
}


def get_available_slots(appointment_date):
    """Return available 30-minute slots for a YYYY-MM-DD date."""

    try:
        selected_date = date.fromisoformat(appointment_date)
    except ValueError:
        raise ValueError("Date must use YYYY-MM-DD format.")

    if selected_date < date.today():
        return []

    hours = CLINIC_HOURS.get(selected_date.weekday())

    if hours is None:
        return []

    opening = datetime.strptime(hours[0], "%H:%M")
    closing = datetime.strptime(hours[1], "%H:%M")

    slots = []
    current = opening

    while current + timedelta(minutes=30) <= closing:
        slot = current.strftime("%H:%M")

        # Do not offer slots that have already started today.
        if selected_date == date.today():
            slot_datetime = datetime.combine(
                selected_date, current.time()
            )
            if slot_datetime <= datetime.now():
                current += timedelta(minutes=30)
                continue

        slots.append(slot)
        current += timedelta(minutes=30)

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute("""
            SELECT appointment_time
            FROM appointments
            WHERE appointment_date = ?
              AND status = 'confirmed'
        """, (appointment_date,)).fetchall()

    booked_slots = {row[0] for row in rows}

    return [
        slot for slot in slots
        if slot not in booked_slots
    ]


def book_appointment(
    customer_name,
    contact,
    appointment_date,
    appointment_time,
    reason="",
):
    """Reserve an available 30-minute slot."""

    customer_name = customer_name.strip()
    contact = contact.strip()
    appointment_date = appointment_date.strip()
    appointment_time = appointment_time.strip()

    if not customer_name or not contact:
        raise ValueError("Name and contact are required.")

    available_slots = get_available_slots(appointment_date)

    if appointment_time not in available_slots:
        raise ValueError(
            "This slot is unavailable. Please choose another slot."
        )

    now = datetime.now()

    try:
        with sqlite3.connect(DB_PATH) as connection:
            # Lock the database for this transaction before checking
            # and inserting, reducing the risk of double booking.
            connection.execute("BEGIN IMMEDIATE")

            # Check availability again inside the transaction.
            row = connection.execute("""
                SELECT 1
                FROM appointments
                WHERE appointment_date = ?
                  AND appointment_time = ?
                  AND status = 'confirmed'
            """, (appointment_date, appointment_time)).fetchone()

            if row:
                raise ValueError(
                    "This slot was just booked. Please choose another."
                )

            connection.execute("""
                INSERT INTO appointments (
                    customer_name,
                    contact,
                    appointment_date,
                    appointment_time,
                    duration_minutes,
                    reason,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 30, ?, 'confirmed', ?)
            """, (
                customer_name,
                contact,
                appointment_date,
                appointment_time,
                reason.strip(),
                now.isoformat(),
            ))

            appointment_id = connection.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

        return appointment_id

    except sqlite3.IntegrityError:
        raise ValueError(
            "This slot is no longer available. Please choose another."
        )



def cancel_appointment(appointment_id, contact):
    """Cancel a confirmed appointment after verifying customer contact."""
    import sqlite3

    try:
        appointment_id = int(appointment_id)
    except (TypeError, ValueError):
        return False, "Please provide a valid appointment ID."

    contact = str(contact).strip()

    if not contact:
        return False, "Please provide the contact used for booking."

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")

        appointment = conn.execute(
            """
            SELECT status
            FROM appointments
            WHERE appointment_id = ?
              AND contact = ?
            """,
            (appointment_id, contact),
        ).fetchone()

        if appointment is None:
            return False, (
                "We could not find an appointment matching "
                "that ID and contact information."
            )

        if appointment[0] != "confirmed":
            return False, (
                f"This appointment cannot be cancelled because "
                f"its status is '{appointment[0]}'."
            )

        conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE appointment_id = ?
              AND contact = ?
            """,
            (appointment_id, contact),
        )

    return True, (
        f"Appointment {appointment_id} has been cancelled successfully. "
        "The slot is available for booking again."
    )
