import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  FileCheck, 
  CheckCircle2, 
  AlertTriangle, 
  ScanSearch, 
  ArrowRight, 
  ShieldCheck, 
  Cpu, 
  FileText, 
  Search, 
  History, 
  BookOpen, 
  XCircle,
  Info,
  Sparkles,
  Boxes,
  Printer,
  Plus
} from 'lucide-react';

import { type DashboardStats, type MerchantDashboardStats, type Product } from '../types';
import { api } from '../services/api';
import StatusBadge from '../components/ui/StatusBadge';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import EmptyState from '../components/ui/EmptyState';
import { formatAnalysisDateTime } from '../utils/datetime';
import { useAuth } from '../context/AuthContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { useLanguage } from '../context/LanguageContext';

export default function Dashboard() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { workspaceInfo } = useWorkspace();
  const { t } = useLanguage();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [merchantStats, setMerchantStats] = useState<MerchantDashboardStats | null>(null);
  const [merchantProducts, setMerchantProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const isMerchant = user?.role === 'MERCHANT_PUBLIC' || workspaceInfo.id === 'MERCHANT';
  const isNormalUser = (user?.role === 'PUBLIC_USER' || user?.role === 'NORMAL_USER' || workspaceInfo.id === 'USER') && !isMerchant;

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [data, mStats, mProds] = await Promise.all([
          api.getDashboardStats(),
          isMerchant ? api.getProductStats().catch(() => null) : Promise.resolve(null),
          isMerchant ? api.getProducts({ limit: 5 }).then(r => r.products).catch(() => []) : Promise.resolve([])
        ]);
        setStats(data);
        if (mStats) setMerchantStats(mStats);
        if (mProds) setMerchantProducts(mProds);
      } catch (err) {
        setError('Failed to load dashboard statistics. Please ensure the backend server is active.');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, [isMerchant]);

  if (loading) {
    return (
      <div className="space-y-6">
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  const dashboardData: DashboardStats = stats || {
    total_analyzed: 0,
    compliant: 0,
    needs_review: 0,
    failures: 0,
    violations: 0,
    average_score: 0,
    recent: []
  };

  const packagesScreened = dashboardData.packages_screened ?? dashboardData.total_analyzed;
  const compliantPackages = dashboardData.compliant_packages ?? dashboardData.compliant;
  const reviewFindings = dashboardData.review_findings ?? dashboardData.needs_review ?? 0;
  const failedFindings = dashboardData.failed_findings ?? dashboardData.failures ?? 0;
  const needAttentionProducts = Math.max(0, packagesScreened - compliantPackages);
  const nonCompliantPackages = needAttentionProducts;

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return t('dashboard.greeting_morning');
    if (hour < 18) return t('dashboard.greeting_afternoon');
    return t('dashboard.greeting_evening');
  };

  const displayName = user?.full_name || user?.username || user?.email || 'User';

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {error && (
        <div className="p-4 rounded-xl bg-red-50/90 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button 
            onClick={() => window.location.reload()} 
            className="text-xs font-semibold text-red-800 dark:text-red-200 underline hover:no-underline cursor-pointer"
          >
            {t('common.retry')}
          </button>
        </div>
      )}

      {/* Header: Greeting & Quick Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
              {getGreeting()}, {displayName}
            </h1>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border font-mono uppercase tracking-wider ${
              isNormalUser 
                ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800' 
                : isMerchant
                ? 'bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-800'
                : 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400'
            }`}>
              {isNormalUser ? t('dashboard.consumer.tag') : isMerchant ? t('roles.commercial_brand') : workspaceInfo.label}
            </span>
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {isNormalUser 
              ? t('dashboard.consumer.subtitle')
              : isMerchant
              ? t('merchant.dashboard.subtitle')
              : t('dashboard.overview_subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {isMerchant && (
            <button
              onClick={() => navigate('/products/new')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm hover:shadow-md"
            >
              <Plus className="w-4 h-4" />
              <span>{t('merchant.dashboard.add_product_sku')}</span>
            </button>
          )}
          <button
            onClick={() => navigate('/analyze')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow-sm hover:shadow-md"
          >
            <ScanSearch className="w-4 h-4" />
            <span>{isNormalUser ? t('dashboard.consumer.check_product_btn') : isMerchant ? t('merchant.dashboard.scan_package_label') : t('navigation.analyze_package')}</span>
          </button>
          {isMerchant && (
            <button
              onClick={() => navigate('/preprint')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl text-xs font-semibold transition-colors cursor-pointer shadow-sm"
            >
              <Printer className="w-3.5 h-3.5 text-indigo-500" />
              <span>{t('merchant.dashboard.preprint_artworks')}</span>
            </button>
          )}
          <button
            onClick={() => navigate('/history')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 rounded-xl text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <History className="w-3.5 h-3.5" />
            <span>{isNormalUser ? t('dashboard.consumer.my_scan_history') : t('navigation.screening_history')}</span>
          </button>
          <button
            onClick={() => navigate('/rules')}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 rounded-xl text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>{isNormalUser ? t('dashboard.consumer.packaging_guide') : t('navigation.compliance_rules')}</span>
          </button>
        </div>
      </div>

      {/* Primary Consumer Quick Start Card for Normal User */}
      {isNormalUser && packagesScreened === 0 && (
        <div className="p-6 rounded-2xl bg-linear-to-r from-indigo-500/10 via-emerald-500/10 to-sky-500/10 border border-indigo-200 dark:border-indigo-800/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 shadow-sm">
          <div className="space-y-1.5 max-w-xl">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 text-[11px] font-bold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>{t('dashboard.consumer.quick_start_tag')}</span>
            </div>
            <h3 className="text-base sm:text-lg font-extrabold text-slate-900 dark:text-slate-100">
              {t('dashboard.consumer.quick_start_title')}
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
              {t('dashboard.consumer.quick_start_desc')}
            </p>
          </div>
          <button
            onClick={() => navigate('/analyze')}
            className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs sm:text-sm font-bold rounded-xl shadow-sm hover:shadow-md transition-all flex items-center gap-2 shrink-0 cursor-pointer"
          >
            <ScanSearch className="w-4 h-4" />
            <span>{t('dashboard.consumer.check_now')}</span>
          </button>
        </div>
      )}

      {/* KPI Row (Merchant specific or Consumer specific) */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-sm p-4">
        <div className="flex flex-wrap divide-y sm:divide-y-0 sm:divide-x divide-slate-100 dark:divide-slate-800">
          <div className="flex-1 min-w-37.5 p-2 flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isMerchant ? 'bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400' : 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400'}`}>
              {isMerchant ? <Boxes className="w-5 h-5" /> : <FileCheck className="w-5 h-5" />}
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {isMerchant ? t('merchant.dashboard.active_skus') : isNormalUser ? t('dashboard.consumer.products_checked') : t('dashboard.stats.packages_screened')}
              </p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                {isMerchant ? (merchantStats?.active_products ?? merchantProducts.length) : packagesScreened}
              </p>
            </div>
          </div>
          <div className="flex-1 min-w-37.5 p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {isMerchant ? t('merchant.dashboard.checks_screened') : isNormalUser ? t('dashboard.consumer.passed') : t('dashboard.stats.compliant_packages')}
              </p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                {isMerchant ? (merchantStats?.products_checked ?? packagesScreened) : compliantPackages}
              </p>
            </div>
          </div>
          <div className="flex-1 min-w-37.5 p-2 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {isMerchant ? t('merchant.dashboard.attention_required') : isNormalUser ? t('dashboard.consumer.need_attention') : t('dashboard.stats.review_findings')}
              </p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                {isMerchant ? (merchantStats?.attention_required ?? reviewFindings) : isNormalUser ? needAttentionProducts : reviewFindings}
              </p>
            </div>
          </div>
          <div className="flex-1 min-w-37.5 p-2 flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isMerchant ? 'bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400' : 'bg-red-50 dark:bg-red-950/50 text-red-600 dark:text-red-400'}`}>
              {isMerchant ? <Printer className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                {isMerchant ? t('merchant.dashboard.preprint_artworks') : isNormalUser ? t('dashboard.consumer.failed_findings') : t('dashboard.stats.failed_findings')}
              </p>
              <p className="text-xl font-bold text-slate-900 dark:text-slate-100">
                {isMerchant ? (merchantStats?.packaging_artworks ?? 0) : failedFindings}
              </p>
            </div>
          </div>
        </div>
        <div className="mt-2.5 pt-2.5 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400 dark:text-slate-500 flex items-center gap-1.5 px-1">
          <Info className="w-3.5 h-3.5 text-slate-400 dark:text-slate-500 shrink-0" />
          <span>
            {isNormalUser 
              ? t('dashboard.consumer.privacy_notice') 
              : isMerchant
              ? t('dashboard.consumer.merchant_privacy_notice')
              : t('dashboard.stats.finding_info')}
          </span>
        </div>
      </div>

      {/* Merchant Product Catalog Quick Card */}
      {isMerchant && (
        <div className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xs space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Boxes className="w-4 h-4 text-sky-600 dark:text-sky-400" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                {t('merchant.dashboard.managed_sku_catalog')}
              </h3>
            </div>
            <button
              onClick={() => navigate('/products')}
              className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline cursor-pointer"
            >
              {t('merchant.dashboard.view_full_catalog')}
            </button>
          </div>

          {merchantProducts.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {merchantProducts.slice(0, 3).map(p => (
                <div
                  key={p.id}
                  onClick={() => navigate(`/products/${p.id}`)}
                  className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-700/80 hover:border-sky-500/50 transition-all cursor-pointer group"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                      {p.category ? (t(`merchant.categories.${p.category}`) || p.category) : t('merchant.categories.GENERAL')}
                    </span>
                    <span className={`text-[10px] font-bold ${p.status === 'ACTIVE' ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-400'}`}>
                      {p.status === 'ACTIVE' ? t('merchant.status.active') : t('merchant.status.archived')}
                    </span>
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100 mt-2 truncate group-hover:text-sky-600 dark:group-hover:text-sky-400">
                    {p.product_name}
                  </h4>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                    {p.brand_name ? `${p.brand_name} • ` : ''}{t('merchant.dashboard.mrp')}: {p.mrp_declared ? `₹${p.mrp_declared.toFixed(2)}` : '—'}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-4 bg-slate-50 dark:bg-slate-800/40 rounded-xl border border-dashed border-slate-200 dark:border-slate-700">
              <p className="text-xs text-slate-500">{t('merchant.dashboard.no_products_catalog')}</p>
              <button
                onClick={() => navigate('/products/new')}
                className="mt-2 text-xs font-bold text-sky-600 hover:underline cursor-pointer"
              >
                {t('merchant.dashboard.register_first_sku')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Action Required Callout */}
      {(isNormalUser ? needAttentionProducts > 0 : (nonCompliantPackages > 0 || failedFindings > 0 || reviewFindings > 0)) && (
        <div className={`border rounded-xl p-4 flex items-center justify-between gap-4 ${
          failedFindings > 0 
            ? 'bg-red-50 dark:bg-red-950/40 border-red-200 dark:border-red-800/60' 
            : 'bg-amber-50 dark:bg-amber-950/40 border-amber-200 dark:border-amber-800/60'
        }`}>
          <div className="flex items-center gap-3">
            {failedFindings > 0 ? (
              <XCircle className="w-5 h-5 text-red-600 dark:text-red-500 shrink-0" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-500 shrink-0" />
            )}
            <p className={`text-sm font-medium ${failedFindings > 0 ? 'text-red-900 dark:text-red-200' : 'text-amber-900 dark:text-amber-200'}`}>
              <span className="font-bold">
                {isNormalUser 
                  ? (needAttentionProducts === 1
                      ? t('dashboard.consumer.attention_single')
                      : t('dashboard.consumer.attention_multiple', { count: needAttentionProducts }))
                  : t('dashboard.action_required_discrepancies', { count: nonCompliantPackages })}
              </span>
            </p>
          </div>
          <button
            onClick={() => navigate('/history')}
            className={`shrink-0 px-3 py-1.5 text-white text-xs font-semibold rounded-lg transition-colors cursor-pointer shadow-sm ${
              failedFindings > 0 ? 'bg-red-600 hover:bg-red-700' : 'bg-amber-600 hover:bg-amber-700'
            }`}
          >
            {isNormalUser ? t('dashboard.consumer.view_my_checks') : t('dashboard.review_findings')}
          </button>
        </div>
      )}

      {/* Consumer Guidance Section for Normal User */}
      {isNormalUser && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                {t('dashboard.consumer.guide_title')}
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {t('dashboard.consumer.guide_subtitle')}
              </p>
            </div>
            <button
              onClick={() => navigate('/rules')}
              className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
            >
              {t('dashboard.consumer.full_rules')} &rarr;
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_1_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_1_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-sky-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_2_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_2_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_3_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_3_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_4_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_4_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_5_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_5_desc')}
              </p>
            </div>

            <div className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5 shadow-2xs">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-teal-500 shrink-0" />
                <h4 className="text-xs font-bold text-slate-900 dark:text-slate-100">{t('dashboard.consumer.guide_6_title')}</h4>
              </div>
              <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                {t('dashboard.consumer.guide_6_desc')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Horizontal Inspection Stepper (Workflow overview) */}
      <div className="bg-slate-50/50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-2 text-xs font-medium text-slate-600 dark:text-slate-400 overflow-x-auto">
        <div className="flex items-center gap-1.5 shrink-0"><ScanSearch className="w-3.5 h-3.5 text-indigo-500" /> {t('dashboard.steps.capture')}</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><Cpu className="w-3.5 h-3.5 text-indigo-500" /> {t('dashboard.steps.extract')}</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><ShieldCheck className="w-3.5 h-3.5 text-indigo-500" /> {isNormalUser ? t('dashboard.consumer.step_check') : t('dashboard.steps.screen')}</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><Search className="w-3.5 h-3.5 text-indigo-500" /> {isNormalUser ? t('dashboard.consumer.step_evidence') : t('dashboard.steps.verify')}</div>
        <ArrowRight className="w-3 h-3 text-slate-300 dark:text-slate-600 shrink-0" />
        <div className="flex items-center gap-1.5 shrink-0"><FileText className="w-3.5 h-3.5 text-indigo-500" /> {t('dashboard.steps.report')}</div>
      </div>

      {/* Recent Personal Screenings Table */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-tight">
            {isNormalUser ? t('dashboard.consumer.my_recent_checks') : t('dashboard.recent_screenings')}
          </h3>
          {dashboardData.recent.length > 0 && (
            <button
              onClick={() => navigate('/history')}
              className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
            >
              {t('dashboard.consumer.view_all_history')} &rarr;
            </button>
          )}
        </div>
        
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          {dashboardData.recent.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    <th className="py-2.5 px-4 font-semibold">{t('dashboard.table.product')}</th>
                    <th className="py-2.5 px-4 font-semibold">{t('dashboard.table.score')}</th>
                    <th className="py-2.5 px-4 font-semibold">{t('dashboard.table.status')}</th>
                    <th className="py-2.5 px-4 font-semibold">{t('dashboard.table.date')}</th>
                    <th className="py-2.5 px-4 text-right font-semibold">{t('dashboard.table.action')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {dashboardData.recent.slice(0, 5).map((item) => (
                    <tr 
                      key={item.id} 
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      onClick={() => navigate(`/results/${item.id}`)}
                    >
                      <td className="py-2 px-4">
                        <div className="font-semibold text-slate-900 dark:text-slate-100 truncate max-w-50 sm:max-w-xs">
                          {item.product_name || 'Unknown Product'}
                        </div>
                      </td>
                      <td className="py-2 px-4">
                        <span className={`font-mono font-medium ${typeof item.score === 'number' && item.score >= 90 ? 'text-emerald-600 dark:text-emerald-400' : typeof item.score === 'number' && item.score >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400'}`}>
                          {typeof item.score === 'number' ? item.score.toFixed(1) : item.score}
                        </span>
                      </td>
                      <td className="py-2 px-4">
                        <StatusBadge status={item.status} size="xs" />
                      </td>
                      <td className="py-2 px-4 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                        {formatAnalysisDateTime(item.created_at)}
                      </td>
                      <td className="py-2 px-4 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/results/${item.id}`); }}
                          className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 cursor-pointer"
                        >
                          {t('common.view')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8">
              <EmptyState 
                icon={ScanSearch}
                title={isNormalUser ? t('dashboard.consumer.no_screenings_title') : t('dashboard.no_screenings')}
                description={isNormalUser ? t('dashboard.consumer.no_screenings_desc') : t('dashboard.no_screenings_desc')}
                actionLabel={isNormalUser ? t('dashboard.consumer.check_product') : t('navigation.analyze_package')}
                onAction={() => navigate('/analyze')}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
