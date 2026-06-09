import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Float, Text, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Lead(Base):
    __tablename__ = "leads"

    # ── Identity ──────────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    first_name: Mapped[str] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    state: Mapped[str] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str] = mapped_column(String(200), nullable=True)

    # ── Profile (from ad form) ────────────────────────────────────────────────
    # agent | broker | imf | posp | advisor | unknown | invalid
    lead_type: Mapped[str] = mapped_column(String(50), default="unknown")
    # facebook | instagram | website | referral
    source_platform: Mapped[str] = mapped_column(String(50), default="unknown")
    team_size: Mapped[int] = mapped_column(Integer, nullable=True)
    uses_software: Mapped[bool] = mapped_column(Boolean, nullable=True)
    open_to_platform: Mapped[bool] = mapped_column(Boolean, nullable=True)
    willing_for_demo: Mapped[bool] = mapped_column(Boolean, nullable=True)

    # ── Channel ───────────────────────────────────────────────────────────────
    # whatsapp | email
    channel: Mapped[str] = mapped_column(String(20), default="email")
    channel_id: Mapped[str] = mapped_column(String(200), nullable=True)  # email or phone

    # ── State (updated per interaction) ──────────────────────────────────────
    # new | contacted | qualified | demo_scheduled | demo_done | converted | lost | invalid
    status: Mapped[str] = mapped_column(String(50), default="new")
    # new | cold | warm | hot
    lead_quality: Mapped[str] = mapped_column(String(20), default="new")
    lead_score: Mapped[int] = mapped_column(Integer, default=0)
    current_intent: Mapped[str] = mapped_column(String(100), nullable=True)
    assigned_to: Mapped[str] = mapped_column(String(100), nullable=True)

    # ── Compliance ────────────────────────────────────────────────────────────
    opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_logged_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Key timestamps ────────────────────────────────────────────────────────
    first_response_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    first_human_call_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    converted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Chat ─────────────────────────────────────────────────────────────────
    # Unique token embedded in the chat link sent to lead — their "key" to the room
    chat_token: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=True,
        default=lambda: str(uuid.uuid4())
    )
    chat_opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    alert_sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Ownership ─────────────────────────────────────────────────────────────
    # The employee who owns this lead (round-robin on intake; reassignable).
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)

    # ── Human override ────────────────────────────────────────────────────────
    # Team members can manually boost a lead and leave notes
    human_priority: Mapped[bool] = mapped_column(Boolean, default=False)
    human_notes: Mapped[str] = mapped_column(Text, nullable=True)

    # ── Extended profile (populated via chat flow) ────────────────────────────
    current_software: Mapped[str] = mapped_column(String(200), nullable=True)
    company_website: Mapped[str] = mapped_column(String(300), nullable=True)
    demo_preference: Mapped[str] = mapped_column(String(200), nullable=True)  # preferred call time
    meet_link: Mapped[str] = mapped_column(String(300), nullable=True)        # saved Google Meet link for this lead

    # ── Re-engagement (set when lead says "maybe later") ──────────────────────
    # Scheduler checks this: if re_engage_after <= now → send re-engagement nudge
    re_engage_after: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    interactions: Mapped[list] = relationship("Interaction", back_populates="lead",
                                               cascade="all, delete-orphan")
    escalations: Mapped[list] = relationship("Escalation", back_populates="lead",
                                              cascade="all, delete-orphan")
    demos: Mapped[list] = relationship("Demo", back_populates="lead",
                                       cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Lead id={self.id} name={self.first_name} quality={self.lead_quality} score={self.lead_score}>"
