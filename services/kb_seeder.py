"""
Knowledge Base Seeder — loads BeyondSure product Q&A into the database on startup.

Runs automatically when the server starts (called from main.py).
Idempotent: skips if the KB already has entries, so re-starts don't duplicate data.

To reset and re-seed: delete all rows from the knowledge_base table, then restart.

Categories (must match kb_lookup.py intent→category mapping):
  "Pricing & Plans"    ← pricing_query intent
  "Features"           ← feature_query intent
  "Onboarding & Setup" ← onboarding_query intent
  "Objection Handling" ← objection_cost / objection_timing / objection_switching intents
"""

from database import SessionLocal
from models.knowledge_base import KnowledgeBase


# ─────────────────────────────────────────────────────────────────────────────
# KB entries — (question, answer, category)
# ─────────────────────────────────────────────────────────────────────────────

KB_ENTRIES: list[tuple[str, str, str]] = [

    # ── Pricing & Plans (6 entries) ───────────────────────────────────────────
    (
        "How much does BeyondSure cost?",
        (
            "BeyondSure has three plans:\n"
            "• Essential — ₹24,780/year (up to 3 logins) — great for small teams\n"
            "• Professional — ₹48,380/year (up to 50 logins) — our most popular\n"
            "• Enterprise — ₹71,980/year (unlimited logins) — for large teams\n\n"
            "All plans include a one-time setup fee of ₹1,000 and an additional "
            "₹1,200 + GST per employee login per year. No monthly plans — annual subscription."
        ),
        "Pricing & Plans",
    ),
    (
        "What is the cheapest plan?",
        (
            "Our Essential Plan starts at ₹24,780 per year — that's a one-time ₹1,000 setup fee, "
            "₹20,000 annual maintenance, and GST. It supports up to 3 employee logins and includes "
            "Lead Management, Live Quotation, 5 Policy Comparison, and Renewals. "
            "It's built for solo agents and small teams just getting started."
        ),
        "Pricing & Plans",
    ),
    (
        "Is there a free trial?",
        (
            "We don't offer a free trial, but we do offer a personalised demo so you can see "
            "exactly how the platform works for your specific business before committing. "
            "Would you like to schedule one? It only takes 15 minutes."
        ),
        "Pricing & Plans",
    ),
    (
        "How is pricing structured?",
        (
            "Pricing has two components:\n"
            "1. Annual Maintenance Fee — covers hosting, white-labelling, training, and support "
            "(₹20,000 / ₹40,000 / ₹60,000 depending on your plan)\n"
            "2. Per Employee Login — ₹1,200 + GST per login per year, the same across all plans\n\n"
            "There's also a one-time setup fee of ₹1,000. No hidden charges."
        ),
        "Pricing & Plans",
    ),
    (
        "What does the per employee cost include?",
        (
            "Each employee login (₹1,200 + GST/year) includes access to technology upgrades, "
            "new feature rollouts, continuous bug fixes, tech support via chat/email/call, "
            "SMS & email communication costs, user activity tracking, and a personalised dashboard."
        ),
        "Pricing & Plans",
    ),
    (
        "Are there any hidden charges?",
        (
            "No hidden charges on the plans themselves. One thing to note: integration support "
            "with third-party tools and APIs is chargeable separately — our team will give you "
            "a quote based on what you need. Everything else is covered in the annual fee."
        ),
        "Pricing & Plans",
    ),

    # ── Features (7 entries) ──────────────────────────────────────────────────
    (
        "What does BeyondSure actually do?",
        (
            "BeyondSure is a complete insurance distribution platform — it gives your business:\n"
            "• Lead Management — capture, track, and follow up on every lead\n"
            "• Live Quotation — instant quotes across multiple insurers\n"
            "• 5 Policy Comparison — compare up to 5 policies side by side for clients\n"
            "• Automated Renewals — never miss a renewal again\n"
            "• MIS Reports — real-time analytics on leads, sales, and commissions\n"
            "• White-label platform — your own brand, your own identity\n\n"
            "It's fully web-based — no app to install, works on any device."
        ),
        "Features",
    ),
    (
        "Does BeyondSure have a mobile app?",
        (
            "BeyondSure is a web-based SaaS platform — it works on any browser on desktop, "
            "tablet, or mobile. There's no separate app to download or install. "
            "Just open your browser and you're ready to go."
        ),
        "Features",
    ),
    (
        "Does it integrate with WhatsApp?",
        (
            "Yes — BeyondSure supports WhatsApp integration for lead communication and "
            "client notifications. Our team will help you set this up as part of onboarding."
        ),
        "Features",
    ),
    (
        "Does it send automatic renewal reminders?",
        (
            "Yes — BeyondSure automatically sends policy renewal reminders to your clients "
            "so no renewal ever slips through. Your team gets notified too, so you can follow up "
            "personally when it matters most."
        ),
        "Features",
    ),
    (
        "What are MIS reports?",
        (
            "MIS (Management Information System) reports give you real-time visibility into "
            "your business — leads by stage, policies sold, commissions earned, team performance, "
            "and more. Available on Professional and Enterprise plans. "
            "Think of it as your business dashboard, always up to date."
        ),
        "Features",
    ),
    (
        "Can clients compare policies on BeyondSure?",
        (
            "Yes — BeyondSure lets you compare up to 5 policies simultaneously across insurers "
            "with live quotations. Your clients can see the differences clearly and make informed "
            "decisions quickly — which means faster conversions for your team."
        ),
        "Features",
    ),
    (
        "What is white-labelling?",
        (
            "White-labelling means BeyondSure powers the platform but it runs under your brand — "
            "your logo, your name, your colours. Your clients see your brand, not ours. "
            "This is included in all plans and is one of the key reasons businesses choose us: "
            "you build your own identity, not someone else's."
        ),
        "Features",
    ),

    # ── Onboarding & Setup (4 entries) ────────────────────────────────────────
    (
        "How long does it take to get started?",
        (
            "You can go live within 48–72 hours. Setup includes:\n"
            "• Product configuration for your business\n"
            "• White-labelling with your brand\n"
            "• A dedicated Relationship Manager assigned to your account\n"
            "• Full onboarding session for your team\n\n"
            "The one-time setup fee is just ₹1,000."
        ),
        "Onboarding & Setup",
    ),
    (
        "Can I migrate my existing data from Excel or another system?",
        (
            "Yes — BeyondSure has a bulk upload feature that supports Excel imports and "
            "integrations from other systems. You can bring your existing leads, clients, "
            "and policy data with you without starting from scratch. "
            "Our team will guide you through the migration during onboarding."
        ),
        "Onboarding & Setup",
    ),
    (
        "What support do I get after signing up?",
        (
            "Every account gets a dedicated Relationship Manager available 9:30 AM – 7 PM. "
            "They handle everything — onboarding, training, troubleshooting, and ongoing questions. "
            "You also get access to a knowledge base, help guides, and a tech support team "
            "reachable via chat, email, or call. Enterprise clients also get Learning & "
            "Development modules for their team."
        ),
        "Onboarding & Setup",
    ),
    (
        "Is training provided?",
        (
            "Yes — BeyondSure includes an initial onboarding training session plus refresher "
            "sessions as part of the annual maintenance. Enterprise plan clients also get full "
            "Learning & Development modules. Your dedicated RM will make sure your team is "
            "comfortable with the platform before you go live."
        ),
        "Onboarding & Setup",
    ),

    # ── Objection Handling (4 entries) ────────────────────────────────────────
    (
        "It's too expensive / no budget",
        (
            "Completely understand — that's why we have the Essential Plan at ₹24,780/year, "
            "which works out to about ₹2,065/month. Consider what one missed renewal or a "
            "lead that slipped through costs you — in most cases, the platform pays for itself "
            "quickly. And unlike hiring extra staff, this scales with you. "
            "Would a quick demo help you see the ROI more clearly?"
        ),
        "Objection Handling",
    ),
    (
        "I already use Excel or manage manually",
        (
            "Excel works — until a lead slips through, a renewal is missed, or your team grows "
            "and things get complicated. BeyondSure automates exactly those things: leads tracked, "
            "renewals sent, commissions calculated — without manual effort. "
            "Most teams who switched say they wish they'd done it sooner. "
            "Want to see a 15-minute walkthrough?"
        ),
        "Objection Handling",
    ),
    (
        "I already use another platform / happy with current system",
        (
            "The key difference is ownership. With most platforms, you're working under their "
            "brand and their rules. BeyondSure gives you your own branded platform — your logo, "
            "your identity, your client relationships. You're building your business, not someone "
            "else's legacy. That's something most platforms simply don't offer."
        ),
        "Objection Handling",
    ),
    (
        "Not now / call me later / not the right time",
        (
            "Absolutely — no pressure at all. Just so you know, BeyondSure can be set up and "
            "live within 48–72 hours, so when the time is right, getting started is quick. "
            "I'll check back in a few days. Feel free to reach out anytime — we'd love to help "
            "when you're ready."
        ),
        "Objection Handling",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Seeder function
# ─────────────────────────────────────────────────────────────────────────────

def seed_kb() -> int:
    """
    Load KB entries into the database.
    Idempotent — skips if the KB already has entries.
    Returns the number of entries inserted (0 if skipped).
    """
    db = SessionLocal()
    try:
        existing_count = db.query(KnowledgeBase).count()
        if existing_count >= len(KB_ENTRIES):
            print(f"[KB Seeder] KB already has {existing_count} entries — skipping seed")
            return 0

        inserted = 0
        for question, answer, category in KB_ENTRIES:
            entry = KnowledgeBase(
                question=question,
                answer=answer,
                category=category,
                active=True,
                is_placeholder=False,
            )
            db.add(entry)
            inserted += 1

        db.commit()
        print(f"[KB Seeder] ✓ Inserted {inserted} KB entries across 4 categories")
        return inserted

    except Exception as e:
        db.rollback()
        print(f"[KB Seeder] ✗ Failed to seed KB: {e}")
        return 0
    finally:
        db.close()
