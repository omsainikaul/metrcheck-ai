import React from 'react';
import {
  BadgeCheck,
  CheckCircle,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Database,
  ShieldCheck,
  Layers
} from 'lucide-react';
import {
  type FSSAIVerificationResult,
  type GS1VerificationResult,
  type ExternalVerificationSummary,
  type CrossCheckFieldResult
} from '../../types';
import { useLanguage } from '../../context/LanguageContext';

interface ExternalVerificationProps {
  fssaiVerification?: FSSAIVerificationResult | null;
  gs1Verification?: GS1VerificationResult | null;
  fssaiLicense?: string | null;
  externalVerification?: ExternalVerificationSummary | null;
}

const VerificationCard: React.FC<{
  title: string;
  value: string;
  isValid: boolean;
  statusText?: string;
  message: string;
  provider: string;
  type: 'LIVE' | 'CACHE' | 'FORMAT';
}> = ({ title, value, isValid, statusText, message, provider, type }) => {
  const { t } = useLanguage();
  return (
    <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-1">{title}</div>
          <div className="font-mono text-sm text-slate-900 dark:text-slate-100">{value}</div>
        </div>
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold ${
          isValid ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
        }`}>
          {isValid ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
          {statusText || (isValid ? t('verification.status_valid', { defaultValue: 'VALID' }) : t('verification.status_invalid', { defaultValue: 'INVALID' }))}
        </div>
      </div>
      
      <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">
        {message}
      </div>
      
      <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-slate-400 mt-3 pt-3 border-t border-slate-200 dark:border-slate-700">
        <span>{provider}</span>
        <span className={
          type === 'LIVE' ? 'text-emerald-500 dark:text-emerald-400' :
          type === 'CACHE' ? 'text-indigo-500 dark:text-indigo-400' : 'text-amber-500 dark:text-amber-400'
        }>
          {type === 'LIVE' ? t('verification.type_live', { defaultValue: 'LIVE REGISTRY' }) : 
           type === 'CACHE' ? t('verification.type_cache', { defaultValue: 'PERSISTENT CACHE' }) : 
           t('verification.type_format', { defaultValue: 'FORMAT & CHECKSUM' })}
        </span>
      </div>
    </div>
  );
};

const CrossCheckRow: React.FC<{ item: CrossCheckFieldResult }> = ({ item }) => {
  const { t } = useLanguage();
  const getStatusBadge = () => {
    switch (item.status) {
      case 'MATCH':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"><CheckCircle className="w-3 h-3" /> {t('verification.status_match', { defaultValue: 'MATCH' })}</span>;
      case 'PARTIAL_MATCH':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"><AlertTriangle className="w-3 h-3" /> {t('verification.status_partial', { defaultValue: 'PARTIAL' })}</span>;
      case 'MISMATCH':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"><XCircle className="w-3 h-3" /> {t('verification.status_mismatch', { defaultValue: 'MISMATCH' })}</span>;
      case 'UNVERIFIED':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"><HelpCircle className="w-3 h-3" /> {t('verification.status_unverified', { defaultValue: 'UNVERIFIED' })}</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">N/A</span>;
    }
  };

  return (
    <tr className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50/50 dark:hover:bg-slate-800/30">
      <td className="py-2.5 px-3 text-xs font-medium text-slate-800 dark:text-slate-200">
        {item.check_type.replace(/_/g, ' ')}
      </td>
      <td className="py-2.5 px-3 text-xs text-slate-600 dark:text-slate-300 font-mono">
        {item.extracted_value || <span className="text-slate-400 italic">None</span>}
      </td>
      <td className="py-2.5 px-3 text-xs text-slate-600 dark:text-slate-300 font-mono">
        {item.registry_value || <span className="text-slate-400 italic">—</span>}
      </td>
      <td className="py-2.5 px-3 text-center">
        {getStatusBadge()}
      </td>
      <td className="py-2.5 px-3 text-xs text-slate-500 dark:text-slate-400">
        {item.discrepancy_details || 'Verified consistent.'}
      </td>
    </tr>
  );
};

const ExternalVerification: React.FC<ExternalVerificationProps> = ({
  fssaiVerification,
  gs1Verification,
  fssaiLicense,
  externalVerification
}) => {
  const { t } = useLanguage();
  if (!fssaiVerification && !gs1Verification && !fssaiLicense && !externalVerification) return null;

  const fssai = externalVerification?.fssai_verification || fssaiVerification;
  const gs1 = externalVerification?.gs1_verification || gs1Verification;

  const fssaiNumber = fssai?.licence_number || fssaiLicense || t('verification.not_detected', { defaultValue: 'Not detected' });
  const fssaiValid = fssai ? fssai.status === 'VERIFIED' : (fssaiLicense ? fssaiLicense.length === 14 : false);
  const fssaiMsg = fssai?.message || (fssaiLicense && fssaiLicense.length === 14 ? t('verification.format_verified_14_digits', { defaultValue: 'Format verified (14 digits)' }) : t('verification.licence_format_invalid', { defaultValue: 'Licence format invalid' }));
  const fssaiProvider = fssai?.provider || 'FoSCoS Public Registry API';
  const fssaiType = fssai?.is_live ? 'LIVE' : (fssai?.provider?.includes('Cache') ? 'CACHE' : 'FORMAT');

  const gs1Gtin = gs1?.gtin || externalVerification?.barcode_detected || t('verification.not_detected', { defaultValue: 'Not detected' });
  const gs1Valid = gs1 ? gs1.status === 'VERIFIED' : false;
  const gs1Msg = gs1?.message || t('verification.barcode_checksum_check', { defaultValue: 'Barcode checksum check' });
  const gs1Provider = gs1?.provider || 'GS1 India DataKart';
  const gs1Type = gs1?.is_live ? 'LIVE' : (gs1?.provider?.includes('Cache') ? 'CACHE' : 'FORMAT');

  const confidence = externalVerification?.confidence;
  const crossChecks = externalVerification?.cross_checks || [];

  return (
    <div id="section-external-verification" className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-2xs mb-6 overflow-hidden">
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BadgeCheck className="w-5 h-5 text-indigo-500" />
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {t('verification.title', { defaultValue: 'EXTERNAL REGISTRY VERIFICATION & CROSS-CHECKING' })}
          </span>
          <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
            {t('verification.sec13', { defaultValue: 'SEC 13' })}
          </span>
        </div>

        {confidence && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-500">{t('verification.confidence_tier', { defaultValue: 'Confidence Tier:' })}</span>
            <span className={`px-2.5 py-0.5 rounded-full font-bold text-[11px] ${
              confidence.tier === 'HIGH' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300' :
              confidence.tier === 'MEDIUM' ? 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300' :
              'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
            }`}>
              {confidence.tier} ({Math.round(confidence.score * 100)}%)
            </span>
          </div>
        )}
      </div>

      {/* Registry Cards */}
      <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {(fssaiLicense || fssai) && (
          <VerificationCard
            title={t('verification.fssai_registry', { defaultValue: 'FSSAI / FoSCoS Registry' })}
            value={fssaiNumber}
            isValid={fssaiValid}
            statusText={fssai?.status ? (fssai.status === 'VERIFIED' ? t('verification.status_valid', { defaultValue: 'VALID' }) : fssai.status) : (fssaiValid ? t('verification.status_valid', { defaultValue: 'VALID' }) : t('verification.status_invalid', { defaultValue: 'INVALID' }))}
            message={fssaiMsg}
            provider={fssaiProvider}
            type={fssaiType}
          />
        )}
        
        {(gs1 || externalVerification?.barcode_detected) && (
          <VerificationCard
            title={t('verification.gs1_registry', { defaultValue: 'GS1 DataKart / GTIN' })}
            value={gs1Gtin}
            isValid={gs1Valid}
            statusText={gs1?.status ? (gs1.status === 'VERIFIED' ? t('verification.status_valid', { defaultValue: 'VALID' }) : gs1.status) : (gs1Valid ? t('verification.status_valid', { defaultValue: 'VALID' }) : t('verification.status_checked', { defaultValue: 'CHECKED' }))}
            message={gs1Msg}
            provider={gs1Provider}
            type={gs1Type}
          />
        )}
      </div>

      {/* Cross-Checking Consistency Matrix */}
      {crossChecks.length > 0 && (
        <div className="p-4 pt-0">
          <div className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5" />
            {t('verification.matrix_title', { defaultValue: 'Statutory Cross-Checking Consistency Matrix' })}
          </div>
          <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-100 dark:bg-slate-800 text-[11px] font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
                  <th className="py-2 px-3">{t('verification.col_target', { defaultValue: 'Cross-Check Target' })}</th>
                  <th className="py-2 px-3">{t('verification.col_extracted', { defaultValue: 'Extracted on Label' })}</th>
                  <th className="py-2 px-3">{t('verification.col_registry', { defaultValue: 'Registry / QR Record' })}</th>
                  <th className="py-2 px-3 text-center">{t('verification.col_status', { defaultValue: 'Status' })}</th>
                  <th className="py-2 px-3">{t('verification.col_findings', { defaultValue: 'Findings & Provenance' })}</th>
                </tr>
              </thead>
              <tbody>
                {crossChecks.map((cc, idx) => (
                  <CrossCheckRow key={idx} item={cc} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Offline & API Connectivity Banner */}
      <div className="bg-slate-50 dark:bg-slate-800/30 px-4 py-2.5 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Database className="w-3.5 h-3.5 text-indigo-500" />
            {t('verification.wal_cache_active', { defaultValue: 'SQLite Persistent WAL Cache Active' })}
          </span>
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
            {t('verification.air_gap_ready', { defaultValue: 'Offline Air-Gap Verification Ready' })}
          </span>
        </div>
        {externalVerification?.summary_verdict && (
          <span className="italic text-slate-600 dark:text-slate-300 truncate max-w-md">
            {externalVerification.summary_verdict}
          </span>
        )}
      </div>
    </div>
  );
};

export default ExternalVerification;


