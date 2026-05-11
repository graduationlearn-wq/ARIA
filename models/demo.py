from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Demo(Base):
    """
    Records every demo booking that ARIA or a human creates.

    One lead can have multiple demos (e.g. reschedules, no-shows → rebook).
    demo_number tracks the attempt sequence: 1 = first booking, 2 = rebook, etc.
    """

    __tablename__ = "demos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)

    # When the booking was created (not the scheduled time)
    booked_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # What the lead told us their preferred time is (free text from chat)
    scheduled_preference: Mapped[str] = mapped_column(String(300), nullable=True)

    # scheduled | done | no_show | cancelled
    status: Mapped[str] = mapped_column(String(30), default="scheduled")

    # 1 = first demo, 2 = rebook, etc.
    demo_number: Mapped[int] = mapped_column(Integer, default=1)

    # How the demo was booked: aria_chat | human | webhook_form
    booked_via: Mapped[str] = mapped_column(String(50), default="aria_chat")

    notes: Mapped[str] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship("Lead", back_populates="demos")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Demo id={self.id} lead_id={self.lead_id} "
            f"status={self.status} demo_number={self.demo_number}>"
        )
