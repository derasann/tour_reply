from __future__ import annotations

from dataclasses import replace

from .models import BookingRequest

AGT_NET_PRICES = {
    "Hungry Samurai: Sendai Food & Culture Day Tour (with cab)": 30000,
    "Hungry Samurai: Sendai Food & Culture Tour": 30000,
    "Back-alley Night Izakaya Hopping in Sendai": 20000,
    "Back-alley Bar Hopping in Sendai": 20000,
    "Bar Hopping in Kokubuncho VEG (Sendai)": 20000,
    "Foodie Delight: Culinary Walking Tour (150 min)": 15000,
    "Shiogama's 10 Tasting Treasures": 24000,
    "Shiogama's Delicacy Trail to Matsushima's Natural Wonders": 35000,
    "Oyster Fisherman's Cruise & Seasonal Feast (JR train)": 32000,
    "Cruise with Oyster Fisherman + All-you-can-eat Oyster, Matsushima": 40000,
    "Fish & Feast with Local Fisherman! BBQ Lunch": 32000,
    "Nightlife & Tradition: Hachinohe Yokocho Izakaya Experience": 20000,
    "Back-alley Bar Hopping in Miyako (Iwate)": 20000,
    "Bar Hopping in Tsuruoka (Yamagata)": 20000,
    "Dake Onsen Bar Hopping Tour (Fukushima)": 20000,
    'Izakaya and Japanese "Snack Bar" Tour in Kakunodate (Akita)': 20000,
}

EXO_GROSS_PRICES = {
    "Sendai Bar Hopping Tour": 25960,
    "Hungry Samurai: Sendai Food & Culture Day Tour": 38500,
    "Matsushima & Shiogama Full Day Tour": 41800,
    "Hiraizumi Full Day Tour from Sendai": 89650,
    "HD Tour of Hirosaki": 25000,
    "Hirosaki & Aomori Full Day Tour": 35000,
}

ATTRACXI_TOURS = {
    "Attracxi: Mysteries of the Three Holy Mountains of Dewa",
    "Attracxi: Hiraizumi Full Day Tour from Sendai",
    "Attracxi: Master the Way of the Samurai",
    "Attracxi: Shiogama's Delicacy Trail to Matsushima's Natural Wonders",
    "Attracxi: From Cask to Glass - Tohoku's Craft Journey with Local Cuisine",
    "Attracxi: From Cask to Glass – Tohoku's Craft Journey with Local Cuisine",
    "Attracxi: Step into Tradition - Craft, Culture, and Hot Springs in Naruko",
    "Attracxi: Step into Tradition – Craft, Culture, and Hot Springs in Naruko",
    "The Sacred Peaks of Yamagata Day Trip from Sendai",
}

ATTRACXI_GROSS_PER_PERSON = {
    1: 198000,
    2: 99000,
    3: 82500,
    4: 66000,
}

EXO_FIXED_GROUP_PRICES = {
    "Guide Assistant - Meet & Greet / On foot": 19800,
    "Guide Assistant – Meet & Greet / On foot": 19800,
    "Guide Assistant - Meet & Greet / Private Car": 30800,
    "Guide Assistant – Meet & Greet / Private Car": 30800,
}

EXO_TRANSFER_PRICES = {
    "Oneway Private Transfer: Sendai→Matsushima（Sedan）": 19800,
    "Oneway Private Transfer: Sendai→Matsushima（Hiace）": 26400,
}

PRIVATE_SURCHARGE = 10000


class PricingError(ValueError):
    pass


def price_booking(booking: BookingRequest) -> BookingRequest:
    amount, formula = calculate_amount(
        booking.tour_name,
        booking.pax,
        agent_type=booking.agent_type,
        tour_type=booking.tour_type,
    )
    return replace(booking, amount=amount, amount_formula=formula)


def calculate_amount(
    tour_name: str,
    pax: int,
    *,
    agent_type: str = "AGT",
    tour_type: str = "G",
) -> tuple[int, str]:
    if pax < 1:
        raise PricingError("pax must be at least 1")

    normalized_agent_type = agent_type.upper()
    normalized_tour_type = tour_type.upper()

    if tour_name in ATTRACXI_TOURS:
        unit = ATTRACXI_GROSS_PER_PERSON.get(pax, 60500)
        amount = unit * pax
        return amount, f"{unit} × {pax} = {amount}"

    if normalized_agent_type == "EXO":
        if tour_name in EXO_FIXED_GROUP_PRICES:
            amount = EXO_FIXED_GROUP_PRICES[tour_name]
            return amount, f"{amount} yen fixed group price"
        if tour_name in EXO_TRANSFER_PRICES:
            amount = EXO_TRANSFER_PRICES[tour_name]
            return amount, f"{amount} yen per vehicle"
        if tour_name not in EXO_GROSS_PRICES:
            raise PricingError(f"Unknown EXO tour: {tour_name}")
        unit = EXO_GROSS_PRICES[tour_name]
        amount = unit * pax
        return amount, f"{unit} × {pax} = {amount}"

    if tour_name not in AGT_NET_PRICES:
        raise PricingError(f"Unknown AGT/BtoC tour: {tour_name}")

    unit = AGT_NET_PRICES[tour_name]
    subtotal = unit * pax
    amount = int(subtotal * 1.1)
    formula = f"({unit} × {pax}) × 1.1 = {amount}"

    if normalized_tour_type == "PV":
        amount += PRIVATE_SURCHARGE
        formula = f"{formula} + {PRIVATE_SURCHARGE} = {amount}"

    return amount, formula
