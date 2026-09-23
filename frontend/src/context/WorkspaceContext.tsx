import { createContext, useContext, useEffect, useState, useMemo, type ReactNode } from 'react';
import { type WorkspaceType, type WorkspaceDefinition } from '../types';
import { useAuth } from './AuthContext';

export const WORKSPACE_STORAGE_KEY = 'metrcheck-active-workspace';

export const WORKSPACE_DEFINITIONS: Record<WorkspaceType, WorkspaceDefinition> = {
  USER: {
    id: 'USER',
    label: 'Consumer Workspace',
    shortLabel: 'Consumer',
    tagline: 'Check product information and understand compliance findings',
    coreAction: 'CHECK',
    badge: 'CONSUMER ACCESS',
    iconName: 'User',
    description: 'Check product packaging information, review detected declarations, and understand MetrCheck AI compliance findings.',
    capabilities: [
      'Scan packaging product photos & labels',
      'Verify mandatory statutory declarations',
      'Understand compliance score & warnings',
      'Inspect detected MRP, net quantity, manufacturing & expiry dates',
      'Review consumer care and manufacturer information'
    ],
    allowedRoles: ['PUBLIC_USER', 'NORMAL_USER', 'MERCHANT_PUBLIC', 'AUDIT_OFFICER', 'ENFORCEMENT_OFFICER', 'ADMIN']
  },
  MERCHANT: {
    id: 'MERCHANT',
    label: 'Merchant Workspace',
    shortLabel: 'Merchant',
    tagline: 'Prevent compliance problems before production',
    coreAction: 'PREVENT',
    badge: 'MERCHANT PRE-FLIGHT',
    iconName: 'Store',
    description: 'Pre-flight packaging check, actionable corrective fixes, and pre-distribution compliance verification.',
    capabilities: [
      'Analyze packaging artwork before printing',
      'Compliance score & readiness meter',
      'Plain-language corrective recommendations',
      'Visual evidence bounding box preview',
      'Re-check packaging artwork',
      'Export compliance verification report'
    ],
    allowedRoles: ['MERCHANT_PUBLIC', 'AUDIT_OFFICER', 'ENFORCEMENT_OFFICER', 'ADMIN']
  },
  AUDIT: {
    id: 'AUDIT',
    label: 'Audit Workspace',
    shortLabel: 'Audit',
    tagline: 'Verify compliance findings and evidence',
    coreAction: 'VERIFY',
    badge: 'QA & AUDIT VERIFICATION',
    iconName: 'SearchCheck',
    description: 'Detailed technical verification, rule-by-rule compliance checks, OCR evidence confidence, and optical calibration audits.',
    capabilities: [
      'Rule-by-rule statutory checklist verification',
      'Precision visual evidence inspection',
      'OCR word token confidence & bounding box mapping',
      'Physical font height (Rule 12) & ArUco calibration audit',
      'Cross-field derivation & proviso tracking',
      'Technical audit dossier export (CSV, Excel, JSON)'
    ],
    allowedRoles: ['AUDIT_OFFICER', 'ENFORCEMENT_OFFICER', 'ADMIN']
  },
  ENFORCEMENT: {
    id: 'ENFORCEMENT',
    label: 'Enforcement Workspace',
    shortLabel: 'Enforcement',
    tagline: 'Investigate potential violations',
    coreAction: 'INVESTIGATE',
    badge: 'LEGAL METROLOGY ENFORCEMENT',
    iconName: 'ShieldAlert',
    description: 'Statutory contravention investigation, Section 36/38 violation citations, penalty estimation, and official Show-Cause Notice drafts.',
    capabilities: [
      'Identify confirmed statutory contraventions & defects',
      'Statutory legal citations (Section 36/38 & Rule 6/12/18)',
      'Statutory penalty computation & multiplier estimates',
      'Generate & print official Show-Cause Notice drafts',
      'Authorized compliance screening record management',
      'Official enforcement inspection report export'
    ],
    allowedRoles: ['ENFORCEMENT_OFFICER', 'ADMIN']
  }
};

export interface WorkspaceContextType {
  currentWorkspace: WorkspaceType;
  setWorkspace: (workspace: WorkspaceType) => boolean;
  workspaceInfo: WorkspaceDefinition;
  allowedWorkspaces: WorkspaceType[];
  isWorkspaceAllowed: (workspace: WorkspaceType) => boolean;
  isEnforcementWorkspace: boolean;
  isAuditWorkspace: boolean;
  isMerchantWorkspace: boolean;
  isUserWorkspace: boolean;
  canUseEnforcementFeatures: boolean;
  canDeleteAnalyses: boolean;
  officerId: string;
  jurisdiction: string;
}

export function getAllowedWorkspacesForRole(role?: string | null): WorkspaceType[] {
  if (role === 'ADMIN' || role === 'ENFORCEMENT_OFFICER') {
    return ['ENFORCEMENT', 'AUDIT', 'MERCHANT', 'USER'];
  }
  if (role === 'AUDIT_OFFICER') {
    return ['AUDIT', 'MERCHANT', 'USER'];
  }
  if (role === 'MERCHANT_PUBLIC') {
    return ['MERCHANT', 'USER'];
  }
  return ['USER'];
}

