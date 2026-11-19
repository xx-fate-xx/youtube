"""Database tables (control state) and artifact models (editorial files)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field as PField
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- enums


class EpisodeState(StrEnum):
    IDEA = "idea"
    RESEARCH = "research"
    SCRIPT = "script"
    STORYBOARD = "storyboard"
    ASSETS = "assets"
    RENDERED = "rendered"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    PRIVATE_UPLOADED = "private_uploaded"
    PUBLISHED = "published"
    ANALYZED = "analyzed"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    REJECTED = "rejected"


class LicenseClearance(StrEnum):
    CLEARED = "cleared"  # commercial use on YouTube permitted, proof on file
    RESTRICTED = "restricted"  # usable for internal preview only
    UNKNOWN = "unknown"  # blocks approval


class ReviewDecisionKind(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_CHANGES = "needs_changes"


# --------------------------------------------------------------------------- DB tables


class Episode(SQLModel, table=True):
    id: str = Field(primary_key=True)
    channel: str = Field(index=True)
    topic: str
    title: str
    state: str = Field(default=EpisodeState.IDEA.value, index=True)
    target_minutes: float = 10.0
    sample: str | None = None
    remote_video_id: str | None = None
    youtube_privacy: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class StateTransition(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    episode_id: str = Field(index=True, foreign_key="episode.id")
    from_state: str
    to_state: str
    actor: str = "operator"
    note: str = ""
    at: datetime = Field(default_factory=utcnow)


class JobRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    episode_id: str = Field(index=True)
    step: str = Field(index=True)
    status: str = "running"  # running | succeeded | failed
    input_hash: str = ""
    output_path: str = ""
    error: str = ""
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None


class CostEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    at: datetime = Field(default_factory=utcnow, index=True)
    episode_id: str | None = Field(default=None, index=True)
    provider: str
    operation: str
    units: float = 0.0
    unit: str = ""
    usd: float = 0.0
    kind: str = "actual"  # estimate | actual
    paid: bool = False
    consent_ref: str = ""


class VideoStats(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    channel: str = Field(index=True)
    episode_id: str | None = None
    remote_video_id: str | None = None
    title: str = ""
    period_end: datetime = Field(default_factory=utcnow)
    days: int = 30
    views: int = 0
    impressions: int | None = None
    ctr_pct: float | None = None
    avg_view_duration_s: float | None = None
    avg_pct_viewed: float | None = None
    subscribers_gained: int | None = None
    traffic_sources_json: str = "{}"
    production_cost_usd: float | None = None
    source: str = "csv"  # csv | mock | api


# --------------------------------------------------------------------------- artifacts


class Source(BaseModel):
    id: str
    url: str
    title: str
    publisher: str = ""
    published_date: str = ""
    accessed_at: datetime = PField(default_factory=utcnow)
    notes: str = ""


class Claim(BaseModel):
    id: str
    text: str
    source_ids: list[str]
    numeric: bool = False
    supporting_snippet: str = ""
    notes: str = ""
    status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_by: str = ""
    verified_at: datetime | None = None


class ResearchPack(BaseModel):
    episode_id: str
    topic: str
    generated_by: str
    sources: list[Source] = []
    claims: list[Claim] = []
    open_questions: list[str] = []

    def claim(self, claim_id: str) -> Claim:
        for c in self.claims:
            if c.id == claim_id:
                return c
        raise KeyError(f"Unknown claim {claim_id}")

    def source(self, source_id: str) -> Source:
        for s in self.sources:
            if s.id == source_id:
                return s
        raise KeyError(f"Unknown source {source_id}")


class VisualSpec(BaseModel):
    kind: str = "card"  # diagram | card | title | footage
    ref: str = ""  # diagram id, footage asset id, or card text
    steps: str = ""  # diagram build steps shown in this scene, e.g. "2" or "0-3"; "" = all
    camera: str = "auto"  # auto | static | wide | focus:x,y,w,h|x,y,w,h (logical 1920x1080)
    note: str = ""


class ScriptParagraph(BaseModel):
    text: str
    claim_ids: list[str] = []
    visual: VisualSpec = VisualSpec()


class ScriptSection(BaseModel):
    id: str
    heading: str
    paragraphs: list[ScriptParagraph]


class Script(BaseModel):
    episode_id: str
    title: str
    generated_by: str
    is_placeholder: bool = False
    sections: list[ScriptSection]
    editorial_notes: list[str] = []

    @property
    def narration_text(self) -> str:
        return "\n\n".join(p.text for s in self.sections for p in s.paragraphs)

    @property
    def word_count(self) -> int:
        return len(self.narration_text.split())


class Scene(BaseModel):
    id: str
    index: int
    section_id: str
    section_heading: str
    narration: str
    claim_ids: list[str]
    visual: VisualSpec
    est_duration_s: float
    starts_section: bool = False
    ends_section: bool = False


class Storyboard(BaseModel):
    episode_id: str
    width: int = 1920
    height: int = 1080
    fps: int = 30
    scenes: list[Scene]

    @property
    def est_duration_s(self) -> float:
        return sum(s.est_duration_s for s in self.scenes)


class AssetRecord(BaseModel):
    id: str
    path: str  # relative to the episode dir
    kind: str  # diagram | card | footage | music | narration | image | font
    origin: str  # generated_local | user_supplied | stock | ai_generated | system
    author: str
    license: str
    license_proof: str  # URL, file path, or statement
    clearance: LicenseClearance = LicenseClearance.UNKNOWN
    source_url: str = ""
    downloaded_at: datetime | None = None
    created_at: datetime = PField(default_factory=utcnow)
    attribution_required: bool = False
    attribution_text: str = ""
    ai_generated: bool = False
    realistic: bool = False
    sha256: str = ""
    notes: str = ""


class AssetManifest(BaseModel):
    episode_id: str
    assets: list[AssetRecord] = []

    def upsert(self, record: AssetRecord) -> None:
        self.assets = [a for a in self.assets if a.id != record.id] + [record]

    def get(self, asset_id: str) -> AssetRecord | None:
        return next((a for a in self.assets if a.id == asset_id), None)


class WordTiming(BaseModel):
    word: str
    start: float
    end: float


class SceneTiming(BaseModel):
    scene_id: str
    start: float
    end: float
    words: list[WordTiming]


class NarrationTrack(BaseModel):
    episode_id: str
    provider: str
    voice: str
    audio_path: str
    duration_s: float
    is_placeholder: bool
    timing_method: str  # exact | sentence_exact_word_interpolated | estimated
    license_asset_id: str
    scenes: list[SceneTiming]


class ShortSpec(BaseModel):
    id: str
    title: str
    hook: str
    narration: str
    claim_ids: list[str] = []
    diagram: str
    diagram_step: int | None = None
    steps: str = ""  # build steps shown, e.g. "1-3" (overrides diagram_step)
    focus: str = ""  # camera boxes "x,y,w,h|x,y,w,h" in diagram coordinates (1920x1080)
    layout: str = "diagram_center"  # diagram_top | diagram_center | hook_card
    link_text: str = ""


class ReviewDecision(BaseModel):
    episode_id: str
    decision: ReviewDecisionKind
    reviewer: str
    note: str = ""
    at: datetime = PField(default_factory=utcnow)
    video_path: str = ""
    video_sha256: str = ""
    ai_disclosure_altered_content: bool | None = None
    blockers_at_decision: list[str] = []
