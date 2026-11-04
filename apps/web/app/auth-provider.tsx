"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  User,
  UserManager,
  UserManagerSettings,
  WebStorageStateStore,
} from "oidc-client-ts";

const apiUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const authority = process.env.NEXT_PUBLIC_OIDC_AUTHORITY || "";
const clientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID || "";
const apiScope = process.env.NEXT_PUBLIC_OIDC_API_SCOPE || "";
const apiAudience = process.env.NEXT_PUBLIC_OIDC_AUDIENCE || "";

let userManager: UserManager | null = null;

export function getUserManager(): UserManager | null {
  if (typeof window === "undefined" || !authority || !clientId) return null;
  if (!userManager) {
    const store = new WebStorageStateStore({ store: window.sessionStorage });
    const settings: UserManagerSettings = {
      authority,
      client_id: clientId,
      redirect_uri: `${window.location.origin}/auth/callback`,
      post_logout_redirect_uri: `${window.location.origin}/`,
      response_type: "code",
      scope: ["openid", "profile", "email", apiScope].filter(Boolean).join(" "),
      ...(apiAudience ? { extraQueryParams: { audience: apiAudience } } : {}),
      userStore: store,
      stateStore: store,
      automaticSilentRenew: false,
      monitorSession: false,
      loadUserInfo: false,
      filterProtocolClaims: true,
    };
    userManager = new UserManager(settings);
  }
  return userManager;
}

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  tenantId: string;
  role: string;
  tenantInput: string;
  setTenantInput: (value: string) => void;
  authConfigured: boolean;
  error: string;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  selectTenant: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [tenantId, setTenantId] = useState("");
  const [role, setRole] = useState("");
  const [tenantInput, setTenantInput] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const manager = getUserManager();
    const storedTenant = window.sessionStorage.getItem("carbon_esg_tenant_id") || "";
    if (!manager) {
      setLoading(false);
      return;
    }
    let active = true;
    const loaded = (nextUser: User) => { if (active) setUser(nextUser); };
    const unloaded = () => { if (active) { setUser(null); setTenantId(""); setRole(""); } };
    manager.events.addUserLoaded(loaded);
    manager.events.addUserUnloaded(unloaded);
    if (window.location.pathname === "/auth/callback") {
      setLoading(false);
      return () => {
        active = false;
        manager.events.removeUserLoaded(loaded);
        manager.events.removeUserUnloaded(unloaded);
      };
    }
    manager.getUser()
      .then(async (current) => {
        if (!active) return;
        if (!current || current.expired) {
          setUser(null);
          window.sessionStorage.removeItem("carbon_esg_tenant_id");
          window.sessionStorage.removeItem("carbon_esg_role");
          return;
        }
        setUser(current);
        if (!storedTenant) return;
        const response = await fetch(`${apiUrl}/v1/me`, {
          headers: {
            Authorization: `Bearer ${current.access_token}`,
            "X-Tenant-ID": storedTenant,
          },
          cache: "no-store",
        });
        const body = await response.json().catch(() => null);
        if (!active) return;
        if (!response.ok) {
          window.sessionStorage.removeItem("carbon_esg_tenant_id");
          window.sessionStorage.removeItem("carbon_esg_role");
          setError(body?.detail || "Байгууллагын гишүүнчлэл дахин баталгаажсангүй.");
          return;
        }
        setTenantId(storedTenant);
        setRole(body?.role || "");
        window.sessionStorage.setItem("carbon_esg_role", body?.role || "");
      })
      .catch(() => { if (active) setError("Нэвтрэлтийн төлөв эсвэл байгууллагын эрхийг шалгаж чадсангүй."); })
      .finally(() => { if (active) setLoading(false); });
    return () => {
      active = false;
      manager.events.removeUserLoaded(loaded);
      manager.events.removeUserUnloaded(unloaded);
    };
  }, []);

  const signIn = useCallback(async () => {
    setError("");
    const manager = getUserManager();
    if (!manager) {
      setError("OIDC_AUTHORITY болон OIDC_CLIENT_ID тохируулаагүй байна.");
      return;
    }
    await manager.signinRedirect();
  }, []);

  const signOut = useCallback(async () => {
    const manager = getUserManager();
    if (manager) await manager.removeUser();
    window.sessionStorage.removeItem("carbon_esg_tenant_id");
    window.sessionStorage.removeItem("carbon_esg_role");
    setTenantId("");
    setRole("");
    setUser(null);
    setError("");
  }, []);

  const selectTenant = useCallback(async () => {
    const candidate = tenantInput.trim();
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(candidate)) {
      setError("Байгууллагын Tenant ID UUID хэлбэртэй байх ёстой.");
      return;
    }
    if (!user?.access_token) {
      setError("Эхлээд нэвтэрнэ үү.");
      return;
    }
    setError("");
    try {
      const response = await fetch(`${apiUrl}/v1/me`, {
        headers: {
          Authorization: `Bearer ${user.access_token}`,
          "X-Tenant-ID": candidate,
        },
        cache: "no-store",
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(body?.detail || "Энэ байгууллагад нэвтрэх эрх олдсонгүй.");
      }
      window.sessionStorage.setItem("carbon_esg_tenant_id", candidate);
      window.sessionStorage.setItem("carbon_esg_role", body?.role || "");
      setTenantId(candidate);
      setRole(body?.role || "");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Байгууллагыг шалгаж чадсангүй.");
    }
  }, [tenantInput, user]);

  const value = useMemo<AuthContextValue>(() => ({
    user,
    loading,
    tenantId,
    role,
    tenantInput,
    setTenantInput,
    authConfigured: Boolean(authority && clientId && apiAudience),
    error,
    signIn,
    signOut,
    selectTenant,
  }), [user, loading, tenantId, role, tenantInput, error, signIn, signOut, selectTenant]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
