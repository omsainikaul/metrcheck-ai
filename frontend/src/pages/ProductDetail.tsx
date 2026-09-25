import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowLeft, 
  Edit3, 
  ScanSearch, 
  Printer, 
  FileText, 
  AlertTriangle, 
  XCircle, 
  Building2, 
  Scale
} from 'lucide-react';
import { api } from '../services/api';
import { 
  type ProductComplianceSummary, 
  type ProductHistoryItem, 
  type ProductArtworkSummary 
} from '../types';
import { useLanguage } from '../context/LanguageContext';
import StatusBadge from '../components/ui/StatusBadge';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import EmptyState from '../components/ui/EmptyState';
import { formatAnalysisDateTime } from '../utils/datetime';

export default function ProductDetail() {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [summary, setSummary] = useState<ProductComplianceSummary | null>(null);
  const [historyItems, setHistoryItems] = useState<ProductHistoryItem[]>([]);
  const [artworks, setArtworks] = useState<ProductArtworkSummary[]>([]);
  const [activeTab, setActiveTab] = useState<'SCANS' | 'ARTWORKS' | 'DECLARATIONS'>('SCANS');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProductData = async () => {
    if (!productId) return;
    setLoading(true);
    setError(null);
    try {
      const [sumRes, histRes, artRes] = await Promise.all([
        api.getProductSummary(productId),
        api.getProductHistory(productId).catch(() => ({ product_id: productId, analyses: [], total: 0 })),
        api.getProductArtworks(productId).catch(() => ({ product_id: productId, artworks: [], total: 0 }))
      ]);
      setSummary(sumRes);
      setHistoryItems(histRes.analyses || []);
      setArtworks(artRes.artworks || []);
    } catch (err: any) {
      setError(err?.message || 'Failed to load product details.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProductData();
  }, [productId]);

  if (loading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-300">
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl text-center space-y-4 max-w-lg mx-auto mt-12">
        <div className="w-12 h-12 rounded-full bg-red-50 dark:bg-red-950/60 text-red-500 mx-auto flex items-center justify-center">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
          {t('merchant.product_detail.not_found_title')}
        </h2>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
          {error || t('merchant.product_detail.not_found_desc')}
        </p>
        <button
          onClick={() => navigate('/products')}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-xl text-xs font-semibold transition-colors cursor-pointer"
        >
          {t('merchant.product_detail.return_catalog')}
        </button>
      </div>
    );
  }

  const { product } = summary;

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Top Breadcrumb & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => navigate('/products')}
            className="p-2 rounded-xl bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                {product.product_name}
              </h1>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${
                product.status === 'ACTIVE'
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
              }`}>
                {product.status === 'ACTIVE' ? t('merchant.status.active') : t('merchant.status.archived')}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
              {product.brand_name ? `${t('merchant.products.brand_label')}: ${product.brand_name} • ` : ''}{t('merchant.products.table.category')}: {product.category ? (t(`merchant.categories.${product.category}`) || product.category) : t('merchant.categories.GENERAL')} • {t('merchant.products.table.gtin')}: {product.gtin_barcode || '—'}
            </p>
          </div>
        </div>

        {/* Quick Execution Actions */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => navigate(`/analyze?productId=${product.id}`, { state: { productId: product.id, productName: product.product_name } })}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer"
            title={t('sku_workflow.scan_packaging_for_sku')}
          >
            <ScanSearch className="w-4 h-4" />
            <span>{t('sku_workflow.scan_packaging_for_sku')}</span>
          </button>
          <button
            onClick={() => navigate(`/preprint?productId=${product.id}`, { state: { productId: product.id, productName: product.product_name } })}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm cursor-pointer"
            title={t('sku_workflow.upload_artwork_for_sku')}
          >
            <Printer className="w-4 h-4" />
            <span>{t('sku_workflow.upload_artwork_for_sku')}</span>
          </button>
          <button
            onClick={() => navigate(`/products/${product.id}/edit`)}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl text-xs font-semibold transition-colors cursor-pointer shadow-sm"
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>{t('merchant.product_detail.edit_record')}</span>
          </button>
        </div>
      </div>

      {/* Compliance Overview KPI Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.product_detail.latest_score')}</span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className={`text-2xl font-bold font-mono ${
              summary.latest_score >= 90 ? 'text-emerald-600 dark:text-emerald-400' :
              summary.latest_score >= 70 ? 'text-amber-600 dark:text-amber-400' :
              summary.latest_score > 0 ? 'text-red-600 dark:text-red-400' : 'text-slate-400'
            }`}>
              {summary.latest_score > 0 ? summary.latest_score.toFixed(1) : '—'}
            </span>
            <span className="text-xs text-slate-400">/ 100</span>
          </div>
          <div className="mt-1">
            <StatusBadge status={summary.latest_status} size="xs" />
          </div>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.product_detail.physical_scans')}</span>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
            {summary.total_scans}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">
            {summary.latest_scan ? t('merchant.product_detail.last_scan', { time: formatAnalysisDateTime(summary.latest_scan.created_at) }) : t('merchant.product_detail.no_scans_yet')}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.product_detail.packaging_artworks')}</span>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
            {summary.total_artworks}
          </p>
          <p className="text-[10px] text-slate-400 mt-1">
            {summary.latest_artwork ? `Ver ${summary.latest_artwork.iteration_number} (${summary.latest_artwork.workflow_status})` : t('merchant.product_detail.no_artworks_yet')}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.product_detail.findings_severity')}</span>
          <div className="flex items-center gap-3 mt-1.5">
            <div className="flex items-center gap-1">
              <XCircle className="w-4 h-4 text-red-500" />
              <span className="text-sm font-bold text-red-600 dark:text-red-400">{summary.critical_findings_count}</span>
              <span className="text-[10px] text-slate-400">{t('merchant.product_detail.critical')}</span>
            </div>
            <div className="flex items-center gap-1">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              <span className="text-sm font-bold text-amber-600 dark:text-amber-400">{summary.review_findings_count}</span>
              <span className="text-[10px] text-slate-400">{t('merchant.product_detail.review')}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200 dark:border-slate-800 flex items-center gap-4">
        <button
          onClick={() => setActiveTab('SCANS')}
          className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all cursor-pointer flex items-center gap-2 ${
            activeTab === 'SCANS'
              ? 'border-sky-600 text-sky-600 dark:text-sky-400'
              : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          <ScanSearch className="w-4 h-4" />
          <span>{t('merchant.product_detail.tab_scans', { count: historyItems.length })}</span>
        </button>

        <button
          onClick={() => setActiveTab('ARTWORKS')}
          className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all cursor-pointer flex items-center gap-2 ${
            activeTab === 'ARTWORKS'
              ? 'border-sky-600 text-sky-600 dark:text-sky-400'
              : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          <Printer className="w-4 h-4" />
          <span>{t('merchant.product_detail.tab_artworks', { count: artworks.length })}</span>
        </button>

        <button
          onClick={() => setActiveTab('DECLARATIONS')}
          className={`pb-3 text-xs sm:text-sm font-bold border-b-2 transition-all cursor-pointer flex items-center gap-2 ${
            activeTab === 'DECLARATIONS'
              ? 'border-sky-600 text-sky-600 dark:text-sky-400'
              : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
          }`}
        >
          <Scale className="w-4 h-4" />
          <span>{t('merchant.product_detail.tab_declarations')}</span>
        </button>
      </div>

      {/* Tab 1: Physical Scans */}
      {activeTab === 'SCANS' && (
        <div className="space-y-4">
          {historyItems.length > 0 ? (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_scan_date')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_score')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_verdict')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_integrity')}</th>
                      <th className="py-3 px-4 text-right font-semibold">{t('merchant.products.table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {historyItems.map((item) => (
                      <tr
                        key={item.id}
                        onClick={() => navigate(`/results/${item.id}`)}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                      >
                        <td className="py-3 px-4 text-xs font-medium text-slate-800 dark:text-slate-200">
                          {formatAnalysisDateTime(item.created_at)}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`font-mono font-bold ${
                            item.score >= 90 ? 'text-emerald-600 dark:text-emerald-400' :
                            item.score >= 70 ? 'text-amber-600 dark:text-amber-400' :
                            'text-red-600 dark:text-red-400'
                          }`}>
                            {item.score ? item.score.toFixed(1) : '0.0'}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <StatusBadge status={item.status} size="xs" />
                        </td>
                        <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                          {item.integrity_hash ? `${item.integrity_hash.slice(0, 16)}...` : 'SHA256'}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/results/${item.id}`); }}
                            className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline cursor-pointer"
                          >
                            {t('merchant.product_detail.view_audit_report')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="p-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
              <EmptyState
                icon={ScanSearch}
                title={t('merchant.product_detail.no_scans_title')}
                description={t('merchant.product_detail.no_scans_desc')}
                actionLabel={t('sku_workflow.scan_packaging_for_sku')}
                onAction={() => navigate(`/analyze?productId=${product.id}`, { state: { productId: product.id, productName: product.product_name } })}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Pre-Print Artworks */}
      {activeTab === 'ARTWORKS' && (
        <div className="space-y-4">
          {artworks.length > 0 ? (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_artwork_file')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_iteration')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_workflow_status')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_approval')}</th>
                      <th className="py-3 px-4 font-semibold">{t('merchant.product_detail.col_upload_date')}</th>
                      <th className="py-3 px-4 text-right font-semibold">{t('merchant.products.table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                    {artworks.map((art) => (
                      <tr
                        key={art.id}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                      >
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-indigo-500 shrink-0" />
                            <span className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                              {art.filename}
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-xs font-mono font-bold text-slate-700 dark:text-slate-300">
                          v{art.iteration_number}
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                            {art.workflow_status}
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                            art.approval_status === 'APPROVED' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300' :
                            art.approval_status === 'REJECTED' ? 'bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300' :
                            'bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300'
                          }`}>
                            {art.approval_status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400">
                          {formatAnalysisDateTime(art.created_at)}
                        </td>
                        <td className="py-3 px-4 text-right">
                          <button
                            onClick={() => navigate('/preprint')}
                            className="text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline cursor-pointer"
                          >
                            {t('merchant.product_detail.open_preprint_hub')}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="p-8 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
              <EmptyState
                icon={Printer}
                title={t('merchant.product_detail.no_artworks_title')}
                description={t('merchant.product_detail.no_artworks_desc')}
                actionLabel={t('sku_workflow.upload_artwork_for_sku')}
                onAction={() => navigate(`/preprint?productId=${product.id}`, { state: { productId: product.id, productName: product.product_name } })}
              />
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Master Statutory Declarations */}
      {activeTab === 'DECLARATIONS' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
              <Scale className="w-4 h-4 text-sky-600 dark:text-sky-400" />
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                {t('merchant.product_detail.rule6_title')}
              </h3>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/40">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_new.field_net_qty')}</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{product.net_quantity_declared || t('merchant.product_detail.not_declared')}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/40">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_new.field_mrp')}</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{product.mrp_declared ? `₹${product.mrp_declared.toFixed(2)}` : t('merchant.product_detail.not_declared')}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/40">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_new.field_usp')}</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{product.unit_sale_price_declared || t('merchant.product_detail.not_declared')}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_new.field_origin')}</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">{product.country_of_origin || 'India'}</span>
              </div>
            </div>
          </div>

          <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-slate-100 dark:border-slate-800">
              <Building2 className="w-4 h-4 text-sky-600 dark:text-sky-400" />
              <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
                {t('merchant.product_detail.licensure_title')}
              </h3>
            </div>
            <div className="space-y-2 text-xs">
              <div className="py-1 border-b border-slate-50 dark:border-slate-800/40">
                <span className="text-slate-500 dark:text-slate-400 block mb-0.5">{t('merchant.product_detail.mfg_address')}</span>
                <span className="font-medium text-slate-800 dark:text-slate-200">{product.manufacturer_name || t('merchant.product_detail.not_provided')}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-50 dark:border-slate-800/40">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_detail.fssai_license')}</span>
                <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{product.fssai_license || '—'}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-500 dark:text-slate-400">{t('merchant.product_detail.lm_license')}</span>
                <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{product.legal_metrology_license || '—'}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
