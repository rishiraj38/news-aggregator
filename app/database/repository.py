from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Callable, TypeVar
import logging
from sqlalchemy import nullslast
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, PendingRollbackError
from .models import YouTubeVideo, OpenAIArticle, AnthropicArticle, GeneralRSSArticle, Digest, User, Recommendation, PipelineRun
from .connection import get_session

_logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class UserSnapshot:
    """Session-independent copy of a :class:`User` row.

    The pipeline reconnects to Postgres when Render drops the SSL link
    mid-run, which detaches every ORM object loaded from the old session and
    makes even ``user.email`` raise ``DetachedInstanceError``. Passing these
    plain snapshots around instead keeps personalization and email sending
    alive across a reconnect.
    """

    id: str
    email: str
    name: str
    role: Optional[str]
    title: Optional[str]
    expertise_level: Optional[str]
    preferences: Optional[str]
    created_at: Optional[datetime]
    subscription_status: Optional[str]
    admin_welcome_sent: Optional[str]
    trial_warning_1_sent: Optional[str]
    trial_warning_2_sent: Optional[str]
    trial_expired_sent: Optional[str]

    @classmethod
    def from_user(cls, user: User) -> "UserSnapshot":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            role=getattr(user, "role", None),
            title=getattr(user, "title", None),
            expertise_level=getattr(user, "expertise_level", None),
            preferences=getattr(user, "preferences", None),
            created_at=getattr(user, "created_at", None),
            subscription_status=getattr(user, "subscription_status", None),
            admin_welcome_sent=getattr(user, "admin_welcome_sent", None),
            trial_warning_1_sent=getattr(user, "trial_warning_1_sent", None),
            trial_warning_2_sent=getattr(user, "trial_warning_2_sent", None),
            trial_expired_sent=getattr(user, "trial_expired_sent", None),
        )


