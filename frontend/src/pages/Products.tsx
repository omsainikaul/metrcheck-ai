import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Package, 
  Plus, 
  Search, 
  Printer, 
  Edit3, 
  Archive, 
  ChevronRight, 
  AlertTriangle, 
  CheckCircle2, 
  Boxes
} from 'lucide-react';
import { api } from '../services/api';
import { type Product, type MerchantDashboardStats } from '../types';
import { useLanguage } from '../context/LanguageContext';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';
import EmptyState from '../components/ui/EmptyState';
import { formatAnalysisDateTime } from '../utils/datetime';

export default function Products() {
  const navigate = useNavigate();
  const { t } = useLanguage();

  const [products, setProducts] = useState<Product[]>([]);
  const [stats, setStats] = useState<MerchantDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'ARCHIVED'>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  // Archive modal state
  const [productToArchive, setProductToArchive] = useState<Product | null>(null);
  const [isArchiving, setIsArchiving] = useState(false);

  const fetchCatalog = async () => {
    setLoading(true);
    setError(null);
    try {
      const [prodRes, statsRes] = await Promise.all([
        api.getProducts({ limit: 200, status: 'ALL' }),
        api.getProductStats().catch(() => null)
      ]);
      setProducts(prodRes?.products || []);
      if (statsRes) setStats(statsRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load merchant product catalog.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCatalog();
  }, []);

  const handleArchive = async () => {
    if (!productToArchive) return;
    setIsArchiving(true);
    try {
      await api.archiveProduct(productToArchive.id);
      setProducts(prev => prev.map(p => p.id === productToArchive.id ? { ...p, status: 'ARCHIVED' } : p));
      setProductToArchive(null);
    } catch (err: any) {
      alert(err?.message || 'Failed to archive product.');
    } finally {
      setIsArchiving(false);
    }
  };

  // Extract unique categories
  const categories = useMemo(() => {
    const set = new Set<string>();
    products.forEach(p => {
      if (p.category) set.add(p.category);
    });
    return Array.from(set);
  }, [products]);

  // Filtered products
  const filteredProducts = useMemo(() => {
    return products.filter(p => {
      if (statusFilter !== 'ALL' && p.status !== statusFilter) return false;
      if (categoryFilter !== 'ALL' && p.category !== categoryFilter) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchName = p.product_name?.toLowerCase().includes(q);
        const matchBrand = p.brand_name?.toLowerCase().includes(q);
        const matchGtin = p.gtin_barcode?.toLowerCase().includes(q);
        const matchMfg = p.manufacturer_name?.toLowerCase().includes(q);
        const matchFssai = p.fssai_license?.toLowerCase().includes(q);
        if (!matchName && !matchBrand && !matchGtin && !matchMfg && !matchFssai) return false;
      }
      return true;
    });
  }, [products, statusFilter, categoryFilter, searchQuery]);

  if (loading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-300">
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-400">
              <Boxes className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">
                {t('merchant.products.title')}
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
                {t('merchant.products.subtitle')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => navigate('/products/new')}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm hover:shadow-md cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>{t('merchant.products.add_new_sku')}</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.products.active_skus')}</span>
            <Package className="w-4 h-4 text-sky-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2">
            {stats?.active_products ?? products.filter(p => p.status === 'ACTIVE').length}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.products.screened_checks')}</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2">
            {stats?.products_checked ?? 0}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.products.attention_required')}</span>
            <AlertTriangle className="w-4 h-4 text-amber-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2">
            {stats?.attention_required ?? 0}
          </p>
        </div>

        <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{t('merchant.products.preprint_artworks')}</span>
            <Printer className="w-4 h-4 text-indigo-500" />
          </div>
          <p className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2">
            {stats?.packaging_artworks ?? 0}
          </p>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchCatalog} className="text-xs font-semibold underline cursor-pointer">
            {t('common.retry') || 'Retry'}
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder={t('merchant.products.search_placeholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-800 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all"
          />
        </div>

        <div className="flex items-center gap-2">
          {/* Status filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 cursor-pointer"
            aria-label={t('sku_workflow.all_statuses')}
          >
            <option value="ALL">{t('sku_workflow.all_statuses')}</option>
            <option value="ACTIVE">{t('sku_workflow.active')}</option>
            <option value="ARCHIVED">{t('sku_workflow.archived')}</option>
          </select>

          {/* Category filter */}
          {categories.length > 0 && (
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500 cursor-pointer"
            >
              <option value="ALL">{t('merchant.categories.ALL') || 'All Categories'}</option>
              {categories.map(c => (
                <option key={c} value={c}>{t(`merchant.categories.${c}`) || c}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Catalog Table / Grid */}
      {filteredProducts.length > 0 ? (
        <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.sku_info')}</th>
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.category')}</th>
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.gtin')}</th>
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.mrp_qty')}</th>
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.status')}</th>
                  <th className="py-3 px-4 font-semibold">{t('merchant.products.table.registered')}</th>
                  <th className="py-3 px-4 text-right font-semibold">{t('merchant.products.table.actions')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {filteredProducts.map((p) => (
                  <tr
                    key={p.id}
                    onClick={() => navigate(`/products/${p.id}`)}
                    className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors group cursor-pointer"
                  >
                    <td className="py-3 px-4">
                      <div>
                        <div className="font-bold text-slate-900 dark:text-slate-100 group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                          {p.product_name}
                        </div>
                        {p.brand_name && (
                          <div className="text-xs text-slate-500 dark:text-slate-400">
                            {t('merchant.products.brand_label')}: <span className="font-medium text-slate-700 dark:text-slate-300">{p.brand_name}</span>
                          </div>
                        )}
                        {p.manufacturer_name && (
                          <div className="text-[11px] text-slate-400 truncate max-w-xs">
                            {p.manufacturer_name}
                          </div>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <span className="text-xs px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 font-medium">
                        {p.category ? (t(`merchant.categories.${p.category}`) || p.category) : t('merchant.categories.GENERAL')}
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <span className="font-mono text-xs text-slate-600 dark:text-slate-300">
                        {p.gtin_barcode || '—'}
                      </span>
                    </td>

                    <td className="py-3 px-4">
                      <div className="text-xs">
                        <div className="font-semibold text-slate-800 dark:text-slate-200">
                          {p.mrp_declared ? `₹${p.mrp_declared.toFixed(2)}` : '—'}
                        </div>
                        {p.net_quantity_declared && (
                          <div className="text-slate-500 dark:text-slate-400 text-[11px]">
                            {t('merchant.products.qty_label')}: {p.net_quantity_declared}
                          </div>
                        )}
                      </div>
                    </td>

                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        p.status === 'ACTIVE'
                          ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800'
                          : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${p.status === 'ACTIVE' ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                        {p.status === 'ACTIVE' ? t('merchant.status.active') : t('merchant.status.archived')}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {formatAnalysisDateTime(p.created_at)}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <div className="inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => navigate(`/products/${p.id}`)}
                          title={t('merchant.products.tooltips.view_details')}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-sky-950/40 transition-colors cursor-pointer"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => navigate(`/products/${p.id}/edit`)}
                          title={t('merchant.products.tooltips.edit_record')}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-950/40 transition-colors cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        {p.status === 'ACTIVE' && (
                          <button
                            onClick={() => setProductToArchive(p)}
                            title={t('merchant.products.tooltips.archive_product')}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-950/40 transition-colors cursor-pointer"
                          >
                            <Archive className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="p-12 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl">
          <EmptyState
            icon={Boxes}
            title={
              searchQuery
                ? t('merchant.products.no_matching')
                : statusFilter === 'ACTIVE'
                ? t('merchant.products.no_active')
                : statusFilter === 'ARCHIVED'
                ? t('merchant.products.no_archived')
                : t('merchant.products.no_registered')
            }
            description={
              searchQuery
                ? t('merchant.products.no_matching_desc')
                : statusFilter === 'ACTIVE'
                ? t('merchant.products.no_active_desc')
                : statusFilter === 'ARCHIVED'
                ? t('merchant.products.no_archived_desc')
                : t('merchant.products.no_registered_desc')
            }
            actionLabel={searchQuery || statusFilter === 'ARCHIVED' ? undefined : t('merchant.products.add_first_sku')}
            onAction={searchQuery || statusFilter === 'ARCHIVED' ? undefined : () => navigate('/products/new')}
          />
        </div>
      )}

      {/* Archive Modal */}
      {productToArchive && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                <Archive className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-900 dark:text-slate-100">
                  {t('merchant.products.archive_modal_title')}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {productToArchive.product_name}
                </p>
              </div>
            </div>

            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              {t('merchant.products.archive_modal_desc')}
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setProductToArchive(null)}
                disabled={isArchiving}
                className="px-4 py-2 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
              >
                {t('common.cancel') || 'Cancel'}
              </button>
              <button
                type="button"
                onClick={handleArchive}
                disabled={isArchiving}
                className="px-4 py-2 text-xs font-bold text-white bg-amber-600 hover:bg-amber-700 rounded-xl transition-colors shadow-sm cursor-pointer"
              >
                {isArchiving ? t('merchant.products.archiving') : t('merchant.products.confirm_archive')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
