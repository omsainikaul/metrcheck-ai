import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Building2, 
  Store, 
  ShieldCheck, 
  Boxes, 
  CheckCircle2, 
  BadgeCheck
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { api } from '../services/api';
import { type MerchantDashboardStats, type ProductListResponse } from '../types';
import LoadingSkeleton from '../components/ui/LoadingSkeleton';

export default function BusinessProfile() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [stats, setStats] = useState<MerchantDashboardStats | null>(null);
  const [products, setProducts] = useState<ProductListResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMerchantData = async () => {
      try {
        const [statsRes, prodRes] = await Promise.all([
          api.getProductStats().catch(() => null),
          api.getProducts({ limit: 5 }).catch(() => null)
        ]);
        if (statsRes) setStats(statsRes);
        if (prodRes) setProducts(prodRes);
      } catch (err) {
        // ignore
      } finally {
        setLoading(false);
      }
    };
    loadMerchantData();
  }, []);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in duration-300">
        <LoadingSkeleton variant="page" />
      </div>
    );
  }

  const organizationName = user?.organization_id || user?.business_name || user?.full_name || 'Registered Merchant Business';
  const roleName = user?.role === 'MERCHANT_PUBLIC' ? 'Verified Commercial Brand / Merchant' : user?.role || 'Merchant';

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Header Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-sky-600 via-indigo-600 to-slate-900 text-white shadow-lg space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center shrink-0">
              <Store className="w-8 h-8 text-sky-200" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-2xl font-black tracking-tight text-white">
                  {organizationName}
                </h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-sky-400/20 text-sky-200 text-xs font-bold border border-sky-300/30">
                  <BadgeCheck className="w-3.5 h-3.5" />
                  {roleName}
                </span>
              </div>
              <p className="text-xs text-sky-100/80 mt-1 font-mono">
                Organization ID: {user?.organization_id || 'ORG-DEFAULT'} • User ID: {user?.username}
              </p>
            </div>
          </div>

          <button
            onClick={() => navigate('/products/new')}
            className="px-4 py-2 bg-white text-slate-900 hover:bg-sky-50 text-xs font-bold rounded-xl transition-all shadow-sm cursor-pointer shrink-0"
          >
            + Register New SKU
          </button>
        </div>

        {/* Quick Numbers Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-3 border-t border-white/10">
          <div>
            <span className="text-[10px] text-sky-200/70 uppercase tracking-wider font-semibold">Active SKUs</span>
            <p className="text-xl font-bold text-white">{stats?.active_products ?? products?.total ?? 0}</p>
          </div>
          <div>
            <span className="text-[10px] text-sky-200/70 uppercase tracking-wider font-semibold">Checked Products</span>
            <p className="text-xl font-bold text-white">{stats?.products_checked ?? 0}</p>
          </div>
          <div>
            <span className="text-[10px] text-sky-200/70 uppercase tracking-wider font-semibold">Pre-Print Artworks</span>
            <p className="text-xl font-bold text-white">{stats?.packaging_artworks ?? 0}</p>
          </div>
          <div>
            <span className="text-[10px] text-sky-200/70 uppercase tracking-wider font-semibold">Tenant Isolation</span>
            <div className="flex items-center gap-1 text-emerald-300 text-xs font-bold mt-1">
              <ShieldCheck className="w-4 h-4" />
              <span>Isolated</span>
            </div>
          </div>
        </div>
      </div>

      {/* Grid: Business Details & Compliance Identifiers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Business Identity Card */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <Building2 className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Commercial Entity Profile
            </h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Business / Trade Name</span>
              <span className="font-bold text-slate-800 dark:text-slate-200">{organizationName}</span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Account Owner</span>
              <span className="font-medium text-slate-800 dark:text-slate-200">{user?.full_name || user?.username}</span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Registered Email</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">{user?.email || '—'}</span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Contact Phone</span>
              <span className="font-mono text-slate-800 dark:text-slate-200">{user?.phone_number || '—'}</span>
            </div>

            <div className="flex justify-between py-1.5 border-b border-slate-100 dark:border-slate-800">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Country / Jurisdiction</span>
              <span className="font-medium text-slate-800 dark:text-slate-200">India (Legal Metrology Act, 2009)</span>
            </div>

            <div className="flex justify-between py-1.5">
              <span className="text-slate-500 dark:text-slate-400 font-medium">Account Status</span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Active &amp; Authorized
              </span>
            </div>
          </div>
        </div>

        {/* Regulatory Licenses Card */}
        <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
          <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
            <ShieldCheck className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Statutory Licenses &amp; Compliance Identifiers
            </h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 space-y-1">
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider block">
                Legal Metrology Manufacturer / Packer Registration
              </span>
              <p className="text-xs font-mono text-slate-600 dark:text-slate-300">
                Rule 27 / Rule 29 Registration under Packaged Commodities Rules, 2011.
              </p>
              <div className="text-[11px] font-semibold text-sky-600 dark:text-sky-400 pt-1">
                Mandatory for all pre-packed commodities distributed in commerce.
              </div>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 space-y-1">
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider block">
                FSSAI Central / State License (Food Business Operators)
              </span>
              <p className="text-xs font-mono text-slate-600 dark:text-slate-300">
                14-digit statutory license cross-referenced via FoSCoS database validator.
              </p>
            </div>

            <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800 space-y-1">
              <span className="text-[11px] font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider block">
                GS1 India Barcode &amp; GTIN Allocation
              </span>
              <p className="text-xs font-mono text-slate-600 dark:text-slate-300">
                EAN-13 / GTIN prefix verified against GS1 Global Data Dictionary.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Catalog Items */}
      <div className="p-6 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <Boxes className="w-4 h-4 text-sky-600 dark:text-sky-400" />
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100 uppercase tracking-wider">
              Managed Product SKUs
            </h2>
          </div>
          <button
            onClick={() => navigate('/products')}
            className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline cursor-pointer"
          >
            Open Full Catalog ({products?.total || 0}) &rarr;
          </button>
        </div>

        {products && products.products.length > 0 ? (
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {products.products.map(p => (
              <div 
                key={p.id}
                onClick={() => navigate(`/products/${p.id}`)}
                className="py-3 flex items-center justify-between gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/40 rounded-xl px-2 transition-colors cursor-pointer"
              >
                <div>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    {p.product_name}
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">
                    Category: {p.category || 'GENERAL'} • GTIN: {p.gtin_barcode || '—'} • MRP: {p.mrp_declared ? `₹${p.mrp_declared.toFixed(2)}` : '—'}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    p.status === 'ACTIVE' ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300' : 'bg-slate-100 text-slate-600'
                  }`}>
                    {p.status}
                  </span>
                  <span className="text-xs text-sky-600 dark:text-sky-400">&rarr;</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-4 text-center">
            No product SKUs registered yet. Click "+ Register New SKU" to get started.
          </p>
        )}
      </div>
    </div>
  );
}
