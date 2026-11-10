
import os
import re
from datetime import date, datetime, timedelta

import chromadb
import gradio as gr
from dotenv import load_dotenv
from google import genai

from appointment_store import (
    initialize_database,
    get_available_slots,
    book_appointment,
    cancel_appointment,
)


# ============================================================
# 1. CONFIGURATION
# ============================================================

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_PATH = os.path.join(BASE_DIR, "chroma_db")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite",
)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

TOP_K = 4

SYSTEM_RULES = """
You are a friendly, professional dental clinic assistant.

Rules:
1. Answer clinic questions using only the supplied clinic context.
2. Never invent clinic prices, hours, services, policies, or contact details.
3. If the answer is not available in the context, say so clearly and
   recommend contacting the clinic.
4. Do not diagnose medical conditions or prescribe medication.
5. For severe dental pain, facial swelling, uncontrolled bleeding,
   or difficulty breathing or swallowing, advise urgent professional care.
6. Keep answers concise, clear, and welcoming.
7. Appointment booking and cancellation are handled by the application's
   workflow, not by guessing information from the knowledge base.
"""

# Initialize the local appointment database.
initialize_database()

# Initialize ChromaDB.
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

collection = chroma_client.get_collection(
    name="dental_clinic_knowledge"
)

# Initialize Gemini.
llm = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None


# ============================================================
# 2. RAG: RETRIEVE KNOWLEDGE FROM CHROMADB
# ============================================================

def retrieve_context(question):
    """Retrieve relevant clinic documents from ChromaDB."""

    results = collection.query(
        query_texts=[question],
        n_results=TOP_K,
    )

    documents = results.get("documents", [[]])

    if not documents or not documents[0]:
        return ""

    return "\n\n".join(documents[0])


def generate_rag_answer(question):
    """Generate an answer grounded in retrieved clinic information."""

    if llm is None:
        return (
            "The AI model is not configured. Please check that "
            "GOOGLE_API_KEY is set in your .env file."
        )

    try:
        context = retrieve_context(question)

        if not context.strip():
            context = "No relevant clinic information was retrieved."

        prompt = f"""
{SYSTEM_RULES}

CLINIC KNOWLEDGE:
{context}

CUSTOMER QUESTION:
{question}

Write a helpful answer based on the clinic knowledge above.
If the requested information is missing, explain that it is unavailable.
"""

        response = llm.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.35,
                "max_output_tokens": 300,
            },
        )

        answer = response.text

        if not answer:
            return (
                "I'm sorry, I couldn't generate a response just now. "
                "Please try again."
            )

        return answer.strip()

    except Exception as error:
        print(f"RAG/Gemini error: {error}")

        return (
            "I'm sorry, I'm having trouble answering right now. "
            "Please try again in a moment."
        )


# ============================================================
# 3. INTENT DETECTION
# ============================================================


def is_booking_request(message):
    """Recognize common appointment-booking requests, including misspellings."""
    text = message.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    # Common spelling mistakes users may type.
    text = text.replace("appoinment", "appointment")
    text = text.replace("apointment", "appointment")
    text = text.replace("appointement", "appointment")
    text = text.replace("appointmnt", "appointment")

    # Do not interpret cancellation requests as new bookings.
    cancellation_words = (
        "cancel", "cancellation", "cancelation",
        "delete appointment", "remove appointment"
    )
    if any(word in text for word in cancellation_words):
        return False

    booking_patterns = [
        r"\bbook\b",
        r"\bbooking\b",
        r"\bschedule\b",
        r"\bscheduling\b",
        r"\bmake an appointment\b",
        r"\bneed an appointment\b",
        r"\bwant an appointment\b",
        r"\bi need to see a dentist\b",
        r"\bappointment please\b",
    ]

    return any(re.search(pattern, text) for pattern in booking_patterns)



def is_cancellation_request(message):
    """Recognize cancellation requests, including common misspellings."""

    text = message.lower().strip()

    cancellation_words = [
        "cancel",
        "cancellation",
        "cancle",
        "cancelling",
    ]

    appointment_words = [
        "appointment",
        "appoinment",
        "appointement",
        "booking",
        "booked",
    ]

    return (
        any(word in text for word in cancellation_words)
        and any(word in text for word in appointment_words)
    )


# ============================================================
# 4. DATE AND TIME HELPERS
# ============================================================

def format_date(date_text):
    """Convert YYYY-MM-DD into a readable date."""

    return datetime.strptime(
        date_text, "%Y-%m-%d"
    ).strftime("%d %b %Y")


def format_time(time_text):
    """Convert supported time formats into a readable format."""

    text = str(time_text).strip().upper()

    for time_format in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            parsed = datetime.strptime(text, time_format)
            return parsed.strftime("%I:%M %p").lstrip("0")
        except ValueError:
            continue

    return str(time_text)


