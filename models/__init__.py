# Import all models so SQLAlchemy registers them before Base.metadata.create_all()
from models.lead import Lead          # noqa: F401
from models.interaction import Interaction  # noqa: F401
from models.escalation import Escalation    # noqa: F401
from models.demo import Demo                # noqa: F401
from models.knowledge_base import KnowledgeBase  # noqa: F401
