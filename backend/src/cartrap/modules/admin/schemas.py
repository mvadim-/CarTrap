"""Pydantic schemas for admin command center APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from cartrap.modules.auth.schemas import AdminManagedUserResponse, InviteResponse
from cartrap.modules.notifications.schemas import PushSubscriptionResponse
from cartrap.modules.provider_connections.schemas import ProviderConnectionResponse
from cartrap.modules.runtime_settings.schemas import RuntimeSettingResponse, RuntimeSettingUpdatePayload
from cartrap.modules.system_status.schemas import FreshnessEnvelopeResponse, RefreshStateResponse


class AdminOverviewUsersResponse(BaseModel):
    total: int = 0
    admins: int = 0
    regular_users: int = 0
    active_last_24h: int = 0
    active_last_7d: int = 0
    blocked: int = 0
    disabled: int = 0


class AdminOverviewInvitesResponse(BaseModel):
    pending: int = 0
    accepted: int = 0
    revoked: int = 0
    expired: int = 0


class AdminOverviewProvidersResponse(BaseModel):
    total_connections: int = 0
    connected: int = 0
    expiring: int = 0
    reconnect_required: int = 0
    disconnected: int = 0
    error: int = 0
    connected_users: int = 0
    reconnect_required_users: int = 0
    disconnected_users: int = 0


class AdminOverviewSearchesResponse(BaseModel):
    total_saved_searches: int = 0
    users_with_saved_searches: int = 0
    stale_or_problem: int = 0
    searches_with_new_matches: int = 0


class AdminOverviewWatchlistResponse(BaseModel):
    total_tracked_lots: int = 0
    users_with_tracked_lots: int = 0
    unseen_updates: int = 0
    stale_or_problem: int = 0


class AdminOverviewPushResponse(BaseModel):
    total_subscriptions: int = 0
    users_with_push: int = 0
    users_without_push: int = 0


class AdminOverviewSystemResponse(BaseModel):
    live_sync_status: str
    stale: bool = False
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_error_message: Optional[str] = None


class AdminOverviewResponse(BaseModel):
    generated_at: datetime
    users: AdminOverviewUsersResponse
    invites: AdminOverviewInvitesResponse
    providers: AdminOverviewProvidersResponse
    searches: AdminOverviewSearchesResponse
    watchlist: AdminOverviewWatchlistResponse
    push: AdminOverviewPushResponse
    system: AdminOverviewSystemResponse


class AdminSystemHealthResponse(BaseModel):
    generated_at: datetime
    app_name: str
    environment: str
    live_sync: dict
    blocked_users: int = 0
    expired_pending_invites: int = 0
    provider_reconnect_required: int = 0
    saved_search_attention: int = 0
    watchlist_attention: int = 0


class AdminUserDirectoryCountsResponse(BaseModel):
    provider_connections: int = 0
    saved_searches: int = 0
    tracked_lots: int = 0
    push_subscriptions: int = 0


class AdminUserDirectoryFlagsResponse(BaseModel):
    has_pending_invite: bool = False
    has_reconnect_required_provider: bool = False
    has_unseen_watchlist_updates: bool = False


class AdminUserDirectoryRowResponse(BaseModel):
    id: str
    email: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    provider_state: str
    counts: AdminUserDirectoryCountsResponse
    flags: AdminUserDirectoryFlagsResponse


class AdminUserDirectoryResponse(BaseModel):
    items: list[AdminUserDirectoryRowResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25


class AdminSavedSearchSummaryResponse(BaseModel):
    id: str
    label: str
    providers: list[str] = Field(default_factory=list)
    result_count: Optional[int] = None
    cached_result_count: Optional[int] = None
    new_count: int = 0
    last_synced_at: Optional[datetime] = None
    freshness: FreshnessEnvelopeResponse
    refresh_state: RefreshStateResponse
    created_at: datetime


class AdminTrackedLotSummaryResponse(BaseModel):
    id: str
    provider: str
    lot_key: str
    lot_number: str
    title: str
    status: str
    raw_status: str
    current_bid: Optional[float] = None
    buy_now_price: Optional[float] = None
    currency: str
    sale_date: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    freshness: FreshnessEnvelopeResponse
    refresh_state: RefreshStateResponse
    has_unseen_update: bool = False
    latest_change_at: Optional[datetime] = None
    created_at: datetime


class AdminRecentActivityResponse(BaseModel):
    last_login_at: Optional[datetime] = None
    last_saved_search_at: Optional[datetime] = None
    last_tracked_lot_at: Optional[datetime] = None
    last_push_subscription_at: Optional[datetime] = None
    last_provider_activity_at: Optional[datetime] = None
    has_unseen_watchlist_updates: bool = False


class AdminDangerZoneSummaryResponse(BaseModel):
    provider_connections: int = 0
    saved_searches: int = 0
    tracked_lots: int = 0
    push_subscriptions: int = 0
    lot_snapshots: int = 0
    invites: int = 0


class AdminUserDetailResponse(BaseModel):
    account: AdminManagedUserResponse
    counts: AdminUserDirectoryCountsResponse
    invites: list[InviteResponse] = Field(default_factory=list)
    provider_connections: list[ProviderConnectionResponse] = Field(default_factory=list)
    saved_searches: list[AdminSavedSearchSummaryResponse] = Field(default_factory=list)
    tracked_lots: list[AdminTrackedLotSummaryResponse] = Field(default_factory=list)
    push_subscriptions: list[PushSubscriptionResponse] = Field(default_factory=list)
    recent_activity: AdminRecentActivityResponse
    danger_zone: AdminDangerZoneSummaryResponse


class AdminActionRequest(BaseModel):
    provider: Optional[str] = None
    resource_id: Optional[str] = None


class AdminActionResponse(BaseModel):
    action: str
    message: str
    scope: Literal["account", "provider", "resource", "danger"]
    user: Optional[AdminManagedUserResponse] = None
    generated_password: Optional[str] = None
    counts: dict[str, int] = Field(default_factory=dict)


class AdminInviteListResponse(BaseModel):
    items: list[InviteResponse] = Field(default_factory=list)


class AdminRuntimeSettingsResponse(BaseModel):
    groups: list["AdminRuntimeSettingsGroupResponse"] = Field(default_factory=list)


class AdminRuntimeSettingsGroupResponse(BaseModel):
    key: str
    label: str
    items: list[RuntimeSettingResponse] = Field(default_factory=list)


class AdminRuntimeSettingsUpdateRequest(BaseModel):
    updates: list[RuntimeSettingUpdatePayload] = Field(default_factory=list, min_length=1)


class AdminRuntimeSettingsResetRequest(BaseModel):
    keys: list[str] = Field(default_factory=list, min_length=1)
