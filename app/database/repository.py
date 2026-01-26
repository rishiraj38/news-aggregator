from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from .models import YouTubeVideo, OpenAIArticle, AnthropicArticle, GeneralRSSArticle, Digest, User, Recommendation, PipelineRun
from .connection import get_session


class Repository:
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()

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
        video = YouTubeVideo(
            video_id=video_id,
            title=title,
            url=url,
            channel_id=channel_id,
            published_at=published_at,
            description=description,
            transcript=transcript,
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
        formatted_videos = [
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "url": v["url"],
                "channel_id": v.get("channel_id", ""),
                "published_at": v["published_at"],
                "description": v.get("description", ""),
                "transcript": v.get("transcript"),
            }
            for v in videos
        ]
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

    def get_articles_without_digest(
        self, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        articles = []
        seen_ids = set()

        digests = self.session.query(Digest).all()
        for d in digests:
            seen_ids.add(f"{d.article_type}:{d.article_id}")

        youtube_videos = (
            self.session.query(YouTubeVideo)
            .filter(
                YouTubeVideo.transcript.isnot(None),
                YouTubeVideo.transcript != "__UNAVAILABLE__",
            )
            .all()
        )
        for video in youtube_videos:
            key = f"youtube:{video.video_id}"
            if key not in seen_ids:
                articles.append(
                    {
                        "type": "youtube",
                        "id": video.video_id,
                        "title": video.title,
                        "url": video.url,
                        "content": video.transcript or video.description or "",
                        "published_at": video.published_at,
                    }
                )

        openai_articles = self.session.query(OpenAIArticle).all()
        for article in openai_articles:
            key = f"openai:{article.guid}"
            if key not in seen_ids:
                articles.append(
                    {
                        "type": "openai",
                        "id": article.guid,
                        "title": article.title,
                        "url": article.url,
                        "content": article.description or "",
                        "published_at": article.published_at,
                    }
                )

        anthropic_articles = (
            self.session.query(AnthropicArticle)
            .filter(AnthropicArticle.markdown.isnot(None))
            .all()
        )
        for article in anthropic_articles:
            key = f"anthropic:{article.guid}"
            if key not in seen_ids:
                articles.append(
                    {
                        "type": "anthropic",
                        "id": article.guid,
                        "title": article.title,
                        "url": article.url,
                        "content": article.markdown or article.description or "",
                        "published_at": article.published_at,
                    }
                )

        # General RSS Articles
        general_articles = self.session.query(GeneralRSSArticle).all()
        for article in general_articles:
            key = f"{article.source}:{article.guid}"
            if key not in seen_ids:
                articles.append(
                    {
                        "type": article.source,
                        "id": article.guid,
                        "title": article.title,
                        "url": article.url,
                        "content": article.description or "",
                        "published_at": article.published_at,
                    }
                )

        if limit:
            articles = articles[:limit]

        return articles

    def create_digest(
        self,
        article_type: str,
        article_id: str,
        url: str,
        title: str,
        summary: str,
        published_at: Optional[datetime] = None,
    ) -> Optional[Digest]:
        digest_id = f"{article_type}:{article_id}"
        existing = self.session.query(Digest).filter_by(id=digest_id).first()
        if existing:
            return None

        if published_at:
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            created_at = published_at
        else:
            created_at = datetime.now(timezone.utc)

        digest = Digest(
            id=digest_id,
            article_type=article_type,
            article_id=article_id,
            url=url,
            title=title,
            summary=summary,
            created_at=created_at,
        )
        self.session.add(digest)
        self.session.commit()
        return digest

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
                "created_at": d.created_at,
                "sent_at": d.sent_at,
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
        return self.session.query(User).filter(User.is_active == "true").all()

    def update_user_preferences(self, user_id: str, new_preferences: str) -> bool:
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            user.preferences = new_preferences
            self.session.commit()
            return True
    def update_user_status(self, user_id: str, status: str) -> bool:
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            user.subscription_status = status
            self.session.commit()
            return True
        return False

    def update_user_admin_welcome(self, user_id: str) -> bool:
        user = self.session.query(User).filter_by(id=user_id).first()
        if user:
            user.admin_welcome_sent = "true"
            self.session.commit()
            return True
        return False

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
            print(f"⚠️ Warning: Attempted to recommend missing digest {digest_id}")
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

    def get_user_recommended_digest_ids(self, user_id: str) -> List[str]:
        """
        Returns a list of digest IDs that have already been recommended to the user.
        """
        return [
            rec.digest_id
            for rec in self.session.query(Recommendation.digest_id)
            .filter_by(user_id=user_id)
            .all()
        ]

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
        run = self.session.query(PipelineRun).filter_by(id=run_id).first()
        if run:
            if status:
                run.status = status
                if status in ["SUCCESS", "FAILED"]:
                    run.end_time = datetime.now(timezone.utc)
            
            if log_entry:
                timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
                # Append to existing log summary
                current_log = run.log_summary or ""
                # Keep log size manageable (last 5000 chars?) - For now just append
                run.log_summary = f"{current_log}\n[{timestamp}] {log_entry}".strip()
            
            if users_processed is not None:
                run.users_processed = str(users_processed)
            
            self.session.commit()
            return True
        return False
