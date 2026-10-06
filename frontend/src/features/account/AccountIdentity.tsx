"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
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

function normalizeIdentity(value: Partial<AccountIdentity>): AccountIdentity {
  const firstName = typeof value.firstName === "string" ? value.firstName.trim() : "";
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

export function AccountIdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<AccountIdentity>(EMPTY_IDENTITY);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) return;
      setIdentity(normalizeIdentity(JSON.parse(stored) as Partial<AccountIdentity>));
    } catch {
      // A damaged local identity must never block the application shell.
    }
  }, []);

  function updateIdentity(patch: Partial<AccountIdentity>) {
    setIdentity((current) => {
      const next = normalizeIdentity({ ...current, ...patch });
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Local persistence is a temporary account-ready seam until cloud Auth.
      }
      return next;
    });
  }

  const value = useMemo<AccountIdentityContextValue>(() => {
    const firstNameLabel = identity.firstName || "צלם";
    return {
      identity,
      firstNameLabel,
      profileOwnerLabel: identity.profileName || firstNameLabel,
      updateIdentity,
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
    throw new Error("useAccountIdentity must be used inside AccountIdentityProvider");
  }
  return context;
}