export function getDefaultWorkspaceForRole(role?: string | null): WorkspaceType {
  if (role === 'ADMIN' || role === 'ENFORCEMENT_OFFICER') {
    return 'ENFORCEMENT';
  }
  if (role === 'AUDIT_OFFICER') {
    return 'AUDIT';
  }
  if (role === 'MERCHANT_PUBLIC') {
    return 'MERCHANT';
  }
  return 'USER';
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  // Compute allowed workspaces strictly based on backend authenticated role
  const allowedWorkspaces = useMemo<WorkspaceType[]>(() => {
    return getAllowedWorkspacesForRole(user?.role);
  }, [user]);

  // Default workspace based on user role
  const defaultWorkspace = useMemo<WorkspaceType>(() => {
    return getDefaultWorkspaceForRole(user?.role);
  }, [user]);

  const [currentWorkspace, setCurrentWorkspaceState] = useState<WorkspaceType>(() => {
    // Initialize to 'USER' (neutral, accessible to all roles) before auth resolves.
    // The useEffect below corrects this to the role's proper workspace once auth loads.
    // This prevents non-enforcement users from seeing a flash of the ENFORCEMENT workspace.
    try {
      const saved = localStorage.getItem(WORKSPACE_STORAGE_KEY) as WorkspaceType | null;
      if (saved && (saved in WORKSPACE_DEFINITIONS)) {
        return saved;
      }
    } catch {
      // Fallback
    }
    return 'USER';
  });

  // Ensure active workspace is always in allowedWorkspaces when auth state loads/changes
  useEffect(() => {
    if (loading) return;
    
    try {
      const saved = localStorage.getItem(WORKSPACE_STORAGE_KEY) as WorkspaceType | null;
      if (saved && allowedWorkspaces.includes(saved)) {
        setCurrentWorkspaceState(saved);
      } else {
        setCurrentWorkspaceState(defaultWorkspace);
        localStorage.setItem(WORKSPACE_STORAGE_KEY, defaultWorkspace);
      }
    } catch {
      setCurrentWorkspaceState(defaultWorkspace);
    }
  }, [user, allowedWorkspaces, defaultWorkspace, loading]);

  const isWorkspaceAllowed = (ws: WorkspaceType): boolean => {
    return allowedWorkspaces.includes(ws);
  };

  const setWorkspace = (ws: WorkspaceType): boolean => {
    if (!isWorkspaceAllowed(ws)) {
      console.warn(`[WorkspaceContext] Role ${user?.role || 'UNKNOWN'} is not authorized for workspace ${ws}`);
      return false;
    }
    setCurrentWorkspaceState(ws);
    try {
      localStorage.setItem(WORKSPACE_STORAGE_KEY, ws);
    } catch {
      // Ignore
    }
    return true;
  };

  const workspaceInfo = WORKSPACE_DEFINITIONS[currentWorkspace] || WORKSPACE_DEFINITIONS.MERCHANT;

  const isEnforcementWorkspace = currentWorkspace === 'ENFORCEMENT';
  const isAuditWorkspace = currentWorkspace === 'AUDIT';
  const isMerchantWorkspace = currentWorkspace === 'MERCHANT';
  const isUserWorkspace = currentWorkspace === 'USER';

  // Backend authorization capability flags
  const canUseEnforcementFeatures = (user?.role === 'ADMIN' || user?.role === 'ENFORCEMENT_OFFICER') && isEnforcementWorkspace;
  const canDeleteAnalyses = user?.role === 'ADMIN' || user?.role === 'ENFORCEMENT_OFFICER';

  const officerId = user?.role === 'ADMIN' 
    ? 'SYS-ADMIN-DOCA' 
    : user?.role === 'ENFORCEMENT_OFFICER' 
    ? (user.username === 'officer' ? 'LM-INSP-2026-IND' : `LM-INSP-${user.username.toUpperCase()}`)
    : user?.role === 'AUDIT_OFFICER'
    ? (user.username === 'audit' ? 'QA-AUDIT-9921' : `QA-AUDIT-${user.username.toUpperCase()}`)
    : user?.role === 'MERCHANT_PUBLIC'
    ? 'MERCHANT-PUB'
    : 'USER-CONSUMER';

  const jurisdiction = user?.jurisdiction || (
    user?.role === 'ADMIN' || user?.role === 'ENFORCEMENT_OFFICER'
      ? 'Consumer Affairs & Legal Metrology Directorate'
      : user?.role === 'AUDIT_OFFICER'
      ? 'Packaging Quality & Standard Division'
      : user?.role === 'MERCHANT_PUBLIC'
      ? 'Commercial Packaging Verification'
      : 'Consumer Self-Service'
  );

  return (
    <WorkspaceContext.Provider
      value={{
        currentWorkspace,
        setWorkspace,
        workspaceInfo,
        allowedWorkspaces,
        isWorkspaceAllowed,
        isEnforcementWorkspace,
        isAuditWorkspace,
        isMerchantWorkspace,
        isUserWorkspace,
        canUseEnforcementFeatures,
        canDeleteAnalyses,
        officerId,
        jurisdiction,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): WorkspaceContextType {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
}
