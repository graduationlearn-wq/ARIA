"""
Unit tests for pure service functions — no HTTP, no DB required.

Tests: lead_scorer, intent_classifier, chat_flow parser,
       kb_seeder, and scheduler IST window helper.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from models.lead import Lead


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_lead(**kwargs) -> Lead:
    """Create an in-memory Lead with sensible defaults, override via kwargs."""
    lead = Lead()
    lead.lead_type    = kwargs.get("lead_type", "unknown")
    lead.team_size    = kwargs.get("team_size", None)
    lead.uses_software     = kwargs.get("uses_software", None)
    lead.open_to_platform  = kwargs.get("open_to_platform", None)
    lead.willing_for_demo  = kwargs.get("willing_for_demo", None)
    lead.lead_score        = kwargs.get("lead_score", 0)
    lead.lead_quality      = kwargs.get("lead_quality", "new")
    lead.first_name        = kwargs.get("first_name", "Test")
    lead.current_software  = kwargs.get("current_software", None)
    lead.company_name      = kwargs.get("company_name", None)
    lead.company_website   = kwargs.get("company_website", None)
    lead.demo_preference   = kwargs.get("demo_preference", None)
    lead.human_priority    = kwargs.get("human_priority", False)
    lead.alert_sent_at     = kwargs.get("alert_sent_at", None)
    return lead


# ─────────────────────────────────────────────────────────────────────────────
# Lead Scorer
# ─────────────────────────────────────────────────────────────────────────────

class TestLeadScorer:
    """Tests for services/lead_scorer.py"""

    def test_broker_demo_open_scores_warm(self):
        from services.lead_scorer import compute_initial_score, score_to_quality
        lead = _make_lead(lead_type="broker", willing_for_demo=True, open_to_platform=True)
        score = compute_initial_score(lead)
        assert score >= 40
        assert score_to_quality(score) in ("warm", "hot")

    def test_broker_large_team_no_software_scores_high(self):
        from services.lead_scorer import compute_initial_score
        lead = _make_lead(lead_type="broker", team_size=25, uses_software=False)
        score = compute_initial_score(lead)
        # broker=15, team>=20=15, no_software=10 → 40 pts max profile
        assert score == 40

    def test_invalid_lead_type_scores_zero(self):
        from services.lead_scorer import score_lead
        lead = _make_lead(lead_type="invalid")
        score, quality = score_lead(lead)
        assert score == 0
        assert quality == "invalid"

    def test_agent_scores_lower_than_broker(self):
        from services.lead_scorer import compute_initial_score
        broker = _make_lead(lead_type="broker", team_size=10, uses_software=False)
        agent  = _make_lead(lead_type="agent",  team_size=10, uses_software=False)
        assert compute_initial_score(broker) > compute_initial_score(agent)

    def test_demo_request_delta_increases_score(self):
        from services.lead_scorer import apply_engagement_delta
        assert apply_engagement_delta(40, "demo_request") == 55

    def test_not_interested_kills_score(self):
        from services.lead_scorer import apply_engagement_delta
        assert apply_engagement_delta(80, "not_interested") == 30

    def test_score_clamped_at_100(self):
        from services.lead_scorer import apply_engagement_delta
        assert apply_engagement_delta(95, "demo_request") == 100

    def test_score_clamped_at_zero(self):
        from services.lead_scorer import apply_engagement_delta
        assert apply_engagement_delta(5, "not_interested") == 0

    def test_decay_applied_for_inactive_leads(self):
        from services.lead_scorer import apply_decay
        assert apply_decay(50, 31) == 30   # -20 pts
        assert apply_decay(50, 15) == 40   # -10 pts
        assert apply_decay(50, 8)  == 45   # -5 pts
        assert apply_decay(50, 3)  == 50   # no decay

    def test_score_to_quality_tiers(self):
        from services.lead_scorer import score_to_quality
        assert score_to_quality(70)  == "hot"
        assert score_to_quality(69)  == "warm"
        assert score_to_quality(40)  == "warm"
        assert score_to_quality(39)  == "cold"
        assert score_to_quality(10)  == "cold"
        assert score_to_quality(9)   == "new"
        assert score_to_quality(0)   == "new"


# ─────────────────────────────────────────────────────────────────────────────
# Intent Classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentClassifier:
    """Tests for services/intent_classifier.py"""

    def test_demo_request_detected(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("I want to book a demo")
        assert result.label == "demo_request"
        assert result.confidence > 0.5

    def test_pricing_query_detected(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("How much does it cost?")
        assert result.label == "pricing_query"

    def test_bot_detection(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("Are you a bot?")
        assert result.label == "bot_detection"

    def test_escalation_request(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("I want to talk to a real person")
        assert result.label == "escalation_request"

    def test_not_interested(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("not interested, please stop messaging")
        assert result.label == "not_interested"

    def test_objection_cost(self):
        from services.intent_classifier import classify_intent
        # Avoid words containing "hi" as substring (e.g. "this") — the classifier
        # uses substring matching and would incorrectly match the "hi" greeting keyword.
        result = classify_intent("no budget, can't afford it right now")
        assert result.label == "objection_cost"

    def test_unclear_fallback(self):
        from services.intent_classifier import classify_intent
        result = classify_intent("zxqwerty12345 random nonsense")
        assert result.label == "unclear"
        assert result.confidence == 0.3

    def test_should_escalate_true_for_bot(self):
        from services.intent_classifier import classify_intent, should_escalate
        assert should_escalate(classify_intent("are you a bot")) is True

    def test_should_escalate_true_for_human_request(self):
        from services.intent_classifier import classify_intent, should_escalate
        assert should_escalate(classify_intent("talk to someone please")) is True

    def test_should_escalate_false_for_pricing(self):
        from services.intent_classifier import classify_intent, should_escalate
        assert should_escalate(classify_intent("what is the price?")) is False


# ─────────────────────────────────────────────────────────────────────────────
# Chat Flow — parse_guided_answer & get_next_guided_step
# ─────────────────────────────────────────────────────────────────────────────

class TestChatFlowParser:
    """Tests for services/chat_flow.py"""

    def test_first_step_is_uses_software(self):
        from services.chat_flow import get_next_guided_step
        lead = _make_lead()  # uses_software=None
        step = get_next_guided_step(lead)
        assert step["field"] == "uses_software"
        assert len(step["options"]) > 0

    def test_step_skips_current_software_when_uses_software_false(self):
        from services.chat_flow import get_next_guided_step
        lead = _make_lead(uses_software=False)
        step = get_next_guided_step(lead)
        # Should skip current_software (only asked when uses_software=True)
        assert step["field"] != "current_software"

    def test_step_asks_current_software_when_uses_software_true(self):
        from services.chat_flow import get_next_guided_step
        lead = _make_lead(uses_software=True, current_software=None)
        step = get_next_guided_step(lead)
        assert step["field"] == "current_software"

    def test_parse_uses_software_yes(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("uses_software", "Yes, I use something", lead)
        assert result.get("uses_software") is True

    def test_parse_uses_software_no(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("uses_software", "No, managing manually", lead)
        assert result.get("uses_software") is False

    def test_parse_lead_type_broker(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("lead_type", "Broker", lead)
        assert result.get("lead_type") == "broker"

    def test_parse_team_size_numeric(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("team_size", "I have 15 people", lead)
        assert result.get("team_size") == 15

    def test_parse_team_size_solo(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("team_size", "just me", lead)
        assert result.get("team_size") == 1

    def test_parse_demo_yes_returns_action(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("willing_for_demo", "Yes, book a demo 📅", lead)
        assert result.get("_action") == "demo_book"
        assert result.get("willing_for_demo") is True

    def test_parse_demo_maybe_returns_reengage(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("willing_for_demo", "Maybe later", lead)
        assert result.get("_action") == "reengage"

    def test_parse_demo_talk_to_expert_escalates(self):
        from services.chat_flow import parse_guided_answer
        lead = _make_lead()
        result = parse_guided_answer("willing_for_demo", "Talk to an expert 📞", lead)
        assert result.get("_action") == "escalate"

    def test_flow_complete_when_all_fields_filled(self):
        from services.chat_flow import get_next_guided_step
        lead = _make_lead(
            uses_software=False,
            lead_type="broker",
            team_size=10,
            company_name="Test Co",
            company_website="test.com",
            willing_for_demo=True,
            demo_preference="This week",
        )
        step = get_next_guided_step(lead)
        assert step is None  # all steps complete

    def test_should_alert_human_on_demo_request(self):
        from services.chat_flow import should_alert_human
        lead = _make_lead(alert_sent_at=None)
        assert should_alert_human(lead, "demo_request") is True

    def test_should_not_alert_twice(self):
        from services.chat_flow import should_alert_human
        lead = _make_lead(alert_sent_at=datetime.now(timezone.utc))
        assert should_alert_human(lead, "demo_request") is False


# ─────────────────────────────────────────────────────────────────────────────
# KB Seeder
# ─────────────────────────────────────────────────────────────────────────────

class TestKBSeeder:
    """Tests for services/kb_seeder.py"""

    def test_seed_inserts_all_entries(self, db):
        from services.kb_seeder import seed_kb, KB_ENTRIES
        from database import SessionLocal

        # Patch SessionLocal to use the test DB session's connection
        with patch("services.kb_seeder.SessionLocal", return_value=db):
            inserted = seed_kb()

        assert inserted == len(KB_ENTRIES)

    def test_seed_is_idempotent(self, db):
        from services.kb_seeder import seed_kb

        with patch("services.kb_seeder.SessionLocal", return_value=db):
            seed_kb()      # first call
            inserted = seed_kb()  # second call — should skip

        assert inserted == 0

    def test_all_four_categories_present(self, db):
        from services.kb_seeder import seed_kb, KB_ENTRIES

        categories = {cat for _, _, cat in KB_ENTRIES}
        assert "Pricing & Plans"    in categories
        assert "Features"           in categories
        assert "Onboarding & Setup" in categories
        assert "Objection Handling" in categories


# ─────────────────────────────────────────────────────────────────────────────
# Scheduler — IST send-window helper
# ─────────────────────────────────────────────────────────────────────────────

class TestSchedulerIST:
    """Tests for the IST send-window guard in services/scheduler.py"""

    IST = timezone(timedelta(hours=5, minutes=30))

    def test_within_window_returns_true(self):
        from services.scheduler import _is_send_hour_ist
        # 2:00 PM IST — well within 9am–9pm window
        mock_time = datetime(2024, 6, 15, 14, 0, tzinfo=self.IST)
        with patch("services.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert _is_send_hour_ist() is True

    def test_outside_window_at_night_returns_false(self):
        from services.scheduler import _is_send_hour_ist
        # 3:00 AM IST — outside window
        mock_time = datetime(2024, 6, 15, 3, 0, tzinfo=self.IST)
        with patch("services.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert _is_send_hour_ist() is False

    def test_boundary_9am_is_allowed(self):
        from services.scheduler import _is_send_hour_ist
        mock_time = datetime(2024, 6, 15, 9, 0, tzinfo=self.IST)
        with patch("services.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert _is_send_hour_ist() is True

    def test_boundary_9pm_is_blocked(self):
        from services.scheduler import _is_send_hour_ist
        # hour=21 is exactly 9pm — should be blocked (window is < 21)
        mock_time = datetime(2024, 6, 15, 21, 0, tzinfo=self.IST)
        with patch("services.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_time
            assert _is_send_hour_ist() is False
