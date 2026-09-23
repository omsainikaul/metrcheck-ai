import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Scale,
  FileText,
  Clock,
  AlertTriangle,
  Layers,
  Lock,
  ChevronRight
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type {
  EnforcementCaseDetail,
  EnforcementNotice
} from '../types';

export default function EnforcementCaseWorkspace() {
  const { caseId } = useParams<{ caseId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [caseData, setCaseData] = useState<EnforcementCaseDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'OVERVIEW' | 'VIOLATIONS' | 'PENALTIES' | 'NOTICES' | 'TIMELINE'>('OVERVIEW');

  // Action Modals
  const [showPenaltyModal, setShowPenaltyModal] = useState<boolean>(false);
  const [repeatOffence, setRepeatOffence] = useState<boolean>(false);
  const [priorNotices, setPriorNotices] = useState<number>(0);
  const [calculatingPenalty, setCalculatingPenalty] = useState<boolean>(false);

  const [showNoticeModal, setShowNoticeModal] = useState<boolean>(false);
  const [noticeType, setNoticeType] = useState<string>('SHOW_CAUSE');
  const [officerName, setOfficerName] = useState<string>(user?.full_name || 'Legal Metrology Inspector');
  const [officerDesignation, setOfficerDesignation] = useState<string>('Inspector, Legal Metrology');
  const [deadlineDays, setDeadlineDays] = useState<number>(15);
  const [issuingNotice, setIssuingNotice] = useState<boolean>(false);

  const [showCloseModal, setShowCloseModal] = useState<boolean>(false);
  const [closureReason, setClosureReason] = useState<string>('');
  const [resolutionType, setResolutionType] = useState<string>('COMPOUNDED');
  const [closingCase, setClosingCase] = useState<boolean>(false);

  const [showTransitionModal, setShowTransitionModal] = useState<boolean>(false);
  const [targetStatus, setTargetStatus] = useState<string>('');
  const [transitionReason, setTransitionReason] = useState<string>('');
  const [transitioning, setTransitioning] = useState<boolean>(false);

  const [selectedNoticeView, setSelectedNoticeView] = useState<EnforcementNotice | null>(null);

  const loadCase = async () => {
    if (!caseId) return;
    try {
      setLoading(true);
      const data = await api.getEnforcementCase(caseId);
      setCaseData(data);
    } catch (err) {
      console.error('Failed to load enforcement case:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCase();
  }, [caseId]);

  const handleCalculatePenalty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) return;
    setCalculatingPenalty(true);
    try {
      await api.calculateCasePenalty(caseId, repeatOffence, priorNotices);
      setShowPenaltyModal(false);
      await loadCase();
      setActiveTab('PENALTIES');
    } catch (err: any) {
      alert(err.message || 'Failed to calculate statutory penalty.');
    } finally {
      setCalculatingPenalty(false);
    }
  };

  const handleIssueNotice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) return;
    setIssuingNotice(true);
    try {
      await api.issueCaseNotice(caseId, {
        notice_type: noticeType,
        officer_name: officerName,
        officer_designation: officerDesignation,
        deadline_days: deadlineDays
      });
      setShowNoticeModal(false);
      await loadCase();
      setActiveTab('NOTICES');
    } catch (err: any) {
      alert(err.message || 'Failed to issue statutory notice.');
    } finally {
      setIssuingNotice(false);
    }
  };

  const handleCloseCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId || !closureReason) return;
    setClosingCase(true);
    try {
      await api.closeEnforcementCase(caseId, closureReason, resolutionType);
      setShowCloseModal(false);
      await loadCase();
    } catch (err: any) {
      alert(err.message || 'Failed to close enforcement case.');
    } finally {
      setClosingCase(false);
    }
  };

  const handleTransition = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId || !targetStatus || !transitionReason) return;
    setTransitioning(true);
    try {
      await api.transitionEnforcementCase(caseId, targetStatus, transitionReason);
      setShowTransitionModal(false);
      setTargetStatus('');
      setTransitionReason('');
      await loadCase();
    } catch (err: any) {
      alert(err.message || 'Failed to transition case status.');
    } finally {
      setTransitioning(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-slate-400">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading enforcement docket...</span>
        </div>
      </div>
    );
  }

  if (!caseData) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <AlertTriangle className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-white">Enforcement Case Not Found</h2>
        <p className="text-sm text-slate-400">The requested legal docket does not exist or you lack authorization to inspect it.</p>
        <button
          onClick={() => navigate('/enforcement')}
          className="px-4 py-2 bg-slate-800 text-slate-200 rounded-xl text-xs font-semibold hover:bg-slate-700"
        >
          Back to Enforcement Docket
        </button>
      </div>
    );
  }

  const isClosed = caseData.status === 'CLOSED';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-16">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/enforcement')}
            className="p-2 bg-slate-900 border border-slate-800 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold text-amber-400">{caseData.case_reference}</span>
              <span className="text-slate-600">·</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {caseData.status}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                {caseData.severity}
              </span>
            </div>
            <h1 className="text-xl font-bold text-white">{caseData.product_name}</h1>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {!isClosed && (
            <>
              <button
                onClick={() => setShowPenaltyModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
              >
                <Scale className="w-4 h-4" />
                <span>Evaluate Penalty</span>
              </button>

              <button
                onClick={() => setShowNoticeModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold shadow-sm transition-all"
              >
                <FileText className="w-4 h-4" />
                <span>Issue SCN Notice</span>
              </button>

              <button
                onClick={() => setShowTransitionModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl border border-slate-700 text-xs font-semibold transition-all"
              >
                <ChevronRight className="w-4 h-4" />
                <span>Update State</span>
              </button>

              <button
                onClick={() => setShowCloseModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-rose-900/40 text-rose-300 rounded-xl border border-rose-800/40 text-xs font-semibold transition-all"
              >
                <Lock className="w-4 h-4" />
                <span>Close Case</span>
              </button>
            </>
          )}

          {isClosed && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-400">
              <Lock className="w-3.5 h-3.5 text-slate-500" />
              <span>Case Closed ({caseData.closure_reason || 'Archived'})</span>
            </div>
          )}
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
        {[
          { id: 'OVERVIEW', label: 'Docket Overview', icon: Layers },
          { id: 'VIOLATIONS', label: `Violations (${caseData.violations.length})`, icon: AlertTriangle },
          { id: 'PENALTIES', label: `Penalty Calculations (${caseData.penalties.length})`, icon: Scale },
          { id: 'NOTICES', label: `Statutory Notices (${caseData.notices.length})`, icon: FileText },
          { id: 'TIMELINE', label: `Auditable Timeline (${caseData.timeline.length})`, icon: Clock }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                isActive
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab 1: Docket Overview */}
      {activeTab === 'OVERVIEW' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                Violation & Case Summary
              </h3>
              <p className="text-slate-200 text-sm leading-relaxed bg-slate-950 p-4 rounded-xl border border-slate-800/80">
                {caseData.violation_summary || 'No summary notes specified.'}
              </p>

              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-2">
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-[11px] text-slate-500 block">Jurisdiction State</span>
                  <span className="text-xs font-semibold text-slate-200">{caseData.jurisdiction_state || 'National'}</span>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-[11px] text-slate-500 block">District Jurisdiction</span>
                  <span className="text-xs font-semibold text-slate-200">{caseData.jurisdiction_district || 'Directorate HQ'}</span>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800">
                  <span className="text-[11px] text-slate-500 block">Investigating Officer</span>
                  <span className="text-xs font-semibold text-amber-400">
                    {caseData.assigned_officer ? `@${caseData.assigned_officer}` : 'Unassigned'}
                  </span>
                </div>
              </div>
            </div>

            {/* Linked Analysis Reference */}
            {caseData.source_analysis && (
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                    Source Packaging Screening
                  </h3>
                  <button
                    onClick={() => navigate(`/results/${caseData.analysis_id}`)}
                    className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 font-semibold"
                  >
                    <span>View Inspection Report</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                </div>

                <div className="flex items-center gap-4 bg-slate-950 p-4 rounded-xl border border-slate-800">
                  {caseData.source_analysis.image_filename && (
                    <img
                      src={`/api/images/${caseData.source_analysis.image_filename}`}
                      alt="Package specimen"
                      className="w-16 h-16 object-cover rounded-lg border border-slate-800"
                    />
                  )}
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="text-sm font-semibold text-white truncate">{caseData.source_analysis.product_name}</div>
                    <div className="text-xs text-slate-400">
                      Screening Score: <strong className="text-rose-400">{caseData.source_analysis.score}/100</strong> · Status: {caseData.source_analysis.status}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column Details */}
          <div className="space-y-6">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
              <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                Statutory Status
              </h3>
              <div className="space-y-3 text-xs">
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Opened At</span>
                  <span className="text-slate-200">{new Date(caseData.opened_at).toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Created By</span>
                  <span className="text-slate-200">@{caseData.created_by}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Notices Issued</span>
                  <span className="text-purple-300 font-semibold">{caseData.notices.length} Notice(s)</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Penalty Status</span>
                  <span className="text-emerald-400 font-semibold">
                    {caseData.penalties.length > 0 ? `₹${caseData.penalties[0].estimated_fine_inr.toLocaleString('en-IN')}` : 'Not Evaluated'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Violations */}
      {activeTab === 'VIOLATIONS' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
          <h3 className="text-base font-bold text-white">Detected Packaging Violations</h3>
          <p className="text-xs text-slate-400">Evidence and statutory contraventions identified under the Packaged Commodities Rules, 2011.</p>

          <div className="space-y-3 pt-2">
            {caseData.violations.map((v, idx) => (
              <div key={idx} className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-rose-400 uppercase tracking-wider">{v.rule_id || 'Statutory Rule'}</span>
                  <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                    {v.severity.toUpperCase()}
                  </span>
                </div>
                <div className="text-sm font-medium text-white">{v.what}</div>
                <div className="text-xs text-slate-400">Reference: {v.source_reference}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Penalties */}
      {activeTab === 'PENALTIES' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Advisory Penalty Evaluation History</h3>
                <p className="text-xs text-slate-400">Calculated under Section 36(1) and Section 38 of the Legal Metrology Act, 2009.</p>
              </div>
              {!isClosed && (
                <button
                  onClick={() => setShowPenaltyModal(true)}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold transition-all"
                >
                  Recalculate Penalty
                </button>
              )}
            </div>

            {caseData.penalties.length === 0 ? (
              <div className="p-8 text-center text-slate-500 space-y-2">
                <Scale className="w-8 h-8 mx-auto text-slate-600" />
                <p className="text-sm">No penalty evaluations recorded for this case yet.</p>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {caseData.penalties.map((p) => (
                  <div key={p.id} className="bg-slate-950 p-5 rounded-xl border border-slate-800/80 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl font-bold text-emerald-400">₹{p.estimated_fine_inr.toLocaleString('en-IN')}</span>
                        <span className="text-xs text-slate-500">(Range: ₹{p.fine_range_min_inr.toLocaleString('en-IN')} – ₹{p.fine_range_max_inr.toLocaleString('en-IN')})</span>
                      </div>
                      <span className="text-xs text-slate-400">{new Date(p.calculated_at).toLocaleString('en-IN')}</span>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">{p.basis}</p>

                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      {p.sections.map((sec, i) => (
                        <span key={i} className="px-2 py-0.5 bg-slate-900 text-slate-300 border border-slate-800 rounded-md text-[10px]">
                          {sec}
                        </span>
                      ))}
                      {p.repeat_offence && (
                        <span className="px-2 py-0.5 bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded-md text-[10px] font-bold">
                          Subsequent Offence Clause Applied
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Statutory Notices */}
      {activeTab === 'NOTICES' && (
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-lg">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white">Statutory Notice Ledger</h3>
                <p className="text-xs text-slate-400">Court-ready Show Cause Notices issued to manufacturer/packer.</p>
              </div>
              {!isClosed && (
                <button
                  onClick={() => setShowNoticeModal(true)}
                  className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold transition-all"
                >
                  Issue New Notice
                </button>
              )}
            </div>

            {caseData.notices.length === 0 ? (
              <div className="p-8 text-center text-slate-500 space-y-2">
                <FileText className="w-8 h-8 mx-auto text-slate-600" />
                <p className="text-sm">No statutory notices issued under this docket.</p>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {caseData.notices.map((n) => (
                  <div key={n.id} className="bg-slate-950 p-5 rounded-xl border border-slate-800/80 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm font-bold text-purple-400">{n.notice_reference}</span>
                        <span className="px-2 py-0.5 bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full text-[10px] font-semibold">
                          {n.notice_type}
                        </span>
                      </div>
                      <span className="text-xs text-slate-400">{new Date(n.issued_at).toLocaleDateString('en-IN')}</span>
                    </div>

                    <div className="text-xs text-slate-300">
                      Recipient: <strong>{n.recipient_name}</strong> · Response Deadline: <strong>{n.deadline_days} days</strong>
                    </div>

                    <div className="flex items-center gap-2 pt-2">
                      <button
                        onClick={() => setSelectedNoticeView(n)}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition-colors"
                      >
                        Inspect Notice Text
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 5: Auditable Timeline */}
      {activeTab === 'TIMELINE' && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6 shadow-lg">
          <h3 className="text-base font-bold text-white">Immutable Case Audit Timeline</h3>
          
          <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {caseData.timeline.map((evt) => (
              <div key={evt.event_id} className="relative space-y-1 text-xs">
                <div className="absolute -left-6 top-1 w-2.5 h-2.5 rounded-full bg-amber-500 border-2 border-slate-900" />
                <div className="flex items-center gap-2">
                  <span className="font-bold text-slate-200">{evt.action.replace('_', ' ')}</span>
                  <span className="text-slate-500">by @{evt.actor_username}</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-500">{new Date(evt.timestamp).toLocaleString('en-IN')}</span>
                </div>
                <p className="text-slate-400 leading-relaxed">{evt.details}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Modal: Calculate Penalty */}
      {showPenaltyModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-bold text-white">Evaluate Statutory Penalty</h3>
            <p className="text-xs text-slate-400">Applies Section 36/38 penalty brackets based on detected violation count and severity weights.</p>
            
            <form onSubmit={handleCalculatePenalty} className="space-y-4">
              <label className="flex items-center gap-3 p-3 bg-slate-950 rounded-xl border border-slate-800 cursor-pointer">
                <input
                  type="checkbox"
                  checked={repeatOffence}
                  onChange={(e) => setRepeatOffence(e.target.checked)}
                  className="rounded text-amber-500 focus:ring-0"
                />
                <span className="text-xs text-slate-200">Mark as Subsequent / Repeat Offence (Higher Fine Cap)</span>
              </label>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Prior Notices Served</label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={priorNotices}
                  onChange={(e) => setPriorNotices(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowPenaltyModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={calculatingPenalty}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold"
                >
                  {calculatingPenalty ? 'Evaluating...' : 'Run Evaluation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Issue SCN Notice */}
      {showNoticeModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-lg w-full space-y-4">
            <h3 className="text-lg font-bold text-white">Generate Statutory Show-Cause Notice</h3>
            <p className="text-xs text-slate-400">Drafts official statutory notice citing specific non-compliances under Rule 32 of LMPC Rules, 2011.</p>
            
            <form onSubmit={handleIssueNotice} className="space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Notice Type</label>
                <select
                  value={noticeType}
                  onChange={(e) => setNoticeType(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                >
                  <option value="SHOW_CAUSE">Statutory Show Cause Notice (Rule 32)</option>
                  <option value="COMPOUNDING">Notice of Compounding Offence (Section 48)</option>
                  <option value="SEIZURE_WARNING">Seizure & Inspection Warning Notice</option>
                  <option value="INSPECTION_SUMMONS">Official Summons / Inspection Notice</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Signing Officer Name</label>
                <input
                  type="text"
                  value={officerName}
                  onChange={(e) => setOfficerName(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Officer Designation</label>
                <input
                  type="text"
                  value={officerDesignation}
                  onChange={(e) => setOfficerDesignation(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Response Deadline (Days)</label>
                <input
                  type="number"
                  min="1"
                  max="90"
                  value={deadlineDays}
                  onChange={(e) => setDeadlineDays(parseInt(e.target.value) || 15)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowNoticeModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={issuingNotice}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold"
                >
                  {issuingNotice ? 'Issuing...' : 'Issue & Archive Notice'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: View Notice Content */}
      {selectedNoticeView && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-2xl w-full space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">{selectedNoticeView.notice_reference}</h3>
                <p className="text-xs text-slate-400">Issued on {new Date(selectedNoticeView.issued_at).toLocaleString('en-IN')}</p>
              </div>
              <button
                onClick={() => setSelectedNoticeView(null)}
                className="p-1.5 text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">
              {selectedNoticeView.content}
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedNoticeView(null)}
                className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Close View
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Update Case State */}
      {showTransitionModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-bold text-white">Update Docket Lifecycle State</h3>
            
            <form onSubmit={handleTransition} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Target State</label>
                <select
                  value={targetStatus}
                  onChange={(e) => setTargetStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                >
                  <option value="">Select target state...</option>
                  <option value="INVESTIGATION">INVESTIGATION</option>
                  <option value="PENALTY_REVIEW">PENALTY_REVIEW</option>
                  <option value="NOTICE_ISSUED">NOTICE_ISSUED</option>
                  <option value="HEARING">HEARING</option>
                  <option value="RESOLVED">RESOLVED</option>
                  <option value="CLOSED">CLOSED</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Reason / Justification</label>
                <textarea
                  rows={3}
                  value={transitionReason}
                  onChange={(e) => setTransitionReason(e.target.value)}
                  placeholder="Record formal justification for stage transition..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowTransitionModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={transitioning}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold"
                >
                  {transitioning ? 'Updating...' : 'Confirm Transition'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Close Case */}
      {showCloseModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-lg font-bold text-white">Formally Close Enforcement Case</h3>
            <p className="text-xs text-slate-400">Archived cases remain fully auditable in the timeline.</p>
            
            <form onSubmit={handleCloseCase} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Resolution Type</label>
                <select
                  value={resolutionType}
                  onChange={(e) => setResolutionType(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                >
                  <option value="COMPOUNDED">Compounded (Fine Paid)</option>
                  <option value="COMPLIED">Complied with Advisory / Packaging Corrected</option>
                  <option value="PROSECUTION_INITIATED">Prosecution Initiated in Court</option>
                  <option value="DISMISSED">Dismissed / No Statutory Offence</option>
                  <option value="WITHDRAWN">Withdrawn</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-400">Closure Reason</label>
                <textarea
                  rows={3}
                  value={closureReason}
                  onChange={(e) => setClosureReason(e.target.value)}
                  placeholder="Mandatory summary of case resolution..."
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white"
                  required
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCloseModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={closingCase}
                  className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold"
                >
                  {closingCase ? 'Closing...' : 'Close & Archive'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