class Repository:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

    def _reconnect(self) -> None:
        """Close the broken session and open a fresh one."""
        try:
            self.session.close()
        except Exception:
            pass
        self.session = get_session()
        _logger.info("Reconnected to database with a fresh session.")

    def _safe_execute(self, fn: Callable[[], T], retries: int = 3) -> T:
        """Execute *fn* with automatic rollback + reconnect on SSL drops.

        Catches OperationalError / PendingRollbackError, rolls back, gets a
        new session, and retries up to *retries* times before re-raising.
        """
        last_err: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except (OperationalError, PendingRollbackError) as exc:
                last_err = exc
                _logger.warning(
                    "DB connection error (attempt %d/%d): %s",
                    attempt, retries, exc,
                )
                try:
                    self.session.rollback()
                except Exception:
                    pass
                self._reconnect()
        raise last_err  # type: ignore[misc]


    def _bulk_create_items(
        self,
        items: List[dict],
        model_class,
        id_field: str,
        id_attr: str,
    ) -> int:
        new_items = []
        for item in items:
            existing = (
                self.session.query(model_class)
                .filter_by(**{id_attr: item[id_field]})
                .first()
            )
            if not existing:
                new_items.append(model_class(**item))
        if new_items:
            self.session.add_all(new_items)
            self.session.commit()
        return len(new_items)

    def create_youtube_video(
        self,
        video_id: str,
        title: str,
        url: str,
        channel_id: str,
        published_at: datetime,
        description: str = "",
        transcript: Optional[str] = None,
    ) -> Optional[YouTubeVideo]:
        existing = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if existing:
            return None
        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        video = YouTubeVideo(
            video_id=video_id,
            title=title,
            url=url,
            channel_id=channel_id,
            published_at=published_at,
            description=description,
            transcript=transcript,
            image_url=thumb,
        )
        self.session.add(video)
        self.session.commit()
        return video

    def create_openai_article(
        self,
        guid: str,
        title: str,
        url: str,
        published_at: datetime,
        description: str = "",
        category: Optional[str] = None,
    ) -> Optional[OpenAIArticle]:
        existing = self.session.query(OpenAIArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = OpenAIArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category,
        )
        self.session.add(article)
        self.session.commit()
        return article

    def create_anthropic_article(
        self,
        guid: str,
        title: str,
        url: str,
        published_at: datetime,
        description: str = "",
        category: Optional[str] = None,
    ) -> Optional[AnthropicArticle]:
        existing = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if existing:
            return None
        article = AnthropicArticle(
            guid=guid,
            title=title,
            url=url,
            published_at=published_at,
            description=description,
            category=category,
        )
        self.session.add(article)
        self.session.commit()
        return article

    def bulk_create_youtube_videos(self, videos: List[dict]) -> int:
        formatted_videos = []
        for v in videos:
            vid = v["video_id"]
            formatted_videos.append(
                {
                    "video_id": vid,
                    "title": v["title"],
                    "url": v["url"],
                    "channel_id": v.get("channel_id", ""),
                    "published_at": v["published_at"],
                    "description": v.get("description", ""),
                    "transcript": v.get("transcript"),
                    "image_url": v.get("image_url")
                    or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                }
            )
        return self._bulk_create_items(
            formatted_videos, YouTubeVideo, "video_id", "video_id"
        )

    def bulk_create_openai_articles(self, articles: List[dict]) -> int:
        formatted_articles = [
            {
                "guid": a["guid"],
                "title": a["title"],
                "url": a["url"],
                "published_at": a["published_at"],
                "description": a.get("description", ""),
                "category": a.get("category"),
                "image_url": a.get("image_url"),
            }
            for a in articles
        ]
        return self._bulk_create_items(
            formatted_articles, OpenAIArticle, "guid", "guid"
        )

    def bulk_create_anthropic_articles(self, articles: List[dict]) -> int:
        formatted_articles = [
            {
                "guid": a["guid"],
                "title": a["title"],
                "url": a["url"],
                "published_at": a["published_at"],
                "description": a.get("description", ""),
                "category": a.get("category"),
                "image_url": a.get("image_url"),
            }
            for a in articles
        ]
        return self._bulk_create_items(
            formatted_articles, AnthropicArticle, "guid", "guid"
        )

    def bulk_create_general_rss_articles(self, articles: List[dict], source: str) -> int:
        formatted_articles = [
            {
                "guid": a["guid"],
                "source": source,
                "title": a["title"],
                "url": a["url"],
                "published_at": a["published_at"],
                "description": a.get("description", ""),
                "category": a.get("category"),
                "image_url": a.get("image_url"),
            }
            for a in articles
        ]
        return self._bulk_create_items(
            formatted_articles, GeneralRSSArticle, "guid", "guid"
        )

    def get_anthropic_articles_without_markdown(
        self, limit: Optional[int] = None
    ) -> List[AnthropicArticle]:
        query = self.session.query(AnthropicArticle).filter(
            AnthropicArticle.markdown.is_(None)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_anthropic_article_markdown(self, guid: str, markdown: str) -> bool:
        article = self.session.query(AnthropicArticle).filter_by(guid=guid).first()
        if article:
            article.markdown = markdown
            self.session.commit()
            return True
        return False

    def get_youtube_videos_without_transcript(
        self, limit: Optional[int] = None
    ) -> List[YouTubeVideo]:
        query = self.session.query(YouTubeVideo).filter(
            YouTubeVideo.transcript.is_(None)
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def update_youtube_video_transcript(self, video_id: str, transcript: str) -> bool:
        video = self.session.query(YouTubeVideo).filter_by(video_id=video_id).first()
        if video:
            video.transcript = transcript
            self.session.commit()
            return True
        return False

    @staticmethod
    def _recency_key(published_at: Optional[datetime]) -> datetime:
        """Sortable UTC key; undated rows sink to the bottom."""
        if published_at is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if published_at.tzinfo is None:
            return published_at.replace(tzinfo=timezone.utc)
        return published_at.astimezone(timezone.utc)

    @staticmethod
    def _interleave_by_source(
        buckets: Dict[str, List[Dict[str, Any]]], limit: Optional[int]
    ) -> List[Dict[str, Any]]:
        """Round-robin across sources so no single feed can monopolise the batch.

        Previously the candidate lists were simply concatenated and sliced, so a
        large backlog from one noisy feed (BBC Sport) consumed every digest slot
        and topic-filtered subscribers ended up with zero matches.
        """
        ordered_sources = sorted(
            buckets.keys(), key=lambda s: len(buckets[s]), reverse=True
        )
        out: List[Dict[str, Any]] = []
        cursor = 0
        while True:
            drained = True
            for source in ordered_sources:
                items = buckets[source]
                if cursor < len(items):
                    drained = False
                    out.append(items[cursor])
                    if limit and len(out) >= limit:
                        return out
            if drained:
                return out
            cursor += 1

    def _pending_rows(self, model, id_column, type_expr, limit: Optional[int], *extra_filters):
        """Newest rows of one source that have no digest yet.

        A ``NOT EXISTS`` anti-join keeps this on the database side. The previous
        implementation pulled every digest and every article table into Python
        and filtered there, which meant loading tens of thousands of ORM rows on
        every run to keep a few dozen.
        """
        already_digested = (
            self.session.query(Digest)
            .filter(Digest.article_type == type_expr, Digest.article_id == id_column)
            .exists()
        )
        query = self.session.query(model).filter(~already_digested, *extra_filters)
        query = query.order_by(nullslast(model.published_at.desc()))
        if limit:
            query = query.limit(limit)
        return query.all()

    def get_articles_without_digest(
        self, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Newest-first, source-balanced pool of articles that still need a digest."""
        # Each source only ever needs `limit` candidates, because the
        # round-robin below can take at most that many from any one of them.
        per_source = limit or 200
        buckets: Dict[str, List[Dict[str, Any]]] = {}

        def add(entry: Dict[str, Any]) -> None:
            buckets.setdefault(entry["type"], []).append(entry)

        for video in self._pending_rows(
            YouTubeVideo,
            YouTubeVideo.video_id,
            "youtube",
            per_source,
            YouTubeVideo.transcript.isnot(None),
            YouTubeVideo.transcript != "__UNAVAILABLE__",
        ):
            thumb = getattr(video, "image_url", None) or (
                f"https://i.ytimg.com/vi/{video.video_id}/hqdefault.jpg"
            )
            add(
                {
                    "type": "youtube",
                    "id": video.video_id,
                    "title": video.title,
                    "url": video.url,
                    "content": video.transcript or video.description or "",
                    "published_at": video.published_at,
                    "image_url": thumb,
                }
            )

        for article in self._pending_rows(
            OpenAIArticle, OpenAIArticle.guid, "openai", per_source
        ):
            add(
                {
                    "type": "openai",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.description or "",
                    "published_at": article.published_at,
                    "image_url": getattr(article, "image_url", None),
                }
            )

        for article in self._pending_rows(
            AnthropicArticle,
            AnthropicArticle.guid,
            "anthropic",
            per_source,
            AnthropicArticle.markdown.isnot(None),
        ):
            add(
                {
                    "type": "anthropic",
                    "id": article.guid,
                    "title": article.title,
                    "url": article.url,
                    "content": article.markdown or article.description or "",
                    "published_at": article.published_at,
                    "image_url": getattr(article, "image_url", None),
                }
            )

        # General RSS rows carry their origin in `source`, which becomes the
        # digest's article_type, so each source is queried as its own lane.
        sources = [
            s
            for (s,) in self.session.query(GeneralRSSArticle.source).distinct().all()
            if s
        ]
        for source in sources:
            for article in self._pending_rows(
                GeneralRSSArticle,
                GeneralRSSArticle.guid,
                source,
                per_source,
                GeneralRSSArticle.source == source,
            ):
                add(
                    {
                        "type": article.source,
                        "id": article.guid,
                        "title": article.title,
                        "url": article.url,
                        "content": article.description or "",
                        "published_at": article.published_at,
                        "image_url": getattr(article, "image_url", None),
                    }
                )

        # SQL ordering already put each bucket newest-first, but undated rows
        # and mixed tz-awareness still need the Python key to agree.
        for items in buckets.values():
            items.sort(key=lambda a: self._recency_key(a.get("published_at")), reverse=True)

        selected = self._interleave_by_source(buckets, limit)

        if buckets:
            _logger.info(
                "Digest candidates by source: %s → selected %d (limit=%s)",
                {k: len(v) for k, v in sorted(buckets.items())},
                len(selected),
                limit,
            )

        return selected

    def create_digest(
        self,
        article_type: str,
        article_id: str,
        url: str,
        title: str,
        summary: str,
        published_at: Optional[datetime] = None,
        image_url: Optional[str] = None,
    ) -> Optional[Digest]:
        digest_id = f"{article_type}:{article_id}"
        existing = self.session.query(Digest).filter_by(id=digest_id).first()
        if existing:
            return None

        # Always use current time for created_at so freshly-created digests
        # are visible to get_recent_digests(hours=24). Previously published_at
        # was used, which meant old articles' digests fell outside the window.
        created_at = datetime.now(timezone.utc)

        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at,
            image_url=image_url,
        )
        self.session.add(digest)
        self.session.commit()
        return digest

    def mark_digest_posted_instagram(self, digest_id: str) -> None:
        """Flag a digest as already posted to Instagram (prevents duplicate posts)."""
        d = self.session.query(Digest).filter_by(id=digest_id).first()
        if d:
            d.posted_to_instagram = "true"
            self.session.commit()

    def get_recent_digests(
        self, hours: int = 24, exclude_sent: bool = True
    ) -> List[Dict[str, Any]]:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = self.session.query(Digest).filter(Digest.created_at >= cutoff_time)

        if exclude_sent:
            query = query.filter(Digest.sent_at.is_(None))

        digests = query.order_by(Digest.created_at.desc()).all()

        return [
            {
                "id": d.id,
                "article_type": d.article_type,
                "article_id": d.article_id,
                "url": d.url,
                "title": d.title,
                "summary": d.summary,
                "image_url": getattr(d, "image_url", None),
                "created_at": d.created_at,
                "sent_at": d.sent_at,
                "posted_to_instagram": getattr(d, "posted_to_instagram", None),
            }
            for d in digests
        ]

    def get_digests_by_ids(self, digest_ids: List[str]) -> List[Dict[str, Any]]:
        if not digest_ids:
            return []
            
        digests = self.session.query(Digest).filter(Digest.id.in_(digest_ids)).all()
        
        return [
            {
                "id": d.id,
                "article_type": d.article_type,
                "article_id": d.article_id,
                "url": d.url,
                "title": d.title,
                "summary": d.summary,
                "image_url": getattr(d, "image_url", None),
                "created_at": d.created_at,
                "sent_at": d.sent_at,
            }
            for d in digests
        ]

    def mark_digests_as_sent(self, digest_ids: List[str]) -> int:
        sent_time = datetime.now(timezone.utc)
        updated = (
            self.session.query(Digest)
            .filter(Digest.id.in_(digest_ids))
            .update({Digest.sent_at: sent_time}, synchronize_session=False)
        )
        self.session.commit()
        return updated

    # User Management Methods
    def create_user(
        self,
        email: str,
        name: str,
        preferences: str,
        title: str = "",
        expertise_level: str = "Intermediate",
    ) -> User:
        import uuid
        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=name,
            preferences=preferences,
            title=title,
            expertise_level=expertise_level,
        )
        self.session.add(user)
        self.session.commit()
        return user

    def get_user_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter_by(email=email).first()

    def get_active_users(self) -> List[User]:
        # String 'true' because sqlite/simple mapping. In production use real boolean.
        return self._safe_execute(
            lambda: self.session.query(User).filter(User.is_active == "true").all()
        )

    def get_active_user_snapshots(self) -> List["UserSnapshot"]:
        """Active users as detached-safe snapshots.

        Read every attribute while the rows are still bound to a live session so
        a later reconnect can never turn ``user.email`` into a lazy-load error.
        """
        def _do() -> List["UserSnapshot"]:
            rows = self.session.query(User).filter(User.is_active == "true").all()
            return [UserSnapshot.from_user(u) for u in rows]

        return self._safe_execute(_do)

    def get_tracked_keywords(self, limit: int = 25) -> List[str]:
        """Distinct keywords across active subscribers, most-requested first.

        Drives ingestion: one network lane per term, so the list is capped.
        Ordering by popularity means a shared term is never dropped in favour
        of a single user's niche one.
        """
        from collections import Counter
        from app.topic_packs.keywords import user_keywords
        import json

        def _do() -> List[str]:
            rows = self.session.query(User.preferences).filter(
                User.is_active == "true"
            ).all()
            counter: Counter = Counter()
            for (raw,) in rows:
                try:
                    prefs = json.loads(raw or "{}")
                except (json.JSONDecodeError, TypeError, ValueError):
                    continue
                if isinstance(prefs, dict):
                    counter.update(user_keywords(prefs))
            return [kw for kw, _ in counter.most_common(limit)]

        return self._safe_execute(_do)

    _USER_FLAG_FIELDS = frozenset(
        {
            "admin_welcome_sent",
            "trial_warning_1_sent",
            "trial_warning_2_sent",
            "trial_expired_sent",
        }
    )

    def set_user_flag(self, user_id: str, field: str, value: str = "true") -> bool:
        """Write one string-boolean flag by id, re-reading the row in the live session."""
        if field not in self._USER_FLAG_FIELDS:
            raise ValueError(f"Refusing to set unknown user flag: {field}")

        def _do() -> bool:
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                return False
            setattr(user, field, value)
            self.session.commit()
            return True

        return self._safe_execute(_do)

    def update_user_preferences(self, user_id: str, new_preferences: str) -> bool:
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            user.preferences = new_preferences
            self.session.commit()
            return True
    def update_user_status(self, user_id: str, status: str) -> bool:
        def _do() -> bool:
            user = self.session.query(User).filter_by(id=user_id).first()
            if not user:
                return False
            user.subscription_status = status
            self.session.commit()
            return True

        return self._safe_execute(_do)

    def update_user_admin_welcome(self, user_id: str) -> bool:
        return self.set_user_flag(user_id, "admin_welcome_sent", "true")

    # Recommendation Methods
    def create_recommendation(
        self,
        user_id: str,
        digest_id: str,
        relevance_score: float,
        rank: int,
        reasoning: str,
    ) -> Recommendation:
        import uuid

        def _do():
            # Check if already recommended
            existing = (
                self.session.query(Recommendation)
                .filter_by(user_id=user_id, digest_id=digest_id)
                .first()
            )
            if existing:
                return existing

            # Validate digest exists to prevent FK violation/orphans
            digest = self.session.query(Digest).filter_by(id=digest_id).first()
            if not digest:
                _logger.warning("Attempted to recommend missing digest %s", digest_id)
                return None

            rec = Recommendation(
                id=str(uuid.uuid4()),
                user_id=user_id,
                digest_id=digest_id,
                relevance_score=str(relevance_score),
                rank=str(rank),
                reasoning=reasoning,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(rec)
            self.session.commit()
            return rec

        return self._safe_execute(_do)

    def get_user_recommended_digest_ids(self, user_id: str) -> List[str]:
        """
        Returns a list of digest IDs that have already been recommended to the user.
        """
        def _do():
            return [
                rec.digest_id
                for rec in self.session.query(Recommendation.digest_id)
                .filter_by(user_id=user_id)
                .all()
            ]
        return self._safe_execute(_do)

    def get_user_feed(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get the 'Feed' for a user: Recommendations joined with Digest details.
        Ordered by date (newest first) then rank (highest relevance).
        """
        results = (
            self.session.query(Recommendation, Digest)
            .join(Digest, Recommendation.digest_id == Digest.id)
            .filter(Recommendation.user_id == user_id)
            .order_by(Digest.created_at.desc(), Recommendation.rank.asc())
            .limit(limit)
            .all()
        )

        feed = []
        for rec, digest in results:
            feed.append({
                "digest": digest,
                "relevance_score": float(rec.relevance_score),
                "reasoning": rec.reasoning,
                "rank": int(rec.rank)
            })

        return feed

    # Pipeline Monitoring Methods
    def create_pipeline_run(self) -> PipelineRun:
        import uuid
        run = PipelineRun(
            id=str(uuid.uuid4()),
            start_time=datetime.now(timezone.utc),
            status="RUNNING",
            log_summary="Pipeline started...",
            users_processed="0"
        )
        self.session.add(run)
        self.session.commit()
        return run

    def update_pipeline_run(
        self, 
        run_id: str, 
        status: Optional[str] = None, 
        log_entry: Optional[str] = None, 
        users_processed: Optional[int] = None
    ):
        def _do():
            run = self.session.query(PipelineRun).filter_by(id=run_id).first()
            if run:
                if status:
                    run.status = status
                    if status in ["SUCCESS", "FAILED"]:
                        run.end_time = datetime.now(timezone.utc)
                
                if log_entry:
                    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    current_log = run.log_summary or ""
                    run.log_summary = f"{current_log}\n[{timestamp}] {log_entry}".strip()
                
                if users_processed is not None:
                    run.users_processed = str(users_processed)
                
                self.session.commit()
                return True
            return False

        return self._safe_execute(_do)
