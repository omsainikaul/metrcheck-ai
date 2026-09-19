import { 
  type AnalysisResponse, 
  type DashboardStats, 
  type HistoryItem, 
  type ComplianceRule, 
  type AuthUser, 
  type TrendPoint, 
  type StatusBreakdown, 
  type PenaltyEstimate, 
  type ShowCauseNotice, 
  type ProductInfo, 
  type ComplianceResult, 
  type RuleTestRequest, 
  type RuleTestResponse, 
  type RuleConflictItem, 
  type ScoringConfiguration, 
  type ScoreHistoryEntry, 
  type ProductRiskHistory, 
  type BatchRiskDistribution,
  type PreprintUploadResponse,
  type PreprintAnalysisResponse,
  type PreprintApprovalRequest,
  type ArtworkDocument,
  type VersionComparisonRequest,
  type VersionComparisonResult,
  type VersionTimelineEvent,
  type OfficerDashboardSummary,
  type ReviewItem,
  type ReviewDetailResponse,
  type AIvsHumanComparison,
  type ReviewHistoryEvent
} from '../types';

const API_HOST = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const BASE_URL = API_HOST ? `${API_HOST}/api` : '/api';

const TOKEN_KEY = 'metrcheck-token';

export const tokenStore = {
  get: (): string | null => {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set: (token: string) => {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
  },
  clear: () => {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

function authHeaders(): Record<string, string> {
  const token = tokenStore.get();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(options?.headers as Record<string, string> | undefined),
    ...authHeaders(),
  };
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    if (response.status === 401) {
      if (!url.includes('/auth/login')) {
        tokenStore.clear();
      }
      throw new Error(detail?.detail || 'Authentication required. Please log in again.');
    }
    throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────
  login: (username: string, password: string): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  forgotPassword: (identifier: string): Promise<{ message: string; dev_token?: string }> =>
    fetchJSON<{ message: string; dev_token?: string }>(`${BASE_URL}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    }),

  verifyResetToken: (token: string): Promise<{ valid: boolean; username?: string }> =>
    fetchJSON<{ valid: boolean; username?: string }>(`${BASE_URL}/auth/verify-reset-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  resetPassword: (token: string, new_password: string): Promise<{ message: string }> =>
    fetchJSON<{ message: string }>(`${BASE_URL}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password }),
    }),

  verifyInvitation: (token: string): Promise<import('../types').InvitationVerification> =>
    fetchJSON<import('../types').InvitationVerification>(`${BASE_URL}/auth/verify-invitation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    }),

  activateAccount: (token: string, password: string): Promise<{ message: string; username: string }> =>
    fetchJSON<{ message: string; username: string }>(`${BASE_URL}/auth/activate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, password }),
    }),

  register: (body: { username: string; email: string; password: string; full_name?: string; role?: string }): Promise<{ token: string; user: AuthUser }> =>
    fetchJSON<{ token: string; user: AuthUser }>(`${BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  getMe: (): Promise<AuthUser> => fetchJSON<AuthUser>(`${BASE_URL}/auth/me`),

  updateMyEmail: (email: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/me/email`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }),

  // ── Administration API (/api/admin) ──────────────────────────────────
  adminGetUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/admin/users`),

  adminProvisionUser: (body: {
    full_name?: string;
    username: string;
    email: string;
    role: string;
    jurisdiction?: string;
  }): Promise<{ message: string; user: AuthUser; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; user: AuthUser; dev_invitation_token?: string }>(`${BASE_URL}/admin/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  adminResendInvitation: (username: string): Promise<{ message: string; username: string; dev_invitation_token?: string }> =>
    fetchJSON<{ message: string; username: string; dev_invitation_token?: string }>(
      `${BASE_URL}/admin/users/${encodeURIComponent(username)}/resend-invitation`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    ),

  adminSuspendUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/suspend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminReactivateUser: (username: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/reactivate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    }),

  adminChangeRole: (username: string, role: string): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/admin/users/${encodeURIComponent(username)}/change-role`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role }),
    }),

  adminDeleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  adminGetAuditLogs: (limit = 50): Promise<import('../types').AccountAuditLog[]> =>
    fetchJSON<import('../types').AccountAuditLog[]>(`${BASE_URL}/admin/audit-logs?limit=${limit}`),

  // Legacy User APIs
  getUsers: (): Promise<AuthUser[]> => fetchJSON<AuthUser[]>(`${BASE_URL}/auth/users`),

  createUser: (body: { username: string; email?: string; password: string; full_name?: string; jurisdiction?: string; role?: string }): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

  updateUser: (
    username: string,
    updates: { full_name?: string; jurisdiction?: string; email?: string; role?: string; new_password?: string }
  ): Promise<AuthUser> =>
    fetchJSON<AuthUser>(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }),

  deleteUser: async (username: string): Promise<void> => {
    const headers: Record<string, string> = {
      ...authHeaders(),
    };
    const response = await fetch(`${BASE_URL}/auth/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers,
    });
    if (response.status === 401) {
      tokenStore.clear();
      throw new Error('Authentication required. Please log in again.');
    }
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail || `API error: ${response.status} ${response.statusText}`);
    }
  },

  // ── Analyses ──────────────────────────────────────────────────────────
  analyzeProduct: async (file: File): Promise<AnalysisResponse> => {
    const formData = new FormData();
    formData.append('files', file);
    formData.append('labels', JSON.stringify(['Front']));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeProducts: async (items: { file: File; label: string }[]): Promise<AnalysisResponse> => {
    const formData = new FormData();
    const labels: string[] = [];
    items.forEach((item) => {
      formData.append('files', item.file);
      labels.push(item.label || 'Front');
    });
    formData.append('labels', JSON.stringify(labels));
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeText: (text: string): Promise<AnalysisResponse> =>
    fetchJSON<AnalysisResponse>(`${BASE_URL}/analyze/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  getDashboardStats: (): Promise<DashboardStats> => {
    return fetchJSON<DashboardStats>(`${BASE_URL}/stats`);
  },

  getTrends: (days = 14): Promise<TrendPoint[]> => {
    return fetchJSON<TrendPoint[]>(`${BASE_URL}/stats/trends?days=${days}`);
  },

  getStatusBreakdown: (): Promise<StatusBreakdown[]> => {
    return fetchJSON<StatusBreakdown[]>(`${BASE_URL}/stats/by-status`);
  },

  getHistory: (): Promise<HistoryItem[]> => {
    return fetchJSON<HistoryItem[]>(`${BASE_URL}/history`);
  },

  searchHistory: (q: string, status = 'ALL', limit = 50): Promise<{ items: HistoryItem[]; total: number }> => {
    const params = new URLSearchParams({ q, status, limit: String(limit) });
    return fetchJSON<{ items: HistoryItem[]; total: number }>(`${BASE_URL}/history/search?${params}`);
  },

  getAnalysis: (id: string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/history/${id}`);
  },

  deleteAnalysis: (id: string): Promise<{ message: string; id: string }> => {
    return fetchJSON<{ message: string; id: string }>(`${BASE_URL}/history/${id}`, {
      method: 'DELETE',
    });
  },

  clearHistory: (): Promise<{ message: string; deleted_count: number }> => {
    return fetchJSON<{ message: string; deleted_count: number }>(`${BASE_URL}/history`, {
      method: 'DELETE',
    });
  },

  // ── Enforcement (officer/admin only) ──────────────────────────────────
  estimatePenalty: (analysisId: string): Promise<PenaltyEstimate> => {
    return fetchJSON<PenaltyEstimate>(`${BASE_URL}/enforcement/penalty`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  showCauseNotice: (analysisId: string): Promise<ShowCauseNotice> => {
    return fetchJSON<ShowCauseNotice>(`${BASE_URL}/enforcement/notice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysis_id: analysisId }),
    });
  },

  // ── Demo / reference / misc ───────────────────────────────────────────
  getDemoCases: (): Promise<import('../types').DemoCaseMeta[]> => {
    return fetchJSON<import('../types').DemoCaseMeta[]>(`${BASE_URL}/demo/cases`);
  },

  getDemoCase: (caseNum: number | string): Promise<AnalysisResponse> => {
    return fetchJSON<AnalysisResponse>(`${BASE_URL}/demo/${caseNum}`);
  },

  getComplianceRules: (params?: { category?: string; domain?: string; version?: string }): Promise<ComplianceRule[]> => {
    const query = new URLSearchParams();
    if (params?.category) query.append('category', params.category);
    if (params?.domain) query.append('domain', params.domain);
    if (params?.version) query.append('version', params.version);
    const qs = query.toString();
    return fetchJSON<ComplianceRule[]>(`${BASE_URL}/compliance/rules${qs ? `?${qs}` : ''}`);
  },

  getComplianceRuleDetail: (ruleId: string): Promise<ComplianceRule> => {
    return fetchJSON<ComplianceRule>(`${BASE_URL}/compliance/rules/${encodeURIComponent(ruleId)}`);
  },

  testComplianceRule: (req: RuleTestRequest): Promise<RuleTestResponse> => {
    return fetchJSON<RuleTestResponse>(`${BASE_URL}/compliance/test-rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
  },

  getAnalysisConflicts: (analysisId: string): Promise<{ analysis_id: string; conflicts: RuleConflictItem[] }> => {
    return fetchJSON<{ analysis_id: string; conflicts: RuleConflictItem[] }>(`${BASE_URL}/compliance/conflicts/${encodeURIComponent(analysisId)}`);
  },

  getHealth: (): Promise<any> => {
    return fetchJSON<any>(`${BASE_URL}/health`);
  },
  getReportUrl: (id: string, lang?: string): string => {
    const params = new URLSearchParams();
    if (lang && lang !== 'en') {
      params.append('lang', lang);
    }
    const token = tokenStore.get();
    if (token) {
      params.append('token', token);
    }
    const qs = params.toString();
    return `${BASE_URL}/report/${id}${qs ? `?${qs}` : ''}`;
  },
  getCsvReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/csv${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getXlsxReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/xlsx${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getJsonReportUrl: (id: string): string => {
    const token = tokenStore.get();
    return `${BASE_URL}/report/${id}/json${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  },
  getAssetUrl: (url: string): string => {
    if (!url) return '';
    if (url.startsWith('data:')) return url;
    let cleanUrl = url.startsWith('/uploads/') ? url.replace('/uploads/', '/api/images/') : url;
    let fullUrl = (cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://'))
      ? cleanUrl
      : (API_HOST ? `${API_HOST}${cleanUrl}` : cleanUrl);
    const token = tokenStore.get();
    if (token && !fullUrl.includes('token=')) {
      const sep = fullUrl.includes('?') ? '&' : '?';
      return `${fullUrl}${sep}token=${encodeURIComponent(token)}`;
    }
    return fullUrl;
  },
  extractText: (text: string): Promise<ProductInfo> =>
    fetchJSON<ProductInfo>(`${BASE_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    }),

  checkCompliance: (info: ProductInfo): Promise<ComplianceResult> =>
    fetchJSON<ComplianceResult>(`${BASE_URL}/compliance/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(info),
    }),

  // ── Scoring & Risk (Section 7) ──────────────────────────────────────────
  getScoringConfig: (): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`),

  updateScoringConfig: (config: ScoringConfiguration): Promise<ScoringConfiguration> =>
    fetchJSON<ScoringConfiguration>(`${BASE_URL}/scoring/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  getScoreHistory: (analysisId: string): Promise<ScoreHistoryEntry> =>
    fetchJSON<ScoreHistoryEntry>(`${BASE_URL}/scoring/history/${encodeURIComponent(analysisId)}`),

  getProductRiskHistory: (productName: string): Promise<ProductRiskHistory> =>
    fetchJSON<ProductRiskHistory>(`${BASE_URL}/scoring/product/${encodeURIComponent(productName)}/history`),

  getBatchRiskDistribution: (ownerUserId?: string): Promise<BatchRiskDistribution> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<BatchRiskDistribution>(`${BASE_URL}/scoring/batch-distribution${qs}`);
  },

  // ── Pre-Print Packaging Compliance (Section 8) ──────────────────────────
  uploadArtwork: async (file: File, parentArtworkId?: string, iterationNumber = 1): Promise<PreprintUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (parentArtworkId) {
      formData.append('parent_artwork_id', parentArtworkId);
    }
    formData.append('iteration_number', String(iterationNumber));
    return fetchJSON<PreprintUploadResponse>(`${BASE_URL}/preprint/upload`, {
      method: 'POST',
      body: formData,
    });
  },

  analyzeArtwork: (artworkId: string, productName?: string, category?: string): Promise<PreprintAnalysisResponse> => {
    const params = new URLSearchParams();
    if (productName) params.append('product_name', productName);
    if (category) params.append('category', category);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/analyze${qs}`, {
      method: 'POST',
    });
  },

  getArtwork: (artworkId: string): Promise<ArtworkDocument> =>
    fetchJSON<ArtworkDocument>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`),

  uploadArtworkCorrection: async (artworkId: string, file: File): Promise<PreprintAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    return fetchJSON<PreprintAnalysisResponse>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/correction-upload`, {
      method: 'POST',
      body: formData,
    });
  },

  submitArtworkApproval: (artworkId: string, req: PreprintApprovalRequest): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  listArtworks: (ownerUserId?: string): Promise<{ artworks: ArtworkDocument[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ artworks: ArtworkDocument[]; total: number }>(`${BASE_URL}/preprint${qs}`);
  },

  deleteArtwork: (artworkId: string): Promise<{ success: boolean; message: string }> =>
    fetchJSON<{ success: boolean; message: string }>(`${BASE_URL}/preprint/${encodeURIComponent(artworkId)}`, {
      method: 'DELETE',
    }),

  // ── Section 9 Version Comparison ─────────────────────────────────────────
  compareVersions: (req: VersionComparisonRequest): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),

  getComparison: (comparisonId: string): Promise<VersionComparisonResult> =>
    fetchJSON<VersionComparisonResult>(`${BASE_URL}/versions/comparisons/${encodeURIComponent(comparisonId)}`),

  listComparisons: (ownerUserId?: string, limit = 50): Promise<{ comparisons: VersionComparisonResult[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}&limit=${limit}` : `?limit=${limit}`;
    return fetchJSON<{ comparisons: VersionComparisonResult[]; total: number }>(`${BASE_URL}/versions/comparisons${qs}`);
  },

  getVersionTimeline: (entityId: string): Promise<{ entity_id: string; events: VersionTimelineEvent[]; total: number }> =>
    fetchJSON<{ entity_id: string; events: VersionTimelineEvent[]; total: number }>(`${BASE_URL}/versions/timeline/${encodeURIComponent(entityId)}`),

  getVersionTargets: (ownerUserId?: string): Promise<{ targets: any[]; total: number }> => {
    const qs = ownerUserId ? `?owner_user_id=${encodeURIComponent(ownerUserId)}` : '';
    return fetchJSON<{ targets: any[]; total: number }>(`${BASE_URL}/versions/targets${qs}`);
  },

  // ── Section 10 Human Verification / Officer Workflow ─────────────────────
  getReviewDashboard: (): Promise<OfficerDashboardSummary> =>
    fetchJSON<OfficerDashboardSummary>(`${BASE_URL}/reviews/dashboard`),

  getReviewQueue: (status?: string, assignedOfficer?: string, riskLevel?: string, limit = 100): Promise<ReviewItem[]> => {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (assignedOfficer) params.append('assigned_officer', assignedOfficer);
    if (riskLevel) params.append('risk_level', riskLevel);
    params.append('limit', String(limit));
    return fetchJSON<ReviewItem[]>(`${BASE_URL}/reviews/queue?${params.toString()}`);
  },

  getAvailableOfficers: (): Promise<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }> =>
    fetchJSON<{ officers: Array<{ username: string; full_name: string; role: string; status: string }>; total: number }>(`${BASE_URL}/reviews/officers`),

  getReviewDetails: (reviewId: string): Promise<ReviewDetailResponse> =>
    fetchJSON<ReviewDetailResponse>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}`),

  assignReview: (reviewId: string, assignedOfficer: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/assign`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_officer: assignedOfficer, comments }),
    }),

  acceptReview: (reviewId: string, comments?: string, finalStatus?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ comments, final_status: finalStatus }),
    }),

  rejectReview: (reviewId: string, rejectionReason: string, comments: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rejection_reason: rejectionReason, comments }),
    }),

  correctReviewField: (
    reviewId: string, 
    fieldName: string, 
    fieldLabel: string, 
    correctedValue: string, 
    reason?: string, 
    evidenceId?: string
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/correct-field`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        field_name: fieldName,
        field_label: fieldLabel,
        corrected_value: correctedValue,
        reason,
        evidence_id: evidenceId
      }),
    }),

  addReviewEvidence: (
    reviewId: string,
    data: {
      image_index: number;
      image_label: string;
      text: string;
      bbox?: number[];
      linked_rule_id: string;
      linked_field: string;
      comments?: string;
    }
  ): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  removeReviewEvidence: (reviewId: string, evidenceId: string, reason: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/evidence/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ evidence_id: evidenceId, reason }),
    }),

  addReviewComment: (reviewId: string, text: string, commentType = 'GENERAL'): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, comment_type: commentType }),
    }),

  escalateReview: (reviewId: string, escalationReason: string, comments?: string, escalationTarget?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/escalate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        escalation_reason: escalationReason,
        comments,
        escalation_target: escalationTarget
      }),
    }),

  reopenReview: (reviewId: string, reopenReason: string, comments?: string): Promise<any> =>
    fetchJSON<any>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/reopen`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reopen_reason: reopenReason, comments }),
    }),

  getAIvsHumanDiff: (reviewId: string): Promise<AIvsHumanComparison> =>
    fetchJSON<AIvsHumanComparison>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/ai-vs-human`),

  getReviewHistory: (reviewId: string): Promise<{ review_id: string; history: ReviewHistoryEvent[]; total: number }> =>
    fetchJSON<{ review_id: string; history: ReviewHistoryEvent[]; total: number }>(`${BASE_URL}/reviews/${encodeURIComponent(reviewId)}/history`),
};

export default api;