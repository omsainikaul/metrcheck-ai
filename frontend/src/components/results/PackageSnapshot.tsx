import React, { useState } from 'react';
import { FileSearch, ChevronDown, ChevronUp } from 'lucide-react';
import { type ProductInfo } from '../../types';
import { useLanguage } from '../../context/LanguageContext';

interface PackageSnapshotProps {
  productInfo: ProductInfo;
}

const DataField: React.FC<{ label: string, value: string | null | undefined, truncate?: boolean }> = ({ label, value, truncate }) => {
  if (!value) return null;
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
      <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1 uppercase tracking-wider">{label}</div>
      <div className={`text-sm font-medium text-slate-900 dark:text-slate-100 ${truncate ? 'truncate' : 'break-words'}`} title={truncate ? value : undefined}>
        {value}
      </div>
    </div>
  );
};

const PackageSnapshot: React.FC<PackageSnapshotProps> = ({ productInfo = {} as any }) => {
  const { t } = useLanguage();
  const [expanded, setExpanded] = useState(false);
  const info = productInfo || ({} as any);

  const consumerCare = [info.consumer_care_phone, info.consumer_care_email, info.consumer_care]
    .filter(Boolean)
    .filter((v, i, a) => a.indexOf(v) === i)
    .join(' | ');

  return (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
        <FileSearch className="w-5 h-5 text-indigo-500" />
        <span className="font-semibold text-slate-900 dark:text-slate-100">
          {t('results.package_snapshot', { defaultValue: 'PACKAGE SNAPSHOT' })}
        </span>
      </div>
      
      <div className="p-4 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <DataField label={t('results.fields.brand', { defaultValue: 'Brand' })} value={info.brand} />
        <DataField label={t('results.fields.product_name', { defaultValue: 'Product Name' })} value={info.product_name} truncate />
        <DataField label={t('results.fields.net_quantity', { defaultValue: 'Net Quantity' })} value={info.net_quantity} />
        <DataField label={t('results.fields.mrp', { defaultValue: 'MRP' })} value={info.mrp} />
        <DataField label={t('results.fields.batch_lot', { defaultValue: 'Batch/Lot' })} value={info.batch_number} />
        <DataField label={t('results.fields.expiry_best_before', { defaultValue: 'Expiry/Best Before' })} value={info.expiry_date || info.best_before} />
        <DataField label={t('results.fields.manufacturer', { defaultValue: 'Manufacturer' })} value={info.manufacturer} truncate />
        <DataField label={t('results.fields.fssai_lic_no', { defaultValue: 'FSSAI Lic No' })} value={info.fssai_license} />
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full border-t border-slate-100 dark:border-slate-800 p-3 text-xs font-medium text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800/30 flex items-center justify-center gap-1 transition-colors cursor-pointer"
      >
        {expanded ? (
          <><ChevronUp className="w-4 h-4" /> {t('results.hide_additional_fields', { defaultValue: 'Hide Additional Fields' })}</>
        ) : (
          <><ChevronDown className="w-4 h-4" /> {t('results.show_additional_fields', { defaultValue: 'Show Additional Fields' })}</>
        )}
      </button>

      {expanded && (
        <div className="p-4 pt-0 grid grid-cols-1 md:grid-cols-2 gap-3 border-t border-slate-100 dark:border-slate-800">
          <DataField label={t('results.fields.country_of_origin', { defaultValue: 'Country of Origin' })} value={info.country_of_origin} />
          <DataField label={t('results.fields.marketed_by', { defaultValue: 'Marketed By' })} value={info.marketed_by} />
          <DataField label={t('results.fields.customer_care', { defaultValue: 'Customer Care' })} value={consumerCare || undefined} />
          <DataField label={t('results.fields.ingredients', { defaultValue: 'Ingredients' })} value={info.ingredients} />
          <DataField label={t('results.fields.nutritional_info', { defaultValue: 'Nutritional Info' })} value={info.nutritional_info ? t('results.detected_status', { defaultValue: 'Detected' }) : undefined} />
          <DataField label={t('results.fields.allergen_info', { defaultValue: 'Allergen Info' })} value={info.allergen_info} />
        </div>
      )}
    </div>
  );
};

export default PackageSnapshot;

