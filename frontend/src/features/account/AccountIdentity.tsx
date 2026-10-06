"use client";

import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

export type AccountIdentity = {
  firstName: string;
  displayName: string;
  profileName: string | null;
};

type AccountIdentityContextValue = {
  identity: AccountIdentity;
  firstNameLabel: string;
  profileOwnerLabel: string;
  updateIdentity: (patch: Partial<AccountIdentity>) => void;
};

const STORAGE_KEY = "prographer.account.identity.v1";

const EMPTY_IDENTITY: AccountIdentity = {
  firstName: "",
  displayName: "",
  profileName: null,
};

const AccountIdentityContext = createContext<AccountIdentityContextValue | null>(
  null,
);

const listeners = new Set<() => void>();
let cachedRaw: string | null | undefined;
let cachedIdentity: AccountIdentity = EMPTY_IDENTITY;

function normalizeIdentity(value: Partial<AccountIdentity>): AccountIdentity {
  const firstName =
    typeof value.firstName === "string" ? value.firstName.trim() : "";
  const displayName =
    typeof value.displayName === "string" && value.displayName.trim()
      ? value.displayName.trim()
      : firstName;
  const profileName =
    typeof value.profileName === "string" && value.profileName.trim()
      ? value.profileName.trim()
      : null;

  return {
    firstName,
    displayName,
    profileName,
  };
}

function readIdentitySnapshot(): AccountIdentity {
  if (typeof window === "undefined") return EMPTY_IDENTITY;

  let raw: string | null = null;

  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return cachedIdentity;
  }

  if (raw === cachedRaw) return cachedIdentity;

  cachedRaw = raw;

  if (!raw) {
    cachedIdentity = EMPTY_IDENTITY;
    return cachedIdentity;
  }

  try {
    cachedIdentity = normalizeIdentity(
      JSON.parse(raw) as Partial<AccountIdentity>,
    );
  } catch {
    cachedIdentity = EMPTY_IDENTITY;
  }

  return cachedIdentity;
}

function subscribeIdentity(listener: () => void) {
  listeners.add(listener);

  function onStorage(event: StorageEvent) {
    if (event.key !== STORAGE_KEY) return;
    cachedRaw = undefined;
    listener();
  }

  if (typeof window !== "undefined") {
    window.addEventListener("storage", onStorage);
  }

  return () => {
    listeners.delete(listener);
    if (typeof window !== "undefined") {
      window.removeEventListener("storage", onStorage);
    }
  };
}

function persistIdentity(next: AccountIdentity) {
  cachedIdentity = next;

  try {
    const raw = JSON.stringify(next);
    window.localStorage.setItem(STORAGE_KEY, raw);
    cachedRaw = raw;
  } catch {
    cachedRaw = undefined;
  }

  for (const listener of listeners) {
    listener();
  }
}

export function AccountIdentityProvider({ children }: { children: ReactNode }) {
  const identity = useSyncExternalStore(
    subscribeIdentity,
    readIdentitySnapshot,
    () => EMPTY_IDENTITY,
  );

  const value = useMemo<AccountIdentityContextValue>(() => {
    const firstNameLabel = identity.firstName || "צלם";

    return {
      identity,
      firstNameLabel,
      profileOwnerLabel: identity.profileName || firstNameLabel,
      updateIdentity: (patch) => {
        const current = readIdentitySnapshot();
        persistIdentity(normalizeIdentity({ ...current, ...patch }));
      },
    };
  }, [identity]);

  return (
    <AccountIdentityContext.Provider value={value}>
      {children}
    </AccountIdentityContext.Provider>
  );
}

export function useAccountIdentity() {
  const context = useContext(AccountIdentityContext);

  if (!context) {
    throw new Error(
      "useAccountIdentity must be used inside AccountIdentityProvider",
    );
  }

  return context;
}
