import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import EmailStr
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    Text,
    Enum,
    func,
)
from app.db.database import Base
from app.db import drop_downs
from app.db.model_utils import uuid_pk, now_utc


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[drop_downs.UserPlan] = mapped_column(Enum(drop_downs.UserPlan),
                                                      nullable=False, unique=True)
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    billing_interval: Mapped[drop_downs.BillingInterval] = mapped_column(
        Enum(drop_downs.BillingInterval, name="billing_interval"),
        nullable=False,
        default=drop_downs.BillingInterval.MONTHLY,
    )

    # Quota limits — None = unlimited
    max_projects: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_documents_per_project: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_queries_per_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Whether this plan is publicly visible in the pricing UI
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc(), onupdate=now_utc()
    )

    # relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Plan name={self.name} price_cents={self.price_cents}>"


class Subscription(Base):
    """
    One active row per user at any time — their current plan + billing state.

    Stripe is the source of truth for payments.
    This table mirrors just enough Stripe state to enforce access locally
    without a Stripe API call on every request.

    Lifecycle:
        1. User picks a plan → Stripe Checkout session created.
        2. Stripe fires `checkout.session.completed` webhook.
        3. Your webhook handler writes/upserts this row with status=ACTIVE.
        4. On renewal: `invoice.paid` → keep status=ACTIVE.
        5. On failed payment: `invoice.payment_failed` → status=PAST_DUE.
        6. On cancellation: `customer.subscription.deleted` → status=CANCELLED.
        7. Middleware checks status + current_period_end before allowing queries.
    """
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = uuid_pk()

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one subscription row per user at all times
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),  # never delete a plan with active subs
        nullable=False,
        index=True,
    )

    status: Mapped[drop_downs.SubscriptionStatus] = mapped_column(
        Enum(drop_downs.SubscriptionStatus, name="subscription_status"),
        nullable=False,
        default=drop_downs.SubscriptionStatus.ACTIVE,
        index=True,
    )

    # Stripe identifiers — needed to open the customer portal and handle webhooks
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    # Current billing window — copied from Stripe on every webhook.
    # Access is allowed while now() < current_period_end AND status == ACTIVE.
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Rolling query counter for the current billing period.
    # Reset to 0 when current_period_start changes (new billing cycle).
    queries_this_period: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Set when the user requests cancellation — Stripe keeps access until period ends
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc(), onupdate=now_utc()
    )

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="subscription", lazy="noload")
    plan: Mapped["Plan"] = relationship("Plan", back_populates="subscriptions", lazy="noload")

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} plan={self.plan_id} status={self.status}>"


class UserApiKey(Base):
    """
    Stores one API key per LLM provider per user (BYOK model).

    SECURITY — never store the raw key.
    Encrypt with Fernet (symmetric) before insert, decrypt at query time.
    Only the last 4 chars are stored in plaintext for display ("...sk-9xAb").

    from cryptography.fernet import Fernet
    key = settings.ENCRYPTION_KEY          # 32-byte base64 secret in .env
    fernet = Fernet(key)
    encrypted = fernet.encrypt(raw_api_key.encode()).decode()

    One row per provider per user — enforced by the unique constraint below.
    If the user rotates their key, UPDATE the existing row, don't INSERT a new one.
    """
    __tablename__ = "user_api_keys"

    __table_args__ = (
        # One key per provider per user
        Index("uq_user_api_keys_user_provider", "user_id", "provider", unique=True),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[drop_downs.LLMProvider] = mapped_column(
        Enum(drop_downs.LLMProvider, name="llm_provider"),
        nullable=False,
    )

    # Fernet-encrypted API key — never the raw value
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Last 4 chars of the raw key for display only — e.g. "9xAb"
    key_hint: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)

    # Optional label the user gives this key ("work key", "personal")
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Set False to disable without deleting — useful for admin key suspension
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc(), onupdate=now_utc()
    )

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys", lazy="noload")

    def __repr__(self) -> str:
        return f"<UserApiKey user={self.user_id} provider={self.provider} hint=...{self.key_hint}>"


class TokenUsageLog(Base):
    """
    One row per LLM call. Drives the usage dashboard.

    In BYOK mode: no billing here — this is purely for the user's
    visibility into their own API spend.

    In Managed LLM mode: cost_usd_micros becomes your billing meter.
    Aggregate it per billing period to know what to charge the user.

    Linked to query_history via query_history_id (nullable — future
    ingestion LLM calls won't have a query_history row).

    cost_usd_micros: integer micro-dollars (1 USD = 1_000_000).
    Integer avoids floating-point rounding errors in aggregations.
    Example: $0.000250 → 250 micros.
    """
    __tablename__ = "token_usage_log"

    __table_args__ = (
        # Most common dashboard query: "all usage for this user, newest first"
        Index("ix_token_usage_log_user_created", "user_id", "created_at"),
        # For billing aggregation: sum cost per user per billing period
        Index("ix_token_usage_log_user_provider_created", "user_id", "provider", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Links back to the Q&A that triggered this call (null for non-query calls)
    query_history_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("query_history.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    provider: Mapped[drop_downs.LLMProvider] = mapped_column(
        Enum(drop_downs.LLMProvider, name="llm_provider"),
        nullable=False,
        index=True,
    )

    # Exact model string as returned by the provider ("gpt-4o", "claude-sonnet-4-20250514")
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Token counts from the provider response
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Micro-dollars (1 USD = 1_000_000). Null in BYOK if you don't track cost.
    # In Managed LLM mode, populate this on every call.
    cost_usd_micros: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=now_utc(), index=True
    )

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="token_usage", lazy="noload")

    def __repr__(self) -> str:
        return (
            f"<TokenUsageLog user={self.user_id} model={self.model} "
            f"in={self.input_tokens} out={self.output_tokens}>"
        )