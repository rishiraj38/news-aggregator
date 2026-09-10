from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"

    video_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    description = Column(Text)
    transcript = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class OpenAIArticle(Base):
    __tablename__ = "openai_articles"

    guid = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)
    published_at = Column(DateTime, nullable=False)
    category = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AnthropicArticle(Base):
    __tablename__ = "anthropic_articles"

    guid = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)
    published_at = Column(DateTime, nullable=False)
    category = Column(String, nullable=True)
    markdown = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class GeneralRSSArticle(Base):
    __tablename__ = "general_rss_articles"

    guid = Column(String, primary_key=True)
    source = Column(String, nullable=False)  # e.g. "techcrunch", "theverge"
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    description = Column(Text)
    published_at = Column(DateTime, nullable=False)
    category = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Digest(Base):
    __tablename__ = "digests"

    id = Column(String, primary_key=True)
    article_type = Column(String, nullable=False)
    article_id = Column(String, nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    image_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    posted_to_instagram = Column(String, nullable=True)  # "true" when posted


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)  # UUID
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    preferences = Column(Text, nullable=False)  # JSON string of profile dict
    title = Column(String, nullable=True)
    expertise_level = Column(String, default="Intermediate")
    is_active = Column(String, default="true")  # Boolean stored as string for simplicity
    subscription_status = Column(String, default="trial")
    role = Column(String, default="user")
    plan = Column(String, default="free")  # "free" | "pro"; role="admin" overrides
    admin_welcome_sent = Column(String, default="false") # Boolean stored as string in this repo's pattern?
    trial_warning_2_sent = Column(String, default="false")
    trial_warning_1_sent = Column(String, default="false")
    trial_expired_sent = Column(String, default="false")
    created_at = Column(DateTime, default=datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    digest_id = Column(String, nullable=False)
    relevance_score = Column(String, nullable=False)  # Float stored as string
    rank = Column(String, nullable=False)  # Int stored as string
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(String, primary_key=True)  # UUID
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, default="RUNNING")  # RUNNING, SUCCESS, FAILED
    log_summary = Column(Text, default="")
    users_processed = Column(String, default="0")  # Int stored as string for consistency
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailDelivery(Base):
    """One row per email the pipeline attempted to send.

    `recommendations` records what was *picked* for a subscriber, but not whether
    the email carrying it actually went out — which is how weeks of failed sends
    stayed invisible. This is the authoritative "who got what, and did it land".
    """

    __tablename__ = "email_deliveries"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(String, nullable=False)
    email = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # digest | trial_warning | trial_expired | admin_welcome
    subject = Column(String, nullable=True)
    status = Column(String, nullable=False)  # sent | failed
    error = Column(Text, nullable=True)
    digest_ids = Column(Text, nullable=True)  # JSON list of digest ids in the email
    pipeline_run_id = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)

