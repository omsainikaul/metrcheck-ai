import { useState, type FormEvent } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { 
  ShieldCheck, 
  Lock, 
  User as UserIcon, 
  Mail,
  Phone,
  Eye, 
  EyeOff, 
  Loader2, 
  ArrowLeft, 
  Store, 
  SearchCheck, 
  ShieldAlert, 
  ArrowRight, 
  KeyRound, 
  CheckCircle2, 
  RotateCcw,
  BadgeCheck,
  Building2,
  MapPin,
  FileCheck2,
  Info,
  X,
  Sparkles,
  Copy,
  Check
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useWorkspace, WORKSPACE_DEFINITIONS, getAllowedWorkspacesForRole } from '../context/WorkspaceContext';
import { api } from '../services/api';
import { 
  type WorkspaceType, 
  type AuthUser, 
  type RegisterUserPayload, 
  type RegisterMerchantPayload,
  type OfficerAccessRequestPayload,
  type OfficerAccessRequestItem
} from '../types';

type TopLevelAccessCategory = 'USER' | 'MERCHANT' | 'OFFICER';
type OfficerSubtype = 'AUDIT' | 'ENFORCEMENT';

export default function Login() {
  const { login, registerUser, registerMerchant, logout } = useAuth();
  const { setWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from?.pathname || '/';

  // Navigation hierarchy state
  const [selectedCategory, setSelectedCategory] = useState<TopLevelAccessCategory | null>(null);
  const [selectedOfficerSubtype, setSelectedOfficerSubtype] = useState<OfficerSubtype | null>(null);

  // Authentication mode: login or register
  const [mode, setMode] = useState<'login' | 'register'>('login');

  // Form Fields
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [mobileNumber, setMobileNumber] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showConfirmPw, setShowConfirmPw] = useState(false);

  // Merchant-specific registration state
  const [businessName, setBusinessName] = useState('');
  const [businessType, setBusinessType] = useState('Manufacturer');
  const [tradeName, setTradeName] = useState('');
  const [addressLine1, setAddressLine1] = useState('');
  const [addressLine2, setAddressLine2] = useState('');
  const [city, setCity] = useState('');
  const [stateName, setStateName] = useState('');
  const [pincode, setPincode] = useState('');
  const [country] = useState('India');
  const [gstin, setGstin] = useState('');
  const [fssaiLicense, setFssaiLicense] = useState('');
  const [legalMetrologyLicense, setLegalMetrologyLicense] = useState('');
  const [otherIdentifier, setOtherIdentifier] = useState('');

  // Status & Feedback
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Officer Access Request State
  const [officerRequestModal, setOfficerRequestModal] = useState<'AUDIT' | 'ENFORCEMENT' | null>(null);
  const [officerFullName, setOfficerFullName] = useState('');
  const [officerOfficialEmail, setOfficerOfficialEmail] = useState('');
  const [officerMobileNumber, setOfficerMobileNumber] = useState('');
  const [officerEmployeeId, setOfficerEmployeeId] = useState('');
  const [officerDesignation, setOfficerDesignation] = useState('');
  const [officerDepartment, setOfficerDepartment] = useState('');
  const [officerState, setOfficerState] = useState('');
  const [officerDistrict, setOfficerDistrict] = useState('');
  const [officerReason, setOfficerReason] = useState('');
  const [officerOfficeAddress, setOfficerOfficeAddress] = useState('');
  const [officerAdditionalInfo, setOfficerAdditionalInfo] = useState('');

  const [officerRequestBusy, setOfficerRequestBusy] = useState(false);
  const [officerRequestError, setOfficerRequestError] = useState<string | null>(null);
  const [officerRequestSuccess, setOfficerRequestSuccess] = useState<OfficerAccessRequestItem | null>(null);
  const [copiedRequestId, setCopiedRequestId] = useState(false);

  // Access denied state: set when an authenticated user attempts to enter an unauthorized workspace
  const [accessDeniedUser, setAccessDeniedUser] = useState<AuthUser | null>(null);

  // Determine active target workspace for auth submission
  const activeWorkspace: WorkspaceType | null = 
    selectedCategory === 'USER' ? 'USER' :
    selectedCategory === 'MERCHANT' ? 'MERCHANT' :
    selectedCategory === 'OFFICER' && selectedOfficerSubtype ? selectedOfficerSubtype :
    null;

  // Handlers for category selection
  const handleSelectCategory = (cat: TopLevelAccessCategory) => {
    setSelectedCategory(cat);
    setSelectedOfficerSubtype(null);
    setMode('login');
    setError(null);
    setAccessDeniedUser(null);
  };

  const handleSelectOfficerSubtype = (sub: OfficerSubtype) => {
    setSelectedOfficerSubtype(sub);
    setMode('login');
    setError(null);
    setAccessDeniedUser(null);
  };

  const handleBackToTopLevel = () => {
    setSelectedCategory(null);
    setSelectedOfficerSubtype(null);
    setMode('login');
    setError(null);
    setAccessDeniedUser(null);
  };

  const handleBackToOfficerSelection = () => {
    setSelectedOfficerSubtype(null);
    setMode('login');
    setError(null);
    setAccessDeniedUser(null);
  };

  const handlePopulateCredentials = (u: string, p: string, cat: TopLevelAccessCategory, sub?: OfficerSubtype) => {
    setUsername(u);
    setPassword(p);
    setSelectedCategory(cat);
    if (sub) {
      setSelectedOfficerSubtype(sub);
    }
    setMode('login');
    setError(null);
  };

  const handleAccessDeniedContinueAllowed = () => {
    if (!accessDeniedUser) return;
    const allowed = getAllowedWorkspacesForRole(accessDeniedUser.role);
    const fallback = allowed[0] || 'USER';
    setWorkspace(fallback);
    navigate(from, { replace: true });
  };

  const handleAccessDeniedSignOut = () => {
    logout();
    setAccessDeniedUser(null);
    setUsername('');
    setPassword('');
    setError(null);
  };

  const resetOfficerForm = () => {
    setOfficerFullName('');
    setOfficerOfficialEmail('');
    setOfficerMobileNumber('');
    setOfficerEmployeeId('');
    setOfficerDesignation('');
    setOfficerDepartment('');
    setOfficerState('');
    setOfficerDistrict('');
    setOfficerReason('');
    setOfficerOfficeAddress('');
    setOfficerAdditionalInfo('');
    setOfficerRequestError(null);
    setOfficerRequestSuccess(null);
    setCopiedRequestId(false);
  };

  const handleOpenOfficerRequest = (subtype: 'AUDIT' | 'ENFORCEMENT') => {
    resetOfficerForm();
    setOfficerRequestModal(subtype);
  };

  const handleCloseOfficerRequest = () => {
    setOfficerRequestModal(null);
    resetOfficerForm();
  };

  const handleSubmitOfficerRequest = async (e: FormEvent) => {
    e.preventDefault();
    if (!officerRequestModal) return;
    setOfficerRequestError(null);

    // Validation
    if (
      !officerFullName.trim() ||
      !officerOfficialEmail.trim() ||
      !officerMobileNumber.trim() ||
      !officerEmployeeId.trim() ||
      !officerDesignation.trim() ||
      !officerDepartment.trim() ||
      !officerState.trim() ||
      !officerDistrict.trim() ||
      !officerReason.trim()
    ) {
      setOfficerRequestError('Please fill in all required official fields marked with an asterisk (*).');
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(officerOfficialEmail.trim())) {
      setOfficerRequestError('Please enter a valid official email address format.');
      return;
    }

    setOfficerRequestBusy(true);
    try {
      const payload: OfficerAccessRequestPayload = {
        requested_role: officerRequestModal === 'AUDIT' ? 'AUDIT_OFFICER' : 'ENFORCEMENT_OFFICER',
        full_name: officerFullName.trim(),
        official_email: officerOfficialEmail.trim(),
        mobile_number: officerMobileNumber.trim(),
        employee_officer_id: officerEmployeeId.trim(),
        designation: officerDesignation.trim(),
        department_organization: officerDepartment.trim(),
        state: officerState.trim(),
        district_jurisdiction: officerDistrict.trim(),
        reason: officerReason.trim(),
        office_address: officerOfficeAddress.trim() || undefined,
        additional_information: officerAdditionalInfo.trim() || undefined,
      };

      const result = await api.submitOfficerAccessRequest(payload);
      setOfficerRequestSuccess(result);
    } catch (err: any) {
      setOfficerRequestError(
        err?.message || 'Failed to submit officer access request. Please check details and try again.'
      );
    } finally {
      setOfficerRequestBusy(false);
    }
  };

  const handleCopyRequestId = (reqId: string) => {
    navigator.clipboard.writeText(reqId);
    setCopiedRequestId(true);
    setTimeout(() => setCopiedRequestId(false), 2000);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAccessDeniedUser(null);

    const targetWs = activeWorkspace || 'USER';

    // Validation
    if (mode === 'register') {
      if (password.length < 8) {
        setError('Password must be at least 8 characters long.');
        return;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match. Please verify your password confirmation.');
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
        setError('Please enter a valid email address.');
        return;
      }

      if (selectedCategory === 'USER') {
        if (!fullName.trim() || !username.trim() || !email.trim()) {
          setError('Full Name, Username, and Email are required.');
          return;
        }
      } else if (selectedCategory === 'MERCHANT') {
        if (!fullName.trim() || !username.trim() || !email.trim() || !businessName.trim() || !addressLine1.trim() || !city.trim() || !stateName.trim() || !pincode.trim()) {
          setError('Please complete all required fields in the Account, Business, and Address sections.');
          return;
        }
      }
    } else {
      if (!username.trim() || !password) {
        setError('Please enter your username (or email) and password.');
        return;
      }
    }

    setBusy(true);
    try {
      let authenticatedUser: AuthUser;

      if (mode === 'login') {
        authenticatedUser = await login(username.trim(), password);
      } else if (selectedCategory === 'USER') {
        const payload: RegisterUserPayload = {
          full_name: fullName.trim(),
          username: username.trim(),
          email: email.trim(),
          password,
          mobile_number: mobileNumber.trim() || undefined,
        };
        authenticatedUser = await registerUser(payload);
      } else {
        const payload: RegisterMerchantPayload = {
          full_name: fullName.trim(),
          username: username.trim(),
          email: email.trim(),
          mobile_number: mobileNumber.trim() || undefined,
          password,
          business_name: businessName.trim(),
          business_type: businessType,
          trade_name: tradeName.trim() || undefined,
          address_line1: addressLine1.trim(),
          address_line2: addressLine2.trim() || undefined,
          city: city.trim(),
          state: stateName.trim(),
          pincode: pincode.trim(),
          country: country.trim(),
          gstin: gstin.trim() || undefined,
          fssai_license: fssaiLicense.trim() || undefined,
          legal_metrology_license: legalMetrologyLicense.trim() || undefined,
          other_identifier: otherIdentifier.trim() || undefined,
        };
        authenticatedUser = await registerMerchant(payload);
      }

      const allowedWorkspaces = getAllowedWorkspacesForRole(authenticatedUser.role);

      // Verify if authenticated role is authorized for the requested target workspace
      if (allowedWorkspaces.includes(targetWs)) {
        setWorkspace(targetWs);
        navigate(from, { replace: true });
      } else {
        // Access Denied: User role does NOT have permission for this workspace
        setAccessDeniedUser(authenticatedUser);
      }
    } catch (err: any) {
      setError(
        err?.message || 
        (mode === 'login' 
          ? 'Incorrect username or password. Please check your credentials and try again.' 
          : 'Registration failed. Please check the entered details.')
      );
    } finally {
      setBusy(false);
    }
  };

  const targetDef = activeWorkspace ? WORKSPACE_DEFINITIONS[activeWorkspace] : null;

  return (
    <div className="min-h-screen w-full flex flex-col justify-between py-8 px-4 sm:px-6 lg:px-8 bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      {/* Top Brand Nav */}
      <div className="max-w-5xl w-full mx-auto flex items-center">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <span className="text-base font-extrabold tracking-tight text-white block">MetrCheck AI</span>
            <span className="text-xs text-slate-400">AI-Assisted Statutory Compliance</span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-5xl w-full mx-auto my-8">
        {/* ==================================================================== */}
        {/* STATE 1: ACCESS DENIED SCREEN (Role not authorized for workspace)    */}
        {/* ==================================================================== */}
        {accessDeniedUser && targetDef ? (
          <div className="max-w-lg mx-auto rounded-3xl border border-amber-500/30 bg-slate-900/90 backdrop-blur-md shadow-2xl p-6 sm:p-8 space-y-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-amber-500/15 text-amber-400 rounded-2xl border border-amber-500/30 shrink-0">
                <ShieldAlert className="w-8 h-8" />
              </div>
              <div className="space-y-1">
                <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Access Control Boundary</span>
                <h2 className="text-xl font-black text-white tracking-tight">Workspace Access Restricted</h2>
              </div>
            </div>

            <p className="text-sm text-slate-300 leading-relaxed">
              The <strong className="text-white">{targetDef.label}</strong> is restricted. Your authenticated account does not have permission to access this operational workspace.
            </p>

            {/* Account & Permission Summary Card */}
            <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2.5 text-xs font-mono">
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Authenticated Account:</span>
                <span className="font-bold text-slate-200">{accessDeniedUser.username}</span>
              </div>
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Backend Role:</span>
                <span className="font-bold text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded border border-sky-500/20">
                  {accessDeniedUser.role_label || accessDeniedUser.role}
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-400 border-b border-slate-800/80 pb-2">
                <span>Requested Workspace:</span>
                <span className="font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                  {targetDef.label} ({targetDef.coreAction})
                </span>
              </div>
              <div className="flex justify-between items-center text-slate-400 pt-0.5">
                <span>Authorized Workspace:</span>
                <span className="font-bold text-emerald-400">
                  {getAllowedWorkspacesForRole(accessDeniedUser.role)[0]} Workspace
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-3 pt-2">
              <button
                type="button"
                onClick={handleAccessDeniedContinueAllowed}
                className="w-full py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs sm:text-sm font-bold shadow-lg shadow-indigo-600/30 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
              >
                <span>Continue to Authorized Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={handleAccessDeniedSignOut}
                className="w-full py-2.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Sign In With Another Account</span>
              </button>
            </div>
          </div>
        ) : selectedCategory === null ? (
          /* ==================================================================== */
          /* STATE 2: TOP-LEVEL ACCESS PORTAL (Choose your access)                */
          /* ==================================================================== */
          <div className="space-y-8 animate-in fade-in duration-300">
            {/* Title & Introduction */}
            <div className="text-center space-y-2 max-w-2xl mx-auto">
              <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-white">
                Choose your access
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                Select how you want to use MetrCheck AI.
              </p>
            </div>

            {/* Exactly 3 Top-Level Access Cards: Normal User, Merchant, Officer */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* CARD 1: NORMAL USER */}
              <div 
                onClick={() => handleSelectCategory('USER')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-cyan-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <UserIcon className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-400/30 uppercase">
                      CHECK
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
                      Normal User
                    </h3>
                    <p className="text-xs text-cyan-400/90 font-medium mt-0.5">
                      For consumers and users who want to check packaged products.
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Check product information, review detected declarations, and understand MetrCheck AI compliance findings.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Check and understand product information.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Open Access</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold shadow-md shadow-cyan-600/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Continue as Normal User</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* CARD 2: MERCHANT */}
              <div 
                onClick={() => handleSelectCategory('MERCHANT')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-sky-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/30 text-sky-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <Store className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-sky-500/20 text-sky-300 border border-sky-400/30 uppercase">
                      PREVENT
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-sky-300 transition-colors">
                      Merchant
                    </h3>
                    <p className="text-xs text-sky-400/90 font-medium mt-0.5">
                      For manufacturers, brands, packers, importers and retailers.
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Check products before release, maintain product records, and review compliance findings.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Verify and improve product packaging compliance.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-sky-400 font-semibold flex items-center gap-1">
                    <BadgeCheck className="w-3.5 h-3.5" />
                    <span>Business Access</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-md shadow-sky-600/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Continue as Merchant</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* CARD 3: OFFICER */}
              <div 
                onClick={() => handleSelectCategory('OFFICER')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-amber-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <ShieldAlert className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-400/30 uppercase">
                      OFFICIAL
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-amber-300 transition-colors">
                      Officer
                    </h3>
                    <p className="text-xs text-amber-400/90 font-medium mt-0.5">
                      For authorized Legal Metrology officers.
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Access authorized audit, compliance verification, investigation, and enforcement workflows.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Verify compliance and perform authorized regulatory workflows.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-amber-400 font-semibold flex items-center gap-1">
                    <Lock className="w-3.5 h-3.5" />
                    <span>Official Access / Restricted</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shadow-md shadow-amber-600/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Continue as Officer</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : selectedCategory === 'OFFICER' && selectedOfficerSubtype === null ? (
          /* ==================================================================== */
          /* STATE 3: OFFICER TYPE SELECTION (Audit Officer vs Enforcement Officer)*/
          /* ==================================================================== */
          <div className="max-w-3xl mx-auto space-y-8 animate-in fade-in zoom-in-95 duration-200">
            {/* Officer Header */}
            <div className="text-center space-y-2">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold uppercase tracking-wider mb-2">
                <Lock className="w-3.5 h-3.5" />
                <span>Authorized Regulatory Access</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                Officer Access
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                Select your authorized officer workspace.
              </p>
            </div>

            {/* Exactly 2 Officer Subtype Choices: Audit vs Enforcement */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* 1. Audit Officer */}
              <div 
                onClick={() => handleSelectOfficerSubtype('AUDIT')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-indigo-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <SearchCheck className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 uppercase">
                      VERIFY
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-indigo-300 transition-colors">
                      Audit Officer
                    </h3>
                    <p className="text-xs text-indigo-400/90 font-medium mt-0.5">
                      For quality, compliance and audit users
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Perform compliance verification, review evidence, and maintain audit records.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Verify what was detected and why.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-indigo-400 font-semibold flex items-center gap-1">
                    <BadgeCheck className="w-3.5 h-3.5" />
                    <span>Officer / QA Auth</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold shadow-md shadow-indigo-600/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Continue to Audit</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* 2. Enforcement Officer */}
              <div 
                onClick={() => handleSelectOfficerSubtype('ENFORCEMENT')}
                className="rounded-3xl border border-slate-800 bg-slate-900/70 hover:border-amber-500/60 hover:bg-slate-900/90 transition-all duration-200 p-6 flex flex-col justify-between group cursor-pointer shadow-xl relative overflow-hidden"
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="w-12 h-12 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                      <ShieldAlert className="w-6 h-6" />
                    </div>
                    <span className="px-2.5 py-1 rounded-full text-[10px] font-black tracking-wider bg-amber-500/20 text-amber-300 border border-amber-400/30 uppercase">
                      INVESTIGATE
                    </span>
                  </div>

                  <div>
                    <h3 className="text-lg font-bold text-white group-hover:text-amber-300 transition-colors">
                      Enforcement Officer
                    </h3>
                    <p className="text-xs text-amber-400/90 font-medium mt-0.5">
                      For authorized Legal Metrology enforcement officials
                    </p>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Access authorized investigation and enforcement workflows.
                  </p>

                  <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1">
                    <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">Primary Goal:</span>
                    <p className="text-xs text-slate-200 font-medium">Review findings and support regulatory action.</p>
                  </div>
                </div>

                <div className="pt-5 mt-4 border-t border-slate-800/80 flex items-center justify-between">
                  <span className="text-[11px] text-amber-400 font-semibold flex items-center gap-1">
                    <Lock className="w-3.5 h-3.5" />
                    <span>Official Auth</span>
                  </span>
                  <button
                    type="button"
                    className="px-3.5 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold shadow-md shadow-amber-600/30 transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Continue to Enforcement</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>

            {/* Back Button */}
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={handleBackToTopLevel}
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>← Change access type</span>
              </button>
            </div>
          </div>
        ) : (
          /* ==================================================================== */
          /* STATE 4: AUTHENTICATION FORM FOR SELECTED ACCESS TYPE               */
          /* ==================================================================== */
          <div className={`${selectedCategory === 'MERCHANT' && mode === 'register' ? 'max-w-2xl' : 'max-w-md'} mx-auto space-y-4 animate-in fade-in zoom-in-95 duration-200`}>
            {/* Top Workspace Context Banner */}
            <div className="flex items-center justify-between p-3.5 rounded-2xl bg-slate-900 border border-slate-800 shadow-md">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className={`p-2 rounded-xl shrink-0 ${
                  activeWorkspace === 'USER' ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30' :
                  activeWorkspace === 'MERCHANT' ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30' :
                  activeWorkspace === 'AUDIT' ? 'bg-indigo-500/15 text-indigo-400 border border-indigo-500/30' :
                  'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                }`}>
                  {activeWorkspace === 'USER' ? <UserIcon className="w-4 h-4" /> :
                   activeWorkspace === 'MERCHANT' ? <Store className="w-4 h-4" /> :
                   activeWorkspace === 'AUDIT' ? <SearchCheck className="w-4 h-4" /> :
                   <ShieldAlert className="w-4 h-4" />}
                </div>
                <div className="min-w-0">
                  <span className="text-[10px] uppercase font-bold text-slate-400 block tracking-wider">
                    {mode === 'login' ? 'Signing in to' : 'Registering for'}
                  </span>
                  <p className="text-xs font-bold text-white truncate">
                    {targetDef?.label} • <span className="font-mono text-indigo-300">{targetDef?.coreAction}</span>
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={selectedCategory === 'OFFICER' ? handleBackToOfficerSelection : handleBackToTopLevel}
                className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:underline px-2.5 py-1 rounded-lg hover:bg-slate-800 transition-colors shrink-0 cursor-pointer"
              >
                {selectedCategory === 'OFFICER' ? '← Change officer type' : '← Change access type'}
              </button>
            </div>

            {/* Login / Registration Card */}
            <div className="rounded-3xl border border-slate-800 bg-slate-900/80 backdrop-blur-md shadow-2xl overflow-hidden">
              {/* Mode Header / Tabs: Normal User & Merchant get Sign In + Register tabs; Officers get Sign In header */}
              {selectedCategory === 'USER' ? (
                <div className="p-2 border-b border-slate-800 bg-slate-950/40">
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-slate-800/60 border border-slate-700/60">
                    {(['login', 'register'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { setMode(m); setError(null); }}
                        className={`py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                          mode === m
                            ? 'bg-cyan-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {m === 'login' ? 'Sign In' : 'Register'}
                      </button>
                    ))}
                  </div>
                </div>
              ) : selectedCategory === 'MERCHANT' ? (
                <div className="p-2 border-b border-slate-800 bg-slate-950/40">
                  <div className="grid grid-cols-2 gap-1 p-1 rounded-xl bg-slate-800/60 border border-slate-700/60">
                    {(['login', 'register'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { setMode(m); setError(null); }}
                        className={`py-2 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                          mode === m
                            ? 'bg-sky-600 text-white shadow-sm'
                            : 'text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        {m === 'login' ? 'Sign In' : 'Register Merchant'}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="p-3.5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
                  <span className="text-xs font-bold text-white flex items-center gap-2">
                    <Lock className={`w-3.5 h-3.5 ${activeWorkspace === 'AUDIT' ? 'text-indigo-400' : 'text-amber-400'}`} />
                    <span>{activeWorkspace === 'AUDIT' ? 'Audit Officer Login' : 'Enforcement Officer Login'}</span>
                  </span>
                  <span className={`text-[10px] font-black tracking-wider px-2 py-0.5 rounded border uppercase ${
                    activeWorkspace === 'AUDIT'
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                      : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  }`}>
                    {targetDef?.coreAction}
                  </span>
                </div>
              )}

              {/* Form Body */}
              <form onSubmit={handleSubmit} className="p-6 space-y-4">
                {/* ── NORMAL USER REGISTRATION FORM ── */}
                {selectedCategory === 'USER' && mode === 'register' && (
                  <div className="space-y-4">
                    <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-xs text-cyan-300 leading-relaxed">
                      Create a personal account to inspect packaged products and review detected compliance findings.
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Full Name <span className="text-rose-400">*</span>
                      </label>
                      <div className="relative">
                        <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          value={fullName}
                          onChange={(e) => setFullName(e.target.value)}
                          placeholder="e.g. Rahul Sharma"
                          required
                          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Username <span className="text-rose-400">*</span>
                      </label>
                      <div className="relative">
                        <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          placeholder="Choose a username"
                          autoComplete="username"
                          required
                          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Email Address <span className="text-rose-400">*</span>
                      </label>
                      <div className="relative">
                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type="email"
                          value={email}
                          onChange={(e) => setEmail(e.target.value)}
                          placeholder="user@example.com"
                          autoComplete="email"
                          required
                          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Mobile Number (Optional)
                      </label>
                      <div className="relative">
                        <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type="tel"
                          value={mobileNumber}
                          onChange={(e) => setMobileNumber(e.target.value)}
                          placeholder="+91 98765 43210"
                          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Password <span className="text-rose-400">*</span>
                      </label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type={showPw ? 'text' : 'password'}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••"
                          autoComplete="new-password"
                          required
                          minLength={8}
                          className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPw(!showPw)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                        >
                          {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">
                        Confirm Password <span className="text-rose-400">*</span>
                      </label>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type={showConfirmPw ? 'text' : 'password'}
                          value={confirmPassword}
                          onChange={(e) => setConfirmPassword(e.target.value)}
                          placeholder="••••••••"
                          autoComplete="new-password"
                          required
                          minLength={8}
                          className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-cyan-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                        <button
                          type="button"
                          onClick={() => setShowConfirmPw(!showConfirmPw)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                        >
                          {showConfirmPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* ── MERCHANT REGISTRATION FORM (4 Structured Sections) ── */}
                {selectedCategory === 'MERCHANT' && mode === 'register' && (
                  <div className="space-y-6">
                    {/* Section A: Account Information */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 pb-1.5 border-b border-slate-800">
                        <UserIcon className="w-4 h-4 text-sky-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          Section A — Account Information
                        </h4>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Full Name <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            placeholder="e.g. Anand Mahindra"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Username <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            placeholder="Choose username"
                            autoComplete="username"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Business Email <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            placeholder="compliance@brand.com"
                            autoComplete="email"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Mobile Number
                          </label>
                          <input
                            type="tel"
                            value={mobileNumber}
                            onChange={(e) => setMobileNumber(e.target.value)}
                            placeholder="+91 98765 43210"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Password <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="••••••••"
                            autoComplete="new-password"
                            required
                            minLength={8}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Confirm Password <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            placeholder="••••••••"
                            autoComplete="new-password"
                            required
                            minLength={8}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Section B: Business Information */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 pb-1.5 border-b border-slate-800">
                        <Building2 className="w-4 h-4 text-sky-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          Section B — Business Information
                        </h4>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div className="sm:col-span-2">
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Legal Business Name <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={businessName}
                            onChange={(e) => setBusinessName(e.target.value)}
                            placeholder="e.g. Acme Organic Foods Private Limited"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Business Type <span className="text-rose-400">*</span>
                          </label>
                          <select
                            value={businessType}
                            onChange={(e) => setBusinessType(e.target.value)}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white cursor-pointer"
                          >
                            <option value="Manufacturer">Manufacturer</option>
                            <option value="Packer">Packer</option>
                            <option value="Importer">Importer</option>
                            <option value="Retailer">Retailer</option>
                            <option value="Distributor">Distributor</option>
                            <option value="Brand Owner">Brand Owner</option>
                            <option value="Other">Other</option>
                          </select>
                        </div>

                        <div className="sm:col-span-3">
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Trade / Brand Name (Optional)
                          </label>
                          <input
                            value={tradeName}
                            onChange={(e) => setTradeName(e.target.value)}
                            placeholder="e.g. Acme Naturals"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Section C: Business Address */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 pb-1.5 border-b border-slate-800">
                        <MapPin className="w-4 h-4 text-sky-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          Section C — Business Address
                        </h4>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="sm:col-span-2">
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Address Line 1 <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={addressLine1}
                            onChange={(e) => setAddressLine1(e.target.value)}
                            placeholder="Plot / Building / Street Address"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div className="sm:col-span-2">
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Address Line 2 (Optional)
                          </label>
                          <input
                            value={addressLine2}
                            onChange={(e) => setAddressLine2(e.target.value)}
                            placeholder="Industrial Area / Landmark"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            City <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            placeholder="e.g. Mumbai"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            State <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={stateName}
                            onChange={(e) => setStateName(e.target.value)}
                            placeholder="e.g. Maharashtra"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            PIN Code <span className="text-rose-400">*</span>
                          </label>
                          <input
                            value={pincode}
                            onChange={(e) => setPincode(e.target.value)}
                            placeholder="400001"
                            required
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Country
                          </label>
                          <input
                            value={country}
                            disabled
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/40 border border-slate-700/60 text-sm text-slate-400 cursor-not-allowed"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Section D: Regulatory / Business Identifiers */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 pb-1.5 border-b border-slate-800">
                        <FileCheck2 className="w-4 h-4 text-sky-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                          Section D — Regulatory &amp; Business Identifiers (Where Applicable)
                        </h4>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            GSTIN (Optional)
                          </label>
                          <input
                            value={gstin}
                            onChange={(e) => setGstin(e.target.value.toUpperCase())}
                            placeholder="27AAAAA0000A1Z5"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white font-mono placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            FSSAI Licence Number (If Food Product)
                          </label>
                          <input
                            value={fssaiLicense}
                            onChange={(e) => setFssaiLicense(e.target.value)}
                            placeholder="100XXXXXXXXXXX"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white font-mono placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Legal Metrology Licence / Reg Details
                          </label>
                          <input
                            value={legalMetrologyLicense}
                            onChange={(e) => setLegalMetrologyLicense(e.target.value)}
                            placeholder="e.g. LM-REG-2024-XXXX"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>

                        <div>
                          <label className="block text-xs font-medium text-slate-400 mb-1.5">
                            Other Import / Business Identifier
                          </label>
                          <input
                            value={otherIdentifier}
                            onChange={(e) => setOtherIdentifier(e.target.value)}
                            placeholder="IEC / CIN / MSME"
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-sky-500 outline-none text-sm text-white placeholder:text-slate-500"
                          />
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-400 leading-relaxed pt-1">
                        Note: Entering identifiers registers business metadata for packaging reports. Official statutory compliance verification remains subject to statutory regulatory inspection.
                      </p>
                    </div>
                  </div>
                )}

                {/* ── STANDARD SIGN IN FORM (Used by all access categories in login mode) ── */}
                {mode === 'login' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Username or Email</label>
                      <div className="relative">
                        <UserIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          value={username}
                          onChange={(e) => setUsername(e.target.value)}
                          placeholder="Enter username or email"
                          autoComplete="username"
                          required
                          className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-1.5">
                        <label className="block text-xs font-medium text-slate-400">Password</label>
                        <Link
                          to="/forgot-password"
                          className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                        >
                          Forgot password?
                        </Link>
                      </div>
                      <div className="relative">
                        <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type={showPw ? 'text' : 'password'}
                          value={password}
                          onChange={(e) => setPassword(e.target.value)}
                          placeholder="••••••••"
                          autoComplete="current-password"
                          required
                          className="w-full pl-10 pr-11 py-2.5 rounded-xl bg-slate-800/70 border border-slate-700 focus:border-indigo-500 outline-none text-sm text-white placeholder:text-slate-500"
                        />
                        <button
                          type="button"
                          onClick={() => setShowPw(!showPw)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 cursor-pointer"
                        >
                          {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {error && (
                  <div className="px-4 py-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-400">
                    {error}
                  </div>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className={`w-full py-3 rounded-xl disabled:opacity-60 text-white text-xs sm:text-sm font-bold flex items-center justify-center gap-2 transition-all shadow-lg cursor-pointer active:scale-98 ${
                    activeWorkspace === 'ENFORCEMENT'
                      ? 'bg-amber-600 hover:bg-amber-500 shadow-amber-900/40'
                      : activeWorkspace === 'AUDIT'
                      ? 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-900/40'
                      : activeWorkspace === 'MERCHANT'
                      ? 'bg-sky-600 hover:bg-sky-500 shadow-sky-900/40'
                      : 'bg-cyan-600 hover:bg-cyan-500 shadow-cyan-900/40'
                  }`}
                >
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                  <span>
                    {busy 
                      ? 'Verifying credentials…' 
                      : mode === 'login' 
                      ? `Sign In as ${targetDef?.shortLabel}` 
                      : selectedCategory === 'USER' 
                      ? 'Create User Account' 
                      : 'Create Merchant Account'}
                  </span>
                </button>
              </form>

              {/* Informational Panel for Officer Workspaces */}
              {activeWorkspace === 'AUDIT' && (
                <div className="px-6 pb-4">
                  <div className="p-3.5 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 font-bold text-indigo-300">
                      <SearchCheck className="w-4 h-4 text-indigo-400 shrink-0" />
                      <span>Authorized audit accounts only.</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      Audit Workspace access is provisioned and managed by system administrators. Public self-registration is disabled to maintain chain of custody.
                    </p>
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => handleOpenOfficerRequest('AUDIT')}
                        className="text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 underline cursor-pointer inline-flex items-center gap-1"
                      >
                        <span>Request Audit Access</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {activeWorkspace === 'ENFORCEMENT' && (
                <div className="px-6 pb-4">
                  <div className="p-3.5 rounded-2xl bg-amber-950/40 border border-amber-500/30 text-xs space-y-1.5">
                    <div className="flex items-center gap-2 font-bold text-amber-300">
                      <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>Authorized enforcement officers only.</span>
                    </div>
                    <p className="text-slate-300 text-[11px] leading-relaxed">
                      Enforcement Workspace access is provisioned for authorized enforcement officers. Public self-registration is disabled.
                    </p>
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => handleOpenOfficerRequest('ENFORCEMENT')}
                        className="text-[11px] font-semibold text-amber-400 hover:text-amber-300 underline cursor-pointer inline-flex items-center gap-1"
                      >
                        <span>Request Enforcement Access</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Development-Only Demo Accounts Section (Gated strictly by VITE_METRCHECK_DEMO_MODE) */}
              {import.meta.env.VITE_METRCHECK_DEMO_MODE === 'true' && (
                <div className="px-6 pb-6 pt-1">
                  <div className="rounded-2xl bg-slate-950/60 border border-slate-800/90 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-amber-300" /> Development Demo Credentials
                      </span>
                      <span className="text-[9px] text-slate-500 font-mono">Fill &amp; Authenticate</span>
                    </div>

                    <div className="space-y-2 text-xs">
                      {/* Normal User Demo */}
                      <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-200">NORMAL USER</span>
                            <span className="text-[10px] text-cyan-400 font-mono">user / user123</span>
                          </div>
                          <p className="text-[10px] text-slate-500">Consumer check workspace access</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handlePopulateCredentials('user', 'user123', 'USER')}
                          className="px-2.5 py-1 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                        >
                          Use Account
                        </button>
                      </div>

                      {/* Demo Merchant */}
                      <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-200">DEMO MERCHANT</span>
                            <span className="text-[10px] text-sky-400 font-mono">merchant / merchant123</span>
                          </div>
                          <p className="text-[10px] text-slate-500">Merchant Pre-Flight workspace access</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handlePopulateCredentials('merchant', 'merchant123', 'MERCHANT')}
                          className="px-2.5 py-1 rounded-lg bg-sky-600/20 hover:bg-sky-600/30 text-sky-300 border border-sky-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                        >
                          Use Account
                        </button>
                      </div>

                      {/* Audit Officer */}
                      <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-200">AUDIT OFFICER</span>
                            <span className="text-[10px] text-indigo-400 font-mono">audit / audit123</span>
                          </div>
                          <p className="text-[10px] text-slate-500">Audit &amp; Compliance verification access</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handlePopulateCredentials('audit', 'audit123', 'OFFICER', 'AUDIT')}
                          className="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                        >
                          Use Account
                        </button>
                      </div>

                      {/* Enforcement Officer */}
                      <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/80 border border-slate-800">
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-slate-200">ENFORCEMENT OFFICER</span>
                            <span className="text-[10px] text-emerald-400 font-mono">officer / officer123</span>
                          </div>
                          <p className="text-[10px] text-slate-500">Enforcement, Audit &amp; Merchant access</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => handlePopulateCredentials('officer', 'officer123', 'OFFICER', 'ENFORCEMENT')}
                          className="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold transition-colors cursor-pointer"
                        >
                          Use Account
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Back Navigation */}
            <div className="text-center">
              <button
                type="button"
                onClick={selectedCategory === 'OFFICER' ? handleBackToOfficerSelection : handleBackToTopLevel}
                className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{selectedCategory === 'OFFICER' ? 'Return to Officer Selection' : 'Return to Access Selection'}</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Interactive Officer Access Request Modal */}
      {officerRequestModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 overflow-y-auto animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl max-w-2xl w-full p-6 sm:p-8 space-y-6 my-8 max-h-[90vh] overflow-y-auto">
            {officerRequestSuccess ? (
              /* Success Confirmation View */
              <div className="space-y-6 text-center">
                <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/10">
                  <CheckCircle2 className="w-8 h-8" />
                </div>

                <div className="space-y-2">
                  <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    STATUS: PENDING ADMINISTRATIVE REVIEW
                  </div>
                  <h3 className="text-xl font-bold text-white">Access Request Submitted Successfully</h3>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    Your official access request has been recorded in the central compliance audit log and queued for administrative approval.
                  </p>
                </div>

                {/* Request Details Card */}
                <div className="p-4 sm:p-5 rounded-2xl bg-slate-950/70 border border-slate-800 text-left space-y-3">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                    <span className="text-xs text-slate-400">Request Tracking ID</span>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-lg border border-indigo-500/20">
                        {officerRequestSuccess.request_id}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyRequestId(officerRequestSuccess.request_id)}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
                        title="Copy Request ID"
                      >
                        {copiedRequestId ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-500 block text-[11px]">Requested Role</span>
                      <span className="font-semibold text-slate-200">
                        {officerRequestSuccess.requested_role === 'AUDIT_OFFICER' ? 'Audit Officer' : 'Enforcement Officer'}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Applicant Name</span>
                      <span className="font-semibold text-slate-200">{officerRequestSuccess.full_name}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Official Email</span>
                      <span className="font-semibold text-slate-200">{officerRequestSuccess.official_email}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 block text-[11px]">Jurisdiction</span>
                      <span className="font-semibold text-slate-200">
                        {officerRequestSuccess.district_jurisdiction}, {officerRequestSuccess.state}
                      </span>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80">
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      💡 <strong>Next Steps:</strong> An authorized administrator will verify your credentials and jurisdiction. Once approved, you will receive an account activation link to set your password and access the official workspace.
                    </p>
                  </div>
                </div>

                <div className="pt-2">
                  <button
                    type="button"
                    onClick={handleCloseOfficerRequest}
                    className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all shadow-lg shadow-indigo-600/20 cursor-pointer"
                  >
                    Back to Officer Login
                  </button>
                </div>
              </div>
            ) : (
              /* Request Form View */
              <form onSubmit={handleSubmitOfficerRequest} className="space-y-5">
                {/* Modal Header */}
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl border ${
                      officerRequestModal === 'AUDIT'
                        ? 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}>
                      {officerRequestModal === 'AUDIT' ? <SearchCheck className="w-5 h-5" /> : <ShieldAlert className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-base font-bold text-white">
                          Request {officerRequestModal === 'AUDIT' ? 'Audit Officer' : 'Enforcement Officer'} Access
                        </h3>
                        <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full border ${
                          officerRequestModal === 'AUDIT'
                            ? 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                            : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                        }`}>
                          {officerRequestModal === 'AUDIT' ? 'Internal Audit' : 'Statutory Enforcement'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">
                        Submit official credentials for administrative verification and account provisioning.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleCloseOfficerRequest}
                    className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Error Banner */}
                {officerRequestError && (
                  <div className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center gap-2.5 animate-in fade-in duration-150">
                    <ShieldAlert className="w-4 h-4 shrink-0" />
                    <span>{officerRequestError}</span>
                  </div>
                )}

                {/* Form Fields Grid */}
                <div className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Full Name <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerFullName}
                        onChange={(e) => setOfficerFullName(e.target.value)}
                        placeholder="e.g., Rajesh Sharma"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Official Email <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="email"
                        required
                        value={officerOfficialEmail}
                        onChange={(e) => setOfficerOfficialEmail(e.target.value)}
                        placeholder="e.g., rajesh.sharma@gov.in"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Mobile Number <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="tel"
                        required
                        value={officerMobileNumber}
                        onChange={(e) => setOfficerMobileNumber(e.target.value)}
                        placeholder="+91 98765 43210"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Employee / Officer ID <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerEmployeeId}
                        onChange={(e) => setOfficerEmployeeId(e.target.value)}
                        placeholder="e.g., LMO-DL-2024-889"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Designation <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerDesignation}
                        onChange={(e) => setOfficerDesignation(e.target.value)}
                        placeholder="e.g., Assistant Controller / Senior Inspector"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        Department / Organization <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerDepartment}
                        onChange={(e) => setOfficerDepartment(e.target.value)}
                        placeholder="e.g., Department of Legal Metrology"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        State / UT <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerState}
                        onChange={(e) => setOfficerState(e.target.value)}
                        placeholder="e.g., Delhi"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        District / Jurisdiction <span className="text-red-400">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={officerDistrict}
                        onChange={(e) => setOfficerDistrict(e.target.value)}
                        placeholder="e.g., New Delhi Zone-1"
                        className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Reason for Access / Statutory Purpose <span className="text-red-400">*</span>
                    </label>
                    <textarea
                      required
                      rows={2}
                      value={officerReason}
                      onChange={(e) => setOfficerReason(e.target.value)}
                      placeholder="Specify the regulatory jurisdiction, inspection duties, or audit verification scope..."
                      className="w-full px-3.5 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Office / Department Address <span className="text-slate-500 text-[11px] font-normal">(Optional)</span>
                    </label>
                    <input
                      type="text"
                      value={officerOfficeAddress}
                      onChange={(e) => setOfficerOfficeAddress(e.target.value)}
                      placeholder="Official chamber or departmental office address"
                      className="w-full px-3.5 py-2.5 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Additional Information / Supervisor Reference <span className="text-slate-500 text-[11px] font-normal">(Optional)</span>
                    </label>
                    <textarea
                      rows={2}
                      value={officerAdditionalInfo}
                      onChange={(e) => setOfficerAdditionalInfo(e.target.value)}
                      placeholder="Any reference number, supervising officer details, or specific remarks..."
                      className="w-full px-3.5 py-2 bg-slate-950/80 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-hidden focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all resize-none"
                    />
                  </div>
                </div>

                {/* Notice */}
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
                  <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
                  <span>
                    Self-registration is disabled for Officer roles. Submissions are vetted against department databases before single-use activation credentials are provided.
                  </span>
                </div>

                {/* Form Buttons */}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleCloseOfficerRequest}
                    disabled={officerRequestBusy}
                    className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold transition-all cursor-pointer disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={officerRequestBusy}
                    className={`inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-white text-xs font-bold transition-all cursor-pointer shadow-lg disabled:opacity-50 ${
                      officerRequestModal === 'AUDIT'
                        ? 'bg-indigo-600 hover:bg-indigo-500 shadow-indigo-600/20'
                        : 'bg-amber-600 hover:bg-amber-500 shadow-amber-600/20'
                    }`}
                  >
                    {officerRequestBusy && <Loader2 className="w-4 h-4 animate-spin" />}
                    <span>{officerRequestBusy ? 'Submitting Request...' : 'Submit Official Access Request'}</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="max-w-5xl w-full mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-600">
        <span>Problem Statement 26034 · Directorate of Legal Metrology Compliance Support</span>
        <Link to="/admin/login" className="text-slate-500 hover:text-slate-400 transition-colors text-[11px] flex items-center gap-1">
          <Lock className="w-3 h-3" />
          <span>Administrator Portal</span>
        </Link>
      </div>
    </div>
  );
}