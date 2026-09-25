import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ShieldCheck, 
  ArrowLeft, 
  CheckCircle2, 
  XCircle, 
  Edit3, 
  PlusCircle, 
  Trash2, 
  MessageSquare, 
  RotateCcw, 
  ArrowUpRight, 
  Clock, 
  UserCheck, 
  Layers, 
  Sparkles,
  GitCompare
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type ReviewDetailResponse, 
  type AIvsHumanComparison
} from '../types';
import EvidenceViewer from '../components/EvidenceViewer';
import { useLanguage } from '../context/LanguageContext';

export default function ReviewWorkspace() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [review, setReview] = useState<ReviewDetailResponse | null>(null);
  const [diffComparison, setDiffComparison] = useState<AIvsHumanComparison | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'EVIDENCE' | 'CORRECTIONS' | 'DIFF' | 'HISTORY'>('EVIDENCE');
  const [submitting, setSubmitting] = useState<boolean>(false);

  // Modals state
  const [modalType, setModalType] = useState<'ACCEPT' | 'REJECT' | 'CORRECT' | 'ADD_EVIDENCE' | 'REMOVE_EVIDENCE' | 'COMMENT' | 'ESCALATE' | 'REOPEN' | 'ASSIGN' | null>(null);
  
  // Form states
  const [commentText, setCommentText] = useState<string>('');
  const [rejectionReason, setRejectionReason] = useState<string>('INCORRECT_EXTRACTION');
  const [selectedField, setSelectedField] = useState<string>('mrp');
  const [correctedValue, setCorrectedValue] = useState<string>('');
  const [correctionReason, setCorrectionReason] = useState<string>('');
  const [escalationReason, setEscalationReason] = useState<string>('');
  const [escalationTarget, setEscalationTarget] = useState<string>('ADMIN');
  const [reopenReason, setReopenReason] = useState<string>('');
  const [officers, setOfficers] = useState<Array<{ username: string; full_name: string; role: string }>>([]);
  const [assignedOfficer, setAssignedOfficer] = useState<string>('');

  // Evidence removal state
  const [targetEvidenceId, setTargetEvidenceId] = useState<string>('');
  const [removeEvidenceReason, setRemoveEvidenceReason] = useState<string>('');

  // Missing Evidence state
  const [missingEvidenceText, setMissingEvidenceText] = useState<string>('');
  const [missingLinkedRule, setMissingLinkedRule] = useState<string>('LM-001');
  const [missingLinkedField, setMissingLinkedField] = useState<string>('manufacturer');

  const fieldLabels: Record<string, string> = useMemo(() => ({
    product_name: t('audit_review.fields.product_name'),
    brand: t('audit_review.fields.brand'),
    mrp: t('audit_review.fields.mrp'),
    net_quantity: t('audit_review.fields.net_quantity'),
    manufacturer: t('audit_review.fields.manufacturer'),
    marketed_by: t('audit_review.fields.marketed_by'),
    fssai_license: t('audit_review.fields.fssai_license'),
    consumer_care: t('audit_review.fields.consumer_care'),
    country_of_origin: t('audit_review.fields.country_of_origin'),
    manufacture_date: t('audit_review.fields.manufacture_date'),
    expiry_date: t('audit_review.fields.expiry_date'),
    batch_number: t('audit_review.fields.batch_number'),
    ingredients: t('audit_review.fields.ingredients'),
    nutritional_info: t('audit_review.fields.nutritional_info')
  }), [t]);

  const loadReviewData = async () => {
    if (!reviewId) return;
    try {
      setLoading(true);
      const [revData, offRes] = await Promise.all([
        api.getReviewDetails(reviewId),
        api.getAvailableOfficers()
      ]);
      setReview(revData);
      setOfficers(offRes.officers || []);

      // Load diff comparison
      try {
        const diffData = await api.getAIvsHumanDiff(reviewId);
        setDiffComparison(diffData);
      } catch (err) {
        console.warn("Could not load diff comparison:", err);
      }
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_load'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReviewData();
  }, [reviewId]);

  const handleAcceptSubmit = async () => {
    if (!review) return;
    setSubmitting(true);
    try {
      await api.acceptReview(review.review_id, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_accept'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRejectSubmit = async () => {
    if (!review || !commentText.trim()) return;
    setSubmitting(true);
    try {
      await api.rejectReview(review.review_id, rejectionReason, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_reject'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCorrectFieldSubmit = async () => {
    if (!review || !correctedValue.trim()) return;
    setSubmitting(true);
    try {
      await api.correctReviewField(
        review.review_id,
        selectedField,
        fieldLabels[selectedField] || selectedField,
        correctedValue,
        correctionReason
      );
      setModalType(null);
      setCorrectedValue('');
      setCorrectionReason('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_correct'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAddEvidenceSubmit = async () => {
    if (!review || !missingEvidenceText.trim()) return;
    setSubmitting(true);
    try {
      await api.addReviewEvidence(review.review_id, {
        image_index: 0,
        image_label: "Front",
        text: missingEvidenceText,
        linked_rule_id: missingLinkedRule,
        linked_field: missingLinkedField,
        comments: commentText
      });
      setModalType(null);
      setMissingEvidenceText('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_add_evidence'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemoveEvidenceSubmit = async () => {
    if (!review || !targetEvidenceId || !removeEvidenceReason.trim()) return;
    setSubmitting(true);
    try {
      await api.removeReviewEvidence(review.review_id, targetEvidenceId, removeEvidenceReason);
      setModalType(null);
      setTargetEvidenceId('');
      setRemoveEvidenceReason('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_remove_evidence'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCommentSubmit = async () => {
    if (!review || !commentText.trim()) return;
    setSubmitting(true);
    try {
      await api.addReviewComment(review.review_id, commentText);
      setModalType(null);
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_comment'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEscalateSubmit = async () => {
    if (!review || !escalationReason.trim()) return;
    setSubmitting(true);
    try {
      await api.escalateReview(review.review_id, escalationReason, commentText, escalationTarget);
      setModalType(null);
      setEscalationReason('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_escalate'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReopenSubmit = async () => {
    if (!review || !reopenReason.trim()) return;
    setSubmitting(true);
    try {
      await api.reopenReview(review.review_id, reopenReason, commentText);
      setModalType(null);
      setReopenReason('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.workspace.error_reopen'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAssignSubmit = async () => {
    if (!review || !assignedOfficer) return;
    setSubmitting(true);
    try {
      await api.assignReview(review.review_id, assignedOfficer, commentText);
      setModalType(null);
      setAssignedOfficer('');
      setCommentText('');
      await loadReviewData();
    } catch (err: any) {
      alert(err.message || t('audit_review.modal_assign.error_fallback'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !review) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <Clock className="w-6 h-6 animate-spin text-indigo-500" />
          <span>{t('audit_review.workspace.loading')}</span>
        </div>
      </div>
    );
  }

  const aiSnap = review.ai_snapshot || {};
  const humanRes = review.human_verified_result || {};
  const images = aiSnap.images || [];
  const compResult = aiSnap.compliance_result || {};
  const checks = compResult.checks || [];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-6">
      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800/80 pb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/reviews')}
            className="p-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
            title={t('audit_review.workspace.back_tooltip')}
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl md:text-2xl font-black text-white tracking-tight">
                {review.product_name}
              </h1>
              <span className="font-mono text-xs px-2.5 py-0.5 rounded-md bg-slate-900 border border-slate-800 text-slate-400">
                {review.analysis_id.slice(0, 14)}
              </span>
              <span className={`px-2.5 py-1 text-xs font-bold rounded-full ${
                review.status.startsWith('VERIFIED') 
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : (review.status === 'REJECTED' 
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' 
                      : 'bg-amber-500/20 text-amber-300 border border-amber-500/30')
              }`}>
                {t('audit_review.workspace.status_prefix')}{review.status.replace('_', ' ')}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              {t('audit_review.workspace.assigned_label')}<strong className="text-indigo-300">{review.assigned_officer ? `@${review.assigned_officer}` : t('audit_review.workspace.unassigned')}</strong>
              {review.verified_by && <> • {t('audit_review.workspace.verified_by_label')}<strong className="text-emerald-300">@{review.verified_by}</strong> ({new Date(review.verified_at || '').toLocaleString()})</>}
            </p>
          </div>
        </div>

        {/* Action Buttons Toolbar */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setModalType('ASSIGN')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <UserCheck className="w-4 h-4 text-blue-400" />
            <span>{t('audit_review.workspace.btn_assign')}</span>
          </button>

          <button
            onClick={() => {
              setSelectedField('mrp');
              setCorrectedValue('');
              setModalType('CORRECT');
            }}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <Edit3 className="w-4 h-4 text-amber-400" />
            <span>{t('audit_review.workspace.btn_correct_field')}</span>
          </button>

          <button
            onClick={() => setModalType('ADD_EVIDENCE')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <PlusCircle className="w-4 h-4 text-emerald-400" />
            <span>{t('audit_review.workspace.btn_add_evidence')}</span>
          </button>

          <button
            onClick={() => setModalType('ACCEPT')}
            className="px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shadow-emerald-950 cursor-pointer"
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>{t('audit_review.workspace.btn_accept_ai')}</span>
          </button>

          <button
            onClick={() => setModalType('REJECT')}
            className="px-3.5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm shadow-rose-950 cursor-pointer"
          >
            <XCircle className="w-4 h-4" />
            <span>{t('audit_review.workspace.btn_reject_ai')}</span>
          </button>

          <button
            onClick={() => setModalType('ESCALATE')}
            className="px-3 py-2 rounded-xl bg-purple-900/40 border border-purple-500/30 text-purple-300 hover:bg-purple-900/60 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
          >
            <ArrowUpRight className="w-4 h-4" />
            <span>{t('audit_review.workspace.btn_escalate')}</span>
          </button>

          <button
            onClick={() => setModalType('COMMENT')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <MessageSquare className="w-4 h-4 text-sky-400" />
            <span>{t('audit_review.workspace.btn_add_comment')}</span>
          </button>

          <button
            onClick={() => setModalType('REMOVE_EVIDENCE')}
            className="px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 flex items-center gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>{t('audit_review.workspace.btn_remove_evidence')}</span>
          </button>

          {['VERIFIED_PASS', 'VERIFIED_FAIL', 'VERIFIED_NEEDS_REVIEW', 'REJECTED', 'CLOSED'].includes(review.status) && (
            <button
              onClick={() => setModalType('REOPEN')}
              className="px-3 py-2 rounded-xl bg-cyan-900/40 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-900/60 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
              <span>{t('audit_review.workspace.btn_reopen')}</span>
            </button>
          )}
        </div>
      </div>

      {/* Comparison Summary Banner: AI Result vs Human-Verified Working Result */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: AI Automated Output */}
        <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
              {t('audit_review.workspace.ai_banner_title')}
            </span>
            <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
              review.ai_status === 'PASS' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
            }`}>
              {review.ai_status}
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-black text-white">{review.ai_score.toFixed(1)}/100</span>
            <span className="text-xs text-slate-400">{t('audit_review.workspace.risk_label')} <strong className="text-slate-300">{review.ai_risk_level}</strong></span>
            <span className="text-xs text-slate-400">{t('audit_review.workspace.critical_issues_label')} <strong className="text-red-400">{review.critical_issues_count}</strong></span>
          </div>
          <p className="text-[11px] text-slate-400">
            {t('audit_review.workspace.ai_snapshot_date', { date: new Date(review.created_at).toLocaleString() })}
          </p>
        </div>

        {/* Right: Human Verified Result */}
        <div className="p-4 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-indigo-300 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              {t('audit_review.workspace.human_banner_title')}
            </span>
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
              {review.final_human_status || review.status}
            </span>
          </div>
          <div className="flex items-baseline gap-3">
            <span className="text-2xl font-black text-indigo-300">
              {review.human_score !== null && review.human_score !== undefined ? `${review.human_score.toFixed(1)}/100` : `${review.ai_score.toFixed(1)}/100`}
            </span>
            <span className="text-xs text-indigo-200/70">
              {t('audit_review.workspace.risk_label')} <strong className="text-indigo-200">{review.human_risk_level || review.ai_risk_level}</strong>
            </span>
            <span className="text-xs text-indigo-200/70">
              {t('audit_review.workspace.corrections_applied_label')} <strong className="text-amber-300">{review.field_corrections.length}</strong>
            </span>
          </div>
          <p className="text-[11px] text-indigo-200/60">
            {t('audit_review.workspace.human_authoritative_note')} {humanRes.last_recalculated_at ? t('audit_review.workspace.recalculated_at', { time: new Date(humanRes.last_recalculated_at).toLocaleTimeString() }) : ''}
          </p>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveTab('EVIDENCE')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'EVIDENCE' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>{t('audit_review.workspace.tab_evidence')}</span>
        </button>

        <button
          onClick={() => setActiveTab('CORRECTIONS')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'CORRECTIONS' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Edit3 className="w-4 h-4" />
          <span>{t('audit_review.workspace.tab_corrections', { count: review.field_corrections.length })}</span>
        </button>

        <button
          onClick={() => setActiveTab('DIFF')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'DIFF' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <GitCompare className="w-4 h-4" />
          <span>{t('audit_review.workspace.tab_diff')}</span>
        </button>

        <button
          onClick={() => setActiveTab('HISTORY')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer ${
            activeTab === 'HISTORY' ? 'bg-indigo-600 text-white shadow-xs shadow-indigo-950' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>{t('audit_review.workspace.tab_history', { count: review.history.length })}</span>
        </button>
      </div>

      {/* Tab 1: Evidence Viewer & Checks */}
      {activeTab === 'EVIDENCE' && (
        <div className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 md:p-6 space-y-6">
          <EvidenceViewer
            analysisId={review.analysis_id}
            images={images}
            checks={checks}
          />
        </div>
      )}

      {/* Tab 2: Officer Field Corrections & Evidence Modifications */}
      {activeTab === 'CORRECTIONS' && (
        <div className="space-y-6">
          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Edit3 className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-white">{t('audit_review.corrections.title')}</h3>
              </div>
              <button
                onClick={() => setModalType('CORRECT')}
                className="px-3 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold cursor-pointer"
              >
                {t('audit_review.corrections.btn_add')}
              </button>
            </div>

            {review.field_corrections.length === 0 ? (
              <p className="text-xs text-slate-400 py-4">{t('audit_review.corrections.empty')}</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {review.field_corrections.map((corr, idx) => (
                  <div key={idx} className="py-3 flex flex-col md:flex-row items-start md:items-center justify-between gap-2">
                    <div>
                      <span className="text-xs font-bold text-white block">{corr.field_label} ({corr.field_name})</span>
                      <div className="flex items-center gap-2 text-xs mt-1">
                        <span className="text-slate-400 line-through">{t('audit_review.corrections.original_label')}{corr.original_value || 'None'}</span>
                        <span className="text-slate-400">→</span>
                        <span className="text-emerald-400 font-bold">{t('audit_review.corrections.corrected_label')}{corr.corrected_value}</span>
                      </div>
                      <p className="text-[11px] text-slate-400 mt-0.5">{t('audit_review.corrections.reason_label')}{corr.reason}</p>
                    </div>
                    <div className="text-right text-[10px] text-slate-400">
                      <span>{t('audit_review.corrections.by_label', { officer: corr.officer_username, role: corr.officer_role })}</span>
                      <span className="block">{new Date(corr.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-4 shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">{t('audit_review.corrections.evidence_mods_title')}</h3>
              </div>
            </div>

            {review.evidence_modifications.length === 0 ? (
              <p className="text-xs text-slate-400 py-4">{t('audit_review.corrections.evidence_mods_empty')}</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {review.evidence_modifications.map((mod, idx) => (
                  <div key={idx} className="py-3 flex items-start justify-between gap-2">
                    <div>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                        mod.action === 'ADDED' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {mod.action === 'ADDED' ? t('audit_review.diff.state_added') : t('audit_review.diff.state_removed')}
                      </span>
                      {mod.action === 'ADDED' ? (
                        <p className="text-xs text-slate-300 mt-1">
                          {t('audit_review.corrections.rule_prefix')}<strong>{mod.evidence?.linked_rule_id}</strong> — {t('audit_review.corrections.text_prefix')}"{mod.evidence?.text}"
                        </p>
                      ) : (
                        <p className="text-xs text-slate-300 mt-1">
                          {t('audit_review.corrections.evidence_id_prefix')}<strong>{mod.evidence_id}</strong> — {t('audit_review.corrections.reason_label')}{mod.reason}
                        </p>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">
                      @{mod.officer_username} • {new Date(mod.timestamp).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: AI vs Human Diff */}
      {activeTab === 'DIFF' && diffComparison && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-6 shadow-sm">
          <div className="border-b border-slate-800 pb-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-indigo-400" />
              {t('audit_review.diff.title')}
            </h3>
            <p className="text-xs text-slate-400 mt-1">{diffComparison.summary}</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase font-bold text-[10px]">
                  <th className="py-2.5 px-3">{t('audit_review.diff.col_field')}</th>
                  <th className="py-2.5 px-3">{t('audit_review.diff.col_ai_value')}</th>
                  <th className="py-2.5 px-3">{t('audit_review.diff.col_human_value')}</th>
                  <th className="py-2.5 px-3">{t('audit_review.diff.col_diff_state')}</th>
                  <th className="py-2.5 px-3">{t('audit_review.diff.col_attribution')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {diffComparison.field_diffs.map((fd, i) => (
                  <tr key={i} className={`hover:bg-slate-800/30 ${fd.is_changed ? 'bg-indigo-950/20' : ''}`}>
                    <td className="py-2.5 px-3 font-semibold text-slate-200">{fieldLabels[fd.field_name] || fd.field_label}</td>
                    <td className="py-2.5 px-3 text-slate-400">{fd.ai_value || '—'}</td>
                    <td className="py-2.5 px-3 font-bold text-white">{fd.human_value || '—'}</td>
                    <td className="py-2.5 px-3">
                      {fd.is_changed ? (
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold text-[10px]">
                          {fd.change_type === 'CORRECTED' 
                            ? t('audit_review.diff.state_corrected') 
                            : (fd.change_type === 'ADDED' ? t('audit_review.diff.state_added') : t('audit_review.diff.state_removed'))}
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                          {t('audit_review.diff.state_unchanged')}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">
                      {fd.officer_username ? `@${fd.officer_username}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Review History Timeline */}
      {activeTab === 'HISTORY' && (
        <div className="rounded-2xl bg-slate-900 border border-slate-800 p-6 space-y-6 shadow-sm">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Clock className="w-5 h-5 text-indigo-400" />
              {t('audit_review.history.title')}
            </h3>
          </div>

          <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {review.history.map((evt, idx) => (
              <div key={idx} className="relative space-y-1">
                <span className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-indigo-500 ring-4 ring-slate-950" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">{evt.action}</span>
                  <span className="text-[10px] text-slate-400">{new Date(evt.timestamp).toLocaleString()}</span>
                </div>
                <p className="text-xs text-slate-300">{evt.details}</p>
                <span className="text-[10px] text-slate-400 block">{t('audit_review.history.actor_prefix', { officer: evt.actor_username, role: evt.actor_role })}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action Modals */}

      {/* Modal 1: Correct Field */}
      {modalType === 'CORRECT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Edit3 className="w-4 h-4 text-amber-400" />
              {t('audit_review.modal_correct.title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_correct.select_field')}</label>
                <select
                  value={selectedField}
                  onChange={(e) => setSelectedField(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  {Object.entries(fieldLabels).map(([fKey, fLabel]) => (
                    <option key={fKey} value={fKey}>{fLabel}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_correct.corrected_value')}</label>
                <input
                  type="text"
                  placeholder={t('audit_review.modal_correct.value_placeholder')}
                  value={correctedValue}
                  onChange={(e) => setCorrectedValue(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_correct.reason_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_correct.reason_placeholder')}
                  value={correctionReason}
                  onChange={(e) => setCorrectionReason(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleCorrectFieldSubmit}
                disabled={!correctedValue.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_correct.applying_btn') : t('audit_review.modal_correct.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Accept AI Result */}
      {modalType === 'ACCEPT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              {t('audit_review.modal_accept.title')}
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              {t('audit_review.modal_accept.desc')}
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_accept.notes_label')}</label>
              <textarea
                placeholder={t('audit_review.modal_accept.notes_placeholder')}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleAcceptSubmit}
                disabled={submitting}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_accept.confirming_btn') : t('audit_review.modal_accept.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Reject AI Result */}
      {modalType === 'REJECT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-400" />
              {t('audit_review.modal_reject.title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_reject.reason_label')}</label>
                <select
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="INCORRECT_EXTRACTION">{t('audit_review.modal_reject.reason_incorrect_extraction')}</option>
                  <option value="INSUFFICIENT_EVIDENCE">{t('audit_review.modal_reject.reason_insufficient_evidence')}</option>
                  <option value="WRONG_RULE_EVALUATION">{t('audit_review.modal_reject.reason_wrong_rule_evaluation')}</option>
                  <option value="IMAGE_QUALITY_ISSUE">{t('audit_review.modal_reject.reason_image_quality_issue')}</option>
                  <option value="OTHER">{t('audit_review.modal_reject.reason_other')}</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_reject.explanation_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_reject.explanation_placeholder')}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleRejectSubmit}
                disabled={!commentText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_reject.rejecting_btn') : t('audit_review.modal_reject.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 4: Assign */}
      {modalType === 'ASSIGN' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <UserCheck className="w-4 h-4 text-indigo-400" />
              {t('audit_review.modal_assign.workspace_title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_assign.select_officer')}</label>
                <select
                  value={assignedOfficer}
                  onChange={(e) => setAssignedOfficer(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
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
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_assign.notes_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_assign.notes_placeholder')}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleAssignSubmit}
                disabled={!assignedOfficer || submitting}
                className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_assign.assigning_btn') : t('audit_review.modal_assign.confirm_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 5: Add Missing Evidence */}
      {modalType === 'ADD_EVIDENCE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <PlusCircle className="w-4 h-4 text-emerald-400" />
              {t('audit_review.modal_add_evidence.title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_add_evidence.rule_id_label')}</label>
                <input
                  type="text"
                  placeholder={t('audit_review.modal_add_evidence.rule_id_placeholder')}
                  value={missingLinkedRule}
                  onChange={(e) => setMissingLinkedRule(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_add_evidence.field_label')}</label>
                <select
                  value={missingLinkedField}
                  onChange={(e) => setMissingLinkedField(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  {Object.entries(fieldLabels).map(([fKey, fLabel]) => (
                    <option key={fKey} value={fKey}>{fLabel}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_add_evidence.text_found_label')}</label>
                <input
                  type="text"
                  placeholder={t('audit_review.modal_add_evidence.text_found_placeholder')}
                  value={missingEvidenceText}
                  onChange={(e) => setMissingEvidenceText(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_add_evidence.notes_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_add_evidence.notes_placeholder')}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleAddEvidenceSubmit}
                disabled={!missingEvidenceText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_add_evidence.saving_btn') : t('audit_review.modal_add_evidence.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 6: Escalate */}
      {modalType === 'ESCALATE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <ArrowUpRight className="w-4 h-4 text-purple-400" />
              {t('audit_review.modal_escalate.title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_escalate.target_label')}</label>
                <select
                  value={escalationTarget}
                  onChange={(e) => setEscalationTarget(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                >
                  <option value="ADMIN">{t('audit_review.modal_escalate.target_admin')}</option>
                  <option value="ENFORCEMENT_DIRECTOR">{t('audit_review.modal_escalate.target_enforcement_director')}</option>
                  <option value="LEGAL_COUNSEL">{t('audit_review.modal_escalate.target_legal_counsel')}</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_escalate.reason_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_escalate.reason_placeholder')}
                  value={escalationReason}
                  onChange={(e) => setEscalationReason(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleEscalateSubmit}
                disabled={!escalationReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_escalate.escalating_btn') : t('audit_review.modal_escalate.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 7: Reopen */}
      {modalType === 'REOPEN' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-cyan-400" />
              {t('audit_review.modal_reopen.title')}
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed">
              {t('audit_review.modal_reopen.desc')}
            </p>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_reopen.reason_label')}</label>
              <textarea
                placeholder={t('audit_review.modal_reopen.reason_placeholder')}
                value={reopenReason}
                onChange={(e) => setReopenReason(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleReopenSubmit}
                disabled={!reopenReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_reopen.reopening_btn') : t('audit_review.modal_reopen.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 8: Add Comment */}
      {modalType === 'COMMENT' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-sky-400" />
              {t('audit_review.modal_comment.title')}
            </h3>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_comment.note_label')}</label>
              <textarea
                placeholder={t('audit_review.modal_comment.note_placeholder')}
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                rows={3}
                className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
              />
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleCommentSubmit}
                disabled={!commentText.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_comment.saving_btn') : t('audit_review.modal_comment.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 9: Remove Evidence */}
      {modalType === 'REMOVE_EVIDENCE' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-xs">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Trash2 className="w-4 h-4 text-rose-400" />
              {t('audit_review.modal_remove_evidence.title')}
            </h3>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_remove_evidence.id_label')}</label>
                <input
                  type="text"
                  placeholder={t('audit_review.modal_remove_evidence.id_placeholder')}
                  value={targetEvidenceId}
                  onChange={(e) => setTargetEvidenceId(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-sm text-slate-200"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">{t('audit_review.modal_remove_evidence.reason_label')}</label>
                <textarea
                  placeholder={t('audit_review.modal_remove_evidence.reason_placeholder')}
                  value={removeEvidenceReason}
                  onChange={(e) => setRemoveEvidenceReason(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-slate-800 pt-4">
              <button onClick={() => setModalType(null)} className="px-4 py-2 rounded-xl bg-slate-800 text-xs font-semibold text-slate-300">
                {t('common.cancel')}
              </button>
              <button
                onClick={handleRemoveEvidenceSubmit}
                disabled={!targetEvidenceId.trim() || !removeEvidenceReason.trim() || submitting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-xs font-bold text-white"
              >
                {submitting ? t('audit_review.modal_remove_evidence.removing_btn') : t('audit_review.modal_remove_evidence.submit_btn')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