def normalize_time(time_text):
    """Normalize a time so different user formats can be compared."""

    text = str(time_text).strip().upper().replace(".", ":")

    for time_format in ("%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text, time_format).strftime("%H:%M")
        except ValueError:
            continue

    return text


def parse_preferred_date(message):
    """Accept today, tomorrow, or an ISO date."""

    text = message.strip().lower()

    if text == "today":
        return date.today()

    if text == "tomorrow":
        return date.today() + timedelta(days=1)

    try:
        selected_date = date.fromisoformat(text)

        # Require the exact YYYY-MM-DD format.
        if selected_date.isoformat() == text:
            return selected_date

    except ValueError:
        pass

    return None


def find_next_available_date(start_date, max_days=60):
    """Find the next date with available appointment slots."""

    for day_offset in range(1, max_days + 1):
        candidate = start_date + timedelta(days=day_offset)

        slots = get_available_slots(candidate.isoformat())

        if slots:
            return candidate, slots

    return None, []


def show_slots(date_text, slots, prefix=""):
    """Format available appointment slots for the customer."""

    lines = [
        f"{index}. {format_time(slot)}"
        for index, slot in enumerate(slots, start=1)
    ]

    message = (
        f"{prefix}"
        f"Available appointment slots for {format_date(date_text)}:\n\n"
        + "\n".join(lines)
        + "\n\nPlease enter the slot number or a time, "
          "such as 9:00 AM."
    )

    return message


def choose_slot(message, slots):
    """Match the user's selection to an available slot."""

    text = message.strip()

    # The customer may select a slot using its list number.
    if text.isdigit():
        number = int(text)

        if 1 <= number <= len(slots):
            return slots[number - 1]

    # Or the customer may type a time.
    requested_time = normalize_time(text)

    for slot in slots:
        if normalize_time(slot) == requested_time:
            return slot

    return None


# ============================================================
# 5. APPOINTMENT BOOKING WORKFLOW
# ============================================================

def handle_booking(message, state):
    """Collect booking details and save only after confirmation."""

    text = message.strip()
    lower_text = text.lower()

    if lower_text in {"stop", "stop booking", "cancel", "exit"}:
        return (
            "Booking process stopped. No appointment was booked.",
            None,
        )

    # Start a new booking.
    if state is None:
        state = {
            "workflow": "booking",
            "step": "date",
        }

        return (
            "I'd be happy to help you book a 30-minute appointment.\n\n"
            "Which date would you prefer? You can enter today, "
            "tomorrow, or a date in YYYY-MM-DD format.",
            state,
        )

    step = state["step"]

    # Step 1: Collect the date.
    if step == "date":
        selected_date = parse_preferred_date(text)

        if selected_date is None:
            return (
                "Please enter today, tomorrow, or a valid date "
                "in YYYY-MM-DD format.",
                state,
            )

        if selected_date < date.today():
            return (
                "That date is in the past. Please choose today, "
                "tomorrow, or another future date.",
                state,
            )

        slots = get_available_slots(selected_date.isoformat())

        if not slots:
            next_date, next_slots = find_next_available_date(
                selected_date
            )

            if not next_date:
                return (
                    "Sorry, I couldn't find an available slot "
                    "within the next 60 days. Please contact the clinic.",
                    None,
                )

            state["date"] = next_date.isoformat()
            state["slots"] = next_slots
            state["step"] = "slot"

            return show_slots(
                state["date"],
                next_slots,
                prefix=(
                    f"No slots are available for "
                    f"{format_date(selected_date.isoformat())}.\n"
                    f"The next available date is "
                    f"{format_date(state['date'])}.\n\n"
                ),
            ), state

        state["date"] = selected_date.isoformat()
        state["slots"] = slots
        state["step"] = "slot"

        return show_slots(state["date"], slots), state

    # Step 2: Collect the slot.
    if step == "slot":
        # Refresh availability in case another booking was made.
        current_slots = get_available_slots(state["date"])
        state["slots"] = current_slots

        if not current_slots:
            next_date, next_slots = find_next_available_date(
                date.fromisoformat(state["date"])
            )

            if not next_date:
                return (
                    "No appointment slots are currently available. "
                    "Please try again later.",
                    None,
                )

            state["date"] = next_date.isoformat()
            state["slots"] = next_slots

            return show_slots(
                state["date"],
                next_slots,
                prefix="Those slots are no longer available.\n\n",
            ), state

        selected_slot = choose_slot(text, current_slots)

        if selected_slot is None:
            return (
                "That selection isn't valid. Please enter one of "
                "the listed slot numbers or an available time.",
                state,
            )

        state["time"] = selected_slot
        state["step"] = "name"

        return "May I have your full name, please?", state

    # Step 3: Collect the customer's name.
    if step == "name":
        if len(text) < 2:
            return "Please enter your name.", state

        state["customer_name"] = text
        state["step"] = "contact"

        return (
            "Thank you! Please enter your phone number or email address.",
            state,
        )

    # Step 4: Collect contact information.
    if step == "contact":
        if len(text) < 5:
            return (
                "Please enter a valid phone number or email address.",
                state,
            )

        state["contact"] = text
        state["step"] = "reason"

        return (
            "What is the reason for your visit? For example, "
            "a dental check-up or teeth cleaning.\n\n"
            "You can also type 'skip'.",
            state,
        )

    # Step 5: Collect the reason for the visit.
    if step == "reason":
        state["reason"] = "" if lower_text == "skip" else text
        state["step"] = "confirm"

        return (
            "Please review your appointment request:\n\n"
            f"Name: {state['customer_name']}\n"
            f"Date: {format_date(state['date'])}\n"
            f"Time: {format_time(state['time'])}\n"
            f"Contact: {state['contact']}\n"
            f"Reason: {state['reason'] or 'Not specified'}\n\n"
            "Would you like to confirm this booking? "
            "Reply yes or no.",
            state,
        )

    
    # Step 6: Confirm and save the appointment.
    if step == "confirm":
        if lower_text in {"no", "n"}:
            return (
                "Booking cancelled. No appointment was created.",
                None,
            )

        if lower_text not in {"yes", "y", "confirm"}:
            return (
                "Please reply yes to confirm or no to cancel "
                "this booking.",
                state,
            )

        try:
            # Check that the selected slot is still available.
            latest_slots = get_available_slots(state["date"])

            matching_slot = next(
                (
                    slot for slot in latest_slots
                    if normalize_time(slot)
                    == normalize_time(state["time"])
                ),
                None,
            )

            if matching_slot is None:
                next_date, next_slots = find_next_available_date(
                    date.fromisoformat(state["date"])
                )

                if not next_date:
                    return (
                        "That slot is no longer available, and "
                        "I couldn't find another slot. Please try later.",
                        None,
                    )

                state["date"] = next_date.isoformat()
                state["slots"] = next_slots
                state["step"] = "slot"

                return show_slots(
                    state["date"],
                    next_slots,
                    prefix=(
                        "Sorry, that slot is no longer available. "
                        "Please choose another slot.\n\n"
                    ),
                ), state

            # book_appointment returns one integer: the appointment ID.
            appointment_id = book_appointment(
                customer_name=state["customer_name"],
                contact=state["contact"],
                appointment_date=state["date"],
                appointment_time=matching_slot,
                reason=state.get("reason", ""),
            )

            return (
                "Your appointment has been booked successfully! 🎉\n\n"
                f"Appointment ID: {appointment_id}\n"
                f"Date: {format_date(state['date'])}\n"
                f"Time: {format_time(matching_slot)}\n\n"
                "Please keep your appointment ID for future reference."
            ), None

        except ValueError as error:
            print(f"Booking validation error: {error}")

            latest_slots = get_available_slots(state["date"])

            if latest_slots:
                state["slots"] = latest_slots
                state["step"] = "slot"

                return show_slots(
                    state["date"],
                    latest_slots,
                    prefix=(
                        f"Booking could not be completed: {error}\n\n"
                        "Please choose an available slot:\n\n"
                    ),
                ), state

            return (
                f"Booking could not be completed: {error}\n\n"
                "Please start a new booking to find another available date.",
                None,
            )

        except Exception as error:
            print(f"Booking error: {type(error).__name__}: {error}")

            return (
                "Sorry, I couldn't save your appointment right now. "
                "Please try again or contact the clinic.",
                state,
            )


# ============================================================
# 6. APPOINTMENT CANCELLATION WORKFLOW
# ============================================================

def handle_cancellation(message, state):
    """Verify the appointment ID and contact before cancellation."""

    text = message.strip()
    lower_text = text.lower()

    if lower_text in {
        "stop",
        "stop cancellation",
        "exit cancellation",
    }:
        return (
            "Cancellation process stopped. Your appointment is unchanged.",
            None,
        )

    # Start cancellation.
    if state is None:
        state = {
            "workflow": "cancellation",
            "step": "appointment_id",
        }

        return (
            "I can help cancel your appointment.\n\n"
            "Please enter your appointment ID.",
            state,
        )

    step = state["step"]

    # Step 1: Collect appointment ID.
    if step == "appointment_id":
        if not text.isdigit():
            return (
                "Please enter a valid numeric appointment ID. "
                "You can find it in your booking confirmation.",
                state,
            )

        state["appointment_id"] = int(text)
        state["step"] = "contact"

        return (
            "Please enter the phone number or email address "
            "you used when booking.",
            state,
        )

    # Step 2: Collect the original contact information.
    if step == "contact":
        if len(text) < 5:
            return (
                "That contact information looks too short. "
                "Please enter the phone number or email address "
                "you used when booking.",
                state,
            )

        state["contact"] = text
        state["step"] = "confirm"

        return (
            f"Please confirm: do you want to cancel appointment "
            f"{state['appointment_id']}? Reply yes or no.",
            state,
        )

    # Step 3: Confirm cancellation.
    if step == "confirm":
        if lower_text in {"no", "n"}:
            return (
                "Cancellation aborted. Your appointment is unchanged.",
                None,
            )

        if lower_text not in {"yes", "y", "confirm"}:
            return (
                "Please reply yes to confirm or no to keep "
                "your appointment.",
                state,
            )

        try:
            success, result = cancel_appointment(
                state["appointment_id"],
                state["contact"],
            )

            if success:
                return (
                    f"{result}\n\n"
                    "Is there anything else I can help you with?",
                    None,
                )

            # Keep the workflow active when the details do not match.
            state["step"] = "contact"
            state.pop("contact", None)

            return (
                f"{result}\n\n"
                "Please enter the phone number or email address "
                "you used when booking, and I'll try again.",
                state,
            )

        except Exception as error:
            print(f"Cancellation error: {error}")

            state["step"] = "contact"
            state.pop("contact", None)

            return (
                "Sorry, I couldn't complete the cancellation. "
                "Please enter the phone number or email address "
                "you used when booking so we can try again.",
                state,
            )

    return (
        "The cancellation session has an unexpected state. "
        "Please start again by asking to cancel an appointment.",
        None,
    )


def main_menu_message():
    return (
        "🏥 **Welcome to the Dental Clinic Assistant!**\n\n"
        "How can I help you today?\n\n"
        "🦷 **1. Book an appointment** — type `book appointment`\n"
        "❌ **2. Cancel an appointment** — type `cancel appointment`\n"
        "ℹ️ **3. Clinic information** — ask me a question\n\n"
        "🔄 To begin again at any time, type `START`."
    )


# ============================================================
# 7. MAIN CHATBOT RESPONSE
# ============================================================

def respond(message, history, appointment_state):
    if not message or not message.strip():
        return "Please type your question.", appointment_state

    message = message.strip()

    

    # Restart the conversation from scratch.
    # Restart the conversation and display the main menu.
    if is_restart_request(message):
       return main_menu_message(), None

    # Continue an active cancellation workflow first.
    if (
        appointment_state is not None
        and appointment_state.get("workflow") == "cancellation"
    ):
        answer, new_state = handle_cancellation(
            message,
            appointment_state,
        )
        return answer, new_state

    # Continue an active booking workflow.
    if (
        appointment_state is not None
        and appointment_state.get("workflow") == "booking"
    ):
        answer, new_state = handle_booking(
            message,
            appointment_state,
        )
        return answer, new_state

    # Start cancellation before RAG.
    if is_cancellation_request(message):
        answer, new_state = handle_cancellation(message, None)
        return answer, new_state

    # Start booking before RAG.
    if is_booking_request(message):
        answer, new_state = handle_booking(message, None)
        return answer, new_state

    # Normal clinic questions use RAG.
    answer = generate_rag_answer(message)

    return answer, appointment_state


def is_restart_request(message):
    """Recognize common restart commands."""
    text = message.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)

    restart_phrases = {
    "start",
    "start over",
    "startover",
    "start again",
    "restart",
    "reset",
    "start from scratch",
    "start from the beginning",
    "begin again",
    "restart conversation",
    "reset conversation",
    "main menu",
    "menu",
}

    return text in restart_phrases

# ============================================================
# 8. GRADIO CHAT INTERFACE
# ============================================================

appointment_state = gr.State(value=None)

demo = gr.ChatInterface(
    fn=respond,
    additional_inputs=[appointment_state],
    additional_outputs=[appointment_state],
    title="Dental Clinic Assistant",
    description=(
        "Ask questions about the clinic, book a 30-minute appointment, "
        "or cancel an existing appointment. Appointment requests are "
        "managed using the local demo database."
    ),
    examples=[
        ["What are the clinic opening hours?", None],
        ["What is the consultation fee?", None],
        ["Do you offer teeth cleaning?", None],
        ["I want to book an appointment", None],
        ["How do I cancel my appointment?", None],
    ],
    save_history=False,
)


if __name__ == "__main__":
    demo.launch()
