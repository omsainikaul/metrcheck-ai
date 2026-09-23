import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  FolderOpen,
  Search,
  Scale,
  FileText,
  CheckCircle2,
  UserCheck,
  RefreshCw,
  Eye
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type {
  EnforcementCaseSummary,
  EnforcementDashboardMetrics,
  EnforcementCaseStatus,
  EnforcementCaseSeverity
} from '../types';

export default function EnforcementDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [metrics, setMetrics] = useState<EnforcementDashboardMetrics | null>(null);
  const [cases, setCases] = useState<EnforcementCaseSummary[]>([]);
  const [totalCases, setTotalCases] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [officerFilter, setOfficerFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const loadData = async () => {
    try {
      setRefreshing(true);
      const [mRes, cRes] = await Promise.all([
        api.getEnforcementDashboard(),
        api.listEnforcementCases({
          status: statusFilter,
          severity: severityFilter,
          assigned_officer: officerFilter === 'ME' ? user?.username : undefined,
          search: searchQuery || undefined,
          page_size: 100
        })
      ]);
      setMetrics(mRes);
      setCases(cRes.cases || []);
      setTotalCases(cRes.total || 0);
    } catch (err) {
      console.error('Failed to load enforcement dashboard data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [statusFilter, severityFilter, officerFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const getStatusBadge = (status: EnforcementCaseStatus) => {
    switch (status) {
      case 'OPEN':
        return 'bg-blue-500/15 text-blue-300 border-blue-500/30';
      case 'INVESTIGATION':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'PENALTY_REVIEW':
        return 'bg-orange-500/15 text-orange-300 border-orange-500/30';
      case 'NOTICE_ISSUED':
        return 'bg-purple-500/15 text-purple-300 border-purple-500/30';
      case 'HEARING':
        return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
      case 'RESOLVED':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'CLOSED':
        return 'bg-slate-500/15 text-slate-400 border-slate-500/30';
      default:
        return 'bg-slate-500/15 text-slate-300 border-slate-500/30';
    }
  };

  const getSeverityBadge = (severity: EnforcementCaseSeverity) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
      case 'HIGH':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'MEDIUM':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
      case 'LOW':
        return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-950 border border-slate-800 rounded-2xl p-6 md:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <div className="p-2.5 bg-amber-500/20 border border-amber-500/30 rounded-xl text-amber-400">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h1 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
                Enforcement Case Management
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                DoCA Legal Metrology
              </span>
            </div>
            <p className="text-slate-400 text-sm max-w-2xl">
              Manage statutory legal enforcement proceedings, evaluate penalties under Section 36/38 of the Legal Metrology Act, 2009, issue show-cause notices, and track judicial resolution.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={loadData}
              disabled={refreshing}
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 text-sm font-medium transition-all shadow-sm active:scale-95"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-indigo-400' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Active Cases</span>
              <FolderOpen className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white">{metrics.total_active_cases}</div>
            <div className="text-[11px] text-slate-500">{metrics.open_cases} Open · {metrics.investigation_cases} Inves.</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Assigned To Me</span>
              <UserCheck className="w-4 h-4 text-amber-400" />
            </div>
            <div className="text-2xl font-bold text-amber-300">{metrics.assigned_to_me}</div>
            <div className="text-[11px] text-slate-500">Your direct caseload</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Penalty Review</span>
              <Scale className="w-4 h-4 text-orange-400" />
            </div>
            <div className="text-2xl font-bold text-orange-300">{metrics.penalty_review_cases}</div>
            <div className="text-[11px] text-slate-500">Awaiting sanction calculation</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Notices Issued</span>
              <FileText className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-2xl font-bold text-purple-300">{metrics.notices_issued_cases}</div>
            <div className="text-[11px] text-slate-500">{metrics.total_notices_served} Total served</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Penalties Est.</span>
              <Scale className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-xl font-bold text-emerald-400">
              ₹{(metrics.total_penalties_estimated_inr || 0).toLocaleString('en-IN')}
            </div>
            <div className="text-[11px] text-slate-500">Advisory statutory sum</div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-4 space-y-2">
            <div className="flex items-center justify-between text-slate-400 text-xs">
              <span>Resolved / Closed</span>
              <CheckCircle2 className="w-4 h-4 text-blue-400" />
            </div>
            <div className="text-2xl font-bold text-slate-300">
              {metrics.resolved_cases + metrics.closed_cases}
            </div>
            <div className="text-[11px] text-slate-500">{metrics.closed_cases} Archived cases</div>
          </div>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-4 space-y-4">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search by case reference (e.g. MC-ENF-2026-...), product name, or violation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="INVESTIGATION">Investigation</option>
              <option value="PENALTY_REVIEW">Penalty Review</option>
              <option value="NOTICE_ISSUED">Notice Issued</option>
              <option value="HEARING">Hearing</option>
              <option value="RESOLVED">Resolved</option>
              <option value="CLOSED">Closed</option>
            </select>

            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>

            <select
              value={officerFilter}
              onChange={(e) => setOfficerFilter(e.target.value)}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Officers</option>
              <option value="ME">Assigned to Me</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
            >
              Search
            </button>
          </div>
        </form>
      </div>

      {/* Enforcement Cases List */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-white">Enforcement Case Docket</h2>
            <p className="text-xs text-slate-400 mt-0.5">{totalCases} total case(s) found</p>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-500 space-y-3">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-indigo-500" />
            <p className="text-sm">Loading enforcement dockets...</p>
          </div>
        ) : cases.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-3">
            <FolderOpen className="w-12 h-12 mx-auto text-slate-600" />
            <p className="text-base font-medium text-slate-300">No Enforcement Cases Match Your Filter</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Cases are created directly from escalated packaging compliance reviews or through manual docket opening.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/60 text-slate-400 text-[11px] font-semibold uppercase tracking-wider border-b border-slate-800/80">
                  <th className="py-3 px-4">Case Reference</th>
                  <th className="py-3 px-4">Product / Target</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Assigned Officer</th>
                  <th className="py-3 px-4">Notices</th>
                  <th className="py-3 px-4">Opened Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-xs">
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => navigate(`/enforcement/cases/${c.id}`)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-indigo-400 group-hover:text-indigo-300">
                      {c.case_reference}
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-white max-w-xs truncate">{c.product_name}</div>
                      <div className="text-[11px] text-slate-500 truncate">{c.jurisdiction_state || 'National Jurisdiction'}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded-md border text-[10px] font-bold ${getSeverityBadge(c.severity)}`}>
                        {c.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded-md border text-[10px] font-semibold ${getStatusBadge(c.status)}`}>
                        {c.status.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      {c.assigned_officer ? (
                        <div className="flex items-center gap-1.5 text-slate-300">
                          <UserCheck className="w-3.5 h-3.5 text-slate-500" />
                          <span>@{c.assigned_officer}</span>
                        </div>
                      ) : (
                        <span className="text-slate-600 italic">Unassigned</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      {c.notice_count > 0 ? (
                        <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full font-semibold text-[10px]">
                          {c.notice_count} notice{c.notice_count > 1 ? 's' : ''}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      {c.opened_at ? new Date(c.opened_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/enforcement/cases/${c.id}`);
                        }}
                        className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition-colors inline-flex items-center gap-1"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
