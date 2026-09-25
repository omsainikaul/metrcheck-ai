import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  Clock, 
  AlertTriangle, 
  CheckCircle2, 
  Users, 
  RefreshCw, 
  Search, 
  SlidersHorizontal,
  ChevronRight,
  UserCheck
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type ReviewItem, 
  type OfficerDashboardSummary, 
  type ReviewStatus 
} from '../types';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';

export default function OfficerDashboard() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<OfficerDashboardSummary | null>(null);
  const [queue, setQueue] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [officers, setOfficers] = useState<Array<{ username: string; full_name: string; role: string }>>([]);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [officerFilter, setOfficerFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Quick Assignment Modal
  const [assignModalReview, setAssignModalReview] = useState<ReviewItem | null>(null);
  const [selectedOfficer, setSelectedOfficer] = useState<string>('');
  const [assignComments, setAssignComments] = useState<string>('');
  const [assigning, setAssigning] = useState<boolean>(false);

  const loadData = async () => {
    try {
      setRefreshing(true);
      const [sumRes, qRes, offRes] = await Promise.all([
        api.getReviewDashboard(),
        api.getReviewQueue(),
        api.getAvailableOfficers()
      ]);
      setSummary(sumRes);
      setQueue(qRes);
      setOfficers(offRes.officers || []);
    } catch (err) {
      console.error("Failed to load officer dashboard data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAssignSubmit = async () => {
    if (!assignModalReview || !selectedOfficer) return;
    setAssigning(true);
    try {
      await api.assignReview(assignModalReview.review_id, selectedOfficer, assignComments);
      setAssignModalReview(null);
      setSelectedOfficer('');
      setAssignComments('');
      await loadData();
    } catch (err: any) {
      alert(err.message || t('audit_review.modal_assign.error_fallback'));
    } finally {
      setAssigning(false);
    }
  };

  // Filter queue items
  const filteredQueue = useMemo(() => {
    return queue.filter(item => {
      if (statusFilter !== 'ALL') {
        if (statusFilter === 'PENDING' && item.status !== 'PENDING_REVIEW') return false;
        if (statusFilter === 'ASSIGNED' && item.status !== 'ASSIGNED') return false;
        if (statusFilter === 'IN_REVIEW' && !['IN_REVIEW', 'CORRECTION_REQUIRED'].includes(item.status)) return false;
        if (statusFilter === 'VERIFIED' && !item.status.startsWith('VERIFIED')) return false;
        if (statusFilter === 'REJECTED' && item.status !== 'REJECTED') return false;
        if (statusFilter === 'ESCALATED' && item.status !== 'ESCALATED') return false;
        if (statusFilter === 'REOPENED' && item.status !== 'REOPENED') return false;
      }
      if (riskFilter !== 'ALL' && item.ai_risk_level.toUpperCase() !== riskFilter.toUpperCase()) {
        return false;
      }
      if (officerFilter !== 'ALL') {
        if (officerFilter === 'UNASSIGNED' && item.assigned_officer) return false;
        if (officerFilter === 'MY_ASSIGNMENTS' && item.assigned_officer?.toLowerCase() !== user?.username.toLowerCase()) return false;
        if (officerFilter !== 'UNASSIGNED' && officerFilter !== 'MY_ASSIGNMENTS' && item.assigned_officer?.toLowerCase() !== officerFilter.toLowerCase()) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        return (
          item.product_name.toLowerCase().includes(q) ||
          item.analysis_id.toLowerCase().includes(q) ||
          (item.assigned_officer && item.assigned_officer.toLowerCase().includes(q))
        );
      }
      return true;
    });
  }, [queue, statusFilter, riskFilter, officerFilter, searchQuery, user]);

  const getStatusBadge = (st: ReviewStatus) => {
    switch (st) {
      case 'PENDING_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">{t('audit_review.badges.pending_review')}</span>;
      case 'ASSIGNED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">{t('audit_review.badges.assigned')}</span>;
      case 'IN_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">{t('audit_review.badges.in_review')}</span>;
      case 'CORRECTION_REQUIRED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">{t('audit_review.badges.corrections_active')}</span>;
      case 'VERIFIED_PASS':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">{t('audit_review.badges.verified_pass')}</span>;
      case 'VERIFIED_FAIL':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-red-500/10 text-red-400 border border-red-500/20">{t('audit_review.badges.verified_fail')}</span>;
      case 'VERIFIED_NEEDS_REVIEW':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">{t('audit_review.badges.verified_needs_review')}</span>;
      case 'REJECTED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">{t('audit_review.badges.rejected')}</span>;
      case 'ESCALATED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">{t('audit_review.badges.escalated')}</span>;
      case 'REOPENED':
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">{t('audit_review.badges.reopened')}</span>;
      default:
        return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700">{st}</span>;
    }
  };

  const getRiskBadge = (risk: string) => {
    const r = risk.toUpperCase();
    if (r === 'CRITICAL') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-red-500/20 text-red-400 border border-red-500/30">{t('audit_review.badges.risk_critical')}</span>;
    if (r === 'HIGH') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">{t('audit_review.badges.risk_high')}</span>;
    if (r === 'MEDIUM') return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">{t('audit_review.badges.risk_medium')}</span>;
    return <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">{t('audit_review.badges.risk_low')}</span>;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-500" />
          <span>{t('audit_review.dashboard.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-8">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2.5">
            <span className="p-2 rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
              <ShieldCheck className="w-6 h-6" />
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              {t('audit_review.dashboard.title')}
            </h1>
            <span className="text-xs font-bold px-2.5 py-1 rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {t('audit_review.dashboard.badge_sec10')}
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            {t('audit_review.dashboard.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-700 hover:border-slate-600 text-sm font-medium text-slate-200 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
            <span>{t('audit_review.dashboard.refresh_queue')}</span>
          </button>
        </div>
      </div>

      {/* KPI Metrics Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-7 gap-3">
        <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{t('audit_review.dashboard.kpi_total_queue')}</span>
          <div className="text-2xl font-black text-white mt-2">{summary?.total_queue ?? 0}</div>
          <span className="text-[10px] text-slate-400 mt-1">{t('audit_review.dashboard.kpi_total_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-amber-950/20 border border-amber-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-amber-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_pending')}</span>
          <div className="text-2xl font-black text-amber-400 mt-2">{summary?.pending_review ?? 0}</div>
          <span className="text-[10px] text-amber-400/70 mt-1">{t('audit_review.dashboard.kpi_pending_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-blue-950/20 border border-blue-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-blue-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_assigned')}</span>
          <div className="text-2xl font-black text-blue-400 mt-2">{summary?.assigned ?? 0}</div>
          <span className="text-[10px] text-blue-400/70 mt-1">{t('audit_review.dashboard.kpi_assigned_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_in_review')}</span>
          <div className="text-2xl font-black text-indigo-400 mt-2">{summary?.in_review ?? 0}</div>
          <span className="text-[10px] text-indigo-400/70 mt-1">{t('audit_review.dashboard.kpi_in_review_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-emerald-950/20 border border-emerald-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_verified')}</span>
          <div className="text-2xl font-black text-emerald-400 mt-2">{summary?.verified ?? 0}</div>
          <span className="text-[10px] text-emerald-400/70 mt-1">{t('audit_review.dashboard.kpi_verified_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-red-950/20 border border-red-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-red-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_rejected')}</span>
          <div className="text-2xl font-black text-red-400 mt-2">{summary?.rejected ?? 0}</div>
          <span className="text-[10px] text-red-400/70 mt-1">{t('audit_review.dashboard.kpi_rejected_desc')}</span>
        </div>

        <div className="p-4 rounded-2xl bg-purple-950/20 border border-purple-500/30 shadow-sm flex flex-col justify-between">
          <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider">{t('audit_review.dashboard.kpi_escalated')}</span>
          <div className="text-2xl font-black text-purple-400 mt-2">{summary?.escalated ?? 0}</div>
          <span className="text-[10px] text-purple-400/70 mt-1">{t('audit_review.dashboard.kpi_escalated_desc')}</span>
        </div>
      </div>

      {/* Main Content Layout: Queue + Workload Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left 3 Columns: Review Queue */}
        <div className="lg:col-span-3 space-y-4">
          {/* Filters Bar */}
          <div className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3">
            <div className="flex flex-col md:flex-row items-center gap-3 justify-between">
              <div className="relative flex-1 w-full">
                <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder={t('audit_review.dashboard.search_placeholder')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-9 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 placeholder-slate-400 focus:outline-hidden focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto">
                <div className="flex items-center gap-1.5 shrink-0">
                  <SlidersHorizontal className="w-3.5 h-3.5 text-slate-400" />
                  <span className="text-xs text-slate-400 font-medium">{t('audit_review.dashboard.filter_status_label')}</span>
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">{t('audit_review.dashboard.status_all')}</option>
                  <option value="PENDING">{t('audit_review.dashboard.status_pending')}</option>
                  <option value="ASSIGNED">{t('audit_review.dashboard.status_assigned')}</option>
                  <option value="IN_REVIEW">{t('audit_review.dashboard.status_in_review')}</option>
                  <option value="VERIFIED">{t('audit_review.dashboard.status_verified')}</option>
                  <option value="REJECTED">{t('audit_review.dashboard.status_rejected')}</option>
                  <option value="ESCALATED">{t('audit_review.dashboard.status_escalated')}</option>
                  <option value="REOPENED">{t('audit_review.dashboard.status_reopened')}</option>
                </select>

                <select
                  value={riskFilter}
                  onChange={(e) => setRiskFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">{t('audit_review.dashboard.risk_all')}</option>
                  <option value="CRITICAL">{t('audit_review.dashboard.risk_critical')}</option>
                  <option value="HIGH">{t('audit_review.dashboard.risk_high')}</option>
                  <option value="MEDIUM">{t('audit_review.dashboard.risk_medium')}</option>
                  <option value="LOW">{t('audit_review.dashboard.risk_low')}</option>
                </select>

                <select
                  value={officerFilter}
                  onChange={(e) => setOfficerFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 focus:outline-hidden focus:border-indigo-500 cursor-pointer"
                >
                  <option value="ALL">{t('audit_review.dashboard.officer_all')}</option>
                  <option value="MY_ASSIGNMENTS">{t('audit_review.dashboard.officer_my_assignments')}</option>
                  <option value="UNASSIGNED">{t('audit_review.dashboard.officer_unassigned')}</option>
                  {officers.map(o => (
                    <option key={o.username} value={o.username}>{o.full_name || o.username}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Queue Items Table */}
          <div className="rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sm text-white">{t('audit_review.dashboard.queue_title')}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                  {filteredQueue.length === 1 
                    ? t('audit_review.dashboard.queue_count_single', { count: filteredQueue.length }) 
                    : t('audit_review.dashboard.queue_count_multiple', { count: filteredQueue.length })}
                </span>
              </div>
              <span className="text-xs text-slate-400">
                {t('audit_review.dashboard.queue_ordering_note')}
              </span>
            </div>

            {filteredQueue.length === 0 ? (
              <div className="p-12 text-center text-slate-400 space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-400/40 mx-auto" />
                <p className="text-sm font-semibold text-slate-300">{t('audit_review.dashboard.empty_title')}</p>
                <p className="text-xs text-slate-400">{t('audit_review.dashboard.empty_desc')}</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800/80">
                {filteredQueue.map(item => (
                  <div
                    key={item.review_id}
                    className="p-4 hover:bg-slate-800/40 transition-colors flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                  >
                    <div className="flex items-start gap-3.5 min-w-0 flex-1">
                      <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 shrink-0 mt-0.5">
                        <AlertTriangle className={`w-5 h-5 ${item.ai_risk_level === 'CRITICAL' ? 'text-red-400' : (item.ai_risk_level === 'HIGH' ? 'text-amber-400' : 'text-slate-400')}`} />
                      </div>

                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-bold text-sm text-white hover:text-indigo-400 transition-colors cursor-pointer" onClick={() => navigate(`/reviews/${item.review_id}`)}>
                            {item.product_name}
                          </span>
                          {getRiskBadge(item.ai_risk_level)}
                          {getStatusBadge(item.status)}
                        </div>

                        <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                          <span className="font-mono text-slate-400">{t('audit_review.dashboard.item_id_prefix')}{item.analysis_id.slice(0, 12)}</span>
                          <span>{t('audit_review.dashboard.item_ai_score')} <strong className="text-slate-200">{item.ai_score.toFixed(1)}/100</strong></span>
                          <span>{t('audit_review.dashboard.item_critical_violations')} <strong className={item.critical_issues_count > 0 ? 'text-red-400' : 'text-slate-200'}>{item.critical_issues_count}</strong></span>
                          {item.assigned_officer ? (
                            <span className="text-indigo-300 font-medium">{t('audit_review.dashboard.item_assigned_prefix', { officer: item.assigned_officer })}</span>
                          ) : (
                            <span className="text-amber-400/80 font-medium">{t('audit_review.dashboard.item_unassigned')}</span>
                          )}
                          <span className="flex items-center gap-1 text-slate-400">
                            <Clock className="w-3 h-3" />
                            {item.age_hours < 24 
                              ? t('audit_review.dashboard.item_age_hours', { hours: item.age_hours }) 
                              : t('audit_review.dashboard.item_age_days', { days: (item.age_hours / 24).toFixed(1) })}
                          </span>
                        </div>

                        {item.review_reasons.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                            {item.review_reasons.slice(0, 3).map((r, i) => (
                              <span key={i} className="text-[10px] px-2 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">
                                {r}
                              </span>
                            ))}
                            {item.review_reasons.length > 3 && (
                              <span className="text-[10px] text-slate-400">
                                {t('audit_review.dashboard.item_more_issues', { count: item.review_reasons.length - 3 })}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                      <button
                        onClick={() => {
                          setAssignModalReview(item);
                          setSelectedOfficer(item.assigned_officer || '');
                        }}
                        className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors cursor-pointer"
                        title={t('audit_review.dashboard.btn_assign_tooltip')}
                      >
                        <UserCheck className="w-4 h-4" />
                      </button>

                      <button
                        onClick={() => navigate(`/reviews/${item.review_id}`)}
                        className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-xs shadow-indigo-950 cursor-pointer"
                      >
                        <span>{t('audit_review.dashboard.btn_inspect_verify')}</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1 Column: Officer Workload Dashboard */}
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 shadow-sm">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
              <Users className="w-4 h-4 text-indigo-400" />
              <h2 className="font-bold text-sm text-white">{t('audit_review.dashboard.workload_title')}</h2>
            </div>

            {summary?.workload.length === 0 ? (
              <p className="text-xs text-slate-400">{t('audit_review.dashboard.no_officers')}</p>
            ) : (
              <div className="space-y-3">
                {summary?.workload.map(off => (
                  <div key={off.officer_username} className="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-200">
                        {off.officer_name}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-indigo-300">
                        {off.officer_role === 'ADMIN' ? t('audit_review.dashboard.role_admin') : (off.officer_role === 'ENFORCEMENT_OFFICER' ? t('audit_review.dashboard.role_enforcement') : t('audit_review.dashboard.role_audit'))}
                      </span>
                    </div>

                    <div className="grid grid-cols-4 gap-1 text-center text-[10px]">
                      <div className="p-1 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-400 block">{t('audit_review.dashboard.workload_total')}</span>
                        <span className="font-bold text-white">{off.total_assigned}</span>
                      </div>
                      <div className="p-1 rounded bg-amber-950/20 border border-amber-500/20">
                        <span className="text-amber-400/70 block">{t('audit_review.dashboard.workload_pending')}</span>
                        <span className="font-bold text-amber-400">{off.pending_count}</span>
                      </div>
                      <div className="p-1 rounded bg-indigo-950/20 border border-indigo-500/20">
                        <span className="text-indigo-400/70 block">{t('audit_review.dashboard.workload_active')}</span>
                        <span className="font-bold text-indigo-400">{off.in_review_count}</span>
                      </div>
                      <div className="p-1 rounded bg-emerald-950/20 border border-emerald-500/20">
                        <span className="text-emerald-400/70 block">{t('audit_review.dashboard.workload_done')}</span>
                        <span className="font-bold text-emerald-400">{off.completed_count}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="p-3 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-xs text-indigo-300 space-y-1">
              <div className="font-bold flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5" />
                {t('audit_review.dashboard.human_authority_title')}
              </div>
              <p className="text-[11px] text-indigo-200/70 leading-relaxed">
                {t('audit_review.dashboard.human_authority_desc')}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Assign Modal */}
      {assignModalReview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-indigo-400" />
                {t('audit_review.modal_assign.title')}
              </h3>
              <button
                onClick={() => setAssignModalReview(null)}
                className="text-slate-400 hover:text-white cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <span className="text-xs text-slate-400">{t('audit_review.modal_assign.target_audit')}</span>
                <p className="text-sm font-bold text-white">{assignModalReview.product_name}</p>
                <p className="text-[10px] font-mono text-slate-400">{t('audit_review.dashboard.item_id_prefix')}{assignModalReview.analysis_id}</p>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_assign.select_officer')}</label>
                <select
                  value={selectedOfficer}
                  onChange={(e) => setSelectedOfficer(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200 focus:outline-hidden focus:border-indigo-500"
                >
                  <option value="">{t('audit_review.modal_assign.choose_officer_placeholder')}</option>
                  {officers.map(o => (
                    <option key={o.username} value={o.username}>
                      {o.full_name || o.username} ({o.role})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_assign.instructions_label')}</label>
                <textarea
                  value={assignComments}
                  onChange={(e) => setAssignComments(e.target.value)}
                  placeholder={t('audit_review.modal_assign.instructions_placeholder')}
                  rows={3}
                  className="w-full p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-hidden focus:border-indigo-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button
                onClick={() => setAssignModalReview(null)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 cursor-pointer"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleAssignSubmit}
                disabled={!selectedOfficer || assigning}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white cursor-pointer"
              >
                {assigning ? t('audit_review.modal_assign.assigning_btn') : t('audit_review.modal_assign.confirm_btn')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
